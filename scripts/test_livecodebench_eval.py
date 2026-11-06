#!/usr/bin/env python3
"""Run a LiveCodeBench evaluation slice against ApexCode-14B."""

import argparse
import json
import os
import sys
import time

LIVECODEBENCH_DIR = "/Users/nileshchakraborty/workspace/LiveCodeBench"
APEX_DIR = "/Users/nileshchakraborty/workspace/apex-code-36gb"
MODEL_CREATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, MODEL_CREATOR_DIR)
sys.path.insert(0, LIVECODEBENCH_DIR)
sys.path.insert(0, APEX_DIR)

from lcb_runner.benchmarks.code_generation import load_code_generation_dataset
from lcb_runner.evaluation.compute_code_generation_metrics import codegen_metrics
from lcb_runner.utils.extraction_utils import extract_code
from lcb_runner.lm_styles import LMStyle
from scripts.deepcoder_pipeline import query_ollama, extract_code_block, CODE_MODEL
from scripts.clean_decoding_pipeline import generate_clean_solution
from scripts.unified_research_pipeline import generate_optimized_solution
from scripts.recursive_task_scheduler import RecursiveTaskScheduler, CognitiveRouter, HardwareGovernor
from scripts.epistemic_cache import EpistemicMemoryBus
from scripts.car_analyzer import CARAnalyzer
from scripts.epistemic_gap_arbiter import EpistemicGapArbiter
from scripts.mathematical_induction_pipeline import generate_mathematical_induction_solution
import asyncio


def main():
    parser = argparse.ArgumentParser(description="LiveCodeBench Evaluation Runner")
    parser.add_argument("--count", type=int, default=25, help="Number of problems to evaluate (default: 25)")
    parser.add_argument("--offset", type=int, default=0, help="Starting problem index (default: 0)")
    parser.add_argument("--output", type=str, default="", help="Output path for results")
    parser.add_argument(
        "--model",
        type=str,
        default="apex-coder-14b",
        help="Ollama model to evaluate (default: apex-coder-14b)",
    )
    parser.add_argument(
        "--subset",
        type=str,
        default="failed",
        choices=["failed", "slice"],
        help="Problem subset: 'failed' evaluates the 25 problems that failed in earlier test; 'slice' evaluates sequential slice from offset.",
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        default="standard",
        choices=["standard", "clean", "contracts", "unified", "recursive_swarm", "mathematical_induction"],
        help="Inference pipeline architecture (default: standard)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="greedy",
        choices=["greedy", "consensus", "calibrated"],
        help="Decoding mode (default: greedy)",
    )
    args = parser.parse_args()

    # Set CODE_MODEL in environment so sub-modules respect it
    os.environ["CODE_MODEL"] = args.model

    FAILED_25_IDS = [
        "1873_A", "1873_B", "1883_B", "1883_C", "1899_A", "1899_C", "1899_D",
        "2730", "2754", "2756", "2757", "2785", "2792",
        "2810", "2811", "2817", "2819", "2824", "2827", "2828",
        "2832", "2833", "2834", "2839", "2849"
    ]

    default_output = "tests/lcb_benchmark_25_failed_results.json" if args.subset == "failed" else "tests/lcb_benchmark_results.json"
    output_path = args.output if args.output else default_output

    print("=" * 72)
    print("🏆 LIVECODEBENCH BENCHMARK: 25 FAILED PROBLEMS EVALUATION")
    print(f"Model: {args.model} | Problem Selection: {args.subset.upper()} (Count: {args.count})")
    print(f"Pipeline: {args.pipeline.upper()} | Decoding Mode: {args.mode}")
    print("=" * 72)

    dataset = load_code_generation_dataset()
    total_available = len(dataset)
    
    if args.subset == "failed":
        ds_map = {p.question_id: p for p in dataset}
        test_slice = [ds_map[pid] for pid in FAILED_25_IDS if pid in ds_map][:args.count]
        print(f"Loaded {total_available} problems. Evaluating targeted failure set of {len(test_slice)} problems:\n")
    else:
        test_slice = dataset[args.offset : args.offset + args.count]
        print(f"Loaded {total_available} problems. Evaluating slice of {len(test_slice)} problems:\n")

    samples_list = []
    generations_list = []
    metadata_list = []

    # Initialize Epistemic Swarm Engine
    memory_bus = EpistemicMemoryBus()
    scheduler = RecursiveTaskScheduler(memory_bus=memory_bus)
    arbiter = EpistemicGapArbiter(memory_bus=memory_bus)

    t_start_total = time.perf_counter()

    for idx, prob in enumerate(test_slice, 1):
        print(f"[{idx}/{len(test_slice)}] {prob.question_id}: {prob.question_title} ({prob.difficulty.value})")
        meta_extra = {}

        if args.pipeline == "recursive_swarm":
            t_prob_start = time.perf_counter()
            def local_gen(prompt):
                r = generate_clean_solution(
                    problem_text=prompt,
                    starter_code=prob.starter_code,
                    mode=args.mode,
                    use_ast_contracts=False,
                    is_competitive_io=True
                )
                return r.get("code", "")

            swarm_res = asyncio.run(scheduler.execute_task(
                task_spec=prob.question_content,
                mode="auto",
                code_generator=local_gen
            ))
            raw_code = swarm_res.get("code", "")
            synth_res = arbiter.synthesize_and_verify(raw_code, prob.question_content)
            code = synth_res.get("code", raw_code)
            latency = round(time.perf_counter() - t_prob_start, 2)
            tokens = len(code.split())
        elif args.pipeline == "unified":
            res = generate_optimized_solution(
                problem_text=prob.question_content,
                starter_code=prob.starter_code,
                mode=args.mode,
                is_competitive_io=True,
            )
            code = res.get("code", "")
            latency = res.get("latency_sec", 0.0)
            tokens = res.get("tokens", 0)
        elif args.pipeline in ("clean", "contracts"):
            res = generate_clean_solution(
                problem_text=prob.question_content,
                starter_code=prob.starter_code,
                mode=args.mode,
                use_ast_contracts=(args.pipeline == "contracts"),
                is_competitive_io=True,
            )
            code = res.get("code", "")
            latency = res.get("latency_sec", 0.0)
            tokens = res.get("tokens", 0)
            meta_extra = {}
        elif args.pipeline == "mathematical_induction":
            res = generate_mathematical_induction_solution(
                prob=prob,
                model=args.model,
                mode=args.mode,
            )
            code = res.get("code", "")
            latency = res.get("latency_sec", 0.0)
            tokens = res.get("tokens", 0)
            meta_extra = {
                "backtracked": False,
                "repaired": False,
                "sample_passed": None,
            }
        else:
            meta_extra = {}
            prompt = (
                f"You are an expert competitive programmer. Solve the following problem in Python 3.\n\n"
                f"PROBLEM:\n{prob.question_content}\n\n"
            )
            if prob.starter_code:
                prompt += f"STARTER CODE:\n```python\n{prob.starter_code}\n```\n\n"
                prompt += (
                    "Implement the complete solution inside the provided starter template. "
                    "Output ONLY the code inside a standard ```python block."
                )
            else:
                prompt += (
                    "Write the complete solution reading from standard input (sys.stdin.read().split()) "
                    "and printing to standard output as required by the problem. "
                    "Output ONLY the code inside a standard ```python block."
                )

            res = query_ollama(
                model=args.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an elite competitive programmer. Return only clean, correct Python code inside a ```python block.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            raw_code = res.get("content", "")
            code = extract_code(raw_code, LMStyle.OpenAIChat) or extract_code_block(raw_code)
            latency = res.get("latency_sec", 0.0)
            tokens = res.get("tokens", 0)

        tok_speed = round(tokens / latency, 1) if latency > 0 else 0.0
        print(f"  ⚡ Synthesized in {latency}s ({tokens} tokens @ {tok_speed} tok/s) | Length: {len(code)} chars")

        samples_list.append(prob.get_evaluation_sample())
        generations_list.append([code])
        metadata_list.append({
            "question_id": prob.question_id,
            "question_title": prob.question_title,
            "difficulty": prob.difficulty.value,
            "latency_sec": latency,
            "tokens": tokens,
            "code": code,
            **meta_extra,
        })

    total_generation_time = round(time.perf_counter() - t_start_total, 2)
    print(f"\n✅ All {len(test_slice)} solutions generated in {total_generation_time}s (Avg: {total_generation_time/len(test_slice):.2f}s/prob).")
    print("\n▶ Running Official LiveCodeBench Execution Test Suites...")

    t_eval_start = time.perf_counter()
    metrics, graded_results, _ = codegen_metrics(
        samples_list,
        generations_list,
        k_list=[1],
        num_process_evaluate=4,
        timeout=6,
    )
    eval_duration = round(time.perf_counter() - t_eval_start, 2)
    print(f"✅ Sandbox execution completed in {eval_duration}s.")

    # Breakdown by difficulty
    stats_by_diff = {"easy": [0, 0], "medium": [0, 0], "hard": [0, 0]}
    detailed_problems = []

    print("\n" + "=" * 72)
    print("📊 LIVECODEBENCH BENCHMARK RESULTS")
    print("=" * 72)
    pass_at_1 = float(metrics.get("pass@1", 0.0))
    print(f"Overall Pass@1: {pass_at_1 * 100:.1f}%\n")

    for idx, (prob, meta) in enumerate(zip(test_slice, metadata_list)):
        res_list = graded_results.get(idx, [])
        all_passed = bool(res_list and all(x > 0 for x in res_list[0]) and len(res_list[0]) > 0) if res_list else False
        status = "✅ PASS" if all_passed else "❌ FAIL"
        passed_cases = sum(1 for x in res_list[0] if x > 0) if res_list else 0
        total_cases = len(res_list[0]) if res_list else 0

        diff = prob.difficulty.value
        if diff in stats_by_diff:
            stats_by_diff[diff][1] += 1
            if all_passed:
                stats_by_diff[diff][0] += 1

        print(f"  [{status}] {prob.question_id:<12}: {prob.question_title[:28]:<28} ({diff:<6}) | Tests: {passed_cases}/{total_cases} ({meta['latency_sec']}s)")

        meta["passed"] = all_passed
        meta["passed_cases"] = passed_cases
        meta["total_cases"] = total_cases
        detailed_problems.append(meta)

    print("\n" + "-" * 72)
    print("📈 BREAKDOWN BY DIFFICULTY:")
    for diff, (passed_cnt, tot_cnt) in stats_by_diff.items():
        if tot_cnt > 0:
            rate = (passed_cnt / tot_cnt) * 100
            print(f"  • {diff.upper():<7}: {passed_cnt}/{tot_cnt} Passed ({rate:.1f}%)")
    print(f"\nTotal Wall-Clock Time: {total_generation_time + eval_duration:.1f}s")
    print("=" * 72)

    # Persist results to disk
    if os.path.isabs(output_path):
        out_file = output_path
    else:
        out_file = os.path.join(MODEL_CREATOR_DIR, output_path)
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    report = {
        "benchmark": "LiveCodeBench",
        "model": args.model,
        "subset": args.subset,
        "pipeline": args.pipeline,
        "decoding_mode": args.mode,
        "problem_count": len(test_slice),
        "overall_pass_at_1": pass_at_1,
        "difficulty_breakdown": stats_by_diff,
        "timing": {
            "generation_sec": total_generation_time,
            "evaluation_sec": eval_duration,
            "total_sec": total_generation_time + eval_duration,
        },
        "telemetry": memory_bus.get_telemetry(),
        "problems": detailed_problems,
    }
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n📄 Saved full evaluation report to: {out_file}\n")


if __name__ == "__main__":
    main()
