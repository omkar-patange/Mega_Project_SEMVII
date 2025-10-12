#!/usr/bin/env python3
"""
Sustained load test that generates enough concurrent users to trigger scaling
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

def sustained_load_test():
    """Generate sustained concurrent load to trigger scaling"""
    print("=" * 60)
    print("SUSTAINED LOAD TEST")
    print("Generating 10+ concurrent users to trigger scaling")
    print("=" * 60)
    
    service_url = "http://userscale-app.userscale.svc.cluster.local:8000"
    
    def make_request(request_id, duration=30):
        """Make a long-running request"""
        request_start = time.time()
        try:
            # Use stream endpoint for long-running requests
            result = run_kubectl_exec(f"curl -s '{service_url}/stream?duration={duration*1000}'")
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
    
    # Start 15 concurrent long-running requests (each 30 seconds)
    print("Starting 15 concurrent long-running requests...")
    print("Each request will run for 30 seconds")
    print("This should generate 15+ concurrent users")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        # Submit all requests at once
        futures = [executor.submit(make_request, i, 30) for i in range(15)]
        
        # Monitor replica count during the test
        print("\nMonitoring replica count...")
        for i in range(20):  # Monitor for 20 intervals
            try:
                result = subprocess.run([
                    "kubectl", "get", "deployment", "userscale-app", "-n", "userscale",
                    "-o", "jsonpath={.spec.replicas}"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    replicas = result.stdout.strip().strip("'")
                    print(f"  Replicas at {i*3}s: {replicas}")
                else:
                    print(f"  Failed to get replicas at {i*3}s: {result.stderr}")
            except Exception as e:
                print(f"  Error getting replicas at {i*3}s: {e}")
            
            time.sleep(3)  # Check every 3 seconds
        
        # Wait for all requests to complete
        print("\nWaiting for requests to complete...")
        results = [future.result() for future in futures]
    
    # Check final replica count
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
    
    # Check metrics during the test
    print("\nChecking metrics...")
    for i in range(5):
        try:
            result = run_kubectl_exec("curl -s http://localhost:8000/metrics")
            if result.returncode == 0:
                metrics = json.loads(result.stdout)
                print(f"  Metrics at {i*10}s: users={metrics.get('active_users', 0)}, cpu={metrics.get('cpu_percent', 0):.1f}%")
            else:
                print(f"  Failed to get metrics at {i*10}s: {result.stderr}")
        except Exception as e:
            print(f"  Error getting metrics at {i*10}s: {e}")
        
        time.sleep(10)
    
    print("\n" + "=" * 60)
    print("SUSTAINED LOAD TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    sustained_load_test()
