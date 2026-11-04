#!/usr/bin/env python3
"""2-Stage Cognitive Decomposition & Reflexion Pipeline (ApexDeepCoder).

Combines:
1. Stage 1 (Algorithmic Invariant Planner): ApexThink-14B (DeepSeek-R1-14B)
   defines state invariants, edge cases, and algorithm blueprint.
2. Stage 2 (Code Generator): ApexCode-14B (Qwen2.5-Coder-14B)
   synthesizes production-grade code with types and unit tests.
3. Stage 3 (Reflexion Self-Repair): Sandboxed AST & execution verification
   with automated error feedback loop.
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import psutil

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
THINK_MODEL = os.environ.get("THINK_MODEL", "apex-think-14b")
CODE_MODEL = os.environ.get("CODE_MODEL", "apex-coder-14b")


def get_memory_usage() -> dict:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "used_gb": round(mem.used / 1024**3, 2),
        "total_gb": round(mem.total / 1024**3, 2),
        "percent": mem.percent,
        "swap_used_mb": round(swap.used / 1024**2, 2),
    }


def query_ollama(model: str, messages: list, temperature: float = 0.2, max_tokens: int = 1024) -> dict:
    url = f"{OLLAMA_URL}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - t0
            return {
                "content": data["choices"][0]["message"]["content"],
                "tokens": data.get("usage", {}).get("completion_tokens", 0),
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


def extract_code_block(text: str) -> str:
    """Extract code from markdown code fences or return raw text."""
    if "```python" in text:
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    if "```" in text:
        match = re.search(r"```[a-zA-Z]*\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()


def verify_and_execute_code(code_str: str, timeout_sec: int = 10) -> dict:
    """Verify code using Python AST and execute in a sandboxed temporary file."""
    # Step 1: AST Syntax Check
    try:
        ast.parse(code_str)
    except SyntaxError as e:
        return {
            "ast_valid": False,
            "executed": False,
            "passed": False,
            "error": f"SyntaxError on line {e.lineno}: {e.msg}",
            "traceback": f"SyntaxError: {e.msg} at line {e.lineno}, offset {e.offset}\n{e.text}",
        }

    # Step 2: Sandboxed Local Subprocess Execution
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(code_str)
        tmp_path = tmp.name

    try:
        res = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        passed = (res.returncode == 0)
        return {
            "ast_valid": True,
            "executed": True,
            "passed": passed,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "error": None if passed else f"Runtime error (exit code {res.returncode}):\n{res.stderr.strip()}",
        }
    except subprocess.TimeoutExpired:
        return {
            "ast_valid": True,
            "executed": True,
            "passed": False,
            "error": f"Execution timed out after {timeout_sec} seconds (possible deadlock or infinite loop)",
        }
    except Exception as e:
        return {
            "ast_valid": True,
            "executed": False,
            "passed": False,
            "error": f"Execution failed: {str(e)}",
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def run_deepcoder_pipeline(
    prompt: str,
    max_repair_attempts: int = 2,
    verbose: bool = True,
) -> dict:
    """Run full 2-stage planning, code generation, and reflexion repair."""
    pipeline_start = time.perf_counter()
    mem_initial = get_memory_usage()

    if verbose:
        print("\n" + "=" * 64)
        print("🧠 [ApexDeepCoder] 2-Stage Cognitive Decomposition Pipeline")
        print(f"Task: {prompt[:80]}...")
        print(f"Initial Memory: {mem_initial['used_gb']} GB / {mem_initial['total_gb']} GB")
        print("=" * 64)

    # -------------------------------------------------------------
    # STAGE 1: Algorithmic Invariant Planning (ApexThink-14B)
    # -------------------------------------------------------------
    if verbose:
        print("\n▶ STAGE 1: Algorithmic Invariant Planning (ApexThink-14B)...")

    stage1_sys = (
        "You are an expert algorithms and systems architect. "
        "Analyze the user's programming problem. In concise bullet points: "
        "1. Define the core state invariants and concurrency requirements. "
        "2. Identify tricky edge cases (empty states, boundary limits, race conditions). "
        "3. Provide the step-by-step algorithm and data structure blueprint. "
        "Do NOT write full code implementation here; focus on the invariant logic and blueprint."
    )
    stage1_res = query_ollama(
        model=THINK_MODEL,
        messages=[
            {"role": "system", "content": stage1_sys},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=896,
    )
    plan_content = stage1_res["content"]
    if verbose:
        print(f"  ✅ Planning completed in {stage1_res['latency_sec']}s ({stage1_res['tokens']} tokens).")

    # -------------------------------------------------------------
    # STAGE 2: Code Synthesis (ApexCode-14B)
    # -------------------------------------------------------------
    if verbose:
        print("\n▶ STAGE 2: Production Code Synthesis (ApexCode-14B)...")

    stage2_sys = (
        "You are a principal software engineer. Implement the solution strictly following "
        "the provided architectural blueprint and invariants.\n"
        "Requirements:\n"
        "- Clean, production-ready Python with full type annotations\n"
        "- Thread safety with locks/conditions where needed\n"
        "- Detailed docstrings\n"
        "- In tests, use sub-second timings (e.g. time.sleep(0.02) or small intervals) so tests run swiftly\n"
        "- For queries returning unordered collections, compare using set(actual) == set(expected)\n"
        "- A self-contained test suite with assert statements verifying edge cases\n"
        "Return the code inside a standard ```python block."
    )
    stage2_prompt = (
        f"PROBLEM:\n{prompt}\n\n"
        f"ARCHITECTURAL BLUEPRINT & INVARIANTS:\n{plan_content}\n\n"
        "Implement the complete, self-contained solution with executable tests now:"
    )
    stage2_res = query_ollama(
        model=CODE_MODEL,
        messages=[
            {"role": "system", "content": stage2_sys},
            {"role": "user", "content": stage2_prompt},
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    code_content = stage2_res["content"]
    extracted_code = extract_code_block(code_content)
    if verbose:
        print(f"  ✅ Initial code generated in {stage2_res['latency_sec']}s ({stage2_res['tokens']} tokens).")

    # -------------------------------------------------------------
    # STAGE 3: Reflexion & Execution-Guided Self-Repair
    # -------------------------------------------------------------
    if verbose:
        print("\n▶ STAGE 3: Reflexion Verification & Execution Feedback...")

    exec_result = verify_and_execute_code(extracted_code, timeout_sec=10)
    repair_count = 0
    repair_history = []

    while not exec_result["passed"] and repair_count < max_repair_attempts:
        repair_count += 1
        err_msg = exec_result.get("error", "Unknown error")
        if verbose:
            print(f"  ⚠️ Test/Syntax failure detected (Attempt {repair_count}/{max_repair_attempts}):")
            print(f"     {err_msg[:120]}...")
            print("  🔄 Feeding error traceback back to ApexCode-14B for self-repair...")

        repair_prompt = (
            f"Your previous Python code failed verification with the following error:\n\n"
            f"```\n{err_msg}\n```\n\n"
            f"PREVIOUS CODE:\n```python\n{extracted_code}\n```\n\n"
            "Analyze the failure, fix the root cause, ensure all string literals and blocks are properly closed, "
            "and return the corrected self-contained Python code inside a ```python block."
        )
        repair_res = query_ollama(
            model=CODE_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert debugger. Fix the provided code so it passes all tests."},
                {"role": "user", "content": repair_prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        extracted_code = extract_code_block(repair_res["content"])
        exec_result = verify_and_execute_code(extracted_code)
        repair_history.append({
            "attempt": repair_count,
            "error_repaired": err_msg,
            "success": exec_result["passed"],
        })

    if verbose:
        if exec_result["passed"]:
            print(f"  ✅ Verification PASSED! (AST valid: True, Tests passed: True, Repairs: {repair_count})")
        else:
            print(f"  ❌ Verification failed after {repair_count} repairs: {exec_result.get('error')[:100]}")

    total_latency = round(time.perf_counter() - pipeline_start, 2)
    mem_final = get_memory_usage()

    return {
        "prompt": prompt,
        "plan": plan_content,
        "final_code": extracted_code,
        "ast_valid": exec_result.get("ast_valid", False),
        "tests_passed": exec_result.get("passed", False),
        "execution_details": exec_result,
        "repairs_performed": repair_count,
        "repair_history": repair_history,
        "latency_sec": {
            "stage1_plan": stage1_res["latency_sec"],
            "stage2_code": stage2_res["latency_sec"],
            "total": total_latency,
        },
        "tokens_generated": stage1_res["tokens"] + stage2_res["tokens"],
        "memory": {
            "initial_ram_gb": mem_initial["used_gb"],
            "final_ram_gb": mem_final["used_gb"],
            "swap_used_mb": mem_final["swap_used_mb"],
        },
    }


def main():
    test_prompt = (
        "Implement a thread-safe BoundedBlockingQueue in Python with max_capacity. "
        "Include enqueue(), dequeue(), size(), and close() methods using threading.Condition. "
        "When closed, all waiting dequeue() calls must raise a QueueClosedError. "
        "Include executable unit tests verifying timeout, capacity blocking, and clean shutdown."
    )
    res = run_deepcoder_pipeline(test_prompt)
    print("\n" + "=" * 64)
    print(f"RESULT SUMMARY: {'PASS' if res['tests_passed'] else 'FAIL'}")
    print(f"Total Latency: {res['latency_sec']['total']}s")
    print(f"Tokens: {res['tokens_generated']}")
    print(f"RAM Used: {res['memory']['final_ram_gb']} GB (Swap: {res['memory']['swap_used_mb']} MB)")
    print("=" * 64)


if __name__ == "__main__":
    main()
