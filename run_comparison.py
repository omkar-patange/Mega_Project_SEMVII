#!/usr/bin/env python3
"""
Quick execution script for Userscale vs HPA comparison

This script provides a simple interface to run the complete comparison test
and automatically format the results.
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Success!")
        if result.stdout:
            print("Output:", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {e}")
        if e.stderr:
            print("Error:", e.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Run Userscale vs HPA Efficiency Comparison")
    parser.add_argument("--quick", action="store_true", help="Run quick test (60s duration, 10 concurrency)")
    parser.add_argument("--full", action="store_true", help="Run full test (120s duration, 20 concurrency)")
    parser.add_argument("--concurrency", type=int, default=20, help="Number of concurrent workers")
    parser.add_argument("--duration", type=int, default=120, help="Test duration in seconds")
    parser.add_argument("--matrix-size", type=int, default=10000, help="Matrix size (elements)")
    parser.add_argument("--namespace", default="userscale", help="Kubernetes namespace")
    parser.add_argument("--skip-k8s-setup", action="store_true", help="Skip Kubernetes setup (for testing)")
    
    args = parser.parse_args()
    
    # Set quick test parameters
    if args.quick:
        args.concurrency = 10
        args.duration = 60
        print("🏃 Quick test mode: 60s duration, 10 concurrency")
    elif args.full:
        args.concurrency = 20
        args.duration = 120
        print("🏋️ Full test mode: 120s duration, 20 concurrency")
    
    print(f"\n🎯 Test Configuration:")
    print(f"   Duration: {args.duration} seconds")
    print(f"   Concurrency: {args.concurrency} workers")
    print(f"   Matrix Size: {args.matrix_size} elements")
    print(f"   Namespace: {args.namespace}")
    
    # Create results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = f"comparison_results_{timestamp}"
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"   Results Directory: {results_dir}")
    
    # Check if we're in the right directory
    if not os.path.exists("comparison_test.py"):
        print("❌ Error: comparison_test.py not found. Please run from the project root directory.")
        sys.exit(1)
    
    # Step 1: Run the comparison test
    comparison_cmd = [
        "python", "comparison_test.py",
        "--namespace", args.namespace,
        "--concurrency", str(args.concurrency),
        "--duration", str(args.duration),
        "--matrix-size", str(args.matrix_size),
        "--output-dir", results_dir
    ]
    
    if args.skip_k8s_setup:
        comparison_cmd.append("--skip-k8s-setup")
    
    if not run_command(comparison_cmd, "Running Userscale vs HPA Comparison Test"):
        print("❌ Comparison test failed. Check the error messages above.")
        sys.exit(1)
    
    # Step 2: Format the results
    detailed_results_file = os.path.join(results_dir, "detailed_results.json")
    
    if os.path.exists(detailed_results_file):
        format_cmd = [
            "python", "format_results.py",
            "--results", detailed_results_file,
            "--output-dir", results_dir,
            "--formats", "csv", "html", "json"
        ]
        
        if not run_command(format_cmd, "Formatting Results"):
            print("⚠️  Results formatting failed, but raw results are available.")
    
    # Step 3: Show summary
    print(f"\n{'='*60}")
    print(f"🎉 COMPARISON COMPLETE!")
    print(f"{'='*60}")
    
    print(f"\n📁 Results saved to: {results_dir}/")
    print(f"📊 Files generated:")
    
    files_to_check = [
        ("detailed_results.json", "Detailed comparison data"),
        ("efficiency_comparison_report.md", "Markdown report"),
        ("comparison_report_", "HTML report"),
        ("comparison_results_", "CSV data"),
        ("comparison_summary_", "JSON summary")
    ]
    
    for file_pattern, description in files_to_check:
        matching_files = [f for f in os.listdir(results_dir) if f.startswith(file_pattern)]
        if matching_files:
            print(f"   ✅ {description}: {matching_files[0]}")
        else:
            print(f"   ❌ {description}: Not found")
    
    # Try to show the markdown report summary
    markdown_report = os.path.join(results_dir, "efficiency_comparison_report.md")
    if os.path.exists(markdown_report):
        print(f"\n📖 Quick Summary from Report:")
        try:
            with open(markdown_report, 'r') as f:
                lines = f.readlines()
                # Find and show key lines
                for i, line in enumerate(lines):
                    if "Overall Winner:" in line:
                        print(f"   {line.strip()}")
                    elif "Throughput Improvement:" in line:
                        print(f"   {line.strip()}")
                    elif "Latency Improvement:" in line:
                        print(f"   {line.strip()}")
                    elif "Resource Efficiency:" in line:
                        print(f"   {line.strip()}")
        except Exception as e:
            print(f"   Could not read summary: {e}")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Open {results_dir}/comparison_report_*.html in your browser for a visual report")
    print(f"   2. Import {results_dir}/comparison_results_*.csv into Excel/Google Sheets")
    print(f"   3. Review {results_dir}/detailed_results.json for complete data")
    
    print(f"\n🏁 Done! Check the {results_dir}/ directory for all results.")


if __name__ == "__main__":
    main()
