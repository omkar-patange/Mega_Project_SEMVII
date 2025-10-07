import os
import math
import time
import logging
from typing import Optional

import httpx
from kubernetes import client, config
from tenacity import retry, stop_after_attempt, wait_fixed


def get_env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None else default


NAMESPACE = get_env("NAMESPACE", "userscale")
DEPLOYMENT = get_env("DEPLOYMENT", "userscale-app")
SERVICE_NAME = get_env("SERVICE_NAME", "userscale-app")
APP_PORT = int(get_env("APP_PORT", "8000"))
SYNC_PERIOD = int(get_env("SYNC_PERIOD", "15"))

ALPHA = float(get_env("ALPHA", "0.4"))
MIN_REPLICAS = int(get_env("MIN_REPLICAS", "1"))
MAX_REPLICAS = int(get_env("MAX_REPLICAS", "20"))
USERS_TARGET_PER_POD = int(get_env("USERS_TARGET_PER_POD", "50"))
CPU_TARGET = float(get_env("CPU_TARGET", "70"))
GPU_TARGET = float(get_env("GPU_TARGET", "70"))
SCALE_UP_STEP = int(get_env("SCALE_UP_STEP", "3"))
SCALE_DOWN_STEP = int(get_env("SCALE_DOWN_STEP", "2"))
GPU_PROM_BASE = os.getenv("GPU_PROM_BASE")  # e.g., http://prometheus:9090


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("userscale-scaler")


class EWMASignal:
    def __init__(self, alpha: float, initial_value: Optional[float] = None):
        self.alpha = alpha
        self.value = initial_value

    def update(self, x: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = self.alpha * x + (1 - self.alpha) * self.value
        return self.value


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def load_kube_config():
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster config")
    except config.ConfigException:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig")


def get_current_replicas(apps: client.AppsV1Api, name: str, namespace: str) -> int:
    dep = apps.read_namespaced_deployment_status(name, namespace)
    return dep.spec.replicas or 0


def get_pod_list(core: client.CoreV1Api, namespace: str, selector: str):
    return core.list_namespaced_pod(namespace, label_selector=selector).items


def get_users_and_cpu(core: client.CoreV1Api, pods, port: int):
    total_active_users = 0
    pod_cpu = []
    for p in pods:
        pod_ip = p.status.pod_ip
        if not pod_ip:
            continue
        try:
            with httpx.Client(timeout=2.0) as s:
                r = s.get(f"http://{pod_ip}:{port}/metrics")
                if r.status_code == 200:
                    m = r.json()
                    total_active_users += int(m.get("active_users", 0))
                    pod_cpu.append(float(m.get("cpu_percent", 0.0)))
        except Exception:
            continue
    avg_cpu = sum(pod_cpu) / len(pod_cpu) if pod_cpu else 0.0
    return total_active_users, avg_cpu


def query_gpu_util() -> Optional[float]:
    if not GPU_PROM_BASE:
        return None
    # Expect a Prometheus metric like: DCGM_FI_DEV_GPU_UTIL
    q = "avg(DCGM_FI_DEV_GPU_UTIL)"
    try:
        with httpx.Client(timeout=3.0) as s:
            r = s.get(f"{GPU_PROM_BASE}/api/v1/query", params={"query": q})
            data = r.json()
            result = data.get("data", {}).get("result", [])
            if result:
                v = float(result[0]["value"][1])
                return v
    except Exception:
        return None
    return None


def compute_desired_by_users(total_users: int, replicas: int) -> int:
    per_pod = USERS_TARGET_PER_POD
    needed = math.ceil(total_users / max(per_pod, 1))
    return max(needed, MIN_REPLICAS)


def compute_desired_by_util(avg_util: float, target: float, replicas: int) -> int:
    if target <= 0:
        return replicas
    ratio = avg_util / target
    if ratio > 1.05:
        return math.ceil(replicas * min(ratio, 2.0))
    if ratio < 0.6:
        return max(math.floor(replicas * max(ratio, 0.5)), MIN_REPLICAS)
    return replicas


def clamp_step(current: int, desired: int) -> int:
    if desired > current:
        return min(current + SCALE_UP_STEP, desired)
    if desired < current:
        return max(current - SCALE_DOWN_STEP, desired)
    return current


def main():
    load_kube_config()
    apps = client.AppsV1Api()
    core = client.CoreV1Api()

    user_ewma = EWMASignal(ALPHA)
    cpu_ewma = EWMASignal(ALPHA)
    gpu_ewma = EWMASignal(ALPHA)

    # Expect app pods labeled app=userscale-app
    selector = f"app={SERVICE_NAME}"

    while True:
        try:
            current = get_current_replicas(apps, DEPLOYMENT, NAMESPACE)
            pods = get_pod_list(core, NAMESPACE, selector)
            total_users, avg_cpu = get_users_and_cpu(core, pods, APP_PORT)
            gpu_util = query_gpu_util()

            u_smooth = user_ewma.update(total_users)
            c_smooth = cpu_ewma.update(avg_cpu)
            g_smooth = gpu_ewma.update(gpu_util) if gpu_util is not None else None

            desired_u = compute_desired_by_users(int(u_smooth), current)
            desired_c = compute_desired_by_util(c_smooth, CPU_TARGET, current)
            desired = max(desired_u, desired_c)
            if g_smooth is not None:
                desired_g = compute_desired_by_util(g_smooth, GPU_TARGET, current)
                desired = max(desired, desired_g)

            desired = max(MIN_REPLICAS, min(desired, MAX_REPLICAS))
            bounded = clamp_step(current, desired)

            if bounded != current:
                body = {"spec": {"replicas": bounded}}
                apps.patch_namespaced_deployment_scale(DEPLOYMENT, NAMESPACE, body)
                logger.info("Scaled replicas %s -> %s (users=%s cpu=%.1f gpu=%s)", current, bounded, int(u_smooth), c_smooth, g_smooth)
            else:
                logger.info("No scale change (replicas=%s users=%s cpu=%.1f gpu=%s)", current, int(u_smooth), c_smooth, g_smooth)
        except Exception as e:
            logger.exception("Scaler loop error: %s", e)

        time.sleep(SYNC_PERIOD)


if __name__ == "__main__":
    main()


