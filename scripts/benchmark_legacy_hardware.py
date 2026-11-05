#!/usr/bin/env python3
"""Cross-Hardware Benchmark: Apple Silicon Unified Memory vs Bare-Metal Intel Core i9 Fedora.

Compares:
1. Docker Sandbox Execution Overhead (Mac VM hypervisor vs Bare-Metal Linux cgroups)
2. Model Throughput & Latency (Metal GPU acceleration vs Intel Core i9 AVX2 CPU)
3. Memory Utilization & Swap Headroom
"""

import argparse
import json
import os
import subprocess
import time
import urllib.request
import psutil

PROMPTS = [
    {
        "name": "Algorithm (Kadane + Monotonic Queue)",
        "prompt": "Write a Python function `max_subarray_sliding_window(nums: list[int], k: int) -> int` that finds the maximum sum subarray of size at least k. Optimize for O(N) time and O(k) space.",
    },
    {
        "name": "AST Contract & Type Safety",
        "prompt": "Implement a thread-safe generic LRU Cache in Python using dataclasses, OrderedDict, typing.Generic, and contract assertions.",
    },
    {
        "name": "Competitive Fast I/O",
        "prompt": "Implement a complete solution for finding strongly connected components using Tarjan's algorithm with fast sys.stdin.read() and sys.setrecursionlimit(300_000).",
    },
]


def query_ollama_endpoint(base_url: str, model: str, prompt: str, max_tokens: int = 256) -> dict:
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.0,  # Deterministic greedy argmax
            "num_ctx": 4096,
        },
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.perf_counter() - start

            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 1)
            prompt_eval_count = data.get("prompt_eval_count", 0)
            prompt_eval_duration_ns = data.get("prompt_eval_duration", 1)

            eval_tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0
            prompt_eval_tps = (
                (prompt_eval_count / (prompt_eval_duration_ns / 1e9))
                if prompt_eval_duration_ns > 0
                else 0
            )

            return {
                "success": True,
                "elapsed_sec": round(elapsed, 2),
                "eval_count": eval_count,
                "tokens_per_sec": round(eval_tps, 2),
                "prompt_eval_count": prompt_eval_count,
                "prompt_eval_tps": round(prompt_eval_tps, 2),
                "total_duration_sec": round(data.get("total_duration", 0) / 1e9, 2),
                "load_duration_ms": round(data.get("load_duration", 0) / 1e6, 2),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def benchmark_docker_sandbox(docker_host: str = None, iterations: int = 5) -> dict:
    """Benchmark sandbox execution latency."""
    env = os.environ.copy()
    if docker_host:
        env["DOCKER_HOST"] = docker_host

    image = "python:3.12-slim"
    py_code = "import sys, math; res = sum(math.isqrt(i) for i in range(100_000)); assert res > 0"

    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory=512m",
            "--cpus=2",
            image,
            "python3", "-c", py_code,
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)
        dt = (time.perf_counter() - t0) * 1000
        if res.returncode == 0:
            latencies.append(dt)

    if not latencies:
        return {"success": False, "error": "All docker runs failed"}

    latencies.sort()
    return {
        "success": True,
        "runs": len(latencies),
        "min_ms": round(latencies[0], 2),
        "mean_ms": round(sum(latencies) / len(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "max_ms": round(latencies[-1], 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Cross-Hardware Benchmark")
    parser.add_argument("--local-url", default="http://127.0.0.1:11434")
    parser.add_argument("--remote-url", default="http://192.168.1.250:11434")
    parser.add_argument("--local-model", default="apex-coder-14b")
    parser.add_argument("--remote-model", default="hf.co/nileshc90/apex-code-14b-instruct:Q5_K_M")
    parser.add_argument("--tokens", type=int, default=192)
    parser.add_argument("--output", default="tests/legacy_hardware_benchmark_results.json")
    args = parser.parse_args()

    print("=" * 72)
    print("🚀 Cross-Hardware Benchmark: Apple Silicon vs Intel Core i9 Bare-Metal Fedora")
    print("=" * 72)

    # 1. System Specifications
    print("\n[1/3] Hardware Specifications")
    print("• Target A (Modern): Apple Silicon Mac (M-Series), ARM64, Unified Memory Metal GPU")
    print("• Target B (Legacy): MacBook Pro 2019 16\", Intel Core i9-9880H (8C/16T AVX2), 31.2 GB DDR4, Bare-Metal Fedora 44 Linux")

    # 2. Docker Sandbox Benchmark
    print("\n[2/3] Benchmarking Docker Sandbox Execution Overhead (5 runs each)...")
    print("  • Measuring Local Docker (Mac Hypervisor)...")
    local_docker = benchmark_docker_sandbox(docker_host=None, iterations=5)
    print(f"    -> Mean: {local_docker.get('mean_ms')} ms (min: {local_docker.get('min_ms')} ms)")

    print("  • Measuring Remote Docker (Fedora Bare-Metal Linux via SSH)...")
    remote_docker = benchmark_docker_sandbox(docker_host="ssh://fedora.local", iterations=5)
    print(f"    -> Mean: {remote_docker.get('mean_ms')} ms (min: {remote_docker.get('min_ms')} ms)")

    # 3. Model Inference Benchmark
    print("\n[3/3] Benchmarking ApexCode-14B-Instruct Inference Throughput...")
    results = {
        "hardware": {
            "modern": "Apple Silicon (Metal GPU Unified Memory)",
            "legacy": "Intel Core i9-9880H @ 2.30GHz (16 vCPUs, AVX2, Fedora 44 Linux)",
        },
        "docker_sandbox": {
            "local_mac_hypervisor": local_docker,
            "fedora_bare_metal_cgroups": remote_docker,
        },
        "prompts": [],
    }

    for idx, p in enumerate(PROMPTS, 1):
        print(f"\n--- Benchmark Prompt {idx}/{len(PROMPTS)}: {p['name']} ---")
        
        # Test Local Apple Silicon
        print(f"  [Apple Silicon Metal GPU] Querying {args.local_model}...")
        res_local = query_ollama_endpoint(args.local_url, args.local_model, p["prompt"], args.tokens)
        if res_local["success"]:
            print(f"    ✓ Generation: {res_local['tokens_per_sec']} t/s | Prompt Eval: {res_local['prompt_eval_tps']} t/s | Latency: {res_local['elapsed_sec']}s")
        else:
            print(f"    ✗ Error: {res_local.get('error')}")

        # Test Remote Intel Core i9
        print(f"  [Intel Core i9 Fedora] Querying {args.remote_model}...")
        res_remote = query_ollama_endpoint(args.remote_url, args.remote_model, p["prompt"], args.tokens)
        if res_remote["success"]:
            print(f"    ✓ Generation: {res_remote['tokens_per_sec']} t/s | Prompt Eval: {res_remote['prompt_eval_tps']} t/s | Latency: {res_remote['elapsed_sec']}s")
        else:
            print(f"    ✗ Error: {res_remote.get('error')}")

        speedup = 0.0
        if res_local.get("success") and res_remote.get("success") and res_remote["tokens_per_sec"] > 0:
            speedup = round(res_local["tokens_per_sec"] / res_remote["tokens_per_sec"], 2)
            print(f"    ⚡ Speedup Factor (Metal GPU vs Intel CPU): {speedup}x")

        results["prompts"].append({
            "name": p["name"],
            "prompt": p["prompt"],
            "apple_silicon": res_local,
            "intel_i9_fedora": res_remote,
            "speedup_factor": speedup,
        })

    # Summary Table
    print("\n" + "=" * 72)
    print("📊 BENCHMARK COMPARISON SUMMARY")
    print("=" * 72)
    print(f"{'Prompt Task':<32} | {'Apple Silicon (GPU)':<20} | {'Intel Core i9 (CPU)':<20} | {'Speedup':<8}")
    print("-" * 88)
    for r in results["prompts"]:
        loc_tps = f"{r['apple_silicon'].get('tokens_per_sec', 0)} t/s" if r['apple_silicon'].get('success') else "ERR"
        rem_tps = f"{r['intel_i9_fedora'].get('tokens_per_sec', 0)} t/s" if r['intel_i9_fedora'].get('success') else "ERR"
        sp = f"{r['speedup_factor']}x" if r['speedup_factor'] else "N/A"
        print(f"{r['name']:<32} | {loc_tps:<20} | {rem_tps:<20} | {sp:<8}")

    print("-" * 88)
    print(f"{'Docker Sandbox Cold Start':<32} | {local_docker.get('mean_ms', 0)} ms (Mac VM)       | {remote_docker.get('mean_ms', 0)} ms (Native Linux) | {'Native cgroups'}")
    print("=" * 72)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Detailed results saved to {args.output}")


if __name__ == "__main__":
    main()
