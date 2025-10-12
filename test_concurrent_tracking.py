#!/usr/bin/env python3
"""
Test concurrent request tracking
"""

import subprocess
import time
import json
import threading

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

def test_concurrent_tracking():
    """Test if concurrent request tracking works"""
    print("Testing concurrent request tracking...")
    
    service_url = "http://userscale-app.userscale.svc.cluster.local:8000"
    
    def make_request(request_id, duration=10):
        """Make a request"""
        print(f"Starting request {request_id}")
        try:
            result = run_kubectl_exec(f"curl -s '{service_url}/stream?duration={duration*1000}'")
            print(f"Request {request_id} completed")
            return result.returncode == 0
        except Exception as e:
            print(f"Request {request_id} failed: {e}")
            return False
    
    def check_metrics():
        """Check metrics periodically"""
        for i in range(20):
            try:
                result = run_kubectl_exec("curl -s http://localhost:8000/metrics")
                if result.returncode == 0:
                    metrics = json.loads(result.stdout)
                    print(f"Metrics at {i*2}s: users={metrics.get('active_users', 0)}, cpu={metrics.get('cpu_percent', 0):.1f}%")
                else:
                    print(f"Failed to get metrics at {i*2}s: {result.stderr}")
            except Exception as e:
                print(f"Error getting metrics at {i*2}s: {e}")
            
            time.sleep(2)
    
    # Start metrics monitoring in background
    metrics_thread = threading.Thread(target=check_metrics)
    metrics_thread.start()
    
    # Start 5 concurrent requests
    print("Starting 5 concurrent requests...")
    threads = []
    for i in range(5):
        thread = threading.Thread(target=make_request, args=(i, 15))
        thread.start()
        threads.append(thread)
    
    # Wait for all requests to complete
    for thread in threads:
        thread.join()
    
    # Wait for metrics thread to finish
    metrics_thread.join()
    
    print("Test complete!")

if __name__ == "__main__":
    test_concurrent_tracking()
