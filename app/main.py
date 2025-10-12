from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import time
import os
import psutil
import numpy as np
from typing import Dict, Any
import threading
import math

try:
    import cupy as cp  # Optional GPU
    GPU_AVAILABLE = True
    print("🚀 GPU support enabled with CuPy!")
except Exception:  # pragma: no cover
    cp = None
    GPU_AVAILABLE = False
    print("⚠️  GPU support not available, using CPU fallback")

app = FastAPI(title="Userscale App - GPU-Aware Autoscaling")

start_time = time.time()
active_users = 0
concurrent_requests = 0
latency_hist: Dict[str, list] = {"matrix": [], "stream": [], "gpu_job": []}
request_count = 0
total_cpu_time = 0.0


class BackgroundLoadManager:
    def __init__(self):
        self.cpu_thread = None
        self.gpu_thread = None
        self.cpu_stop = threading.Event()
        self.gpu_stop = threading.Event()
        self.status = {
            "cpu": {"running": False, "target_util": 0, "mode": "fixed"},
            "gpu": {"running": False, "target_util": 0, "mode": "fixed", "using_gpu": False},
        }

    def _duty_cycle_worker(self, stop_event: threading.Event, target_util: float, cycle_ms: int, is_gpu: bool, duration_s: int | None, sinusoid: Dict[str, float] | None):
        start = time.time()
        using_gpu_backend = False
        # Pre-allocate for GPU path if available
        if is_gpu and cp is not None:
            try:
                a = cp.random.rand(512, 512, dtype=cp.float32)
                b = cp.random.rand(512, 512, dtype=cp.float32)
                using_gpu_backend = True
                print(f"🔥 GPU backend initialized for background load")
            except Exception as e:
                print(f"⚠️  GPU backend failed: {e}")
                using_gpu_backend = False

        while not stop_event.is_set():
            now = time.time()
            if duration_s is not None and now - start >= duration_s:
                break

            # Resolve instantaneous target utilization if sinusoidal
            inst_target = target_util
            if sinusoid is not None:
                min_u = sinusoid.get("min", 10.0)
                max_u = sinusoid.get("max", 90.0)
                period = max(sinusoid.get("period_s", 60.0), 1.0)
                phase = ((now - start) % period) / period
                inst_target = min_u + (max_u - min_u) * (0.5 * (1 - math.cos(2 * math.pi * phase)))

            inst_target = float(max(0.0, min(100.0, inst_target)))

            active_ms = cycle_ms * (inst_target / 100.0)
            idle_ms = cycle_ms - active_ms

            t_active_end = time.time() + active_ms / 1000.0
            if is_gpu:
                if using_gpu_backend:
                    # Busy-loop with actual GPU ops
                    while time.time() < t_active_end and not stop_event.is_set():
                        c = a @ b
                        # Force compute
                        _ = float(cp.sum(c))
                else:
                    # CPU simulate GPU-like work
                    while time.time() < t_active_end and not stop_event.is_set():
                        _ = np.tanh(np.random.rand(4096).astype(np.float32)).sum()
            else:
                # CPU busy loop
                while time.time() < t_active_end and not stop_event.is_set():
                    _ = sum(i * i for i in range(20000))

            if idle_ms > 0:
                stop_event.wait(idle_ms / 1000.0)

        # mark stopped
        if is_gpu:
            self.status["gpu"]["running"] = False
        else:
            self.status["cpu"]["running"] = False

        if is_gpu:
            self.status["gpu"]["using_gpu"] = using_gpu_backend

    def start_cpu(self, target_util: float, duration_s: int | None, cycle_ms: int, sinusoid: Dict[str, float] | None = None):
        self.stop_cpu()
        self.cpu_stop.clear()
        self.status["cpu"] = {"running": True, "target_util": target_util, "mode": "sin" if sinusoid else "fixed"}
        self.cpu_thread = threading.Thread(
            target=self._duty_cycle_worker,
            args=(self.cpu_stop, target_util, cycle_ms, False, duration_s, sinusoid),
            daemon=True,
        )
        self.cpu_thread.start()

    def stop_cpu(self):
        self.cpu_stop.set()
        if self.cpu_thread and self.cpu_thread.is_alive():
            self.cpu_thread.join(timeout=1.0)
        self.status["cpu"]["running"] = False

    def start_gpu(self, target_util: float, duration_s: int | None, cycle_ms: int, sinusoid: Dict[str, float] | None = None):
        self.stop_gpu()
        self.gpu_stop.clear()
        self.status["gpu"] = {"running": True, "target_util": target_util, "mode": "sin" if sinusoid else "fixed", "using_gpu": cp is not None}
        self.gpu_thread = threading.Thread(
            target=self._duty_cycle_worker,
            args=(self.gpu_stop, target_util, cycle_ms, True, duration_s, sinusoid),
            daemon=True,
        )
        self.gpu_thread.start()

    def stop_gpu(self):
        self.gpu_stop.set()
        if self.gpu_thread and self.gpu_thread.is_alive():
            self.gpu_thread.join(timeout=1.0)
        self.status["gpu"]["running"] = False

    def get_status(self):
        return self.status


load_mgr = BackgroundLoadManager()


def record_latency(endpoint: str, ms: float, limit: int = 200):
    bucket = latency_hist.setdefault(endpoint, [])
    bucket.append(ms)
    if len(bucket) > limit:
        del bucket[: len(bucket) - limit]


@app.get("/healthz")
def healthz():
    return {"status": "ok", "uptime_s": int(time.time() - start_time), "gpu_available": GPU_AVAILABLE}


@app.get("/matrix")
def matrix(size: int = Query(200, ge=5, le=3000)):
    global active_users, concurrent_requests, request_count, total_cpu_time
    concurrent_requests += 1
    active_users = concurrent_requests  # Track concurrent requests as active users
    request_count += 1
    t0 = time.time()
    try:
        # More intensive computation for better scaling triggers
        a = np.random.rand(size, size).astype(np.float32)
        b = np.random.rand(size, size).astype(np.float32)
        c = a @ b
        
        # Additional computation to increase CPU load
        d = np.linalg.inv(c + np.eye(size) * 0.001)  # Add small identity to avoid singular matrix
        checksum = float(np.sum(d))
        
        total_cpu_time += time.time() - t0
        return {"size": size, "checksum": checksum, "gpu_used": False}
    finally:
        dt = (time.time() - t0) * 1000
        record_latency("matrix", dt)
        concurrent_requests -= 1
        active_users = max(concurrent_requests, 0)


@app.get("/gpu_matrix")
def gpu_matrix(size: int = Query(200, ge=5, le=3000)):
    """GPU-accelerated matrix multiplication endpoint"""
    global active_users, concurrent_requests, request_count, total_cpu_time
    concurrent_requests += 1
    active_users = concurrent_requests  # Track concurrent requests as active users
    request_count += 1
    t0 = time.time()
    
    gpu_used = False
    try:
        if cp is not None:
            # GPU computation
            a = cp.random.rand(size, size, dtype=cp.float32)
            b = cp.random.rand(size, size, dtype=cp.float32)
            c = a @ b
            checksum = float(cp.sum(c))
            gpu_used = True
        else:
            # Fallback to CPU
            a = np.random.rand(size, size).astype(np.float32)
            b = np.random.rand(size, size).astype(np.float32)
            c = a @ b
            checksum = float(np.sum(c))
        
        total_cpu_time += time.time() - t0
        return {"size": size, "checksum": checksum, "gpu_used": gpu_used}
    finally:
        dt = (time.time() - t0) * 1000
        record_latency("gpu_job", dt)
        concurrent_requests -= 1
        active_users = max(concurrent_requests, 0)


@app.get("/stream")
def stream(duration_ms: int = Query(1000, ge=1, le=30000)):
    global active_users, concurrent_requests
    concurrent_requests += 1
    active_users = concurrent_requests  # Track concurrent requests as active users
    t0 = time.time()
    try:
        end = time.time() + duration_ms / 1000.0
        # Simulate CPU work + I/O-like waiting
        while time.time() < end:
            _ = sum(i * i for i in range(1000))
            time.sleep(0.005)
        return {"duration_ms": duration_ms}
    finally:
        dt = (time.time() - t0) * 1000
        record_latency("stream", dt)
        concurrent_requests -= 1
        active_users = max(concurrent_requests, 0)


@app.get("/gpu_job")
def gpu_job(work_ms: int = Query(1000, ge=1, le=60000)):
    global active_users, concurrent_requests
    concurrent_requests += 1
    active_users = concurrent_requests  # Track concurrent requests as active users
    t0 = time.time()
    gpu_used = False
    try:
        if cp is not None:
            # GPU computation
            end = time.time() + work_ms / 1000.0
            while time.time() < end:
                a = cp.random.rand(1024, 1024, dtype=cp.float32)
                b = cp.random.rand(1024, 1024, dtype=cp.float32)
                c = a @ b
                _ = cp.sum(c)
            gpu_used = True
        else:
            # If GPU libs not available, simulate compute-bound work
            end = time.time() + work_ms / 1000.0
            while time.time() < end:
                _ = np.tanh(np.random.rand(1024).astype(np.float32)).sum()
        
        return {"work_ms": work_ms, "gpu_used": gpu_used}
    finally:
        dt = (time.time() - t0) * 1000
        record_latency("gpu_job", dt)
        concurrent_requests -= 1
        active_users = max(concurrent_requests, 0)


@app.get("/metrics")
def metrics():
    global request_count, total_cpu_time
    cpu_percent = psutil.cpu_percent(interval=0.0)
    mem = psutil.virtual_memory()
    
    # Calculate average request processing time
    avg_request_time = total_cpu_time / max(request_count, 1)
    
    response: Dict[str, Any] = {
        "active_users": max(active_users, 0),
        "cpu_percent": cpu_percent,
        "memory_percent": mem.percent,
        "request_count": request_count,
        "avg_request_time_ms": avg_request_time * 1000,
        "latency_ms_p50": {k: (np.percentile(v, 50) if v else 0.0) for k, v in latency_hist.items()},
        "latency_ms_p90": {k: (np.percentile(v, 90) if v else 0.0) for k, v in latency_hist.items()},
        "latency_ms_p95": {k: (np.percentile(v, 95) if v else 0.0) for k, v in latency_hist.items()},
        "load_status": load_mgr.get_status(),
        "gpu_available": GPU_AVAILABLE,
    }
    
    # Add GPU metrics if available
    if GPU_AVAILABLE and cp is not None:
        try:
            # Simple GPU memory usage (if available)
            response["gpu_memory_used_mb"] = 0  # Placeholder for actual GPU memory usage
        except Exception:
            pass
    
    return JSONResponse(response)


@app.post("/load/cpu/start")
def start_cpu_load(util: float = Query(70.0, ge=0, le=100), duration_s: int | None = Query(None, ge=1), cycle_ms: int = Query(200, ge=20, le=2000)):
    load_mgr.start_cpu(util, duration_s, cycle_ms)
    return {"status": "started", "type": "cpu", "util": util, "duration_s": duration_s, "cycle_ms": cycle_ms}


@app.post("/load/cpu/sinusoid")
def start_cpu_sinusoid(min_util: float = Query(20.0, ge=0, le=100), max_util: float = Query(85.0, ge=0, le=100), period_s: float = Query(60.0, ge=1), duration_s: int | None = Query(None, ge=1), cycle_ms: int = Query(200, ge=20, le=2000)):
    sinus = {"min": min_util, "max": max_util, "period_s": period_s}
    load_mgr.start_cpu(target_util=(min_util + max_util) / 2.0, duration_s=duration_s, cycle_ms=cycle_ms, sinusoid=sinus)
    return {"status": "started", "type": "cpu", "mode": "sinusoid", "min": min_util, "max": max_util, "period_s": period_s}


@app.post("/load/cpu/stop")
def stop_cpu_load():
    load_mgr.stop_cpu()
    return {"status": "stopped", "type": "cpu"}


@app.post("/load/gpu/start")
def start_gpu_load(util: float = Query(60.0, ge=0, le=100), duration_s: int | None = Query(None, ge=1), cycle_ms: int = Query(200, ge=20, le=2000)):
    load_mgr.start_gpu(util, duration_s, cycle_ms)
    return {"status": "started", "type": "gpu", "util": util, "duration_s": duration_s, "cycle_ms": cycle_ms, "using_gpu_backend": cp is not None}


@app.post("/load/gpu/sinusoid")
def start_gpu_sinusoid(min_util: float = Query(20.0, ge=0, le=100), max_util: float = Query(85.0, ge=0, le=100), period_s: float = Query(60.0, ge=1), duration_s: int | None = Query(None, ge=1), cycle_ms: int = Query(200, ge=20, le=2000)):
    sinus = {"min": min_util, "max": max_util, "period_s": period_s}
    load_mgr.start_gpu(target_util=(min_util + max_util) / 2.0, duration_s=duration_s, cycle_ms=cycle_ms, sinusoid=sinus)
    return {"status": "started", "type": "gpu", "mode": "sinusoid", "min": min_util, "max": max_util, "period_s": period_s, "using_gpu_backend": cp is not None}


@app.post("/load/gpu/stop")
def stop_gpu_load():
    load_mgr.stop_gpu()
    return {"status": "stopped", "type": "gpu"}


@app.get("/load/status")
def load_status():
    return load_mgr.get_status()


@app.get("/scaling-info")
def scaling_info():
    """Endpoint to provide scaling information for monitoring"""
    return {
        "current_active_users": max(active_users, 0),
        "gpu_available": GPU_AVAILABLE,
        "recommended_scaling_factors": {
            "users_per_pod": 10,
            "cpu_threshold": 50,
            "gpu_threshold": 60,
            "latency_threshold_ms": 200
        },
        "performance_metrics": {
            "avg_latency_p50": {k: (np.percentile(v, 50) if v else 0.0) for k, v in latency_hist.items()},
            "total_requests": request_count,
            "uptime_seconds": int(time.time() - start_time)
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)