# Kubernetes Autoscaling Comparison: Userscale vs HPA

A comprehensive comparison between Traditional Horizontal Pod Autoscaler (HPA) and Custom Userscale autoscaling system for Kubernetes applications.

## 🎯 Project Overview

This project demonstrates a custom autoscaling solution called **Userscale** that outperforms traditional HPA in resource efficiency while maintaining competitive performance. Userscale uses intelligent multi-metric scaling based on active users, CPU utilization, latency, and GPU usage.

## 🏆 Key Results

- **Resource Efficiency**: Userscale is **130% more efficient** than HPA
- **Dynamic Scaling**: Intelligent scaling from 1 → 2 → 4 → 3 → 2 → 4 replicas
- **Cost Optimization**: Uses 57% fewer resources (2.6 avg replicas vs 6.0)
- **Multi-metric Intelligence**: Scales based on users, CPU, latency, and GPU
- **Fast Response**: 3-second sync period for rapid scaling decisions

## 📁 Project Structure

```
Mega_Project_SEMVII/
├── app/                          # FastAPI application
│   ├── Dockerfile               # App container image
│   ├── main.py                  # Main application with GPU support
│   └── requirements.txt         # App dependencies
├── scaler/                      # Custom Userscale autoscaler
│   ├── main.py                  # Scaler logic with EWMA smoothing
│   └── requirements.txt         # Scaler dependencies
├── k8s/                         # Kubernetes manifests
│   ├── namespace.yaml           # Project namespace
│   ├── rbac.yaml               # Role-based access control
│   ├── configmap.yaml          # Configuration parameters
│   ├── app.yaml                # Application deployment
│   ├── scaler.yaml             # Userscale deployment
│   └── hpa.yaml                # Traditional HPA configuration
├── loadgen/                     # Load generation utilities
│   └── main.py                 # Load testing framework
├── monitoring/                  # Monitoring configuration
│   ├── prometheus.yml          # Prometheus configuration
│   └── grafana-dashboard.json  # Grafana dashboard
├── demo.py                     # Automated demo script
├── command.txt                 # Complete command history
├── requirements.txt            # Main project dependencies
├── PROJECT_SUMMARY.md          # Detailed project summary
└── README.md                   # This file
```

## 🚀 Quick Start

### Prerequisites

- Kubernetes cluster (minikube, kind, or cloud provider)
- Docker
- kubectl configured
- Python 3.8+

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Mega_Project_SEMVII
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the automated demo**
   ```bash
   python demo.py
   ```

### Manual Setup

1. **Deploy the application**
   ```bash
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/rbac.yaml
   kubectl apply -f k8s/configmap.yaml
   kubectl apply -f k8s/app.yaml
   ```

2. **Deploy Userscale autoscaler**
   ```bash
   kubectl apply -f k8s/scaler.yaml
   ```

3. **Deploy HPA for comparison**
   ```bash
   kubectl apply -f k8s/hpa.yaml
   ```

## 🔧 Configuration

### Userscale Configuration

Key parameters in `k8s/configmap.yaml`:

```yaml
USERS_TARGET_PER_POD: "1"       # Users per pod threshold
CPU_TARGET: "10"                # CPU utilization threshold (%)
LATENCY_TARGET_MS: "50"         # Latency threshold (ms)
SCALE_UP_STEP: "5"              # Replicas to add per scale-up
COOLDOWN_PERIOD: "5"            # Cooldown between scaling (s)
SYNC_PERIOD: "3"                # Metrics check interval (s)
```

### HPA Configuration

Traditional HPA settings in `k8s/hpa.yaml`:

```yaml
minReplicas: 1
maxReplicas: 20
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 80
```

## 📊 Performance Comparison

| Metric | Userscale | HPA | Winner |
|--------|-----------|-----|--------|
| **Resource Efficiency** | 2.6 avg replicas | 6.0 avg replicas | 🏆 Userscale |
| **Scaling Behavior** | Dynamic (1→2→4→3→2→4) | Static (6→6→6) | 🏆 Userscale |
| **Success Rate** | 89.7% | 100% | 🏆 HPA |
| **Throughput** | 3.83 RPS | 4.75 RPS | 🏆 HPA |
| **Latency** | 6161ms | 5166ms | 🏆 HPA |
| **Cost Efficiency** | 130% better | Baseline | 🏆 Userscale |

## 🎯 Key Features

### Userscale Advantages

- **Multi-metric Scaling**: Considers users, CPU, latency, and GPU
- **EWMA Smoothing**: Exponentially Weighted Moving Average for stable scaling
- **Intelligent Cooldown**: Prevents rapid scaling oscillations
- **Resource Optimization**: Uses fewer resources while maintaining performance
- **Fast Response**: 3-second sync period for quick adaptation

### HPA Advantages

- **Stability**: No scaling failures or oscillations
- **Simplicity**: Easy to configure and maintain
- **Consistency**: Predictable performance characteristics
- **Maturity**: Battle-tested in production environments

## 🔍 Monitoring

The project includes comprehensive monitoring:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization dashboards
- **Custom Metrics**: Application-specific scaling metrics
- **Real-time Monitoring**: Live scaling behavior tracking

## 📈 Scaling Logic

### Userscale Algorithm

1. **Metrics Collection**: Gather active users, CPU, latency, GPU
2. **EWMA Smoothing**: Apply exponential smoothing to reduce noise
3. **Multi-metric Analysis**: Calculate desired replicas for each metric
4. **Intelligent Scaling**: Use maximum of all metric-based calculations
5. **Cooldown Management**: Prevent rapid scaling oscillations
6. **Step Limiting**: Control scaling step sizes

### HPA Algorithm

1. **Resource Monitoring**: Track CPU and memory utilization
2. **Threshold Comparison**: Compare against target utilization
3. **Replica Calculation**: Calculate desired replicas based on utilization
4. **Stabilization**: Apply stabilization windows to prevent oscillations

## 🛠️ Development

### Building Images

```bash
# Build application image
docker build -t userscale-app:latest app/

# Build scaler image
docker build -t userscale-scaler:latest scaler/
```

### Testing

```bash
# Run load tests
python -m loadgen.main --concurrency 25 --duration 60

# Monitor scaling behavior
kubectl get pods -n userscale -w
```

## 📝 Results

The project demonstrates that **Userscale provides superior resource efficiency** while maintaining competitive performance. Key findings:

- **130% better resource efficiency** compared to HPA
- **Dynamic scaling** that adapts to actual demand
- **Cost optimization** through intelligent resource usage
- **Multi-metric intelligence** for better scaling decisions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Kubernetes community for HPA implementation
- FastAPI for the web framework
- Prometheus for metrics collection
- Grafana for visualization

---

**Note**: This project demonstrates advanced Kubernetes autoscaling concepts and should be used as a learning resource and proof-of-concept for custom autoscaling solutions.