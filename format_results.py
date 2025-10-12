#!/usr/bin/env python3
"""
Results Formatter for Userscale vs HPA Comparison

This script formats and visualizes the comparison results in various formats:
- CSV for spreadsheet analysis
- HTML for web viewing
- JSON for programmatic access
"""

import json
import csv
import argparse
import os
import glob
from datetime import datetime
from typing import Dict, List, Any


class ResultsFormatter:
    def __init__(self, results_file: str):
        self.results_file = results_file
        self.data = self._load_results()
    
    def _load_results(self) -> Dict[str, Any]:
        """Load results from JSON file"""
        # Handle wildcard patterns in file path
        if '*' in self.results_file:
            matching_files = glob.glob(self.results_file)
            if not matching_files:
                print(f"No files found matching pattern: {self.results_file}")
                return {}
            # Use the most recent file if multiple matches
            self.results_file = max(matching_files, key=os.path.getmtime)
            print(f"Using results file: {self.results_file}")
        
        try:
            with open(self.results_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Results file {self.results_file} not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return {}
    
    def format_csv(self, output_file: str):
        """Format results as CSV"""
        if not self.data:
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Metric', 'Userscale', 'HPA', 'Improvement (%)', 'Winner'
            ])
            
            # Write comparison data
            comparison = self.data.get('comparison_results', {})
            
            # Throughput
            us_throughput = comparison.get('userscale', {}).get('throughput_rps', 0)
            hpa_throughput = comparison.get('hpa', {}).get('throughput_rps', 0)
            throughput_improvement = comparison.get('improvements', {}).get('throughput_improvement_percent', 0)
            throughput_winner = 'Userscale' if throughput_improvement > 0 else 'HPA'
            
            writer.writerow([
                'Throughput (RPS)', 
                f"{us_throughput:.2f}", 
                f"{hpa_throughput:.2f}", 
                f"{throughput_improvement:.2f}",
                throughput_winner
            ])
            
            # Latency
            us_latency = comparison.get('userscale', {}).get('avg_latency_ms', 0)
            hpa_latency = comparison.get('hpa', {}).get('avg_latency_ms', 0)
            latency_improvement = comparison.get('improvements', {}).get('latency_improvement_percent', 0)
            latency_winner = 'Userscale' if latency_improvement > 0 else 'HPA'
            
            writer.writerow([
                'Avg Latency (ms)', 
                f"{us_latency:.2f}", 
                f"{hpa_latency:.2f}", 
                f"{latency_improvement:.2f}",
                latency_winner
            ])
            
            # Resource Efficiency
            us_replicas = comparison.get('userscale', {}).get('avg_replicas', 0)
            hpa_replicas = comparison.get('hpa', {}).get('avg_replicas', 0)
            resource_improvement = comparison.get('improvements', {}).get('resource_efficiency_percent', 0)
            resource_winner = 'Userscale' if resource_improvement > 0 else 'HPA'
            
            writer.writerow([
                'Avg Replicas', 
                f"{us_replicas:.2f}", 
                f"{hpa_replicas:.2f}", 
                f"{resource_improvement:.2f}",
                resource_winner
            ])
            
            # Overall Winner
            overall_winner = comparison.get('summary', {}).get('overall_winner', 'Unknown')
            writer.writerow(['Overall Winner', overall_winner, '', '', overall_winner])
        
        print(f"CSV results saved to: {output_file}")
    
    def format_html(self, output_file: str):
        """Format results as HTML report"""
        if not self.data:
            return
        
        comparison = self.data.get('comparison_results', {})
        config = self.data.get('test_configuration', {})
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Userscale vs HPA Efficiency Comparison</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #333; margin-bottom: 10px; }}
        .header p {{ color: #666; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric-card {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .metric-title {{ font-weight: bold; color: #333; margin-bottom: 10px; }}
        .metric-value {{ font-size: 24px; color: #007bff; margin-bottom: 5px; }}
        .metric-improvement {{ color: #28a745; font-weight: bold; }}
        .metric-decline {{ color: #dc3545; font-weight: bold; }}
        .winner-badge {{ display: inline-block; background-color: #28a745; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: bold; }}
        .loser-badge {{ display: inline-block; background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: bold; }}
        .summary {{ background-color: #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .summary h2 {{ color: #333; margin-bottom: 15px; }}
        .config-table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
        .config-table th, .config-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        .config-table th {{ background-color: #f8f9fa; }}
        .chart-container {{ margin: 20px 0; }}
        .bar-chart {{ display: flex; align-items: end; height: 200px; gap: 10px; }}
        .bar {{ display: flex; flex-direction: column; align-items: center; }}
        .bar-fill {{ background-color: #007bff; margin-bottom: 5px; border-radius: 4px 4px 0 0; min-height: 20px; }}
        .bar-label {{ font-size: 12px; }}
        .bar-value {{ font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1> Userscale vs HPA Efficiency Comparison</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="summary">
            <h2> Executive Summary</h2>
            <p><strong>Overall Winner:</strong> <span class="winner-badge">{comparison.get('summary', {}).get('overall_winner', 'Unknown').upper()}</span></p>
            <p>This comparison evaluates the efficiency of Userscale (user-aware scaling) vs HPA (Horizontal Pod Autoscaler) under intensive matrix multiplication load with {config.get('matrix_size', 'N/A')} elements.</p>
        </div>
        
        <h2> Test Configuration</h2>
        <table class="config-table">
            <tr><th>Parameter</th><th>Value</th></tr>
            <tr><td>Namespace</td><td>{config.get('namespace', 'N/A')}</td></tr>
            <tr><td>Concurrency</td><td>{config.get('concurrency', 'N/A')} workers</td></tr>
            <tr><td>Duration</td><td>{config.get('duration', 'N/A')} seconds</td></tr>
            <tr><td>Matrix Size</td><td>{config.get('matrix_size', 'N/A')} elements</td></tr>
        </table>
        
        <h2> Performance Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">Throughput (RPS)</div>
                <div class="metric-value">{comparison.get('userscale', {}).get('throughput_rps', 0):.2f}</div>
                <div class="metric-improvement">
                    {comparison.get('improvements', {}).get('throughput_improvement_percent', 0):+.2f}% vs HPA
                </div>
                <div style="margin-top: 10px;">
                    {'<span class="winner-badge">Winner</span>' if comparison.get('improvements', {}).get('throughput_improvement_percent', 0) > 0 else '<span class="loser-badge">Behind</span>'}
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">Average Latency (ms)</div>
                <div class="metric-value">{comparison.get('userscale', {}).get('avg_latency_ms', 0):.2f}</div>
                <div class="metric-improvement">
                    {comparison.get('improvements', {}).get('latency_improvement_percent', 0):+.2f}% vs HPA
                </div>
                <div style="margin-top: 10px;">
                    {'<span class="winner-badge">Winner</span>' if comparison.get('improvements', {}).get('latency_improvement_percent', 0) > 0 else '<span class="loser-badge">Behind</span>'}
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">Average Replicas</div>
                <div class="metric-value">{comparison.get('userscale', {}).get('avg_replicas', 0):.2f}</div>
                <div class="metric-improvement">
                    {comparison.get('improvements', {}).get('resource_efficiency_percent', 0):+.2f}% vs HPA
                </div>
                <div style="margin-top: 10px;">
                    {'<span class="winner-badge">Winner</span>' if comparison.get('improvements', {}).get('resource_efficiency_percent', 0) > 0 else '<span class="loser-badge">Behind</span>'}
                </div>
            </div>
        </div>
        
        <h2> Detailed Comparison</h2>
        <table class="config-table">
            <tr><th>Metric</th><th>Userscale</th><th>HPA</th><th>Improvement</th><th>Winner</th></tr>
            <tr>
                <td>Throughput (RPS)</td>
                <td>{comparison.get('userscale', {}).get('throughput_rps', 0):.2f}</td>
                <td>{comparison.get('hpa', {}).get('throughput_rps', 0):.2f}</td>
                <td>{comparison.get('improvements', {}).get('throughput_improvement_percent', 0):+.2f}%</td>
                <td>{'Userscale' if comparison.get('improvements', {}).get('throughput_improvement_percent', 0) > 0 else 'HPA'}</td>
            </tr>
            <tr>
                <td>Avg Latency (ms)</td>
                <td>{comparison.get('userscale', {}).get('avg_latency_ms', 0):.2f}</td>
                <td>{comparison.get('hpa', {}).get('avg_latency_ms', 0):.2f}</td>
                <td>{comparison.get('improvements', {}).get('latency_improvement_percent', 0):+.2f}%</td>
                <td>{'Userscale' if comparison.get('improvements', {}).get('latency_improvement_percent', 0) > 0 else 'HPA'}</td>
            </tr>
            <tr>
                <td>Avg Replicas</td>
                <td>{comparison.get('userscale', {}).get('avg_replicas', 0):.2f}</td>
                <td>{comparison.get('hpa', {}).get('avg_replicas', 0):.2f}</td>
                <td>{comparison.get('improvements', {}).get('resource_efficiency_percent', 0):+.2f}%</td>
                <td>{'Userscale' if comparison.get('improvements', {}).get('resource_efficiency_percent', 0) > 0 else 'HPA'}</td>
            </tr>
        </table>
        
        <h2> Key Findings</h2>
        <ul>
            <li><strong>Throughput:</strong> {'✅ Userscale delivers better throughput' if comparison.get('summary', {}).get('userscale_better_throughput', False) else '❌ HPA delivers better throughput'}</li>
            <li><strong>Latency:</strong> {'✅ Userscale provides lower latency' if comparison.get('summary', {}).get('userscale_better_latency', False) else '❌ HPA provides lower latency'}</li>
            <li><strong>Resource Efficiency:</strong> {'✅ Userscale uses resources more efficiently' if comparison.get('summary', {}).get('userscale_more_efficient', False) else '❌ HPA uses resources more efficiently'}</li>
        </ul>
        
        <h2> Recommendations</h2>
        <p>Based on the test results, <strong>{comparison.get('summary', {}).get('overall_winner', 'Unknown')}</strong> demonstrates superior performance for matrix multiplication workloads with {config.get('matrix_size', 'N/A')} elements.</p>
        
        <div style="margin-top: 40px; padding: 20px; background-color: #f8f9fa; border-radius: 8px; text-align: center; color: #666;">
            <p>Report generated by Userscale Efficiency Comparison Tool</p>
            <p>For more details, see the detailed JSON results file.</p>
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML report saved to: {output_file}")
    
    def format_json_summary(self, output_file: str):
        """Format a summary JSON with key metrics"""
        if not self.data:
            return
        
        summary = {
            'test_info': {
                'timestamp': datetime.now().isoformat(),
                'configuration': self.data.get('test_configuration', {}),
            },
            'performance_summary': self.data.get('comparison_results', {}),
            'key_metrics': {
                'overall_winner': self.data.get('comparison_results', {}).get('summary', {}).get('overall_winner', 'Unknown'),
                'throughput_improvement': self.data.get('comparison_results', {}).get('improvements', {}).get('throughput_improvement_percent', 0),
                'latency_improvement': self.data.get('comparison_results', {}).get('improvements', {}).get('latency_improvement_percent', 0),
                'resource_efficiency': self.data.get('comparison_results', {}).get('improvements', {}).get('resource_efficiency_percent', 0)
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        print(f"JSON summary saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Format comparison results")
    parser.add_argument("--results", required=True, help="Path to detailed results JSON file")
    parser.add_argument("--output-dir", default="formatted_results", help="Output directory for formatted files")
    parser.add_argument("--formats", nargs="+", choices=["csv", "html", "json"], 
                       default=["csv", "html", "json"], help="Output formats to generate")
    
    args = parser.parse_args()
    
    # Handle wildcard patterns in output directory
    if '*' in args.output_dir:
        # Replace wildcard with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = args.output_dir.replace('*', timestamp)
        print(f"Using timestamp-based output directory: {args.output_dir}")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize formatter
    formatter = ResultsFormatter(args.results)
    
    if not formatter.data:
        print("No data to format. Exiting.")
        return
    
    # Generate requested formats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if "csv" in args.formats:
        csv_file = os.path.join(args.output_dir, f"comparison_results_{timestamp}.csv")
        formatter.format_csv(csv_file)
    
    if "html" in args.formats:
        html_file = os.path.join(args.output_dir, f"comparison_report_{timestamp}.html")
        formatter.format_html(html_file)
    
    if "json" in args.formats:
        json_file = os.path.join(args.output_dir, f"comparison_summary_{timestamp}.json")
        formatter.format_json_summary(json_file)
    
    print(f"\nAll formatted results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
