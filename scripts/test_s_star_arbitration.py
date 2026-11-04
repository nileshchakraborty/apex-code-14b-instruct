#!/usr/bin/env python3
"""Targeted Verification of Berkeley S* Distinguishing Input Arbiter on Discrepancy Problems.

Evaluates whether S* pairwise arbitration correctly selects the winning candidate on:
1. 1873_A: Short Sort (Unified was correct with Hamming mismatch)
2. 1873_B: Good Kid (Clean was correct with exhaustive search)
3. 1883_B: Chemistry (Clean was correct)
4. 1899_A: Game with Integers (Clean was correct with modulo)
5. 1899_D: Yarik & Musical Notes (Unified was correct with algebraic identity)
6. 2784: Power of Heroes (Clean was correct with prefix sum)
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

TARGET_DISCREPANCY_IDS = ["1873_A", "1873_B", "1883_B", "1899_A", "1899_D", "2784"]


def run_s_star_verification():
    print("=" * 72)
    print("⚖️ BERKELEY S* PAIRWISE ARBITRATION BENCHMARK")
    print(f"Target Discrepancy Problems: {TARGET_DISCREPANCY_IDS}")
    print("=" * 72)

    dataset = load_code_generation_dataset()
    target_problems = [p for p in dataset if p.question_id in TARGET_DISCREPANCY_IDS]
    target_problems.sort(key=lambda p: TARGET_DISCREPANCY_IDS.index(p.question_id))

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
            mode="s_star",
            is_competitive_io=True,
        )
        gen_time = round(time.perf_counter() - t0_prob, 2)
        code = res["code"]
        arb = res.get("arbitration_meta", {})

        print(f"  ⚡ Synthesized in {gen_time}s ({res['tokens']} tokens). AST Valid: {res['ast_valid']}")
        print(f"  ⚖️ S* Verdict: {arb.get('winner_label')} | Reason: {arb.get('reason')}\n")

        samples_list.append(prob.get_evaluation_sample())
        generations_list.append([code])
        metadata_list.append({
            "question_id": prob.question_id,
            "question_title": prob.question_title,
            "difficulty": prob.difficulty.value,
            "latency_sec": gen_time,
            "tokens": res["tokens"],
            "arbitration_meta": arb,
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
    print("📊 S* ARBITRATION BENCHMARK RESULTS")
    print("=" * 72)

    for idx, (prob, meta) in enumerate(zip(target_problems, metadata_list)):
        res_list = graded_results.get(idx, [])
        all_passed = bool(res_list and all(x > 0 for x in res_list[0]) and len(res_list[0]) > 0) if res_list else False
        status = "✅ PASS" if all_passed else "❌ FAIL"
        if all_passed:
            passed_count += 1
        passed_cases = sum(1 for x in res_list[0] if x > 0) if res_list else 0
        total_cases = len(res_list[0]) if res_list else 0

        print(f"  [{status}] {prob.question_id:<10}: {prob.question_title[:28]:<28} ({prob.difficulty.value:<6}) | Tests: {passed_cases}/{total_cases} | Picked: {meta['arbitration_meta'].get('winner_label')}")
        meta["passed"] = all_passed
        meta["passed_cases"] = passed_cases
        meta["total_cases"] = total_cases

    print("-" * 72)
    pass_rate = (passed_count / len(target_problems)) * 100
    print(f"S* Pass Rate: {passed_count}/{len(target_problems)} ({pass_rate:.1f}%)")
    print(f"Total Wall-Clock Time: {total_gen_time + eval_time:.1f}s")
    print("=" * 72)

    out_file = os.path.join(APEX_DIR, "tests/lcb_s_star_arbitration_results.json")
    with open(out_file, "w") as f:
        json.dump({
            "target_problems": TARGET_DISCREPANCY_IDS,
            "passed_count": passed_count,
            "total_target": len(target_problems),
            "pass_rate": pass_rate,
            "problems": metadata_list,
        }, f, indent=2)
    print(f"\n📄 Saved report to: {out_file}\n")


if __name__ == "__main__":
    run_s_star_verification()
