#!/usr/bin/env python3
"""Experiment 1: Empirical Validation of Sandbox Execution Environments.

Tests:
1. Cold Docker (docker run --rm)
2. Warmed Docker Daemon (docker exec)
3. Native Host Python

Measures 30 iterations of realistic test-suite execution (concurrency, data structures, assertions).
Validates boundary constraints:
- Network denial
- Memory limit breach (600 MB allocation in 512 MB cap)
- Filesystem isolation
"""

import json
import os
import statistics
import subprocess
import time
import psutil

DOCKER_IMAGE = "apex-code-36gb:latest"
WARMED_CONTAINER_NAME = "apex-sandbox-daemon"

SAMPLE_TEST_CODE = """
import collections, threading, time
class ConcurrentLRU:
    def __init__(self, capacity: int = 3):
        self.cap = capacity
        self.cache = collections.OrderedDict()
        self.lock = threading.RLock()
    def get(self, key):
        with self.lock:
            if key not in self.cache: return None
            self.cache.move_to_end(key)
            return self.cache[key]
    def put(self, key, value):
        with self.lock:
            if key in self.cache: self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.cap:
                self.cache.popitem(last=False)

cache = ConcurrentLRU(3)
cache.put('a', 1); cache.put('b', 2); cache.put('c', 3)
assert cache.get('a') == 1
cache.put('d', 4)
assert cache.get('b') is None or cache.get('b') == 2
assert cache.get('d') == 4
"""

def setup_warmed_container():
    subprocess.run(["docker", "rm", "-f", WARMED_CONTAINER_NAME], capture_output=True)
    cmd = [
        "docker", "run", "-d",
        "--name", WARMED_CONTAINER_NAME,
        "--net=none",
        "--memory=512m",
        "--cpus=2",
        "--entrypoint", "sleep",
        DOCKER_IMAGE,
        "3600"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to start warm container: {res.stderr}")
    # Warm-up run
    subprocess.run(["docker", "exec", "-i", WARMED_CONTAINER_NAME, "python3", "-c", "assert 1+1==2"], capture_output=True)

def teardown_warmed_container():
    subprocess.run(["docker", "rm", "-f", WARMED_CONTAINER_NAME], capture_output=True)

def benchmark_runs(num_runs=30):
    print(f"🔬 Benchmarking Execution Latency across {num_runs} iterations...")
    setup_warmed_container()

    times_native = []
    times_cold = []
    times_warm = []

    for i in range(num_runs):
        # 1. Native Host Python
        t0 = time.perf_counter()
        r_nat = subprocess.run(["python3", "-c", SAMPLE_TEST_CODE], capture_output=True)
        times_native.append((time.perf_counter() - t0) * 1000)
        assert r_nat.returncode == 0, f"Native run failed: {r_nat.stderr}"

        # 2. Warmed Docker Container
        t0 = time.perf_counter()
        r_warm = subprocess.run(
            ["docker", "exec", "-i", WARMED_CONTAINER_NAME, "python3", "-c", SAMPLE_TEST_CODE],
            capture_output=True
        )
        times_warm.append((time.perf_counter() - t0) * 1000)
        assert r_warm.returncode == 0, f"Warmed Docker failed: {r_warm.stderr}"

        # 3. Cold Docker Run (every 5 runs to avoid excessive container spam, scaled to 10 samples)
        if i < 10:
            t0 = time.perf_counter()
            r_cold = subprocess.run(
                ["docker", "run", "--rm", "-i", "--net=none", "--memory=512m", "--entrypoint", "python3", DOCKER_IMAGE, "-c", SAMPLE_TEST_CODE],
                capture_output=True
            )
            times_cold.append((time.perf_counter() - t0) * 1000)
            assert r_cold.returncode == 0, f"Cold Docker failed: {r_cold.stderr}"

    print("\n--- LATENCY BENCHMARK RESULTS (in milliseconds) ---")
    print(f"Native Python:      Mean={statistics.mean(times_native):.2f}ms | Median={statistics.median(times_native):.2f}ms | Min={min(times_native):.2f}ms | Max={max(times_native):.2f}ms | Stdev={statistics.stdev(times_native):.2f}ms")
    print(f"Warmed Docker Exec: Mean={statistics.mean(times_warm):.2f}ms | Median={statistics.median(times_warm):.2f}ms | Min={min(times_warm):.2f}ms | Max={max(times_warm):.2f}ms | Stdev={statistics.stdev(times_warm):.2f}ms")
    print(f"Cold Docker Run:    Mean={statistics.mean(times_cold):.2f}ms | Median={statistics.median(times_cold):.2f}ms | Min={min(times_cold):.2f}ms | Max={max(times_cold):.2f}ms | Stdev={statistics.stdev(times_cold):.2f}ms")

    # Boundary Tests
    print("\n🔬 Testing Security & Boundary Enforcement...")

    # Test A: Network Isolation
    net_code = "import urllib.request; urllib.request.urlopen('http://1.1.1.1', timeout=1)"
    r_warm_net = subprocess.run(["docker", "exec", "-i", WARMED_CONTAINER_NAME, "python3", "-c", net_code], capture_output=True, text=True)
    r_nat_net = subprocess.run(["python3", "-c", net_code], capture_output=True, text=True)

    print(f"  • Network Call in Warmed Docker (--net=none): ReturnCode={r_warm_net.returncode} | Error: {r_warm_net.stderr.strip().splitlines()[-1] if r_warm_net.stderr else 'None'}")
    print(f"  • Network Call in Native Host:               ReturnCode={r_nat_net.returncode} | Error: {r_nat_net.stderr.strip().splitlines()[-1] if r_nat_net.stderr else 'Reached network!'}")

    # Test B: Memory Ceiling Enforcement (Allocate 600 MB in 512 MB sandbox)
    mem_code = "data = bytearray(650 * 1024 * 1024)"
    r_warm_mem = subprocess.run(["docker", "exec", "-i", WARMED_CONTAINER_NAME, "python3", "-c", mem_code], capture_output=True, text=True)
    print(f"  • 650 MB Allocation in Warmed Docker (512MB cap): ReturnCode={r_warm_mem.returncode} (137 = OOM KILLED) | Stderr: {r_warm_mem.stderr.strip() or 'Killed by kernel'}")

    # Test C: Host Filesystem Isolation
    fs_code = "import os; print(os.path.exists('/Users/nileshchakraborty'))"
    r_warm_fs = subprocess.run(["docker", "exec", "-i", WARMED_CONTAINER_NAME, "python3", "-c", fs_code], capture_output=True, text=True)
    r_nat_fs = subprocess.run(["python3", "-c", fs_code], capture_output=True, text=True)
    print(f"  • Access Host Home Dir in Warmed Docker: Output={r_warm_fs.stdout.strip()} (Should be False)")
    print(f"  • Access Host Home Dir in Native Python: Output={r_nat_fs.stdout.strip()} (True = Host exposed)")

    teardown_warmed_container()

if __name__ == "__main__":
    benchmark_runs(num_runs=30)
