## Userscale: User + CPU/GPU Aware Autoscaling (EWMA Smoothed)

This project demonstrates a custom scaler that combines active user load with system metrics (CPU and GPU) to scale a Kubernetes Deployment up/down using the Kubernetes API. It applies EWMA smoothing to reduce sensitivity to short spikes.

### Components
- **App (FastAPI)**: exposes workloads and a `/metrics` JSON with `active_users`, per-endpoint latencies, and basic system stats.
- **Scaler**: periodically pulls app metrics and Kubernetes metrics; applies EWMA; computes desired replicas within min/max bounds; scales the Deployment.
- **Kubernetes Manifests**: app + scaler Deployments, Service, RBAC, and a ConfigMap for thresholds and tuning params.
- **Load Generator**: simulates streaming, matrix-multiplication, and GPU-like workloads to test scaling behavior.

### Scaling Logic (high-level)
- Inputs per pod: `active_users`, CPU utilization (from metrics.k8s.io), optional GPU utilization (via Prometheus/DCGM if configured).
- EWMA smoothing with `alpha` (0-1). Lower alpha = more smoothing.
- Thresholds:
  - If `active_users_per_pod > users_target`, scale out.
  - If `cpu_utilization > cpu_target`, scale out.
  - If `gpu_utilization > gpu_target`, scale out.
  - If all signals are below lower bands (e.g., 70% of targets), scale in.
- Combines signals conservatively: scale by the largest suggested replicas among user/CPU/GPU signals.

#### Pod requirement formula (user-based)
PodsRequired = ceil((CurrentUsers × PerUserUsage) / PerPodCapacity)

Mapping to config:
- `PerPodCapacity / PerUserUsage = users_target_per_pod`
- Therefore: `PodsRequired = ceil(CurrentUsers / users_target_per_pod)`

In this repo the scaler uses `USERS_TARGET_PER_POD` for the above calculation, with EWMA smoothing applied to `CurrentUsers` to avoid reacting to short spikes.

### Quick Start (Local Docker)
1) Build images
```bash
docker build -f Dockerfile.app -t userscale-app:local .
docker build -f Dockerfile.scaler -t userscale-scaler:local .
```

2) Run app locally
```bash
docker run --rm -p 8000:8000 userscale-app:local
```

3) Exercise endpoints
```bash
curl -s localhost:8000/healthz
curl -s "localhost:8000/matrix?size=300"
curl -s "localhost:8000/stream?duration_ms=2000"
curl -s "localhost:8000/gpu_job?work_ms=1000" # simulates GPU load if CUDA not present
curl -s localhost:8000/metrics | jq
```

4) Load generation
```bash
python -m loadgen.main --scenario matrix --concurrency 20 --size 300 --duration 60
python -m loadgen.main --scenario stream --concurrency 50 --duration 60
python -m loadgen.main --scenario gpu --concurrency 10 --work-ms 1500 --duration 60
```

### Kubernetes Deploy
Assumes a cluster with metrics-server. For GPU tests, deploy NVIDIA drivers and DCGM exporter (optional). Update image names as needed.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/app.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/scaler.yaml
```

Check scaler logs:
```bash
kubectl logs deploy/userscale-scaler -n userscale -f | cat
```

### Configuration (ConfigMap `userscale-config`)
- `alpha`: EWMA smoothing factor (0.2-0.6 typical)
- `min_replicas`, `max_replicas`
- `users_target_per_pod`: target active users per pod
- `cpu_target_utilization`: percent (e.g., 70)
- `gpu_target_utilization`: percent (e.g., 70)
- `scale_up_step`, `scale_down_step`: max replica change per sync
- `gpu_prometheus_base`: optional Prometheus URL; if set, scaler queries DCGM GPU utilization

### Feasibility Notes
- User-based scaling reacts well to request concurrency; CPU/GPU-based scaling reacts to actual compute load. Combining both yields better stability and utilization.


