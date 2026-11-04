#!/usr/bin/env python3
"""Evaluation of Research-Backed Remediation on the 19 Failed Problems from the 50-Set.

Evaluates Adaptive Difficulty Routing + Deterministic Runtime Arbitration on:
FAILED_IDS = [
    '1873_B', '1873_D', '1883_B', '1883_C', '1899_A', '1899_C',
    '2754', '2777', '2784', '2808', '2817', '2827',
    '2832', '2833', '2837', '2839', '2849', '2850', '2854'
]
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

FAILED_50_IDS = [
    "1873_B", "1873_D", "1883_B", "1883_C", "1899_A", "1899_C",
    "2754", "2777", "2784", "2808", "2817", "2827",
    "2832", "2833", "2837", "2839", "2849", "2850", "2854"
]


def run_failed_remediation_benchmark():
    print("=" * 72)
    print("🚀 RESEARCH-BACKED REMEDIATION BENCHMARK (FAILED 19 PROBLEMS)")
    print(f"Target Problem Count: {len(FAILED_50_IDS)}")
    print("Mode: Adaptive Compute-Optimal Routing (Snell et al. 2024)")
    print("=" * 72)

    dataset = load_code_generation_dataset()
    target_problems = [p for p in dataset if p.question_id in FAILED_50_IDS]
    target_problems.sort(key=lambda p: FAILED_50_IDS.index(p.question_id))

    samples_list = []
    generations_list = []
    metadata_list = []

    t_start = time.perf_counter()

    for idx, prob in enumerate(target_problems, 1):
        diff_str = prob.difficulty.value
        print(f"[{idx}/{len(target_problems)}] Synthesizing {prob.question_id}: {prob.question_title[:28]} ({diff_str})...")
        t0_prob = time.perf_counter()

        res = generate_optimized_solution(
            problem_text=prob.question_content,
            starter_code=prob.starter_code,
            difficulty=diff_str,
            mode="adaptive",
            is_competitive_io=True,
        )
        gen_time = round(time.perf_counter() - t0_prob, 2)
        code = res["code"]
        arb = res.get("arbitration_meta", {})

        print(f"  ⚡ {gen_time}s ({res['tokens']} tok) | Route: {arb.get('routing')} | Winner: {arb.get('winner_label')}")

        samples_list.append(prob.get_evaluation_sample())
        generations_list.append([code])
        metadata_list.append({
            "question_id": prob.question_id,
            "question_title": prob.question_title,
            "difficulty": diff_str,
            "latency_sec": gen_time,
            "tokens": res["tokens"],
            "arbitration_meta": arb,
            "code": code,
        })

    total_gen_time = round(time.perf_counter() - t_start, 2)
    print(f"\n✅ All {len(target_problems)} solutions synthesized in {total_gen_time}s.")
    print("▶ Executing Official LiveCodeBench Test Suites in Docker Sandbox...")

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
    print("📊 REMEDIATION SCORECARD FOR PREVIOUSLY FAILED PROBLEMS")
    print("=" * 72)

    for idx, (prob, meta) in enumerate(zip(target_problems, metadata_list)):
        res_list = graded_results.get(idx, [])
        all_passed = bool(res_list and all(x > 0 for x in res_list[0]) and len(res_list[0]) > 0) if res_list else False
        status = "✅ PASS" if all_passed else "❌ FAIL"
        if all_passed:
            passed_count += 1
        passed_cases = sum(1 for x in res_list[0] if x > 0) if res_list else 0
        total_cases = len(res_list[0]) if res_list else 0

        print(f"  [{status}] {prob.question_id:<10}: {prob.question_title[:26]:<26} ({prob.difficulty.value:<6}) | Tests: {passed_cases}/{total_cases} | Route: {meta['arbitration_meta'].get('winner_label')}")
        meta["passed"] = all_passed
        meta["passed_cases"] = passed_cases
        meta["total_cases"] = total_cases

    print("-" * 72)
    pass_rate = (passed_count / len(target_problems)) * 100
    print(f"Recovered Pass Rate: {passed_count}/{len(target_problems)} ({pass_rate:.1f}%)")
    print(f"Total Wall-Clock Time: {total_gen_time + eval_time:.1f}s")
    print("=" * 72)

    out_file = os.path.join(APEX_DIR, "tests/lcb_failed_19_remediation_results.json")
    with open(out_file, "w") as f:
        json.dump({
            "target_problems": FAILED_50_IDS,
            "recovered_count": passed_count,
            "total_target": len(target_problems),
            "recovery_rate": pass_rate,
            "problems": metadata_list,
        }, f, indent=2)
    print(f"\n📄 Saved report to: {out_file}\n")


if __name__ == "__main__":
    run_failed_remediation_benchmark()
