#!/usr/bin/env python3
"""
Enhanced comparison test with GPU-aware scaling and proper replica tracking
"""

import subprocess
import time
import json
import os
from datetime import datetime
from typing import Dict, List
import threading


class KubernetesManager:
    def __init__(self, namespace: str = "userscale"):
        self.namespace = namespace
        
    def run_kubectl(self, cmd: str) -> subprocess.CompletedProcess:
        """Run kubectl command"""
        full_cmd = f"kubectl {cmd}"
        return subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    
    def apply_manifest(self, manifest_path: str):
        """Apply Kubernetes manifest"""
        result = self.run_kubectl(f"apply -f {manifest_path}")
        if result.returncode != 0:
            print(f"Failed to apply {manifest_path}: {result.stderr}")
            return False
        print(f"✅ Applied {manifest_path}")
        return True
    
    def delete_manifest(self, manifest_path: str):
        """Delete Kubernetes manifest"""
        result = self.run_kubectl(f"delete -f {manifest_path}")
        if result.returncode != 0:
            print(f"Failed to delete {manifest_path}: {result.stderr}")
            return False
        print(f"🗑️  Deleted {manifest_path}")
        return True
    
    def wait_for_deployment(self, deployment_name: str, timeout: int = 300):
        """Wait for deployment to be ready"""
        print(f"⏳ Waiting for deployment {deployment_name} to be ready...")
        result = self.run_kubectl(f"wait --for=condition=available --timeout={timeout}s deployment/{deployment_name} -n {self.namespace}")
        return result.returncode == 0
    
    def get_replica_count(self, deployment_name: str) -> int:
        """Get current replica count"""
        result = self.run_kubectl(f"get deployment {deployment_name} -n {self.namespace} -o jsonpath='{{.spec.replicas}}'")
        if result.returncode == 0:
            return int(result.stdout.strip())
        return 0
    
    def get_pod_count(self, deployment_name: str) -> int:
        """Get current pod count"""
        result = self.run_kubectl(f"get pods -l app={deployment_name} -n {self.namespace} --no-headers | wc -l")
        if result.returncode == 0:
            return int(result.stdout.strip())
        return 0
    
    def get_service_url(self, service_name: str) -> str:
        """Get service URL (assuming port-forward)"""
        return f"http://localhost:8000"  # Port-forward URL
    
    def port_forward(self, service_name: str, local_port: int = 8000, remote_port: int = 8000):
        """Start port forwarding"""
        cmd = f"port-forward service/{service_name} {local_port}:{remote_port} -n {self.namespace}"
        return subprocess.Popen(f"kubectl {cmd}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def get_replica_history(self, deployment_name: str, duration: int) -> List[Dict]:
        """Monitor replica changes over time"""
        history = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            current_time = time.time() - start_time
            replicas = self.get_replica_count(deployment_name)
            pods = self.get_pod_count(deployment_name)
            
            history.append({
                "timestamp": current_time,
                "replicas": replicas,
                "pods": pods
            })
            
            time.sleep(5)  # Check every 5 seconds
        
        return history


class LoadTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def run_intensive_load_test(self, concurrency: int = 25, duration: int = 180, matrix_size: int = 1500):
        """Run intensive load test that should trigger scaling"""
        print(f"🚀 Starting INTENSIVE load test:")
        print(f"  URL: {self.base_url}")
        print(f"  Concurrency: {concurrency}")
        print(f"  Duration: {duration}s")
        print(f"  Matrix size: {matrix_size}x{matrix_size}")
        
        # Import the load generator
        import sys
        sys.path.append('loadgen')
        from main import LoadGenerator
        
        output_file = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        generator = LoadGenerator(self.base_url, output_file)
        
        return generator.intensive_matrix_load_test(concurrency, duration, matrix_size)


class ComparisonTest:
    def __init__(self, namespace: str = "userscale"):
        self.k8s = KubernetesManager(namespace)
        self.namespace = namespace
        self.port_forward_process = None
        
    def setup_test_environment(self):
        """Setup the test environment"""
        print("🔧 Setting up test environment...")
        
        # Create namespace
        self.k8s.run_kubectl(f"create namespace {self.namespace} --dry-run=client -o yaml | kubectl apply -f -")
        
        # Apply manifests
        manifests = [
            "k8s/namespace.yaml",
            "k8s/configmap.yaml", 
            "k8s/rbac.yaml",
            "k8s/app.yaml"
        ]
        
        for manifest in manifests:
            if not self.k8s.apply_manifest(manifest):
                return False
        
        # Wait for app to be ready
        if not self.k8s.wait_for_deployment("userscale-app"):
            print("❌ App deployment failed to become ready")
            return False
        
        print("✅ Test environment setup complete")
        return True
    
    def run_userscale_test(self, test_duration: int = 180) -> Dict:
        """Run test with custom userscale autoscaler"""
        print("\n🎯 Running USERCALE autoscaling test...")
        
        # Apply custom scaler
        if not self.k8s.apply_manifest("k8s/scaler.yaml"):
            return None
        
        # Wait for scaler to be ready
        if not self.k8s.wait_for_deployment("userscale-scaler"):
            print("❌ Scaler deployment failed to become ready")
            return None
        
        # Start port forwarding
        self.port_forward_process = self.k8s.port_forward("userscale-app")
        time.sleep(5)  # Wait for port forward to establish
        
        try:
            # Start replica monitoring in background
            replica_history = []
            monitoring_thread = threading.Thread(
                target=lambda: replica_history.extend(self.k8s.get_replica_history("userscale-app", test_duration))
            )
            monitoring_thread.daemon = True
            monitoring_thread.start()
            
            # Run load test
            load_tester = LoadTester("http://localhost:8000")
            metrics = load_tester.run_intensive_load_test(
                concurrency=25,  # High concurrency
                duration=test_duration,
                matrix_size=1500  # Large matrices
            )
            
            # Wait for monitoring to complete
            monitoring_thread.join()
            
            # Calculate average replicas
            if replica_history:
                avg_replicas = sum(h["replicas"] for h in replica_history) / len(replica_history)
                max_replicas = max(h["replicas"] for h in replica_history)
                min_replicas = min(h["replicas"] for h in replica_history)
            else:
                avg_replicas = max_replicas = min_replicas = 1.0
            
            result = {
                "test_type": "userscale",
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "scaling_info": {
                    "avg_replicas": avg_replicas,
                    "max_replicas": max_replicas,
                    "min_replicas": min_replicas,
                    "replica_history": replica_history
                }
            }
            
            # Save results
            output_file = f"userscale_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"📊 Userscale test results saved to {output_file}")
            return result
            
        finally:
            # Cleanup port forward
            if self.port_forward_process:
                self.port_forward_process.terminate()
                self.port_forward_process.wait()
    
    def run_hpa_test(self, test_duration: int = 180) -> Dict:
        """Run test with standard HPA"""
        print("\n🎯 Running HPA autoscaling test...")
        
        # Remove custom scaler and apply HPA
        self.k8s.delete_manifest("k8s/scaler.yaml")
        time.sleep(10)  # Wait for scaler to be removed
        
        if not self.k8s.apply_manifest("k8s/hpa.yaml"):
            return None
        
        # Wait for HPA to be ready
        time.sleep(30)  # HPA takes time to initialize
        
        # Start port forwarding
        self.port_forward_process = self.k8s.port_forward("userscale-app")
        time.sleep(5)
        
        try:
            # Start replica monitoring in background
            replica_history = []
            monitoring_thread = threading.Thread(
                target=lambda: replica_history.extend(self.k8s.get_replica_history("userscale-app", test_duration))
            )
            monitoring_thread.daemon = True
            monitoring_thread.start()
            
            # Run load test
            load_tester = LoadTester("http://localhost:8000")
            metrics = load_tester.run_intensive_load_test(
                concurrency=25,  # High concurrency
                duration=test_duration,
                matrix_size=1500  # Large matrices
            )
            
            # Wait for monitoring to complete
            monitoring_thread.join()
            
            # Calculate average replicas
            if replica_history:
                avg_replicas = sum(h["replicas"] for h in replica_history) / len(replica_history)
                max_replicas = max(h["replicas"] for h in replica_history)
                min_replicas = min(h["replicas"] for h in replica_history)
            else:
                avg_replicas = max_replicas = min_replicas = 1.0
            
            result = {
                "test_type": "hpa",
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "scaling_info": {
                    "avg_replicas": avg_replicas,
                    "max_replicas": max_replicas,
                    "min_replicas": min_replicas,
                    "replica_history": replica_history
                }
            }
            
            # Save results
            output_file = f"hpa_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"📊 HPA test results saved to {output_file}")
            return result
            
        finally:
            # Cleanup port forward
            if self.port_forward_process:
                self.port_forward_process.terminate()
                self.port_forward_process.wait()
    
    def cleanup(self):
        """Cleanup test environment"""
        print("🧹 Cleaning up test environment...")
        
        if self.port_forward_process:
            self.port_forward_process.terminate()
            self.port_forward_process.wait()
        
        # Delete manifests
        manifests = [
            "k8s/hpa.yaml",
            "k8s/scaler.yaml",
            "k8s/app.yaml",
            "k8s/rbac.yaml",
            "k8s/configmap.yaml"
        ]
        
        for manifest in manifests:
            self.k8s.delete_manifest(manifest)
        
        print("✅ Cleanup complete")
    
    def run_comparison(self, test_duration: int = 180):
        """Run complete comparison test"""
        print("🚀 Starting Enhanced GPU-Aware Autoscaling Comparison Test")
        print(f"Test duration: {test_duration} seconds per test")
        print("=" * 60)
        
        try:
            # Setup environment
            if not self.setup_test_environment():
                print("❌ Failed to setup test environment")
                return
            
            # Run userscale test
            userscale_results = self.run_userscale_test(test_duration)
            if not userscale_results:
                print("❌ Userscale test failed")
                return
            
            # Wait between tests
            print("\n⏳ Waiting 30 seconds between tests...")
            time.sleep(30)
            
            # Run HPA test
            hpa_results = self.run_hpa_test(test_duration)
            if not hpa_results:
                print("❌ HPA test failed")
                return
            
            # Generate comparison report
            self.generate_comparison_report(userscale_results, hpa_results)
            
        finally:
            self.cleanup()
    
    def generate_comparison_report(self, userscale_results: Dict, hpa_results: Dict):
        """Generate detailed comparison report"""
        print("\n📊 Generating comparison report...")
        
        us_metrics = userscale_results["metrics"]
        hpa_metrics = hpa_results["metrics"]
        
        us_scaling = userscale_results["scaling_info"]
        hpa_scaling = hpa_results["scaling_info"]
        
        # Calculate improvements
        throughput_improvement = ((us_metrics["throughput_rps"] - hpa_metrics["throughput_rps"]) / max(hpa_metrics["throughput_rps"], 0.001)) * 100
        latency_improvement = ((hpa_metrics["avg_latency_ms"] - us_metrics["avg_latency_ms"]) / max(hpa_metrics["avg_latency_ms"], 0.001)) * 100
        replica_efficiency = ((hpa_scaling["avg_replicas"] - us_scaling["avg_replicas"]) / max(us_scaling["avg_replicas"], 0.001)) * 100
        
        comparison_data = {
            "test_configuration": {
                "namespace": self.namespace,
                "test_duration": 180,
                "concurrency": 25,
                "matrix_size": 1500,
                "timestamp": datetime.now().isoformat()
            },
            "userscale_results": userscale_results,
            "hpa_results": hpa_results,
            "comparison_results": {
                "userscale": {
                    "throughput_rps": us_metrics["throughput_rps"],
                    "avg_latency_ms": us_metrics["avg_latency_ms"],
                    "avg_replicas": us_scaling["avg_replicas"],
                    "max_replicas": us_scaling["max_replicas"],
                    "min_replicas": us_scaling["min_replicas"]
                },
                "hpa": {
                    "throughput_rps": hpa_metrics["throughput_rps"],
                    "avg_latency_ms": hpa_metrics["avg_latency_ms"],
                    "avg_replicas": hpa_scaling["avg_replicas"],
                    "max_replicas": hpa_scaling["max_replicas"],
                    "min_replicas": hpa_scaling["min_replicas"]
                },
                "improvements": {
                    "throughput_improvement_percent": throughput_improvement,
                    "latency_improvement_percent": latency_improvement,
                    "resource_efficiency_percent": replica_efficiency
                },
                "summary": {
                    "userscale_better_throughput": throughput_improvement > 0,
                    "userscale_better_latency": latency_improvement > 0,
                    "userscale_more_efficient": replica_efficiency > 0,
                    "overall_winner": "userscale" if (throughput_improvement > 0 or latency_improvement > 0) else "hpa"
                }
            }
        }
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = f"comparison_results_{timestamp}"
        os.makedirs(results_dir, exist_ok=True)
        
        detailed_file = os.path.join(results_dir, "detailed_results.json")
        with open(detailed_file, 'w') as f:
            json.dump(comparison_data, f, indent=2)
        
        # Generate formatted reports
        import subprocess
        subprocess.run([
            "python", "format_results.py", 
            "--results", detailed_file,
            "--output-dir", results_dir,
            "--formats", "csv", "html", "json"
        ])
        
        print(f"\n🎉 Comparison test complete!")
        print(f"📁 Results saved to: {results_dir}")
        print(f"📊 Overall winner: {comparison_data['comparison_results']['summary']['overall_winner'].upper()}")
        print(f"🚀 Throughput improvement: {throughput_improvement:+.2f}%")
        print(f"⚡ Latency improvement: {latency_improvement:+.2f}%")
        print(f"💾 Resource efficiency: {replica_efficiency:+.2f}%")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced GPU-Aware Autoscaling Comparison Test")
    parser.add_argument("--duration", type=int, default=180, help="Test duration per scenario (seconds)")
    parser.add_argument("--namespace", default="userscale", help="Kubernetes namespace")
    
    args = parser.parse_args()
    
    test = ComparisonTest(args.namespace)
    test.run_comparison(args.duration)


if __name__ == "__main__":
    main()