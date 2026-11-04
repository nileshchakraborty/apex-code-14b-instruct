#!/usr/bin/env python3
"""Empirical Benchmark: Single-Shot Baseline vs. ApexDeepCoder 2-Stage Pipeline.

Compares:
- Baseline: Direct single-shot code generation using apex-coder-14b
- ApexDeepCoder: 2-Stage Cognitive Decomposition (Thinker plan + Coder synthesis) + Reflexion

Evaluates on complex systems & algorithmic tasks:
1. Concurrent LRU Cache with TTL & Lock Striping
2. Augmented Interval Tree with Overlap Queries
3. Thread-safe Sliding Window Rate Limiter
"""

import ast
import json
import os
import sys
import time
import psutil

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepcoder_pipeline import (
    get_memory_usage,
    query_ollama,
    extract_code_block,
    verify_and_execute_code,
    run_deepcoder_pipeline,
    CODE_MODEL,
)

BENCHMARK_PROBLEMS = [
    {
        "id": "concurrent_lru_cache",
        "name": "Concurrent LRU Cache with TTL",
        "difficulty": "Hard (Systems / Concurrency)",
        "prompt": (
            "Implement a thread-safe LRUCache in Python supporting max_size and per-key TTL (time-to-live). "
            "Include get(key), put(key, value, ttl=None), delete(key), and cleanup_expired(). "
            "Use threading.RLock for thread safety and an OrderedDict or doubly-linked list. "
            "Include a self-contained test suite with assert statements verifying cache eviction, TTL expiry, and basic thread concurrency."
        ),
    },
    {
        "id": "augmented_interval_tree",
        "name": "Augmented Interval Tree (Overlap Queries)",
        "difficulty": "Hard (Algorithms / Trees)",
        "prompt": (
            "Implement an Augmented Interval Tree in Python where each node stores an interval [low, high] "
            "and maintains 'max_high' (maximum high value in its subtree). "
            "Include insert(low, high) and find_overlapping(low, high) -> list[tuple[int, int]]. "
            "Handle point intervals [x, x] and negative coordinates properly. "
            "In your executable test suite, compare results using set(tree.find_overlapping(...)) == set(...) to be independent of traversal order."
        ),
    },
    {
        "id": "sliding_window_rate_limiter",
        "name": "Sliding Window Rate Limiter",
        "difficulty": "Medium-Hard (Distributed Systems)",
        "prompt": (
            "Implement an in-memory thread-safe SlidingWindowRateLimiter in Python. "
            "It must enforce a limit of max_requests within a sliding window_seconds per client_id. "
            "Include allow_request(client_id: str) -> bool, get_remaining_allowance(client_id: str) -> int, and reset(client_id: str). "
            "Use threading.Lock and clean up stale timestamp entries to prevent unbounded memory growth. "
            "In your executable assert tests, use small sub-second windows (e.g. window_seconds=0.05 and time.sleep(0.06)) so tests complete in under 1 second."
        ),
    },
]


def run_single_shot_baseline(prompt: str) -> dict:
    """Run baseline single-shot code generation using apex-coder-14b."""
    t0 = time.perf_counter()
    sys_prompt = (
        "You are an expert Python engineer. Implement the solution with full type annotations, "
        "proper docstrings, and a self-contained executable test suite with assert statements. "
        "In tests, keep sleep timings under 0.1s so execution completes swiftly. "
        "Return the code inside a standard ```python block."
    )
    res = query_ollama(
        model=CODE_MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    extracted = extract_code_block(res["content"])
    exec_res = verify_and_execute_code(extracted, timeout_sec=10)
    total_time = round(time.perf_counter() - t0, 2)

    return {
        "ast_valid": exec_res.get("ast_valid", False),
        "tests_passed": exec_res.get("passed", False),
        "execution_details": exec_res,
        "latency_sec": total_time,
        "tokens": res["tokens"],
        "code": extracted,
    }


def run_benchmark():
    print("=" * 72)
    print("🚀 RUNNING EMPIRICAL BENCHMARK: BASELINE 14B vs. APEX DEEPCODER PIPELINE")
    initial_mem = get_memory_usage()
    print(f"System RAM: {initial_mem['used_gb']} GB / {initial_mem['total_gb']} GB | Swap: {initial_mem['swap_used_mb']} MB")
    print("=" * 72)

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": initial_mem,
        "problems": [],
        "summary": {
            "baseline_pass_count": 0,
            "deepcoder_pass_count": 0,
            "total_problems": len(BENCHMARK_PROBLEMS),
        },
    }

    for idx, prob in enumerate(BENCHMARK_PROBLEMS, 1):
        print(f"\n========================================================================")
        print(f"[{idx}/{len(BENCHMARK_PROBLEMS)}] PROBLEM: {prob['name']} ({prob['difficulty']})")
        print("========================================================================")

        # 1. Run Baseline (Single-shot 14B)
        print("▶ Testing Mode A: Single-Shot Baseline (apex-coder-14b)...")
        baseline_res = run_single_shot_baseline(prob["prompt"])
        base_status = "✅ PASS" if baseline_res["tests_passed"] else "❌ FAIL"
        print(f"  Baseline: {base_status} in {baseline_res['latency_sec']}s (AST: {baseline_res['ast_valid']})")
        if not baseline_res["tests_passed"] and baseline_res["execution_details"].get("error"):
            print(f"  Baseline Error: {baseline_res['execution_details']['error'][:90]}...")

        # 2. Run ApexDeepCoder (2-Stage + Reflexion)
        print("\n▶ Testing Mode B: ApexDeepCoder (2-Stage Cognitive + Reflexion)...")
        deepcoder_res = run_deepcoder_pipeline(prob["prompt"], max_repair_attempts=2, verbose=True)
        deep_status = "✅ PASS" if deepcoder_res["tests_passed"] else "❌ FAIL"
        print(f"  DeepCoder: {deep_status} in {deepcoder_res['latency_sec']['total']}s (Repairs: {deepcoder_res['repairs_performed']})")

        if baseline_res["tests_passed"]:
            results["summary"]["baseline_pass_count"] += 1
        if deepcoder_res["tests_passed"]:
            results["summary"]["deepcoder_pass_count"] += 1

        results["problems"].append({
            "id": prob["id"],
            "name": prob["name"],
            "baseline": {
                "ast_valid": baseline_res["ast_valid"],
                "passed": baseline_res["tests_passed"],
                "latency_sec": baseline_res["latency_sec"],
                "tokens": baseline_res["tokens"],
                "error": baseline_res["execution_details"].get("error"),
            },
            "deepcoder": {
                "ast_valid": deepcoder_res["ast_valid"],
                "passed": deepcoder_res["tests_passed"],
                "repairs": deepcoder_res["repairs_performed"],
                "latency_sec": deepcoder_res["latency_sec"]["total"],
                "tokens": deepcoder_res["tokens_generated"],
                "stage1_plan_latency": deepcoder_res["latency_sec"]["stage1_plan"],
                "stage2_code_latency": deepcoder_res["latency_sec"]["stage2_code"],
            },
        })

    final_mem = get_memory_usage()
    results["final_memory"] = final_mem

    # Print Summary Table
    print("\n" + "=" * 72)
    print("📊 EMPIRICAL BENCHMARK SUMMARY TABLE")
    print("=" * 72)
    print(f"{'Problem Name':<35} | {'Baseline (1-Shot)':<18} | {'ApexDeepCoder':<18}")
    print("-" * 72)
    for p in results["problems"]:
        b_txt = "✅ PASS" if p["baseline"]["passed"] else "❌ FAIL"
        d_txt = f"✅ PASS ({p['deepcoder']['repairs']} rep)" if p["deepcoder"]["passed"] else "❌ FAIL"
        print(f"{p['name'][:35]:<35} | {b_txt:<18} | {d_txt:<18}")
    print("-" * 72)
    print(f"Pass Rate Baseline:  {results['summary']['baseline_pass_count']} / {len(BENCHMARK_PROBLEMS)} ({results['summary']['baseline_pass_count']/len(BENCHMARK_PROBLEMS)*100:.1f}%)")
    print(f"Pass Rate DeepCoder: {results['summary']['deepcoder_pass_count']} / {len(BENCHMARK_PROBLEMS)} ({results['summary']['deepcoder_pass_count']/len(BENCHMARK_PROBLEMS)*100:.1f}%)")
    print(f"Peak RAM Used:       {final_mem['used_gb']} GB / {final_mem['total_gb']} GB (Swap: {final_mem['swap_used_mb']} MB)")
    print("=" * 72)

    # Save results to tests/
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_dir = os.path.join(repo_root, "tests")
    os.makedirs(test_dir, exist_ok=True)
    out_file = os.path.join(test_dir, "deepcoder_benchmark_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"📄 Detailed results saved to: {out_file}\n")
    return results


if __name__ == "__main__":
    run_benchmark()
