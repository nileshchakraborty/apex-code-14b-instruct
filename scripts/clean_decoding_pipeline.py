#!/usr/bin/env python3
"""Calibrated Clean Decoding Pipeline for Zero-Shot Code Generation.

Provides:
1. Calibrated decoding configurations (greedy argmax temp=0.0 or Min-P min_p=0.05)
2. Competitive programming Python scaffolding (fast I/O tokenization, recursion limit)
3. AST Contract-guided prompt construction (binding preconditions/postconditions)
4. Pure unassisted zero-shot generation (0 test execution during inference)
"""

import ast
import json
import re
import sys
import time
import urllib.request
from typing import Dict, Any, Optional

try:
    from scripts.ast_contract_compiler import (
        get_ast_contract_prompt_instruction,
        verify_contract_coverage,
    )
    from scripts.repo_graph_extractor import RepoGraphExtractor
except ImportError:
    from ast_contract_compiler import (
        get_ast_contract_prompt_instruction,
        verify_contract_coverage,
    )
    from repo_graph_extractor import RepoGraphExtractor

OLLAMA_API_URL = "http://127.0.0.1:11434/api/chat"
CODE_MODEL = "apex-coder-14b"
THINK_MODEL = "apex-think-14b"


# ==============================================================================
# COMPETITIVE PYTHON RUNTIME SCAFFOLDING
# ==============================================================================

COMPETITIVE_SCAFFOLDING = (
    "COMPETITIVE PYTHON PRODUCTION CONSTRAINTS:\n"
    "1. Fast Bulk I/O: For problems reading from standard input, tokenize bulk data with `sys.stdin.read().split()` to prevent TLE on N=10^5.\n"
    "2. Recursion Limit: If using recursive DFS or tree traversals, always include `sys.setrecursionlimit(300_000)`.\n"
    "3. Integer Safety: Python handles arbitrary-precision integers natively; avoid floating-point division when integer division `//` is required.\n"
    "4. Clean Entrypoint: Wrap the solver in a `def solve():` function and call it under `if __name__ == '__main__':`.\n"
)


# ==============================================================================
# INFERENCE QUERY ENGINE
# ==============================================================================

def query_calibrated_model(
    prompt: str,
    system_prompt: Optional[str] = None,
    mode: str = "greedy",  # "greedy" (temp=0.0) or "calibrated" (temp=0.2, min_p=0.05)
    model: str = CODE_MODEL,
    max_tokens: int = 1536,
    num_ctx: int = 16384,
) -> Dict[str, Any]:
    """Execute clean, unassisted inference using calibrated decoding parameters."""
    if system_prompt is None:
        system_prompt = (
            "You are an elite competitive programmer and systems software engineer. "
            "Write production-grade, mathematically optimal Python 3 code. "
            "Output ONLY the complete solution inside a single ```python block."
        )

    options: Dict[str, Any] = {
        "num_predict": max_tokens,
        "num_ctx": num_ctx,
    }

    if mode == "greedy":
        options["temperature"] = 0.0
        options["top_p"] = 1.0
    elif mode == "calibrated":
        options["temperature"] = 0.2
        options["min_p"] = 0.05
        options["top_p"] = 0.95
    else:
        options["temperature"] = 0.2

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": options,
    }

    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - t0
            content = data.get("message", {}).get("content", "")
            tokens = data.get("eval_count", 0)
            return {
                "content": content,
                "tokens": tokens,
                "latency_sec": round(latency, 2),
                "error": None,
            }
    except Exception as e:
        return {
            "content": "",
            "tokens": 0,
            "latency_sec": round(time.perf_counter() - t0, 2),
            "error": str(e),
        }


def extract_python_code(text: str) -> str:
    """Extract code from ```python markdown fences or return raw text."""
    if "```python" in text:
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    if "```" in text:
        match = re.search(r"```[a-zA-Z]*\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()


# ==============================================================================
# PIPELINE ENTRYPOINT
# ==============================================================================

def generate_clean_solution(
    problem_text: str,
    starter_code: Optional[str] = None,
    repo_context: Optional[str] = None,
    mode: str = "greedy",
    use_ast_contracts: bool = False,
    is_competitive_io: bool = True,
) -> Dict[str, Any]:
    """Generate a clean zero-shot solution with optional AST contracts, repo context, and competitive scaffolding."""
    prompt_parts = []

    if repo_context and repo_context.strip():
        prompt_parts.append(f"{repo_context.strip()}\n")

    prompt_parts.append(f"PROBLEM SPECIFICATION:\n{problem_text}\n")

    if starter_code and starter_code.strip():
        prompt_parts.append(f"STARTER CODE TEMPLATE:\n```python\n{starter_code}\n```\n")

    if is_competitive_io:
        prompt_parts.append(COMPETITIVE_SCAFFOLDING)

    if use_ast_contracts:
        prompt_parts.append(get_ast_contract_prompt_instruction(include_runtime=True))

    full_prompt = "\n".join(prompt_parts)

    res = query_calibrated_model(
        prompt=full_prompt,
        mode=mode,
        model=CODE_MODEL,
    )

    code = extract_python_code(res.get("content", ""))

    # Validate AST validity
    ast_valid = False
    ast_error = None
    try:
        ast.parse(code)
        ast_valid = True
    except SyntaxError as e:
        ast_error = f"Line {e.lineno}: {e.msg}"

    contract_report = None
    if use_ast_contracts and ast_valid:
        contract_report = verify_contract_coverage(code)

    return {
        "code": code,
        "ast_valid": ast_valid,
        "ast_error": ast_error,
        "latency_sec": res.get("latency_sec", 0.0),
        "tokens": res.get("tokens", 0),
        "mode": mode,
        "contract_report": contract_report,
    }


def _test_pipeline():
    print("🧪 Testing Clean Decoding Pipeline (Greedy argmax, temp=0.0)...")
    prob = (
        "Given a list of positive integers nums, find the maximum product of any two distinct elements. "
        "Input: reads t test cases from stdin. Output: prints result for each testcase."
    )
    res = generate_clean_solution(prob, mode="greedy", is_competitive_io=True)
    print(f"  Generated in {res['latency_sec']}s ({res['tokens']} tokens). AST Valid: {res['ast_valid']}")
    assert res["ast_valid"] is True
    print("  Code Preview:\n", res["code"][:180], "...\n")

    print("🧪 Testing Multi-File Context Injection...")
    extractor = RepoGraphExtractor(".")
    extractor.scan_repository(subdirs=["scripts"])
    header = extractor.get_interface_header(target_modules=["scripts.ast_contract_compiler"])
    print(f"  Extracted typed interface header ({len(header)} chars).")
    assert "class ContractVisitor" in header
    print("🎉 Clean Decoding Pipeline verified with multi-file AST context!")


if __name__ == "__main__":
    _test_pipeline()
