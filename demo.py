#!/usr/bin/env python3
"""
Automated demo script for Userscale vs HPA comparison
"""

import subprocess
import time
import os
import sys
from datetime import datetime


def print_banner(title: str):
    """Print a formatted banner"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_command(cmd: str, description: str = "", check: bool = True):
    """Run a command and display results"""
    if description:
        print(f"\n{description}")
    
    print(f"Command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("SUCCESS")
        if result.stdout.strip():
            print(f"Output:\n{result.stdout}")
    else:
        print("FAILED")
        if result.stderr.strip():
            print(f"Error:\n{result.stderr}")
        if check:
            sys.exit(1)
    
    return result.returncode == 0


def check_prerequisites():
    """Check if all prerequisites are available"""
    print_banner("Checking Prerequisites")
    
    # Check kubectl
    if not run_command("kubectl version --client", "Checking kubectl", check=False):
        print("ERROR: kubectl not found. Please install kubectl.")
        return False
    
    # Check Docker
    if not run_command("docker --version", "Checking Docker", check=False):
        print("ERROR: Docker not found. Please install Docker.")
        return False
    
    # Check Python
    if not run_command("python --version", "Checking Python", check=False):
        print("ERROR: Python not found. Please install Python.")
        return False
    
    # Check Kubernetes cluster
    if not run_command("kubectl cluster-info", "Checking Kubernetes cluster", check=False):
        print("ERROR: Kubernetes cluster not accessible. Please start your cluster.")
        return False
    
    print("All prerequisites are available!")
    return True


def build_images():
    """Build Docker images"""
    print_banner("Building Docker Images")
    
    # Build app image
    run_command(
        "docker build -f Dockerfile.app -t userscale-app:local .",
        "Building userscale-app image"
    )
    
    # Build scaler image
    run_command(
        "docker build -f Dockerfile.scaler -t userscale-scaler:local .",
        "Building userscale-scaler image"
    )


def deploy_kubernetes():
    """Deploy Kubernetes components"""
    print_banner("Deploying Kubernetes Components")
    
    # Apply manifests
    manifests = [
        "k8s/namespace.yaml",
        "k8s/configmap.yaml",
        "k8s/rbac.yaml",
        "k8s/app.yaml"
    ]
    
    for manifest in manifests:
        run_command(f"kubectl apply -f {manifest}", f"Applying {manifest}")
    
    # Wait for app to be ready
    run_command(
        "kubectl wait --for=condition=available --timeout=300s deployment/userscale-app -n userscale",
        "Waiting for app deployment"
    )


def run_comparison_test():
    """Run the comparison test"""
    print_banner("Running Comparison Test")
    
    # Run the working comparison test
    run_command(
        "python working_comparison_test.py --duration 60 --namespace userscale",
        "Running Userscale vs HPA comparison test"
    )


def show_results():
    """Show the results"""
    print_banner("Test Results")
    
    # Find the latest results directory
    result_dirs = [d for d in os.listdir('.') if d.startswith('comparison_results_')]
    if not result_dirs:
        print("No results found!")
        return
    
    latest_dir = max(result_dirs)
    print(f"Results directory: {latest_dir}")
    
    # Show available files
    files = os.listdir(latest_dir)
    print(f"Available files: {', '.join(files)}")
    
    # Show summary
    summary_file = os.path.join(latest_dir, "comparison_summary_*.json")
    summary_files = [f for f in files if f.startswith("comparison_summary_")]
    if summary_files:
        summary_file = os.path.join(latest_dir, summary_files[0])
        print(f"\nSummary file: {summary_file}")
        
        # Read and display summary
        try:
            import json
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            print("\n=== COMPARISON RESULTS ===")
            print(f"Test Duration: {summary.get('test_duration', 'N/A')} seconds")
            print(f"Concurrency: {summary.get('concurrency', 'N/A')}")
            print(f"Matrix Size: {summary.get('matrix_size', 'N/A')}")
            
            print("\n=== PERFORMANCE METRICS ===")
            userscale = summary.get('userscale', {})
            hpa = summary.get('hpa', {})
            
            print(f"Userscale - Throughput: {userscale.get('throughput_rps', 0):.2f} RPS, Latency: {userscale.get('avg_latency_ms', 0):.1f}ms")
            print(f"HPA        - Throughput: {hpa.get('throughput_rps', 0):.2f} RPS, Latency: {hpa.get('avg_latency_ms', 0):.1f}ms")
            
            improvements = summary.get('improvements', {})
            print(f"\n=== IMPROVEMENTS ===")
            print(f"Throughput: {improvements.get('throughput_improvement_percent', 0):+.2f}%")
            print(f"Latency: {improvements.get('latency_improvement_percent', 0):+.2f}%")
            print(f"Resource Efficiency: {improvements.get('resource_efficiency_percent', 0):+.2f}%")
            
            winner = summary.get('overall_winner', 'Unknown')
            print(f"\nOverall Winner: {winner.upper()}")
            
        except Exception as e:
            print(f"Error reading summary: {e}")
    
    # Show HTML report
    html_files = [f for f in files if f.endswith('.html')]
    if html_files:
        html_file = os.path.join(latest_dir, html_files[0])
        print(f"\nHTML Report: {html_file}")
        print("Open this file in your browser to view the detailed report with charts.")


def cleanup():
    """Cleanup resources"""
    print_banner("Cleaning Up")
    
    # Delete namespace (this will clean up everything)
    run_command(
        "kubectl delete namespace userscale",
        "Cleaning up Kubernetes resources",
        check=False
    )
    
    print("Cleanup complete!")


def main():
    """Main demo function"""
    print_banner("Userscale vs HPA Autoscaling Demo")
    
    print("""
This demo will:
1. Check prerequisites (kubectl, Docker, Python, Kubernetes cluster)
2. Build Docker images for the application and scaler
3. Deploy Kubernetes components
4. Run a comparison test between Userscale and HPA
5. Show the results
6. Clean up resources

The test will run for 60 seconds per scaling mechanism and compare:
- Throughput (requests per second)
- Latency (average response time)
- Resource efficiency (replica usage)
- Overall performance
""")
    
    try:
        # Step 1: Check prerequisites
        if not check_prerequisites():
            print("Prerequisites check failed. Please fix the issues and try again.")
            return
        
        # Step 2: Build images
        build_images()
        
        # Step 3: Deploy Kubernetes
        deploy_kubernetes()
        
        # Step 4: Run comparison test
        run_comparison_test()
        
        # Step 5: Show results
        show_results()
        
        # Step 6: Ask about cleanup
        print_banner("Demo Complete")
        print("Demo completed successfully!")
        print("\nResults are available in the comparison_results_* directory.")
        print("You can view the HTML report in your browser for detailed charts.")
        
        cleanup_choice = input("\nDo you want to clean up the Kubernetes resources? (y/n): ").lower().strip()
        if cleanup_choice in ['y', 'yes']:
            cleanup()
        else:
            print("Resources left running. You can clean them up later with:")
            print("kubectl delete namespace userscale")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        cleanup_choice = input("Do you want to clean up resources? (y/n): ").lower().strip()
        if cleanup_choice in ['y', 'yes']:
            cleanup()
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        cleanup_choice = input("Do you want to clean up resources? (y/n): ").lower().strip()
        if cleanup_choice in ['y', 'yes']:
            cleanup()


if __name__ == "__main__":
    main()
