#!/usr/bin/env python3
"""
Simple load test without threading to debug the issue
"""

import subprocess
import time
import json
from datetime import datetime

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
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)

def simple_load_test(concurrency: int, duration: int, matrix_size: int = 1000):
    """Simple load test without threading"""
    print(f"Starting simple load test:")
    print(f"  Matrix size: {matrix_size}x{matrix_size}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Duration: {duration} seconds")
    
    service_url = "http://userscale-app.userscale.svc.cluster.local:8000"
    results = []
    start_time = time.time()
    end_time = start_time + duration
    
    print(f"Starting at {datetime.now().strftime('%H:%M:%S')}")
    
    while time.time() < end_time:
        # Make requests sequentially for now
        for i in range(concurrency):
            if time.time() >= end_time:
                break
                
            request_start = time.time()
            try:
                result = run_kubectl_exec(f"curl -s '{service_url}/matrix?size={matrix_size}'")
                request_end = time.time()
                
                if result.returncode == 0 and result.stdout.strip():
                    results.append({
                        'success': True,
                        'duration': request_end - request_start,
                        'timestamp': request_start
                    })
                    print(f"Request {len(results)}: SUCCESS ({request_end - request_start:.2f}s)")
                else:
                    results.append({
                        'success': False,
                        'duration': 0,
                        'timestamp': request_start,
                        'error': result.stderr
                    })
                    print(f"Request {len(results)}: FAILED - {result.stderr}")
            except Exception as e:
                results.append({
                    'success': False,
                    'duration': 0,
                    'timestamp': time.time(),
                    'error': str(e)
                })
                print(f"Request {len(results)}: ERROR - {e}")
    
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

if __name__ == "__main__":
    simple_load_test(concurrency=5, duration=30, matrix_size=1000)
