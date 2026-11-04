#!/usr/bin/env python3
"""Unified Research Optimization Pipeline for Autonomous Code Generation.

Combines all research-backed pillars into a single end-to-end inference engine:
1. Dual-Phase Invariant Induction (System 2 algebraic & simulation analysis)
2. Calibrated Decoding & Competitive Scaffolding (fast bulk I/O, __main__ isolation)
3. Static Semantic AST Bug Scanner (Kadane clamp, negative stride parity audit)
4. Canonical AST Consensus Voting (K=3 unsupervised structural agreement)
5. Multi-File Repository Interface Context Extractor (sub-1,500 token .pyi stubs)
"""

import ast
import json
import re
import sys
import time
from typing import Dict, Any, Optional, List

try:
    from scripts.invariant_induction_pipeline import extract_problem_invariants, synthesize_grounded_code
    from scripts.ast_contract_compiler import audit_semantic_bugs, verify_contract_coverage
    from scripts.ast_consensus_voter import select_consensus_candidate, compute_canonical_ast_hash
    from scripts.clean_decoding_pipeline import CODE_MODEL
except ImportError:
    from invariant_induction_pipeline import extract_problem_invariants, synthesize_grounded_code
    from ast_contract_compiler import audit_semantic_bugs, verify_contract_coverage
    from ast_consensus_voter import select_consensus_candidate, compute_canonical_ast_hash
    from clean_decoding_pipeline import CODE_MODEL


def generate_optimized_solution(
    problem_text: str,
    starter_code: Optional[str] = None,
    repo_context: Optional[str] = None,
    mode: str = "greedy",  # "greedy" (fast dual-phase) or "consensus" (K=3 voting)
    max_ast_repairs: int = 1,
    is_competitive_io: bool = True,
    model: str = CODE_MODEL,
) -> Dict[str, Any]:
    """Generate a solution combining all research-backed code generation optimizations."""
    t0 = time.perf_counter()

    # Step 1: Phase 1 Invariant Induction (System 2)
    p1_res = extract_problem_invariants(
        problem_text=problem_text,
        starter_code=starter_code,
        model=model,
    )
    invariants = p1_res.get("analysis", "")

    # Step 2: Synthesis & Consensus
    candidates: List[str] = []
    tokens_used = p1_res.get("tokens", 0)

    if mode == "consensus":
        # Generate K=3 candidates with calibrated Min-P sampling
        for _ in range(3):
            cand_res = synthesize_grounded_code(
                problem_text=problem_text,
                invariants=invariants,
                starter_code=starter_code,
                repo_context=repo_context,
                mode="calibrated",
                model=model,
                is_competitive_io=is_competitive_io,
            )
            candidates.append(cand_res["code"])
            tokens_used += cand_res.get("tokens", 0)

        consensus = select_consensus_candidate(candidates)
        primary_code = consensus["winner_code"]
        consensus_strength = consensus["consensus_strength"]
    else:
        # Fast greedy argmax pass
        cand_res = synthesize_grounded_code(
            problem_text=problem_text,
            invariants=invariants,
            starter_code=starter_code,
            repo_context=repo_context,
            mode="greedy",
            model=model,
            is_competitive_io=is_competitive_io,
        )
        primary_code = cand_res["code"]
        tokens_used += cand_res.get("tokens", 0)
        consensus_strength = 1.0

    # Step 3: Semantic AST Bug Audit
    semantic_report = audit_semantic_bugs(primary_code)
    contract_report = verify_contract_coverage(primary_code)

    # Step 4: Closed-Loop AST Repair (if semantic bug detected)
    repair_count = 0
    if not semantic_report["clean"] and max_ast_repairs > 0:
        bug_feedback = "\n".join(f"- {b}" for b in semantic_report["bugs"])
        repair_prompt = (
            f"{problem_text}\n\n"
            f"PREVIOUS DRAFT HAS SEMANTIC DEFECTS DETECTED BY AST LINTER:\n"
            f"{bug_feedback}\n\n"
            f"Fix these specific defects while strictly preserving all other logic. Output the revised ```python solution."
        )
        repaired_res = synthesize_grounded_code(
            problem_text=repair_prompt,
            invariants=invariants,
            starter_code=starter_code,
            repo_context=repo_context,
            mode="greedy",
            model=model,
            is_competitive_io=is_competitive_io,
        )
        # Check if repaired code has valid syntax
        if repaired_res["ast_valid"]:
            repaired_report = audit_semantic_bugs(repaired_res["code"])
            if len(repaired_report["bugs"]) < len(semantic_report["bugs"]):
                primary_code = repaired_res["code"]
                semantic_report = repaired_report
                repair_count += 1
                tokens_used += repaired_res.get("tokens", 0)

    total_time = round(time.perf_counter() - t0, 2)

    return {
        "code": primary_code,
        "ast_valid": semantic_report.get("ast_valid", True),
        "semantic_clean": semantic_report.get("clean", True),
        "semantic_bugs": semantic_report.get("bugs", []),
        "contract_density": contract_report.get("contract_density", 0.0),
        "consensus_strength": consensus_strength,
        "repair_count": repair_count,
        "invariants_summary": invariants[:300] + "..." if len(invariants) > 300 else invariants,
        "latency_sec": total_time,
        "tokens": tokens_used,
        "mode": mode,
    }


def _test_unified_pipeline():
    print("🧪 Testing Unified Research Optimization Pipeline...")
    prob_text = (
        "Given an integer array nums, find the subarray with the largest sum, and return its sum. "
        "The subarray elements can be both positive and negative."
    )
    res = generate_optimized_solution(prob_text, mode="greedy", is_competitive_io=True)
    print(f"  Generated in {res['latency_sec']}s ({res['tokens']} tokens). AST Valid: {res['ast_valid']}")
    print(f"  Semantic Clean: {res['semantic_clean']} (Bugs: {res['semantic_bugs']})")
    print(f"  Repairs: {res['repair_count']}")
    assert res["ast_valid"] is True
    print("  Code Preview:\n", res["code"][:250], "...\n")
    print("🎉 Unified Research Optimization Pipeline verified successfully!")


if __name__ == "__main__":
    _test_unified_pipeline()
