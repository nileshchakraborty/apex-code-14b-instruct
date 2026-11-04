#!/usr/bin/env python3
"""Empirical Benchmark: Single-Shot Baseline vs. ApexDeepCoder Adaptive Invariant Pipeline.

Compares:
- Baseline: Direct single-shot code generation using apex-coder-14b
- ApexDeepCoder: Adaptive SSIB Invariant Pipeline with JIT Escalation ('auto', 'medium', 'high')

Comprehensive 9-Problem Suite across 3 Core Pillars:
1. Systems & Concurrency:
   - Problem 1: Concurrent LRU Cache with TTL (Hard Systems)
   - Problem 2: Augmented Interval Tree with Overlap Queries (Hard Algorithms)
   - Problem 3: Sliding Window Rate Limiter (Medium Distributed Systems)

2. LeetCode Algorithmic Levels:
   - Problem 4: LeetCode Easy: Valid Anagram with Unicode & Frequency Mapping
   - Problem 5: LeetCode Medium: Coin Change with Path Reconstruction (DP)
   - Problem 6: LeetCode Hard: Median of Two Sorted Arrays in O(log(min(m, n)))

3. System Design Architecture Levels:
   - Problem 7: System Design Component: Fair ReadWriteLock with Writer Preference
   - Problem 8: System Design Service: Consistent Hashing Ring with Virtual Nodes
   - Problem 9: System Design Distributed: Two-Phase Commit Coordinator (2PC) with Journal
"""

import argparse
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
    # --- Pillar 1: Systems & Concurrency ---
    {
        "id": "concurrent_lru_cache",
        "name": "Concurrent LRU Cache with TTL",
        "category": "Systems & Concurrency",
        "difficulty": "Hard",
        "prompt": (
            "Implement a thread-safe LRUCache in Python supporting max_size and per-key TTL (time-to-live). "
            "Include get(key), put(key, value, ttl=None), delete(key), and cleanup_expired(). "
            "Use threading.RLock for thread safety and an OrderedDict or doubly-linked list. "
            "In your test suite, verify that when capacity exceeds max_size (e.g. max_size=2 and 3 keys 'a','b','c' are added), "
            "the least-recently-used key ('a') is evicted, recent keys ('b','c') are retained, and expired TTL entries return None."
        ),
    },
    {
        "id": "augmented_interval_tree",
        "name": "Augmented Interval Tree (Overlap Queries)",
        "category": "Algorithms & Trees",
        "difficulty": "Hard",
        "prompt": (
            "Implement an Augmented Interval Tree in Python where each node stores an interval [low, high] "
            "and maintains 'max_high' (maximum high value in its subtree). "
            "Include insert(low, high) and find_overlapping(low, high) -> list[tuple[int, int]]. "
            "Handle point intervals [x, x] and negative coordinates properly. "
            "In your executable test suite, verify find_overlapping(q_low, q_high) dynamically against an O(N) linear filter oracle: "
            "set(tree.find_overlapping(q_low, q_high)) == set(iv for iv in all_intervals if iv[0] <= q_high and iv[1] >= q_low)."
        ),
    },
    {
        "id": "sliding_window_rate_limiter",
        "name": "Sliding Window Rate Limiter",
        "category": "Distributed Systems",
        "difficulty": "Medium",
        "prompt": (
            "Implement an in-memory thread-safe SlidingWindowRateLimiter in Python. "
            "It must enforce a limit of max_requests within a sliding window_seconds per client_id. "
            "Include allow_request(client_id: str) -> bool, get_remaining_allowance(client_id: str) -> int, and reset(client_id: str). "
            "Use threading.Lock and clean up stale timestamp entries to prevent unbounded memory growth. "
            "In your executable assert tests, use small sub-second windows (e.g. window_seconds=0.05 and time.sleep(0.06)) so tests complete in under 1 second."
        ),
    },
    # --- Pillar 2: LeetCode Multi-Level Algorithmic Suite ---
    {
        "id": "leetcode_easy_valid_anagram",
        "name": "LeetCode Easy: Valid Anagram with Unicode & Frequency",
        "category": "LeetCode Easy",
        "difficulty": "Easy",
        "prompt": (
            "Implement a function `is_anagram(s: str, t: str, ignore_case: bool = False) -> bool` in Python that determines if `t` is an anagram of `s`. "
            "Requirements: "
            "1. Must handle arbitrary Unicode characters (e.g. accents 'café', emojis, non-Latin alphabets). "
            "2. Strip leading and trailing whitespace. "
            "3. If `ignore_case` is True, compare in case-insensitive manner; otherwise case-sensitive. "
            "4. Achieve O(N) time complexity using frequency mapping. "
            "In your self-contained executable assert test suite, test ASCII anagrams ('listen' vs 'silent'), non-anagrams ('rat' vs 'car'), "
            "mismatched lengths, case sensitivity vs insensitivity ('Debit card' vs 'Bad credit'), unicode strings ('café' vs 'éfac'), and empty strings."
        ),
    },
    {
        "id": "leetcode_medium_coin_change",
        "name": "LeetCode Medium: Coin Change with Path Reconstruction",
        "category": "LeetCode Medium",
        "difficulty": "Medium",
        "prompt": (
            "Implement `coin_change_with_path(coins: list[int], amount: int) -> tuple[int, list[int]]` in Python. "
            "Given a list of distinct coin denominations and an integer target amount, compute: "
            "1. The minimum number of coins needed to make up that amount. "
            "2. The optimal combination of coin values as a list in ascending sorted order. "
            "If that amount cannot be made up by any combination of coins, return `(-1, [])`. "
            "If amount == 0, return `(0, [])`. "
            "Use dynamic programming with O(amount * len(coins)) time complexity. "
            "In your self-contained executable assert test suite, test standard cases (e.g. coins=[1, 2, 5], amount=11 -> (3, [1, 5, 5])), "
            "unreachable targets (e.g. coins=[2], amount=3 -> (-1, [])), base case amount=0, and verify correctness dynamically against a brute-force recursive oracle on small amounts."
        ),
    },
    {
        "id": "leetcode_hard_median_sorted_arrays",
        "name": "LeetCode Hard: Median of Two Sorted Arrays",
        "category": "LeetCode Hard",
        "difficulty": "Hard",
        "prompt": (
            "Implement `find_median_sorted_arrays(nums1: list[int], nums2: list[int]) -> float` in Python. "
            "Given two sorted integer arrays `nums1` and `nums2` of size m and n respectively, return the median of the two sorted arrays. "
            "The overall run time complexity MUST be O(log(min(m, n))) using binary search partitioning. "
            "Handle all edge cases: one array empty, total length odd, total length even, negative numbers, and duplicates. "
            "In your self-contained executable assert test suite, dynamically verify the result against an O(m + n) merge-sort reference oracle: "
            "`def oracle_median(a, b): merged = sorted(a + b); k = len(merged); return float(merged[k//2]) if k % 2 == 1 else (merged[k//2 - 1] + merged[k//2]) / 2.0` "
            "across at least 8 varied test cases including empty inputs `[], [1]`, `[2], []`, `[1, 3], [2]`, and `[1, 2], [3, 4]`."
        ),
    },
    # --- Pillar 3: System Design Multi-Level Suite ---
    {
        "id": "sysdesign_component_rwlock",
        "name": "System Design Component: Fair ReadWriteLock with Writer Preference",
        "category": "System Design (Component)",
        "difficulty": "Medium-Hard",
        "prompt": (
            "Implement a `FairReadWriteLock` in Python using `threading.Condition` and `threading.Lock`. "
            "Requirements: "
            "1. Multiple reader threads can acquire read lock simultaneously (`acquire_read()`, `release_read()`). "
            "2. Only one writer thread can hold write lock exclusively (`acquire_write()`, `release_write()`). "
            "3. Writer preference: if any writer is waiting, incoming readers must block to prevent writer starvation. "
            "4. Provide context managers `read_lock()` and `write_lock()` usable with `with lock.read_lock():` and `with lock.write_lock():`. "
            "In your self-contained assert test suite, test concurrent readers, verify write exclusivity (readers cannot read while writer is active), "
            "and verify that a waiting writer unblocks and completes without starving. "
            "Keep thread sleep delays under 0.05s so the test suite finishes in under 1 second."
        ),
    },
    {
        "id": "sysdesign_service_consistent_hash",
        "name": "System Design Service: Consistent Hashing Ring with Virtual Nodes",
        "category": "System Design (Service)",
        "difficulty": "Hard",
        "prompt": (
            "Implement a production-grade `ConsistentHashRing` in Python for distributed cache and storage partitioning. "
            "Requirements: "
            "1. `__init__(nodes: list[str] = None, virtual_nodes: int = 100)`: Initialize ring with configurable virtual replicas per physical node using hashlib (md5 or sha256). "
            "2. `add_node(node: str)` and `remove_node(node: str)`: Maintain a sorted list of hash tokens using `bisect`. "
            "3. `get_node(key: str) -> str`: Return the physical node responsible for `key` by finding the first token clockwise on the ring. "
            "4. `get_preference_list(key: str, count: int) -> list[str]`: Return `count` distinct physical nodes for replica placement (skipping duplicate virtual nodes). "
            "In your self-contained assert test suite, verify key lookup determinism, verify preference list returns unique physical nodes up to the available nodes, "
            "and test minimal disruption: removing a node only migrates keys assigned to that node."
        ),
    },
    {
        "id": "sysdesign_distributed_2pc",
        "name": "System Design Distributed: Two-Phase Commit Coordinator (2PC)",
        "category": "System Design (Distributed)",
        "difficulty": "Hard",
        "prompt": (
            "Implement an in-memory Two-Phase Commit system in Python with `Participant` and `TwoPhaseCommitCoordinator`. "
            "Requirements: "
            "1. `Participant(node_id: str)`: Manages key-value state, prepared pending transactions, and committed state. "
            "   Implements `prepare(tx_id: str, write_intent: dict) -> bool`, `commit(tx_id: str) -> bool`, and `abort(tx_id: str) -> bool`. "
            "2. `TwoPhaseCommitCoordinator(participants: list[Participant])`: "
            "   - Phase 1 (Prepare): Broadcasts `prepare` to all participants. If any participant returns False or raises exception, coordinator immediately sends `abort` to all. "
            "   - Phase 2 (Commit/Abort): If all participants vote True, coordinator records the transaction in an in-memory journal and broadcasts `commit`. "
            "   - Returns True if committed, False if aborted. "
            "In your self-contained assert test suite, verify successful atomic commit across 3 participants, verify atomic abort and rollback when one participant votes False, "
            "and assert data consistency across all participants in both success and failure scenarios."
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
        num_ctx=16384,
    )
    extracted = extract_code_block(res["content"])
    exec_res = verify_and_execute_code(extracted, timeout_sec=15)
    total_time = round(time.perf_counter() - t0, 2)

    return {
        "ast_valid": exec_res.get("ast_valid", False),
        "tests_passed": exec_res.get("passed", False),
        "execution_details": exec_res,
        "latency_sec": total_time,
        "tokens": res["tokens"],
        "code": extracted,
    }


def run_benchmark(
    problem_filter: str = None,
    reasoning_effort: str = "auto",
    skip_baseline: bool = False,
    max_repairs: int = 2,
):
    print("=" * 76)
    print(f"🚀 RUNNING 9-PROBLEM EMPIRICAL BENCHMARK: BASELINE 14B vs. APEX DEEPCODER")
    print(f"Reasoning Effort Mode: {reasoning_effort.upper()} | Max Repairs: {max_repairs}")
    initial_mem = get_memory_usage()
    print(f"System RAM: {initial_mem['used_gb']} GB / {initial_mem['total_gb']} GB | Swap: {initial_mem['swap_used_mb']} MB")
    print("=" * 76)

    # Filter problems if requested
    problems_to_run = BENCHMARK_PROBLEMS
    if problem_filter:
        pf = problem_filter.lower()
        problems_to_run = [
            p for p in BENCHMARK_PROBLEMS
            if pf in p["id"].lower() or pf in p["name"].lower() or pf == str(BENCHMARK_PROBLEMS.index(p) + 1)
        ]
        if not problems_to_run:
            print(f"❌ No problem matching filter '{problem_filter}' found.")
            return None

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reasoning_effort": reasoning_effort,
        "hardware": initial_mem,
        "problems": [],
        "summary": {
            "baseline_pass_count": 0,
            "deepcoder_pass_count": 0,
            "fast_path_resolved_count": 0,
            "escalated_count": 0,
            "total_problems": len(problems_to_run),
            "baseline_latencies": [],
            "deepcoder_latencies": [],
        },
    }

    for idx, prob in enumerate(problems_to_run, 1):
        print(f"\n============================================================================")
        print(f"[{idx}/{len(problems_to_run)}] {prob['name']} ({prob['category']} - {prob['difficulty']})")
        print("============================================================================")

        # 1. Run Baseline (Single-shot 14B)
        baseline_res = None
        if not skip_baseline:
            print("▶ Testing Mode A: Single-Shot Baseline (apex-coder-14b)...")
            baseline_res = run_single_shot_baseline(prob["prompt"])
            base_status = "✅ PASS" if baseline_res["tests_passed"] else "❌ FAIL"
            print(f"  Baseline: {base_status} in {baseline_res['latency_sec']}s (AST: {baseline_res['ast_valid']})")
            if not baseline_res["tests_passed"] and baseline_res["execution_details"].get("error"):
                print(f"  Baseline Error: {baseline_res['execution_details']['error'][:90]}...")
            if baseline_res["tests_passed"]:
                results["summary"]["baseline_pass_count"] += 1
            results["summary"]["baseline_latencies"].append(baseline_res["latency_sec"])
        else:
            print("▶ Mode A (Baseline): Skipped via flag")

        # 2. Run ApexDeepCoder (Adaptive SSIB Invariant Pipeline)
        print(f"\n▶ Testing Mode B: ApexDeepCoder (effort='{reasoning_effort}')...")
        deepcoder_res = run_deepcoder_pipeline(
            prob["prompt"],
            reasoning_effort=reasoning_effort,
            max_repair_attempts=max_repairs,
            verbose=True,
        )
        deep_status = "✅ PASS" if deepcoder_res["tests_passed"] else "❌ FAIL"
        effort_used = deepcoder_res.get("effort_level", reasoning_effort)
        print(f"  DeepCoder: {deep_status} in {deepcoder_res['latency_sec']['total']}s [Mode: {effort_used}, Repairs: {deepcoder_res['repairs_performed']}]")

        if deepcoder_res["tests_passed"]:
            results["summary"]["deepcoder_pass_count"] += 1
        if "system1" in effort_used or "fast-path" in effort_used:
            results["summary"]["fast_path_resolved_count"] += 1
        elif "system2" in effort_used or "escalated" in effort_used:
            results["summary"]["escalated_count"] += 1

        results["summary"]["deepcoder_latencies"].append(deepcoder_res["latency_sec"]["total"])

        prob_entry = {
            "id": prob["id"],
            "name": prob["name"],
            "category": prob["category"],
            "difficulty": prob["difficulty"],
            "deepcoder": {
                "ast_valid": deepcoder_res.get("ast_valid"),
                "passed": deepcoder_res.get("tests_passed"),
                "effort_level": effort_used,
                "repairs": deepcoder_res.get("repairs_performed"),
                "latency_sec": deepcoder_res["latency_sec"]["total"],
                "tokens": deepcoder_res.get("tokens_generated"),
                "sandbox": deepcoder_res.get("sandbox_used"),
            },
        }
        if baseline_res:
            prob_entry["baseline"] = {
                "ast_valid": baseline_res["ast_valid"],
                "passed": baseline_res["tests_passed"],
                "latency_sec": baseline_res["latency_sec"],
                "tokens": baseline_res["tokens"],
                "error": baseline_res["execution_details"].get("error"),
            }
        results["problems"].append(prob_entry)

    final_mem = get_memory_usage()
    results["final_memory"] = final_mem

    total_probs = len(problems_to_run)
    base_pass = results["summary"]["baseline_pass_count"]
    deep_pass = results["summary"]["deepcoder_pass_count"]
    avg_base_lat = round(sum(results["summary"]["baseline_latencies"]) / max(1, len(results["summary"]["baseline_latencies"])), 2) if not skip_baseline else 0.0
    avg_deep_lat = round(sum(results["summary"]["deepcoder_latencies"]) / max(1, len(results["summary"]["deepcoder_latencies"])), 2)

    results["summary"]["avg_baseline_latency_sec"] = avg_base_lat
    results["summary"]["avg_deepcoder_latency_sec"] = avg_deep_lat

    # Print Summary Table
    print("\n" + "=" * 84)
    print("📊 9-PROBLEM EMPIRICAL BENCHMARK SUMMARY TABLE")
    print("=" * 84)
    print(f"{'Problem Name':<34} | {'Baseline (1-Shot)':<18} | {'ApexDeepCoder (' + reasoning_effort + ')':<26}")
    print("-" * 84)
    for p in results["problems"]:
        if "baseline" in p:
            b_txt = f"{'✅ PASS' if p['baseline']['passed'] else '❌ FAIL'} ({p['baseline']['latency_sec']}s)"
        else:
            b_txt = "SKIPPED"
        d = p["deepcoder"]
        d_mode = "sys1" if "system1" in d["effort_level"] else ("sys2" if "system2" in d["effort_level"] else ("esc" if "escalated" in d["effort_level"] else d["effort_level"]))
        d_txt = f"{'✅ PASS' if d['passed'] else '❌ FAIL'} ({d['latency_sec']}s, {d_mode})"
        print(f"{p['name'][:34]:<34} | {b_txt:<18} | {d_txt:<26}")
    print("-" * 84)
    if not skip_baseline:
        print(f"Pass Rate Baseline:   {base_pass} / {total_probs} ({base_pass/total_probs*100:.1f}%) | Avg Latency: {avg_base_lat}s")
    print(f"Pass Rate DeepCoder:  {deep_pass} / {total_probs} ({deep_pass/total_probs*100:.1f}%) | Avg Latency: {avg_deep_lat}s")
    print(f"Auto-Effort Paths:    {results['summary']['fast_path_resolved_count']} Fast-Path Resolved | {results['summary']['escalated_count']} Escalated to R1")
    print(f"Peak RAM Used:        {final_mem['used_gb']} GB / {final_mem['total_gb']} GB (Swap: {final_mem['swap_used_mb']} MB)")
    print("=" * 84)

    # Save results to tests/deepcoder_benchmark_results.json
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_dir = os.path.join(repo_root, "tests")
    os.makedirs(test_dir, exist_ok=True)
    out_file = os.path.join(test_dir, "deepcoder_benchmark_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"📄 Full benchmark report persisted to: {out_file}\n")
    return results


def main():
    parser = argparse.ArgumentParser(description="ApexDeepCoder vs Baseline Benchmark")
    parser.add_argument("--effort", default="auto", choices=["auto", "low", "medium", "high"], help="Reasoning effort level")
    parser.add_argument("--problem", default=None, help="Filter problem by ID, name, or index (1-9)")
    parser.add_argument("--skip-baseline", action="store_true", help="Skip baseline evaluation")
    parser.add_argument("--max-repairs", type=int, default=2, help="Max reflexion repair attempts")
    args = parser.parse_args()

    run_benchmark(
        problem_filter=args.problem,
        reasoning_effort=args.effort,
        skip_baseline=args.skip_baseline,
        max_repairs=args.max_repairs,
    )


if __name__ == "__main__":
    main()
