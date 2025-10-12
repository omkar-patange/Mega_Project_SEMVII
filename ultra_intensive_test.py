#!/usr/bin/env python3
"""
Ultra intensive test that will definitely trigger scaling
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
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=120)

def ultra_intensive_test():
    """Generate ULTRA intensive load that WILL trigger scaling"""
    print("=" * 60)
    print("ULTRA INTENSIVE LOAD TEST")
    print("This WILL trigger scaling!")
    print("=" * 60)
    
    service_url = "http://userscale-app.userscale.svc.cluster.local:8000"
    
    # Test 1: Very large matrix operations
    print("\n1. Testing with HUGE matrix operations (3000x3000)...")
    start_time = time.time()
    
    def make_huge_request(request_id):
        """Make a request with huge matrix"""
        request_start = time.time()
        try:
            # Use MASSIVE matrix size
            result = run_kubectl_exec(f"curl -s '{service_url}/matrix?size=3000'")
            request_end = time.time()
            
            if result.returncode == 0 and result.stdout.strip():
                return {
                    'success': True,
                    'duration': request_end - request_start,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'type': 'huge_matrix'
                }
            else:
                return {
                    'success': False,
                    'duration': 0,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'error': result.stderr,
                    'type': 'huge_matrix'
                }
        except Exception as e:
            return {
                'success': False,
                'duration': 0,
                'timestamp': time.time(),
                'request_id': request_id,
                'error': str(e),
                'type': 'huge_matrix'
            }
    
    # Run 50 concurrent huge matrix operations
    print("Running 50 concurrent huge matrix operations...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_huge_request, i) for i in range(50)]
        results1 = [future.result() for future in futures]
    
    print(f"Completed {len(results1)} huge matrix operations in {time.time() - start_time:.1f}s")
    
    # Test 2: Continuous stream operations
    print("\n2. Testing with continuous stream operations...")
    start_time = time.time()
    
    def make_stream_request(request_id):
        """Make a stream request"""
        request_start = time.time()
        try:
            result = run_kubectl_exec(f"curl -s '{service_url}/stream?duration=10'")
            request_end = time.time()
            
            if result.returncode == 0 and result.stdout.strip():
                return {
                    'success': True,
                    'duration': request_end - request_start,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'type': 'stream'
                }
            else:
                return {
                    'success': False,
                    'duration': 0,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'error': result.stderr,
                    'type': 'stream'
                }
        except Exception as e:
            return {
                'success': False,
                'duration': 0,
                'timestamp': time.time(),
                'request_id': request_id,
                'error': str(e),
                'type': 'stream'
            }
    
    # Run 30 concurrent stream operations
    print("Running 30 concurrent stream operations...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(make_stream_request, i) for i in range(30)]
        results2 = [future.result() for future in futures]
    
    print(f"Completed {len(results2)} stream operations in {time.time() - start_time:.1f}s")
    
    # Test 3: Mixed intensive load
    print("\n3. Testing with mixed intensive load...")
    start_time = time.time()
    end_time = start_time + 60  # 60 seconds of intensive load
    
    def make_mixed_request(request_id):
        """Make mixed requests"""
        request_start = time.time()
        try:
            # Alternate between different types of requests
            if request_id % 3 == 0:
                result = run_kubectl_exec(f"curl -s '{service_url}/matrix?size=2500'")
            elif request_id % 3 == 1:
                result = run_kubectl_exec(f"curl -s '{service_url}/stream?duration=5'")
            else:
                result = run_kubectl_exec(f"curl -s '{service_url}/gpu_matrix?size=2000'")
            
            request_end = time.time()
            
            if result.returncode == 0 and result.stdout.strip():
                return {
                    'success': True,
                    'duration': request_end - request_start,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'type': 'mixed'
                }
            else:
                return {
                    'success': False,
                    'duration': 0,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'error': result.stderr,
                    'type': 'mixed'
                }
        except Exception as e:
            return {
                'success': False,
                'duration': 0,
                'timestamp': time.time(),
                'request_id': request_id,
                'error': str(e),
                'type': 'mixed'
            }
    
    # Run continuous mixed load for 60 seconds
    print("Running continuous mixed load for 60 seconds...")
    results3 = []
    request_id = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
        futures = []
        
        # Submit initial batch
        for _ in range(40):
            if time.time() >= end_time:
                break
            future = executor.submit(make_mixed_request, request_id)
            futures.append(future)
            request_id += 1
        
        # Continue submitting requests
        while time.time() < end_time:
            completed = []
            for future in futures:
                if future.done():
                    result = future.result()
                    results3.append(result)
                    completed.append(future)
                    
                    if time.time() < end_time:
                        new_future = executor.submit(make_mixed_request, request_id)
                        futures.append(new_future)
                        request_id += 1
            
            for future in completed:
                futures.remove(future)
            
            time.sleep(0.1)
        
        # Wait for remaining futures
        for future in futures:
            try:
                result = future.result(timeout=5)
                results3.append(result)
            except:
                pass
    
    print(f"Completed {len(results3)} mixed operations in {time.time() - start_time:.1f}s")
    
    # Check replica count during the test
    print("\n4. Checking replica count...")
    for i in range(10):
        try:
            result = subprocess.run([
                "kubectl", "get", "deployment", "userscale-app", "-n", "userscale",
                "-o", "jsonpath={.spec.replicas}"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                replicas = result.stdout.strip().strip("'")
                print(f"  Replicas at {i*10}s: {replicas}")
            else:
                print(f"  Failed to get replicas at {i*10}s: {result.stderr}")
        except Exception as e:
            print(f"  Error getting replicas at {i*10}s: {e}")
        
        time.sleep(10)
    
    # Final replica count
    try:
        result = subprocess.run([
            "kubectl", "get", "deployment", "userscale-app", "-n", "userscale",
            "-o", "jsonpath={.spec.replicas}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            replicas = result.stdout.strip().strip("'")
            print(f"\nFinal replicas: {replicas}")
        else:
            print(f"\nFailed to get final replicas: {result.stderr}")
    except Exception as e:
        print(f"\nError getting final replicas: {e}")
    
    # Check pod count
    try:
        result = subprocess.run([
            "kubectl", "get", "pods", "-n", "userscale", "-l", "app=userscale-app",
            "--no-headers"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            pod_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
            print(f"Active pods: {pod_count}")
        else:
            print(f"Failed to get pod count: {result.stderr}")
    except Exception as e:
        print(f"Error getting pod count: {e}")
    
    print("\n" + "=" * 60)
    print("ULTRA INTENSIVE TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    ultra_intensive_test()
