#!/usr/bin/env python3
"""
Intensive load test designed to trigger scaling
"""

import subprocess
import time
import json
from datetime import datetime
import threading
import concurrent.futures

def run_kubectl_exec(cmd: str) -> subprocess.CompletedProcess:
    """Run command inside the app pod"""
    # Get pod name
    pod_result = subprocess.run([
        "kubectl", "get", "pods", "-n", "userscale", "-l", "app=userscale-app", 
        "-o", "jsonpath={.items[0].metadata.name}"
    ], capture_output=True, text=True)
    
    if pod_result.returncode != 0:
        raise Exception(f"Failed to get pod name: {pod_result.stderr}")
    
    pod_name = pod_result.stdout.strip()
    
    # Run command in pod
    full_cmd = ["kubectl", "exec", "-n", "userscale", pod_name, "--", "sh", "-c", cmd]
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=60)

def intensive_load_test(concurrency: int, duration: int, matrix_size: int = 2000):
    """Generate VERY intensive load to trigger scaling"""
    print(f"Starting INTENSIVE load test:")
    print(f"  Matrix size: {matrix_size}x{matrix_size}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Duration: {duration} seconds")
    print(f"  This WILL trigger scaling!")
    
    service_url = "http://userscale-app.userscale.svc.cluster.local:8000"
    results = []
    start_time = time.time()
    end_time = start_time + duration
    
    print(f"Starting at {datetime.now().strftime('%H:%M:%S')}")
    
    def make_request(request_id):
        """Make a single request"""
        request_start = time.time()
        try:
            # Use very large matrix size to create intensive load
            result = run_kubectl_exec(f"curl -s '{service_url}/matrix?size={matrix_size}'")
            request_end = time.time()
            
            if result.returncode == 0 and result.stdout.strip():
                return {
                    'success': True,
                    'duration': request_end - request_start,
                    'timestamp': request_start,
                    'request_id': request_id
                }
            else:
                return {
                    'success': False,
                    'duration': 0,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'error': result.stderr
                }
        except Exception as e:
            return {
                'success': False,
                'duration': 0,
                'timestamp': time.time(),
                'request_id': request_id,
                'error': str(e)
            }
    
    # Use ThreadPoolExecutor for better concurrency control
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        request_id = 0
        futures = []
        
        # Submit initial batch of requests
        for _ in range(concurrency * 2):  # Start with 2x concurrency
            if time.time() >= end_time:
                break
            future = executor.submit(make_request, request_id)
            futures.append(future)
            request_id += 1
        
        # Continue submitting requests while test is running
        while time.time() < end_time:
            # Check completed futures and submit new ones
            completed = []
            for future in futures:
                if future.done():
                    result = future.result()
                    results.append(result)
                    completed.append(future)
                    
                    # Submit new request if test is still running
                    if time.time() < end_time:
                        new_future = executor.submit(make_request, request_id)
                        futures.append(new_future)
                        request_id += 1
            
            # Remove completed futures
            for future in completed:
                futures.remove(future)
            
            # Small delay to prevent overwhelming
            time.sleep(0.1)
        
        # Wait for remaining futures to complete
        for future in futures:
            try:
                result = future.result(timeout=5)
                results.append(result)
            except:
                pass
    
    # Calculate metrics
    successful = [r for r in results if r['success']]
    total = len(results)
    
    print(f"\nResults:")
    print(f"Total requests: {total}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {total - len(successful)}")
    print(f"Success rate: {len(successful)/total*100:.1f}%")
    
    if successful:
        durations = [r['duration'] for r in successful]
        print(f"Avg latency: {sum(durations)/len(durations)*1000:.1f}ms")
        print(f"Total duration: {time.time() - start_time:.1f}s")
        print(f"Throughput: {len(successful)/(time.time() - start_time):.2f} RPS")
    
    return {
        'total_requests': total,
        'successful_requests': len(successful),
        'failed_requests': total - len(successful),
        'success_rate': len(successful)/total*100 if total > 0 else 0,
        'throughput_rps': len(successful)/(time.time() - start_time) if (time.time() - start_time) > 0 else 0,
        'avg_latency_ms': sum(durations)/len(durations)*1000 if successful else 0,
        'total_duration': time.time() - start_time
    }

if __name__ == "__main__":
    # Run very intensive test
    intensive_load_test(concurrency=30, duration=120, matrix_size=2500)
