#!/usr/bin/env python3
"""
Test script to verify connection to the application
"""

import requests
import time
import subprocess
import threading

def test_port_forward():
    """Test port forwarding connection"""
    print("Testing port forwarding connection...")
    
    # Start port forwarding in background
    pf_process = subprocess.Popen(
        ["kubectl", "port-forward", "service/userscale-app", "8000:8000", "-n", "userscale"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for port forward to establish
    time.sleep(5)
    
    try:
        # Test connection
        response = requests.get("http://localhost:8000/healthz", timeout=10)
        print(f"Port forward test: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"Port forward test failed: {e}")
        return False
    finally:
        pf_process.terminate()
        pf_process.wait()

def test_pod_exec():
    """Test by executing commands inside the pod"""
    print("Testing pod exec connection...")
    
    try:
        # Get pod name
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "userscale", "-l", "app=userscale-app", "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True, text=True
        )
        pod_name = result.stdout.strip()
        print(f"Pod name: {pod_name}")
        
        # Test health endpoint via kubectl exec
        result = subprocess.run([
            "kubectl", "exec", "-n", "userscale", pod_name, "--",
            "curl", "-s", "http://localhost:8000/healthz"
        ], capture_output=True, text=True, timeout=10)
        
        print(f"Pod exec test: {result.returncode} - {result.stdout}")
        return result.returncode == 0
    except Exception as e:
        print(f"Pod exec test failed: {e}")
        return False

def test_service_dns():
    """Test using service DNS name"""
    print("Testing service DNS connection...")
    
    try:
        # Test from within cluster using service name
        result = subprocess.run([
            "kubectl", "run", "test-pod", "--image=curlimages/curl", "--rm", "-i", "--restart=Never", "-n", "userscale", "--",
            "curl", "-s", "http://userscale-app.userscale.svc.cluster.local:8000/healthz"
        ], capture_output=True, text=True, timeout=30)
        
        print(f"Service DNS test: {result.returncode} - {result.stdout}")
        return result.returncode == 0
    except Exception as e:
        print(f"Service DNS test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing various connection methods...")
    
    # Test 1: Port forwarding
    pf_success = test_port_forward()
    
    # Test 2: Pod exec
    exec_success = test_pod_exec()
    
    # Test 3: Service DNS
    dns_success = test_service_dns()
    
    print(f"\nResults:")
    print(f"Port Forward: {'PASS' if pf_success else 'FAIL'}")
    print(f"Pod Exec: {'PASS' if exec_success else 'FAIL'}")
    print(f"Service DNS: {'PASS' if dns_success else 'FAIL'}")
    
    if exec_success or dns_success:
        print("\nAt least one method works! We can proceed with the test.")
    else:
        print("\nAll connection methods failed. Need to debug further.")
