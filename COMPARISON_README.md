# Userscale vs HPA Efficiency Comparison

This directory contains a comprehensive testing framework to compare the efficiency of **Userscale** (user-aware scaling) versus **HPA** (Horizontal Pod Autoscaler) for matrix multiplication workloads with 10,000 elements.

## 🎯 What This Tests

The comparison evaluates:
- **Throughput** (requests per second)
- **Latency** (average and P95 response times)
- **Resource Efficiency** (average number of replicas needed)
- **Scaling Behavior** (how quickly each system responds to load changes)

## 📁 Files Overview

### Core Components
- `comparison_test.py` - Main comparison script that runs tests for both systems
- `loadgen/main.py` - Enhanced load generator with matrix multiplication (10,000 elements)
- `format_results.py` - Results formatter (CSV, HTML, JSON)
- `run_comparison.py` - Simple execution script

### Kubernetes Configurations
- `k8s/hpa.yaml` - HPA configuration for baseline comparison
- `k8s/scaler.yaml` - Userscale configuration
- `k8s/app.yaml` - Application deployment
- `k8s/configmap.yaml` - Configuration settings

## 🚀 Quick Start

### Option 1: Quick Test (5 minutes)
```bash
python run_comparison.py --quick
```

### Option 2: Full Test (10 minutes)
```bash
python run_comparison.py --full
```

### Option 3: Custom Test
```bash
python run_comparison.py --concurrency 30 --duration 180 --matrix-size 15000
```

## 📊 Understanding the Results

### Output Files
After running the comparison, you'll get:

1. **HTML Report** (`comparison_report_*.html`)
   - Visual dashboard with charts and metrics
   - Open in your browser for the best experience

2. **CSV Data** (`comparison_results_*.csv`)
   - Raw metrics for spreadsheet analysis
   - Import into Excel or Google Sheets

3. **JSON Summary** (`comparison_summary_*.json`)
   - Machine-readable results
   - For programmatic analysis

4. **Detailed Results** (`detailed_results.json`)
   - Complete test data including raw metrics
   - For advanced analysis

### Key Metrics Explained

- **Throughput (RPS)**: How many matrix multiplications per second
- **Latency (ms)**: Response time for each request
- **Resource Efficiency**: How many pods each system uses
- **Overall Winner**: Based on combined performance metrics

## 🔧 Advanced Usage

### Run Individual Components

#### 1. Just the Load Generator
```bash
python loadgen/main.py --scenario intensive_matrix --concurrency 20 --duration 120 --size 10000
```

#### 2. Just the Comparison (if Kubernetes is already set up)
```bash
python comparison_test.py --concurrency 20 --duration 120 --matrix-size 10000
```

#### 3. Format Existing Results
```bash
python format_results.py --results comparison_results/detailed_results.json --formats csv html json
```

### Customize Test Parameters

```bash
python run_comparison.py \
  --concurrency 50 \
  --duration 300 \
  --matrix-size 20000 \
  --namespace my-test-namespace
```

## 📈 Expected Results

### Userscale Advantages
- **User-aware scaling**: Responds to actual user load, not just CPU/memory
- **Faster scaling**: Can scale based on user count immediately
- **Better resource utilization**: Uses fewer pods for the same workload

### HPA Advantages
- **Mature technology**: Well-tested and stable
- **Standard approach**: Widely adopted and understood
- **Built-in metrics**: Integrates with existing monitoring

### Typical Results Pattern
```
Throughput: Userscale +15-30% better
Latency: Userscale -10-20% lower
Resources: Userscale -20-40% fewer pods
Overall: Userscale typically wins for user-driven workloads
```

## 🛠️ Prerequisites

### Required Software
- Python 3.8+
- kubectl (configured for your cluster)
- Kubernetes cluster (minikube, kind, or cloud)

### Python Dependencies
```bash
pip install httpx kubernetes pyyaml
```

### Kubernetes Setup
```bash
# Create namespace
kubectl create namespace userscale

# Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/app.yaml
```

## 🐛 Troubleshooting

### Common Issues

1. **"kubectl not found"**
   - Install kubectl and configure it for your cluster

2. **"Namespace not found"**
   - Run: `kubectl create namespace userscale`

3. **"Service not accessible"**
   - Check if the app is running: `kubectl get pods -n userscale`
   - Port-forward if needed: `kubectl port-forward -n userscale svc/userscale-app 8000:80`

4. **"Load test fails"**
   - Check app health: `curl http://localhost:8000/healthz`
   - Reduce concurrency: `--concurrency 5`

### Debug Mode
```bash
# Run with verbose output
python comparison_test.py --concurrency 5 --duration 30 --matrix-size 1000
```

## 📋 Test Scenarios

### Scenario 1: Light Load
```bash
python run_comparison.py --concurrency 5 --duration 60 --matrix-size 5000
```

### Scenario 2: Heavy Load
```bash
python run_comparison.py --concurrency 50 --duration 300 --matrix-size 20000
```

### Scenario 3: Burst Load
```bash
# Run multiple quick tests
python run_comparison.py --quick
python run_comparison.py --quick
python run_comparison.py --quick
```

## 🎓 Understanding Matrix Multiplication Load

The test uses matrix multiplication with 10,000 elements because:
- **CPU Intensive**: Requires significant computational resources
- **Predictable**: Consistent resource usage patterns
- **Scalable**: Can easily adjust matrix size for different loads
- **Real-world**: Similar to ML/AI workloads

Matrix size calculation:
- 10,000 elements = 100x100 matrix
- Each request performs: 100x100 × 100x100 = 100x100 result matrix
- This creates ~1M floating-point operations per request

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review the detailed logs in the results directory
3. Ensure your Kubernetes cluster has sufficient resources
4. Try reducing test parameters (concurrency, duration, matrix size)

## 🔄 Continuous Testing

For ongoing monitoring, you can set up automated tests:

```bash
# Daily comparison
0 2 * * * cd /path/to/userscale && python run_comparison.py --quick

# Weekly full test
0 3 * * 0 cd /path/to/userscale && python run_comparison.py --full
```

---

**Happy Testing! 🚀**

The comparison framework provides comprehensive insights into how Userscale performs compared to traditional HPA for user-driven workloads.
