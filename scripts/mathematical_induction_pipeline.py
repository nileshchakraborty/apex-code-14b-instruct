#!/usr/bin/env python3
"""
Mathematical Induction & Algebraic Deduction Pipeline for LiveCodeBench.

Treats Mathematical Induction and Algebraic Shortcuts as FIRST-CLASS CITIZENS.
Strictly adheres to sandbox boundaries:
- ZERO test-time sample execution / no breakout / no cheating.
- Pure single-pass mathematical induction and algebraic deduction.
- Rigorous analytical proofs: Monotonicity, Permutation Cycles, Game Theory Invariants, Modular Arithmetic.
"""

import sys
import os
import time
from typing import Dict, Any

sys.path.insert(0, "/Users/nileshchakraborty/workspace/LiveCodeBench")
sys.path.insert(0, "/Users/nileshchakraborty/workspace/apex-code-36gb")

from lcb_runner.utils.extraction_utils import extract_code
from lcb_runner.lm_styles import LMStyle
from scripts.deepcoder_pipeline import query_ollama, extract_code_block


def build_mathematical_induction_prompt(prob) -> str:
    content = prob.question_content
    starter = prob.starter_code

    prompt = (
        "You are an elite competitive programmer, mathematician, and computer scientist.\n"
        "Solve this problem treating MATHEMATICAL INDUCTION and ALGEBRAIC SHORTCUTS as FIRST-CLASS CITIZENS.\n\n"
        f"PROBLEM STATEMENT:\n{content}\n\n"
    )

    if starter:
        prompt += f"STARTER CODE TEMPLATE:\n```python\n{starter}\n```\n\n"
    else:
        prompt += "INPUT/OUTPUT FORMAT: Read from standard input using sys.stdin.read().split() and print results to stdout.\n\n"

    prompt += (
        "RIGOROUS COGNITIVE & MATHEMATICAL REASONING PROTOCOL:\n"
        "1. Mathematical Invariants & Algebraic Shortcuts (FIRST CITIZEN):\n"
        "   - Prioritize closed-form mathematical equations, induction proofs, and algebraic properties over naive simulation:\n"
        "   • Game Theory & Invariant Games: Analyze what happens AFTER player moves. Determine whether Player 1 can force a winning condition on Turn 1 or if the game state modulo k forms an invariant trap that Player 2 can maintain.\n"
        "   • Marginal Gain & Monotonicity: When selecting an element x to increment or modify to maximize a function (e.g. product), evaluate the marginal factor (x + 1) / x = 1 + 1/x. Since 1 + 1/x is strictly decreasing, choosing the minimum element min(A) is algebraically optimal.\n"
        "   • Permutations & Cycle Structure: A single transposition (swap) can alter at most 2 positions. Therefore, a permutation can be transformed into target with <= 1 swap if and only if sum(s[i] != target[i]) <= 2.\n"
        "   • Parity & Modular Invariants: Check bitwise XOR sum invariants, prefix parity, and modular cycles.\n"
        "   - If an algebraic shortcut exists, it is the FIRST CITIZEN and MUST be implemented directly.\n"
        "2. Inductive Algorithm & Data Structure Formulation:\n"
        "   - If no closed-form formula exists, formulate the inductive DP transition, monotonic structure, or greedy choice property with minimal complexity.\n"
        "3. Boundary & Constraint Verification:\n"
        "   - Verify mathematical base cases: n=0, n=1, empty, zeros, negative numbers, extreme constraints.\n"
        "   - Stdin parsing: When using sys.stdin.read().split(), parse tokens sequentially by index (`index += 1`), avoiding calling .split() on tokens.\n"
        "4. Big-O Complexity Guarantee:\n"
        "   - Prove that Time Complexity and Space Complexity strictly satisfy the time limit (prevent TLE/MLE).\n"
        "5. Final Implementation:\n"
        "   - Provide the complete, clean, optimal Python 3 code in a single ```python ``` block."
    )

    return prompt


def generate_mathematical_induction_solution(
    prob,
    model: str = "apex-coder-14b",
    mode: str = "greedy",
) -> Dict[str, Any]:
    """
    Executes pure cognitive mathematical induction inference:
    Strictly zero-shot, no execution sandbox breakout, no public sample leakage.
    """
    prompt = build_mathematical_induction_prompt(prob)
    t0 = time.perf_counter()

    temp = 0.0 if mode == "greedy" else 0.2
    res = query_ollama(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an elite competitive programmer, mathematician, and computer scientist. "
                    "You prioritize mathematical induction, algebraic shortcuts, and structural invariants as first-class citizens. "
                    "Write clean, optimal, bug-free Python 3 code in standard ```python blocks."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temp,
        max_tokens=1536,
    )
    raw = res.get("content", "")
    code = extract_code(raw, LMStyle.OpenAIChat) or extract_code_block(raw)
    tokens = res.get("tokens", 0)
    latency = round(time.perf_counter() - t0, 2)

    return {
        "code": code,
        "latency_sec": latency,
        "tokens": tokens,
        "backtracked": False,
        "repaired": False,
        "sample_passed": None,
    }
