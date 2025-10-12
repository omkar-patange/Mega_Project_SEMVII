#!/usr/bin/env python3
"""
Load generator that runs from within the Kubernetes cluster
"""

import argparse
import time
import threading
import json
import subprocess
from typing import Callable, Dict, List
from datetime import datetime


class ClusterLoadGenerator:
    def __init__(self, service_url: str, output_file: str = None):
        self.service_url = service_url
        self.output_file = output_file
        self.results = []
        self.start_time = None
        
    def run_kubectl_exec(self, cmd: str) -> subprocess.CompletedProcess:
        """Run command inside the app pod"""
        # Get pod name
        pod_result = subprocess.run([
            "kubectl", "get", "pods", "-n", "userscale", "-l", "app=userscale-app", 
            "-o", "jsonpath={.items[0].metadata.name}"
        ], capture_output=True, text=True)
        
        if pod_result.returncode != 0:
            raise Exception(f"Failed to get pod name: {pod_result.stderr}")
        
        pod_name = pod_result.stdout.strip()
        
        # Run command in pod with proper shell handling
        full_cmd = ["kubectl", "exec", "-n", "userscale", pod_name, "--", "sh", "-c", cmd]
        return subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
    
    def worker(self, name: str, fn: Callable[[], None], stop_t: float, results_list: List):
        while time.time() < stop_t:
            try:
                request_start = time.time()
                fn()
                request_end = time.time()
                results_list.append({
                    'worker': name,
                    'timestamp': request_start,
                    'duration': request_end - request_start,
                    'success': True
                })
            except Exception as e:
                results_list.append({
                    'worker': name,
                    'timestamp': time.time(),
                    'duration': 0,
                    'success': False,
                    'error': str(e)
                })

    def intensive_matrix_load_test(self, concurrency: int, duration: int, matrix_size: int = 2000):
        """Generate VERY intensive matrix multiplication load to trigger scaling"""
        print(f"Starting INTENSIVE matrix multiplication load test:")
        print(f"  Matrix size: {matrix_size}x{matrix_size} ({matrix_size**2:,} elements)")
        print(f"  Concurrency: {concurrency}")
        print(f"  Duration: {duration} seconds")
        print(f"  Expected to trigger autoscaling!")
        
        def call():
            # Use kubectl exec to make the request
            result = self.run_kubectl_exec(f"curl -s '{self.service_url}/matrix?size={matrix_size}'")
            if result.returncode != 0:
                raise Exception(f"Request failed: {result.stderr}")
            if not result.stdout.strip():
                raise Exception("Empty response")
            return result.stdout

        threads = []
        results_list = []
        self.start_time = time.time()
        stop_t = self.start_time + duration
        
        print(f"Starting load test at {datetime.now().strftime('%H:%M:%S')}")
        
        for i in range(concurrency):
            t = threading.Thread(
                target=self.worker, 
                args=(f"worker-{i}", call, stop_t, results_list), 
                daemon=True
            )
            t.start()
            threads.append(t)

        # Enhanced monitoring with replica tracking
        self._monitor_progress_with_scaling(duration, results_list)
        
        for t in threads:
            t.join()

        self.results = results_list
        self._save_results("intensive_matrix_load_test", {
            'matrix_size': matrix_size,
            'concurrency': concurrency,
            'duration': duration
        })
        
        return self._calculate_metrics()

    def _monitor_progress_with_scaling(self, duration: int, results_list: List):
        """Monitor and display progress with replica tracking"""
        start = time.time()
        
        while time.time() - start < duration:
            time.sleep(10)  # Check every 10 seconds
            elapsed = time.time() - start
            remaining = duration - elapsed
            
            # Try to get current metrics
            try:
                result = self.run_kubectl_exec(f"curl -s '{self.service_url}/metrics'")
                if result.returncode == 0:
                    metrics = json.loads(result.stdout)
                    active_users = metrics.get('active_users', 0)
                    cpu_percent = metrics.get('cpu_percent', 0)
                    print(f"Progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining | Active users: {active_users} | CPU: {cpu_percent:.1f}%")
            except Exception as e:
                print(f"Progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining | Status: {len(results_list)} requests completed")

    def _calculate_metrics(self) -> Dict:
        """Calculate throughput and latency metrics"""
        if not self.results:
            return {}
            
        successful_requests = [r for r in self.results if r.get('success', False)]
        total_requests = len(self.results)
        failed_requests = total_requests - len(successful_requests)
        
        if not successful_requests:
            return {
                'total_requests': total_requests,
                'failed_requests': failed_requests,
                'success_rate': 0.0,
                'throughput_rps': 0.0,
                'avg_latency_ms': 0.0,
                'p95_latency_ms': 0.0
            }   
        
        durations = [r['duration'] for r in successful_requests]
        total_duration = max(r['timestamp'] for r in self.results) - min(r['timestamp'] for r in self.results)
        
        return {
            'total_requests': total_requests,
            'successful_requests': len(successful_requests),
            'failed_requests': failed_requests,
            'success_rate': len(successful_requests) / total_requests * 100,
            'throughput_rps': len(successful_requests) / total_duration if total_duration > 0 else 0,
            'avg_latency_ms': sum(durations) / len(durations) * 1000,
            'p95_latency_ms': sorted(durations)[int(len(durations) * 0.95)] * 1000 if durations else 0,
            'total_duration': total_duration
        }

    def _save_results(self, test_name: str, test_params: Dict):
        """Save results to file"""
        if not self.output_file:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics = self._calculate_metrics()
        
        result_data = {
            'test_name': test_name,
            'timestamp': timestamp,
            'test_parameters': test_params,
            'metrics': metrics,
            'raw_results': self.results
        }
        
        with open(self.output_file, 'w') as f:
            json.dump(result_data, f, indent=2)
        
        print(f"Results saved to {self.output_file}")


def main():
    p = argparse.ArgumentParser(description="Cluster Load Generator for Userscale Testing")
    p.add_argument("--service", default="http://userscale-app.userscale.svc.cluster.local:8000", help="Service URL")
    p.add_argument("--concurrency", type=int, default=20, help="Number of concurrent workers")
    p.add_argument("--duration", type=int, default=120, help="Test duration in seconds")
    p.add_argument("--size", type=int, default=2000, help="Matrix size (elements)")
    p.add_argument("--output", help="Output file for results")
    args = p.parse_args()

    generator = ClusterLoadGenerator(args.service, args.output)
    metrics = generator.intensive_matrix_load_test(args.concurrency, args.duration, args.size)
    
    print("\n=== LOAD TEST RESULTS ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
