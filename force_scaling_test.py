#!/usr/bin/env python3
"""
Force scaling test - generate sustained CPU load to trigger scaling
"""

import subprocess
import time
import json
from datetime import datetime
import threading
import concurrent.futures

def run_kubectl_exec(cmd: str) -> subprocess.CompletedProcess:
    """Run command inside the app pod"""
    pod_result = subprocess.run([
        "kubectl", "get", "pods", "-n", "userscale", "-l", "app=userscale-app", 
        "-o", "jsonpath={.items[0].metadata.name}"
    ], capture_output=True, text=True)
    
    if pod_result.returncode != 0:
        raise Exception(f"Failed to get pod name: {pod_result.stderr}")
    
    pod_name = pod_result.stdout.strip()
    
    full_cmd = ["kubectl", "exec", "-n", "userscale", pod_name, "--", "sh", "-c", cmd]
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=120)

def force_scaling_test():
    """Generate sustained CPU load to force scaling"""
    print("=" * 60)
    print("FORCE SCALING TEST")
    print("Generating sustained CPU load > 10% to trigger scaling")
    print("=" * 60)
    
    service_url = "http://userscale-app.userscale.svc.cluster.local:8000"
    
    def make_cpu_intensive_request(request_id, duration=60):
        """Make CPU-intensive requests"""
        request_start = time.time()
        try:
            # Use matrix endpoint with large size for CPU load
            result = run_kubectl_exec(f"curl -s '{service_url}/matrix?size=3000'")
            request_end = time.time()
            
            if result.returncode == 0 and result.stdout.strip():
                return {
                    'success': True,
                    'duration': request_end - request_start,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'type': 'matrix'
                }
            else:
                return {
                    'success': False,
                    'duration': 0,
                    'timestamp': request_start,
                    'request_id': request_id,
                    'error': result.stderr,
                    'type': 'matrix'
                }
        except Exception as e:
            return {
                'success': False,
                'duration': 0,
                'timestamp': time.time(),
                'request_id': request_id,
                'error': str(e),
                'type': 'matrix'
            }
    
    def monitor_scaling():
        """Monitor replica count and metrics"""
        print("\nMonitoring scaling...")
        for i in range(30):  # Monitor for 30 intervals
            try:
                # Check replica count
                result = subprocess.run([
                    "kubectl", "get", "deployment", "userscale-app", "-n", "userscale",
                    "-o", "jsonpath={.spec.replicas}"
                ], capture_output=True, text=True)
                
                replicas = "unknown"
                if result.returncode == 0:
                    replicas = result.stdout.strip().strip("'")
                
                # Check metrics
                metrics_result = run_kubectl_exec("curl -s http://localhost:8000/metrics")
                if metrics_result.returncode == 0:
                    metrics = json.loads(metrics_result.stdout)
                    users = metrics.get('active_users', 0)
                    cpu = metrics.get('cpu_percent', 0)
                    print(f"  {i*2}s: replicas={replicas}, users={users}, cpu={cpu:.1f}%")
                else:
                    print(f"  {i*2}s: replicas={replicas}, metrics=failed")
                    
            except Exception as e:
                print(f"  {i*2}s: error={e}")
            
            time.sleep(2)
    
    # Start monitoring in background
    monitor_thread = threading.Thread(target=monitor_scaling)
    monitor_thread.start()
    
    # Generate continuous CPU load
    print("Starting continuous CPU load generation...")
    start_time = time.time()
    end_time = start_time + 60  # Run for 60 seconds
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        request_id = 0
        futures = []
        
        # Submit initial batch of requests
        for _ in range(10):
            if time.time() >= end_time:
                break
            future = executor.submit(make_cpu_intensive_request, request_id, 60)
            futures.append(future)
            request_id += 1
        
        # Continue submitting requests while test is running
        while time.time() < end_time:
            completed = []
            for future in futures:
                if future.done():
                    result = future.result()
                    completed.append(future)
                    
                    # Submit new request if test is still running
                    if time.time() < end_time:
                        new_future = executor.submit(make_cpu_intensive_request, request_id, 60)
                        futures.append(new_future)
                        request_id += 1
            
            # Remove completed futures
            for future in completed:
                futures.remove(future)
            
            time.sleep(0.5)  # Submit new requests every 0.5 seconds
        
        # Wait for remaining futures
        for future in futures:
            try:
                future.result(timeout=5)
            except:
                pass
    
    # Wait for monitoring thread to finish
    monitor_thread.join()
    
    # Final status check
    print("\nFinal status check...")
    try:
        result = subprocess.run([
            "kubectl", "get", "deployment", "userscale-app", "-n", "userscale",
            "-o", "jsonpath={.spec.replicas}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            replicas = result.stdout.strip().strip("'")
            print(f"Final replicas: {replicas}")
        else:
            print(f"Failed to get final replicas: {result.stderr}")
    except Exception as e:
        print(f"Error getting final replicas: {e}")
    
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
    print("FORCE SCALING TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    force_scaling_test()
