import argparse
import time
import threading
import httpx
import json
import csv
from typing import Callable, Dict, List
from datetime import datetime


class LoadGenerator:
    def __init__(self, base_url: str, output_file: str = None):
        self.base_url = base_url
        self.output_file = output_file
        self.results = []
        self.start_time = None
        
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
            with httpx.Client(timeout=60.0) as s:  # Increased timeout for larger matrices
                response = s.get(f"{self.base_url}/matrix", params={"size": matrix_size})
                return response.json()

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

    def matrix_load_test(self, concurrency: int, duration: int, matrix_size: int = 10000):
        """Generate intensive matrix multiplication load with 10000 elements"""
        print(f"Starting matrix multiplication load test:")
        print(f"  Matrix size: {matrix_size}x{matrix_size} (10,000 elements)")
        print(f"  Concurrency: {concurrency}")
        print(f"  Duration: {duration} seconds")
        
        # Use matrix size that results in ~10,000 elements for intensive computation
        actual_size = int((matrix_size ** 0.5))  # sqrt(10000) = 100
        
        def call():
            with httpx.Client(timeout=30.0) as s:
                response = s.get(f"{self.base_url}/matrix", params={"size": actual_size})
                return response.json()

        threads = []
        results_list = []
        self.start_time = time.time()
        stop_t = self.start_time + duration
        
        for i in range(concurrency):
            t = threading.Thread(
                target=self.worker, 
                args=(f"worker-{i}", call, stop_t, results_list), 
                daemon=True
            )
            t.start()
            threads.append(t)

        # Monitor progress
        self._monitor_progress(duration)
        
        for t in threads:
            t.join()

        self.results = results_list
        self._save_results("matrix_load_test", {
            'matrix_size': actual_size,
            'concurrency': concurrency,
            'duration': duration
        })
        
        return self._calculate_metrics()

    def burst_load_test(self, concurrency: int, duration: int, burst_cycles: int = 3):
        """Generate burst load patterns to test scaling responsiveness"""
        print(f"Starting BURST load test:")
        print(f"  Burst cycles: {burst_cycles}")
        print(f"  Concurrency per burst: {concurrency}")
        print(f"  Duration: {duration} seconds")
        
        results_list = []
        self.start_time = time.time()
        
        for cycle in range(burst_cycles):
            print(f"\nStarting burst cycle {cycle + 1}/{burst_cycles}")
            
            # Burst period (high load)
            burst_start = time.time()
            burst_duration = duration / burst_cycles * 0.7  # 70% of cycle time
            
            threads = []
            stop_t = burst_start + burst_duration
            
            for i in range(concurrency):
                def call():
                    with httpx.Client(timeout=30.0) as s:
                        # Use larger matrix for more intensive load
                        response = s.get(f"{self.base_url}/matrix", params={"size": 1000})
                        return response.json()
                
                t = threading.Thread(
                    target=self.worker,
                    args=(f"burst-{cycle}-worker-{i}", call, stop_t, results_list),
                    daemon=True
                )
                t.start()
                threads.append(t)
            
            # Wait for burst to complete
            for t in threads:
                t.join()
            
            # Rest period (low load)
            rest_duration = duration / burst_cycles * 0.3  # 30% of cycle time
            print(f"Rest period: {rest_duration:.1f}s")
            time.sleep(rest_duration)
        
        self.results = results_list
        self._save_results("burst_load_test", {
            'burst_cycles': burst_cycles,
            'concurrency': concurrency,
            'duration': duration
        })
        
        return self._calculate_metrics()

    def _monitor_progress_with_scaling(self, duration: int, results_list: List):
        """Monitor and display progress with replica tracking"""
        start = time.time()
        last_replica_count = None
        
        while time.time() - start < duration:
            time.sleep(10)  # Check every 10 seconds
            elapsed = time.time() - start
            remaining = duration - elapsed
            
            # Try to get current replica count
            try:
                with httpx.Client(timeout=5.0) as s:
                    response = s.get(f"{self.base_url}/metrics")
                    if response.status_code == 200:
                        metrics = response.json()
                        active_users = metrics.get('active_users', 0)
                        cpu_percent = metrics.get('cpu_percent', 0)
                        print(f"Progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining | Active users: {active_users} | CPU: {cpu_percent:.1f}%")
            except Exception as e:
                print(f"Progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining | Status: {len(results_list)} requests completed")

    def _monitor_progress(self, duration: int):
        """Monitor and display progress during load test"""
        start = time.time()
        while time.time() - start < duration:
            time.sleep(5)
            elapsed = time.time() - start
            remaining = duration - elapsed
            print(f"Progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining")

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
    p = argparse.ArgumentParser(description="Advanced Load Generator for Userscale Testing")
    p.add_argument("--base", default="http://localhost:8000", help="Base URL of the application")
    p.add_argument("--scenario", choices=["matrix", "stream", "gpu", "intensive_matrix", "burst"], 
                   default="intensive_matrix", help="Load test scenario")
    p.add_argument("--concurrency", type=int, default=20, help="Number of concurrent workers")
    p.add_argument("--duration", type=int, default=120, help="Test duration in seconds")
    p.add_argument("--size", type=int, default=2000, help="Matrix size (elements)")
    p.add_argument("--work-ms", type=int, default=1000, help="GPU work duration in ms")
    p.add_argument("--stream-ms", type=int, default=1000, help="Stream duration in ms")
    p.add_argument("--burst-cycles", type=int, default=3, help="Number of burst cycles")
    p.add_argument("--output", help="Output file for results")
    args = p.parse_args()

    generator = LoadGenerator(args.base, args.output)

    if args.scenario == "intensive_matrix":
        metrics = generator.intensive_matrix_load_test(args.concurrency, args.duration, args.size)
        print("\n=== INTENSIVE LOAD TEST RESULTS ===")
        for key, value in metrics.items():
            print(f"{key}: {value}")
            
    elif args.scenario == "burst":
        metrics = generator.burst_load_test(args.concurrency, args.duration, args.burst_cycles)
        print("\n=== BURST LOAD TEST RESULTS ===")
        for key, value in metrics.items():
            print(f"{key}: {value}")
            
    elif args.scenario == "matrix":
        metrics = generator.matrix_load_test(args.concurrency, args.duration, args.size)
        print("\n=== LOAD TEST RESULTS ===")
        for key, value in metrics.items():
            print(f"{key}: {value}")
            
    elif args.scenario == "stream":
        # Keep original stream functionality
        def call():
            with httpx.Client(timeout=10.0) as s:
                s.get(f"{args.base}/stream", params={"duration_ms": args.stream_ms})
        
        threads = []
        stop_t = time.time() + args.duration
        for i in range(args.concurrency):
            t = threading.Thread(target=generator.worker, args=(f"t{i}", call, stop_t, generator.results), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
            
    elif args.scenario == "gpu":
        def call():
            with httpx.Client(timeout=10.0) as s:
                s.get(f"{args.base}/gpu_job", params={"work_ms": args.work_ms})
        
        threads = []
        stop_t = time.time() + args.duration
        for i in range(args.concurrency):
            t = threading.Thread(target=generator.worker, args=(f"t{i}", call, stop_t, generator.results), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()


if __name__ == "__main__":
    main()