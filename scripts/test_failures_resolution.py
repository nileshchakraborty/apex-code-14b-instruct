#!/usr/bin/env python3
"""Targeted Verification Runner on the 6 LiveCodeBench Benchmark Failures.

Evaluates whether the Unified Research Optimization Pipeline resolves:
1. 1873_A: A. Short Sort (easy)
2. 1873_D: D. 1D Eraser (easy)
3. 1883_C: C. Raspberries (medium)
4. 1899_C: C. Yarik and Array (hard)
5. 1899_D: D. Yarik and Musical Notes (hard)
6. 2754: maximum-strength-of-a-group (medium)
"""

import json
import os
import sys
import time

LIVECODEBENCH_DIR = "/Users/nileshchakraborty/workspace/LiveCodeBench"
APEX_DIR = "/Users/nileshchakraborty/workspace/apex-code-36gb"

sys.path.insert(0, LIVECODEBENCH_DIR)
sys.path.insert(0, APEX_DIR)

from lcb_runner.benchmarks.code_generation import load_code_generation_dataset
from lcb_runner.evaluation.compute_code_generation_metrics import codegen_metrics
from scripts.unified_research_pipeline import generate_optimized_solution

TARGET_FAILED_IDS = ["1873_A", "1873_D", "1883_C", "1899_C", "1899_D", "2754"]


def run_failures_verification():
    print("=" * 72)
    print("🎯 TARGETED VERIFICATION: RESOLVING THE 6 BENCHMARK FAILURES")
    print(f"Target Problem IDs: {TARGET_FAILED_IDS}")
    print("=" * 72)

    dataset = load_code_generation_dataset()
    target_problems = [p for p in dataset if p.question_id in TARGET_FAILED_IDS]
    # Sort to match target order
    target_problems.sort(key=lambda p: TARGET_FAILED_IDS.index(p.question_id))

    print(f"Loaded {len(target_problems)} target problems from LiveCodeBench.\n")

    samples_list = []
    generations_list = []
    metadata_list = []

    t_start = time.perf_counter()

    for idx, prob in enumerate(target_problems, 1):
        print(f"[{idx}/{len(target_problems)}] Evaluating {prob.question_id}: {prob.question_title} ({prob.difficulty.value})...")
        
        t0_prob = time.perf_counter()
        res = generate_optimized_solution(
            problem_text=prob.question_content,
            starter_code=prob.starter_code,
            mode="greedy",
            is_competitive_io=True,
        )
        gen_time = round(time.perf_counter() - t0_prob, 2)
        code = res["code"]

        print(f"  ⚡ Synthesized in {gen_time}s ({res['tokens']} tokens). AST Valid: {res['ast_valid']} | Semantic Clean: {res['semantic_clean']}")
        print(f"  Invariants summary: {res['invariants_summary'][:120]}...\n")

        samples_list.append(prob.get_evaluation_sample())
        generations_list.append([code])
        metadata_list.append({
            "question_id": prob.question_id,
            "question_title": prob.question_title,
            "difficulty": prob.difficulty.value,
            "latency_sec": gen_time,
            "tokens": res["tokens"],
            "semantic_clean": res["semantic_clean"],
            "code": code,
        })

    total_gen_time = round(time.perf_counter() - t_start, 2)
    print(f"✅ All {len(target_problems)} solutions synthesized in {total_gen_time}s.\n")
    print("▶ Executing Official LiveCodeBench Test Suites in Sandbox...")

    t_eval = time.perf_counter()
    metrics, graded_results, _ = codegen_metrics(
        samples_list,
        generations_list,
        k_list=[1],
        num_process_evaluate=4,
        timeout=6,
    )
    eval_time = round(time.perf_counter() - t_eval, 2)
    print(f"✅ Sandbox execution completed in {eval_time}s.\n")

    passed_count = 0
    print("=" * 72)
    print("📊 TARGETED VERIFICATION RESULTS (PREVIOUSLY FAILED PROBLEMS)")
    print("=" * 72)

    for idx, (prob, meta) in enumerate(zip(target_problems, metadata_list)):
        res_list = graded_results.get(idx, [])
        all_passed = bool(res_list and all(x > 0 for x in res_list[0]) and len(res_list[0]) > 0) if res_list else False
        status = "✅ PASS" if all_passed else "❌ FAIL"
        if all_passed:
            passed_count += 1
        passed_cases = sum(1 for x in res_list[0] if x > 0) if res_list else 0
        total_cases = len(res_list[0]) if res_list else 0

        print(f"  [{status}] {prob.question_id:<10}: {prob.question_title[:28]:<28} ({prob.difficulty.value:<6}) | Tests: {passed_cases}/{total_cases}")
        meta["passed"] = all_passed
        meta["passed_cases"] = passed_cases
        meta["total_cases"] = total_cases

    print("-" * 72)
    resolution_rate = (passed_count / len(target_problems)) * 100
    print(f"Resolved: {passed_count}/{len(target_problems)} previously failing problems ({resolution_rate:.1f}%)")
    print(f"Total Wall-Clock Time: {total_gen_time + eval_time:.1f}s")
    print("=" * 72)

    # Save verification report
    out_file = os.path.join(APEX_DIR, "tests/lcb_target_failures_resolved.json")
    with open(out_file, "w") as f:
        json.dump({
            "target_problems": TARGET_FAILED_IDS,
            "resolved_count": passed_count,
            "total_target": len(target_problems),
            "resolution_rate": resolution_rate,
            "problems": metadata_list,
        }, f, indent=2)
    print(f"\n📄 Saved report to: {out_file}\n")


if __name__ == "__main__":
    run_failures_verification()
