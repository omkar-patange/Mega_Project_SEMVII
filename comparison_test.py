#!/usr/bin/env python3
"""
Userscale vs HPA Efficiency Comparison Test

This script runs comprehensive load tests comparing the efficiency of:
1. Userscale (custom user-aware scaling)
2. HPA (Horizontal Pod Autoscaler)

The test generates matrix multiplication load with 10,000 elements and measures:
- Throughput (requests per second)
- Latency (average and P95)
- Resource utilization
- Scaling behavior
- Cost efficiency
"""

import argparse
import subprocess
import time
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
import httpx
import yaml


class KubernetesManager:
    def __init__(self, namespace: str = "userscale"):
        self.namespace = namespace
        
    def apply_config(self, config_file: str) -> bool:
        """Apply Kubernetes configuration"""
        try:
            result = subprocess.run(
                ["kubectl", "apply", "-f", config_file, "-n", self.namespace],
                capture_output=True, text=True, check=True
            )
            print(f"Applied {config_file}: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error applying {config_file}: {e.stderr}")
            return False
    
    def delete_config(self, config_file: str) -> bool:
        """Delete Kubernetes configuration"""
        try:
            subprocess.run(
                ["kubectl", "delete", "-f", config_file, "-n", self.namespace, "--ignore-not-found=true"],
                capture_output=True, text=True, check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error deleting {config_file}: {e.stderr}")
            return False
    
    def get_deployment_replicas(self, deployment_name: str) -> int:
        """Get current number of replicas for a deployment"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "deployment", deployment_name, "-n", self.namespace, "-o", "jsonpath={.spec.replicas}"],
                capture_output=True, text=True, check=True
            )
            return int(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0
    
    def get_pod_count(self, app_label: str) -> int:
        """Get current number of pods with specific label"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", self.namespace, "-l", f"app={app_label}", "--no-headers"],
                capture_output=True, text=True, check=True
            )
            return len([line for line in result.stdout.strip().split('\n') if line and 'Running' in line])
        except subprocess.CalledProcessError:
            return 0
    
    def wait_for_deployment_ready(self, deployment_name: str, timeout: int = 300) -> bool:
        """Wait for deployment to be ready"""
        try:
            result = subprocess.run(
                ["kubectl", "rollout", "status", f"deployment/{deployment_name}", "-n", self.namespace, f"--timeout={timeout}s"],
                capture_output=True, text=True, check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_service_url(self, service_name: str) -> str:
        """Get service URL for testing"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "service", service_name, "-n", self.namespace, "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"],
                capture_output=True, text=True, check=True
            )
            ip = result.stdout.strip()
            if ip:
                return f"http://{ip}"
        except subprocess.CalledProcessError:
            pass
        
        # Fallback to port-forward
        return "http://localhost:8000"


class LoadTestRunner:
    def __init__(self, base_url: str, output_dir: str = "test_results"):
        self.base_url = base_url
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def run_load_test(self, test_name: str, concurrency: int = 20, duration: int = 120, matrix_size: int = 10000) -> Dict[str, Any]:
        """Run load test and collect metrics"""
        output_file = os.path.join(self.output_dir, f"{test_name}_results.json")
        
        cmd = [
            "python", "loadgen/main.py",
            "--base", self.base_url,
            "--scenario", "intensive_matrix",
            "--concurrency", str(concurrency),
            "--duration", str(duration),
            "--size", str(matrix_size),
            "--output", output_file
        ]
        
        print(f"Running load test: {test_name}")
        print(f"Command: {' '.join(cmd)}")
        
        start_time = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            end_time = time.time()
            
            # Load results from output file
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    test_results = json.load(f)
                test_results['execution_time'] = end_time - start_time
                test_results['test_name'] = test_name
                return test_results
            else:
                print(f"Warning: Output file {output_file} not found")
                return {'error': 'Output file not found'}
                
        except subprocess.CalledProcessError as e:
            print(f"Load test failed: {e.stderr}")
            return {'error': e.stderr}


class EfficiencyComparator:
    def __init__(self, output_dir: str = "test_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def collect_metrics_during_test(self, test_name: str, duration: int, k8s_manager: KubernetesManager) -> List[Dict]:
        """Collect Kubernetes metrics during test"""
        metrics = []
        start_time = time.time()
        
        print(f"Collecting metrics for {test_name}...")
        
        while time.time() - start_time < duration:
            timestamp = time.time()
            
            # Collect deployment metrics
            replicas = k8s_manager.get_deployment_replicas("userscale-app")
            pods = k8s_manager.get_pod_count("userscale-app")
            
            metrics.append({
                'timestamp': timestamp,
                'replicas': replicas,
                'pods_running': pods,
                'test_name': test_name
            })
            
            time.sleep(10)  # Collect metrics every 10 seconds
        
        return metrics
    
    def calculate_efficiency_metrics(self, userscale_results: Dict, hpa_results: Dict, 
                                   userscale_metrics: List[Dict], hpa_metrics: List[Dict]) -> Dict[str, Any]:
        """Calculate efficiency comparison metrics"""
        
        def extract_throughput(results: Dict) -> float:
            if 'metrics' in results and 'throughput_rps' in results['metrics']:
                return results['metrics']['throughput_rps']
            return 0.0
        
        def extract_latency(results: Dict) -> float:
            if 'metrics' in results and 'avg_latency_ms' in results['metrics']:
                return results['metrics']['avg_latency_ms']
            return 0.0
        
        def calculate_avg_replicas(metrics: List[Dict]) -> float:
            if not metrics:
                return 0.0
            return sum(m['replicas'] for m in metrics) / len(metrics)
        
        def calculate_scaling_efficiency(metrics: List[Dict]) -> Dict[str, float]:
            if not metrics:
                return {'scaling_speed': 0.0, 'resource_utilization': 0.0}
            
            # Calculate how quickly scaling responds to load
            replica_changes = []
            for i in range(1, len(metrics)):
                if metrics[i]['replicas'] != metrics[i-1]['replicas']:
                    replica_changes.append(metrics[i]['timestamp'] - metrics[i-1]['timestamp'])
            
            scaling_speed = sum(replica_changes) / len(replica_changes) if replica_changes else 0.0
            
            # Calculate average resource utilization efficiency
            avg_replicas = calculate_avg_replicas(metrics)
            resource_utilization = 1.0 / max(avg_replicas, 1.0)  # Higher replicas = lower efficiency
            
            return {
                'scaling_speed': scaling_speed,
                'resource_utilization': resource_utilization
            }
        
        userscale_throughput = extract_throughput(userscale_results)
        hpa_throughput = extract_throughput(hpa_results)
        
        userscale_latency = extract_latency(userscale_results)
        hpa_latency = extract_latency(hpa_results)
        
        userscale_avg_replicas = calculate_avg_replicas(userscale_metrics)
        hpa_avg_replicas = calculate_avg_replicas(hpa_metrics)
        
        userscale_scaling = calculate_scaling_efficiency(userscale_metrics)
        hpa_scaling = calculate_scaling_efficiency(hpa_metrics)
        
        # Calculate efficiency improvements
        throughput_improvement = ((userscale_throughput - hpa_throughput) / max(hpa_throughput, 0.001)) * 100
        latency_improvement = ((hpa_latency - userscale_latency) / max(hpa_latency, 0.001)) * 100
        resource_efficiency = ((hpa_avg_replicas - userscale_avg_replicas) / max(hpa_avg_replicas, 0.001)) * 100
        
        return {
            'userscale': {
                'throughput_rps': userscale_throughput,
                'avg_latency_ms': userscale_latency,
                'avg_replicas': userscale_avg_replicas,
                'scaling_metrics': userscale_scaling
            },
            'hpa': {
                'throughput_rps': hpa_throughput,
                'avg_latency_ms': hpa_latency,
                'avg_replicas': hpa_avg_replicas,
                'scaling_metrics': hpa_scaling
            },
            'improvements': {
                'throughput_improvement_percent': throughput_improvement,
                'latency_improvement_percent': latency_improvement,
                'resource_efficiency_percent': resource_efficiency
            },
            'summary': {
                'userscale_better_throughput': throughput_improvement > 0,
                'userscale_better_latency': latency_improvement > 0,
                'userscale_more_efficient': resource_efficiency > 0,
                'overall_winner': 'userscale' if (throughput_improvement + latency_improvement + resource_efficiency) > 0 else 'hpa'
            }
        }
    
    def generate_report(self, comparison_results: Dict[str, Any], output_file: str):
        """Generate comprehensive comparison report"""
        
        report = f"""
# Userscale vs HPA Efficiency Comparison Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
The comparison test evaluated the efficiency of Userscale (user-aware scaling) vs HPA (Horizontal Pod Autoscaler) 
under intensive matrix multiplication load with 10,000 elements.

**Overall Winner: {comparison_results['summary']['overall_winner'].upper()}**

## Performance Metrics

### Throughput (Requests per Second)
- **Userscale**: {comparison_results['userscale']['throughput_rps']:.2f} RPS
- **HPA**: {comparison_results['hpa']['throughput_rps']:.2f} RPS
- **Improvement**: {comparison_results['improvements']['throughput_improvement_percent']:.2f}%

### Latency (Average)
- **Userscale**: {comparison_results['userscale']['avg_latency_ms']:.2f} ms
- **HPA**: {comparison_results['hpa']['avg_latency_ms']:.2f} ms
- **Improvement**: {comparison_results['improvements']['latency_improvement_percent']:.2f}%

### Resource Efficiency
- **Userscale Avg Replicas**: {comparison_results['userscale']['avg_replicas']:.2f}
- **HPA Avg Replicas**: {comparison_results['hpa']['avg_replicas']:.2f}
- **Resource Efficiency**: {comparison_results['improvements']['resource_efficiency_percent']:.2f}%

## Scaling Behavior

### Userscale Scaling
- Scaling Speed: {comparison_results['userscale']['scaling_metrics']['scaling_speed']:.2f} seconds
- Resource Utilization: {comparison_results['userscale']['scaling_metrics']['resource_utilization']:.2f}

### HPA Scaling
- Scaling Speed: {comparison_results['hpa']['scaling_metrics']['scaling_speed']:.2f} seconds
- Resource Utilization: {comparison_results['hpa']['scaling_metrics']['resource_utilization']:.2f}

## Key Findings

1. **Throughput**: {'✅ Userscale performs better' if comparison_results['summary']['userscale_better_throughput'] else '❌ HPA performs better'}
2. **Latency**: {'✅ Userscale has lower latency' if comparison_results['summary']['userscale_better_latency'] else '❌ HPA has lower latency'}
3. **Resource Efficiency**: {'✅ Userscale uses fewer resources' if comparison_results['summary']['userscale_more_efficient'] else '❌ HPA uses fewer resources'}

## Recommendations

Based on the test results, {'Userscale' if comparison_results['summary']['overall_winner'] == 'userscale' else 'HPA'} demonstrates superior performance for matrix multiplication workloads with 10,000 elements.

### For Production Deployment:
- Consider {'Userscale' if comparison_results['summary']['overall_winner'] == 'userscale' else 'HPA'} for workloads with:
  - High computational intensity
  - Variable user loads
  - {'User-aware scaling requirements' if comparison_results['summary']['overall_winner'] == 'userscale' else 'Standard resource-based scaling'}

---
*Report generated by Userscale Efficiency Comparison Tool*
"""
        
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"Report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Userscale vs HPA Efficiency Comparison")
    parser.add_argument("--namespace", default="userscale", help="Kubernetes namespace")
    parser.add_argument("--concurrency", type=int, default=20, help="Load test concurrency")
    parser.add_argument("--duration", type=int, default=120, help="Test duration in seconds")
    parser.add_argument("--matrix-size", type=int, default=10000, help="Matrix size (elements)")
    parser.add_argument("--output-dir", default="comparison_results", help="Output directory")
    parser.add_argument("--service-url", help="Service URL (auto-detected if not provided)")
    
    args = parser.parse_args()
    
    # Initialize components
    k8s_manager = KubernetesManager(args.namespace)
    comparator = EfficiencyComparator(args.output_dir)
    
    print("=== Userscale vs HPA Efficiency Comparison ===")
    print(f"Test Configuration:")
    print(f"  Namespace: {args.namespace}")
    print(f"  Concurrency: {args.concurrency}")
    print(f"  Duration: {args.duration} seconds")
    print(f"  Matrix Size: {args.matrix_size} elements")
    print(f"  Output Directory: {args.output_dir}")
    
    # Get service URL
    if args.service_url:
        service_url = args.service_url
    else:
        service_url = k8s_manager.get_service_url("userscale-app")
    
    print(f"  Service URL: {service_url}")
    
    # Initialize load test runner
    load_runner = LoadTestRunner(service_url, args.output_dir)
    
    try:
        # Test 1: Userscale
        print("\n=== Phase 1: Testing with Userscale ===")
        
        # Apply userscale configuration
        k8s_manager.delete_config("k8s/hpa.yaml")  # Remove HPA if exists
        k8s_manager.apply_config("k8s/scaler.yaml")  # Apply userscale
        time.sleep(30)  # Wait for userscale to start
        
        # Run load test with userscale
        userscale_results = load_runner.run_load_test(
            "userscale", args.concurrency, args.duration, args.matrix_size
        )
        
        # Collect metrics during userscale test
        userscale_metrics = comparator.collect_metrics_during_test(
            "userscale", args.duration, k8s_manager
        )
        
        # Test 2: HPA
        print("\n=== Phase 2: Testing with HPA ===")
        
        # Apply HPA configuration
        k8s_manager.delete_config("k8s/scaler.yaml")  # Remove userscale
        k8s_manager.apply_config("k8s/hpa.yaml")  # Apply HPA
        time.sleep(30)  # Wait for HPA to be ready
        
        # Run load test with HPA
        hpa_results = load_runner.run_load_test(
            "hpa", args.concurrency, args.duration, args.matrix_size
        )
        
        # Collect metrics during HPA test
        hpa_metrics = comparator.collect_metrics_during_test(
            "hpa", args.duration, k8s_manager
        )
        
        # Compare results
        print("\n=== Phase 3: Analysis ===")
        comparison_results = comparator.calculate_efficiency_metrics(
            userscale_results, hpa_results, userscale_metrics, hpa_metrics
        )
        
        # Generate report
        report_file = os.path.join(args.output_dir, "efficiency_comparison_report.md")
        comparator.generate_report(comparison_results, report_file)
        
        # Save detailed results
        detailed_results = {
            'test_configuration': {
                'namespace': args.namespace,
                'concurrency': args.concurrency,
                'duration': args.duration,
                'matrix_size': args.matrix_size
            },
            'userscale_results': userscale_results,
            'hpa_results': hpa_results,
            'userscale_metrics': userscale_metrics,
            'hpa_metrics': hpa_metrics,
            'comparison_results': comparison_results
        }
        
        results_file = os.path.join(args.output_dir, "detailed_results.json")
        with open(results_file, 'w') as f:
            json.dump(detailed_results, f, indent=2)
        
        print(f"\n=== Comparison Complete ===")
        print(f"Report: {report_file}")
        print(f"Detailed Results: {results_file}")
        
        # Print summary
        print(f"\n=== SUMMARY ===")
        print(f"Overall Winner: {comparison_results['summary']['overall_winner'].upper()}")
        print(f"Throughput Improvement: {comparison_results['improvements']['throughput_improvement_percent']:.2f}%")
        print(f"Latency Improvement: {comparison_results['improvements']['latency_improvement_percent']:.2f}%")
        print(f"Resource Efficiency: {comparison_results['improvements']['resource_efficiency_percent']:.2f}%")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\n=== Cleanup ===")
        k8s_manager.delete_config("k8s/hpa.yaml")
        k8s_manager.delete_config("k8s/scaler.yaml")


if __name__ == "__main__":
    main()
