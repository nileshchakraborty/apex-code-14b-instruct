#!/usr/bin/env python3
"""2-Stage Cognitive Decomposition & Reflexion Pipeline (ApexDeepCoder).

Production-grade implementation featuring:
1. Stage 1: SSIB (Structured Semantic Invariant Block) via ApexThink-14B (DeepSeek-R1-14B)
2. Stage 2: Dual-Track Brute-Force Oracle Property Synthesis via ApexCode-14B (Qwen2.5-Coder-14B)
3. Stage 3: ACI (Agent-Computer Interface) Diagnostic Frame with 2-Tier AST Patch Escalation
4. Zero-Trust Sandboxed Execution via Docker Container with strict memory/CPU caps
5. Context-Adaptive KV-Cache Governance (4k Stage 1, 16k Stage 2)
"""

import ast
import json
import os
import re
import resource
import subprocess
import sys
import tempfile
import time
import urllib.request
import psutil

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
THINK_MODEL = os.environ.get("THINK_MODEL", "apex-think-14b")
CODE_MODEL = os.environ.get("CODE_MODEL", "apex-coder-14b")
DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE", "apex-code-36gb:latest")


def get_memory_usage() -> dict:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "used_gb": round(mem.used / 1024**3, 2),
        "total_gb": round(mem.total / 1024**3, 2),
        "percent": mem.percent,
        "swap_used_mb": round(swap.used / 1024**2, 2),
    }


def query_ollama(
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    num_ctx: int = 8192,
) -> dict:
    url = f"{OLLAMA_URL}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
        },
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


def parse_aci_diagnostic_frame(stderr: str, code_str: str) -> dict:
    """Parse runtime traceback into a structured Agent-Computer Interface (ACI) frame."""
    frame = {
        "status": "FAILED",
        "failure_type": "RuntimeError",
        "failing_function": None,
        "failing_line_number": None,
        "failing_code_snippet": None,
        "exception_message": "",
        "raw_traceback": stderr,
    }

    lines = stderr.strip().split("\n")
    if not lines:
        return frame

    # Extract last line (exception type and message)
    last_line = lines[-1].strip()
    frame["exception_message"] = last_line
    if ":" in last_line:
        frame["failure_type"] = last_line.split(":")[0].strip()

    # Search for failing function and line in user code
    code_lines = code_str.split("\n")
    for line in reversed(lines):
        match = re.search(r'File ".*?", line (\d+)(?:, in (\w+))?', line)
        if match:
            line_no = int(match.group(1))
            func_name = match.group(2)
            frame["failing_line_number"] = line_no
            if func_name and func_name != "<module>":
                frame["failing_function"] = func_name
            if 1 <= line_no <= len(code_lines):
                frame["failing_code_snippet"] = code_lines[line_no - 1].strip()
            break

    return frame


def verify_and_execute_code(code_str: str, timeout_sec: int = 15, use_docker: bool = True) -> dict:
    """Verify code using Python AST and execute in a sandboxed runtime (Docker or ulimit)."""
    # Step 1: AST Syntax Check
    try:
        ast.parse(code_str)
    except SyntaxError as e:
        return {
            "ast_valid": False,
            "executed": False,
            "passed": False,
            "error": f"SyntaxError on line {e.lineno}: {e.msg}",
            "aci_frame": {
                "status": "SYNTAX_ERROR",
                "failure_type": "SyntaxError",
                "failing_function": None,
                "failing_line_number": e.lineno,
                "failing_code_snippet": e.text.strip() if e.text else "",
                "exception_message": f"SyntaxError: {e.msg}",
            },
        }

    # Step 2: Sandboxed Execution via Docker Container (Primary Route)
    if use_docker:
        try:
            docker_cmd = [
                "docker", "run", "--rm", "-i",
                "--net=none",
                "--memory=512m",
                "--cpus=2.0",
                "--pids-limit=64",
                "--entrypoint", "python3",
                DOCKER_IMAGE,
                "-",
            ]
            res = subprocess.run(
                docker_cmd,
                input=code_str,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            passed = (res.returncode == 0)
            aci_frame = None if passed else parse_aci_diagnostic_frame(res.stderr, code_str)
            return {
                "ast_valid": True,
                "executed": True,
                "passed": passed,
                "sandbox": "docker",
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "error": None if passed else f"Runtime error (exit code {res.returncode}):\n{res.stderr.strip()}",
                "aci_frame": aci_frame,
            }
        except subprocess.TimeoutExpired:
            return {
                "ast_valid": True,
                "executed": True,
                "passed": False,
                "sandbox": "docker",
                "error": f"Execution timed out after {timeout_sec} seconds (possible deadlock or infinite loop)",
                "aci_frame": {
                    "status": "TIMEOUT",
                    "failure_type": "TimeoutExpired",
                    "exception_message": f"Execution exceeded {timeout_sec}s timeout boundary",
                },
            }
        except Exception:
            # Fall through to host subprocess with ulimit fallback
            pass

    # Step 3: Fallback Sandboxed Local Subprocess Execution (with resource limits)
    def set_resource_limits():
        try:
            # 1 GB virtual memory cap
            resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
        except Exception:
            pass
        try:
            # 12 second CPU execution cap
            resource.setrlimit(resource.RLIMIT_CPU, (timeout_sec + 2, timeout_sec + 4))
        except Exception:
            pass

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(code_str)
        tmp_path = tmp.name

    try:
        res = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            preexec_fn=set_resource_limits if os.name != "nt" else None,
        )
        passed = (res.returncode == 0)
        aci_frame = None if passed else parse_aci_diagnostic_frame(res.stderr, code_str)
        return {
            "ast_valid": True,
            "executed": True,
            "passed": passed,
            "sandbox": "host_subprocess_ulimit",
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "error": None if passed else f"Runtime error (exit code {res.returncode}):\n{res.stderr.strip()}",
            "aci_frame": aci_frame,
        }
    except subprocess.TimeoutExpired:
        return {
            "ast_valid": True,
            "executed": True,
            "passed": False,
            "sandbox": "host_subprocess_ulimit",
            "error": f"Execution timed out after {timeout_sec} seconds (possible deadlock or infinite loop)",
            "aci_frame": {
                "status": "TIMEOUT",
                "failure_type": "TimeoutExpired",
                "exception_message": f"Execution exceeded {timeout_sec}s timeout boundary",
            },
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class FunctionReplacer(ast.NodeTransformer):
    """AST transformer that splices a single target FunctionDef with a new implementation."""
    def __init__(self, target_func_name: str, new_func_node: ast.AST):
        self.target_func_name = target_func_name
        self.new_func_node = new_func_node
        self.replaced = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name == self.target_func_name:
            self.replaced = True
            return self.new_func_node
        self.generic_visit(node)
        return node


def patch_function_ast(original_code: str, target_func_name: str, new_func_code: str) -> str:
    """Surgically replace a single function definition inside the AST tree."""
    tree = ast.parse(original_code)
    new_tree = ast.parse(new_func_code)

    # Extract the new function node
    new_func_node = None
    for n in ast.walk(new_tree):
        if isinstance(n, ast.FunctionDef) and n.name == target_func_name:
            new_func_node = n
            break

    if new_func_node is None:
        raise ValueError(f"New function code does not contain definition for '{target_func_name}'")

    replacer = FunctionReplacer(target_func_name, new_func_node)
    modified_tree = replacer.visit(tree)
    if not replacer.replaced:
        raise ValueError(f"Target function '{target_func_name}' not found in original AST")

    ast.fix_missing_locations(modified_tree)
    return ast.unparse(modified_tree)


def _run_effort_low(prompt: str, verbose: bool = True) -> dict:
    """Low Effort: Single-shot generation via ApexCode-14B with fast AST/Docker verification (~3-8s)."""
    t0 = time.perf_counter()
    mem_initial = get_memory_usage()
    if verbose:
        print("\n⚡ [ApexDeepCoder] Running LOW Effort Mode (Fast Single-Shot)...")

    sys_prompt = (
        "You are an expert Python engineer. Implement clean, robust, type-annotated Python code "
        "with self-contained executable unit tests. "
        "Keep tests under 0.1s. Return code inside a standard ```python block."
    )
    res = query_ollama(
        model=CODE_MODEL,
        messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500,
        num_ctx=8192,
    )
    code = extract_code_block(res["content"])
    exec_res = verify_and_execute_code(code, timeout_sec=15, use_docker=True)
    total_latency = round(time.perf_counter() - t0, 2)
    mem_final = get_memory_usage()

    if verbose:
        status_tag = "✅ PASSED" if exec_res["passed"] else "❌ FAILED"
        print(f"  {status_tag}: Low Effort Finished in {total_latency}s ({res['tokens']} tokens).")

    return {
        "prompt": prompt,
        "effort_level": "low",
        "plan": "N/A (Bypassed in Low Effort)",
        "final_code": code,
        "ast_valid": exec_res.get("ast_valid", False),
        "tests_passed": exec_res.get("passed", False),
        "sandbox_used": exec_res.get("sandbox", "unknown"),
        "repairs_performed": 0,
        "repair_history": [],
        "latency_sec": {"stage1_plan": 0.0, "stage2_code": res["latency_sec"], "total": total_latency},
        "tokens_generated": res["tokens"],
        "memory": {"initial_ram_gb": mem_initial["used_gb"], "final_ram_gb": mem_final["used_gb"], "swap_used_mb": mem_final["swap_used_mb"]},
    }


def _run_effort_medium(prompt: str, max_repair_attempts: int = 1, verbose: bool = True) -> dict:
    """Medium Effort: Single-pass In-Context SSIB priming + Docker sandbox verification (~15-22s)."""
    t0 = time.perf_counter()
    mem_initial = get_memory_usage()
    if verbose:
        print("\n🟡 [ApexDeepCoder] Running MEDIUM Effort Mode (In-Context SSIB Priming)...")

    sys_prompt = (
        "You are an elite principal algorithms engineer.\n"
        "Before writing code, output a compact 4-line SSIB INVARIANT CONTRACT defining:\n"
        "1. Core State Invariants & Boundary Truth Conditions\n"
        "2. Left and Right Pruning rules (for trees/intervals)\n"
        "3. Concurrency lock management ('with self._lock:')\n"
        "4. Dynamic Reference Oracle Pattern for tests\n"
        "Then implement the complete production class and self-contained executable oracle tests in a standard ```python block."
    )
    res = query_ollama(
        model=CODE_MODEL,
        messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
        num_ctx=8192,
    )
    code = extract_code_block(res["content"])
    exec_res = verify_and_execute_code(code, timeout_sec=15, use_docker=True)
    repair_count = 0
    repair_history = []

    while not exec_res["passed"] and repair_count < max_repair_attempts:
        repair_count += 1
        aci_frame = exec_res.get("aci_frame") or parse_aci_diagnostic_frame(exec_res.get("error", ""), code)
        if verbose:
            print(f"  ⚠️ Medium Mode Repair Attempt {repair_count}: {aci_frame.get('exception_message')[:70]}...")

        repair_prompt = (
            f"Your Python code failed verification with the following error:\n"
            f"Line {aci_frame.get('failing_line_number')}: {aci_frame.get('failing_code_snippet')}\n"
            f"Error: {aci_frame.get('exception_message')}\n\n"
            f"CURRENT CODE:\n```python\n{code}\n```\n\n"
            "Fix the root cause and return corrected code inside a ```python block."
        )
        rep_res = query_ollama(
            model=CODE_MODEL,
            messages=[{"role": "system", "content": "You are a code debugger. Fix the error."}, {"role": "user", "content": repair_prompt}],
            temperature=0.1,
            max_tokens=2048,
            num_ctx=8192,
        )
        code = extract_code_block(rep_res["content"])
        exec_res = verify_and_execute_code(code, timeout_sec=15, use_docker=True)
        repair_history.append({"attempt": repair_count, "aci_frame": aci_frame, "success": exec_res["passed"]})

    total_latency = round(time.perf_counter() - t0, 2)
    mem_final = get_memory_usage()

    if verbose:
        status_tag = "✅ PASSED" if exec_res["passed"] else "❌ FAILED"
        print(f"  {status_tag}: Medium Effort Finished in {total_latency}s ({res['tokens']} tokens).")

    return {
        "prompt": prompt,
        "effort_level": "medium",
        "plan": "In-Context SSIB Header",
        "final_code": code,
        "ast_valid": exec_res.get("ast_valid", False),
        "tests_passed": exec_res.get("passed", False),
        "sandbox_used": exec_res.get("sandbox", "unknown"),
        "repairs_performed": repair_count,
        "repair_history": repair_history,
        "latency_sec": {"stage1_plan": 0.0, "stage2_code": res["latency_sec"], "total": total_latency},
        "tokens_generated": res["tokens"],
        "memory": {"initial_ram_gb": mem_initial["used_gb"], "final_ram_gb": mem_final["used_gb"], "swap_used_mb": mem_final["swap_used_mb"]},
    }


def _run_effort_high(prompt: str, max_repair_attempts: int = 2, verbose: bool = True) -> dict:
    """High Effort: Full 2-Stage SSIB Invariants (ApexThink-14B) + Oracle Code (ApexCode-14B) + Reflexion (~45-65s)."""
    pipeline_start = time.perf_counter()
    mem_initial = get_memory_usage()

    if verbose:
        print("\n🔴 [ApexDeepCoder] Running HIGH Effort Mode (Full 2-Stage Invariant Decomposition)...")

    # STAGE 1: SSIB Invariant Planning (ApexThink-14B, num_ctx: 4096)
    stage1_sys = (
        "You are an expert algorithms and systems architect. "
        "Analyze the programming task and produce a machine-readable STRUCTURED SEMANTIC INVARIANT BLOCK (SSIB):\n"
        "1. FORMAL_PREDICATES:\n"
        "   - Express all overlap, traversal, and pruning checks as exact boolean lambda expressions with standard math operators (<=, >=, <, >).\n"
        "   - For binary search trees with intervals: explicitly state the Left Pruning and Right Pruning rules.\n"
        "     * Left Prune: node.left is not None and node.left.max_high >= query.low\n"
        "     * Right Prune: node.right is not None and node.interval.low <= query.high\n"
        "2. BOUNDARY_TRUTH_TABLE:\n"
        "   - Define explicit expected outcomes for point intervals [x, x], endpoint touching [a, b] & [b, c], and disjoint sets.\n"
        "3. CONCURRENCY_INVARIANTS:\n"
        "   - State the lock hierarchy using Python context managers ('with self._lock:').\n"
        "Do NOT write the entire implementation here; focus strictly on mathematical contracts and invariants."
    )
    stage1_res = query_ollama(
        model=THINK_MODEL,
        messages=[{"role": "system", "content": stage1_sys}, {"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=896,
        num_ctx=4096,
    )
    plan_content = stage1_res["content"]
    if verbose:
        print(f"  ✅ Stage 1 SSIB Contract established in {stage1_res['latency_sec']}s ({stage1_res['tokens']} tokens).")

    # STAGE 2: Code Synthesis with Reference Oracle Verification
    stage2_sys = (
        "You are an elite principal software engineer. Implement the solution adhering strictly "
        "to the SSIB Invariant Contract.\n"
        "REQUIREMENTS:\n"
        "- Clean, production-ready Python with full type annotations and docstrings.\n"
        "- Thread safety using 'with self._lock:' context managers (never manual acquire/release).\n"
        "- DUAL-TRACK ORACLE VERIFICATION IN TESTS:\n"
        "  When testing data structures (e.g. interval tree, LRU, rate limiter), DO NOT rely on manual handwritten expected sets.\n"
        "  Instead, implement a simple, ground-truth O(N) brute-force linear filter or property-based invariant oracle to dynamically verify results.\n"
        "  For intervals: def oracle(intervals, q_low, q_high): return set(iv for iv in intervals if iv[0] <= q_high and iv[1] >= q_low)\n"
        "  For LRU cache tests: remember that a cache of capacity K holds K items! It only evicts when inserting item K+1. (e.g. if max_size=2, putting 'a','b','c' evicts 'a' and retains 'b','c'). Never assert eviction before capacity is strictly exceeded!\n"
        "  For rate limiters: use sub-second intervals (e.g. window_seconds=0.05, sleep=0.06) so all tests execute swiftly in under 1 second.\n"
        "Return the code inside a standard ```python block."
    )
    stage2_prompt = (
        f"PROBLEM SPECIFICATION:\n{prompt}\n\n"
        f"SSIB INVARIANT CONTRACT & BLUEPRINT:\n{plan_content}\n\n"
        "Implement the complete production class and self-contained oracle property tests now:"
    )
    stage2_res = query_ollama(
        model=CODE_MODEL,
        messages=[{"role": "system", "content": stage2_sys}, {"role": "user", "content": stage2_prompt}],
        temperature=0.2,
        max_tokens=2048,
        num_ctx=16384,
    )
    code_content = stage2_res["content"]
    extracted_code = extract_code_block(code_content)
    if verbose:
        print(f"  ✅ Stage 2 Code generated in {stage2_res['latency_sec']}s ({stage2_res['tokens']} tokens).")

    # STAGE 3: Zero-Trust Sandboxed Verification (Docker) + 2-Tier Reflexion
    exec_result = verify_and_execute_code(extracted_code, timeout_sec=15, use_docker=True)
    repair_count = 0
    repair_history = []

    while not exec_result["passed"] and repair_count < max_repair_attempts:
        repair_count += 1
        aci_frame = exec_result.get("aci_frame") or parse_aci_diagnostic_frame(exec_result.get("error", ""), extracted_code)
        failing_func = aci_frame.get("failing_function")

        if verbose:
            print(f"  ⚠️ Failure detected (Attempt {repair_count}/{max_repair_attempts}):")
            print(f"     Type: {aci_frame.get('failure_type')} | Function: {failing_func} | Line: {aci_frame.get('failing_line_number')}")
            print(f"     Message: {aci_frame.get('exception_message')[:90]}...")

        # TIER 1: Surgical Single-Function AST Patching (for business logic methods)
        tier1_succeeded = False
        is_test_function = failing_func and (failing_func.startswith("test") or failing_func in ("main", "<module>"))

        # Verify failing_func is an actual function in the AST and not a module-level error
        is_actual_function = False
        if failing_func and not is_test_function and failing_func not in ("__init__",):
            try:
                tree_check = ast.parse(extracted_code)
                for node in ast.walk(tree_check):
                    if isinstance(node, ast.FunctionDef) and node.name == failing_func:
                        is_actual_function = True
                        break
            except Exception:
                is_actual_function = False

        is_module_level_error = aci_frame.get("failure_type") in ("NameError", "ImportError", "SyntaxError", "IndentationError")

        if is_actual_function and not is_module_level_error:
            if verbose:
                print(f"  🩹 Attempting Tier 1 Surgical AST Patch on function '{failing_func}'...")

            tier1_prompt = (
                f"Your function '{failing_func}' failed test verification with the following ACI Diagnostic Frame:\n"
                f"```json\n{json.dumps(aci_frame, indent=2)}\n```\n\n"
                f"FULL CURRENT CODE:\n```python\n{extracted_code}\n```\n\n"
                f"Rewrite ONLY the function definition 'def {failing_func}(...):' to fix the root cause and satisfy the invariants. "
                "Output ONLY the corrected function inside a ```python block."
            )
            patch_res = query_ollama(
                model=CODE_MODEL,
                messages=[{"role": "system", "content": "You are a surgical code debugger. Rewrite ONLY the specified function."}, {"role": "user", "content": tier1_prompt}],
                temperature=0.1,
                max_tokens=1024,
                num_ctx=8192,
            )
            new_func_code = extract_code_block(patch_res["content"])
            try:
                patched_code = patch_function_ast(extracted_code, failing_func, new_func_code)
                test_run = verify_and_execute_code(patched_code, timeout_sec=15, use_docker=True)
                if test_run["passed"]:
                    extracted_code = patched_code
                    exec_result = test_run
                    tier1_succeeded = True
                    if verbose:
                        print(f"  ✨ Tier 1 Surgical Patch SUCCEEDED in {patch_res['latency_sec']}s!")
            except Exception as e:
                if verbose:
                    print(f"  ℹ️ Tier 1 splice fell back: {e}")

        # TIER 2: Full Module Escalation
        if not tier1_succeeded:
            if verbose:
                print("  🔄 Escalating to Tier 2 Module-Level Re-synthesis with ACI Diagnostics...")

            tier2_prompt = (
                f"Your Python code failed verification with the following ACI Diagnostic Frame:\n"
                f"```json\n{json.dumps(aci_frame, indent=2)}\n```\n\n"
                f"CURRENT IMPLEMENTATION:\n```python\n{extracted_code}\n```\n\n"
                "DIAGNOSTIC GUIDANCE:\n"
                f"- Failing Line {aci_frame.get('failing_line_number')}: {aci_frame.get('failing_code_snippet')}\n"
                f"- Error: {aci_frame.get('exception_message')}\n"
                "- Include all required standard library imports at top (e.g. `from typing import Dict, List, Optional, Tuple, Any, Set`; `import threading, time, bisect, hashlib`).\n"
                "- If an assertion failed in unit tests, check whether the class implementation had a bug OR if the test assertion made an arithmetic or protocol assumption error.\n"
                "- Ensure all method signatures match the specification.\n"
                "- Ensure both the class logic and the self-contained test assertions pass 100%.\n"
                "Return the complete corrected self-contained Python code in a ```python block."
            )
            repair_res = query_ollama(
                model=CODE_MODEL,
                messages=[{"role": "system", "content": "You are an expert systems engineer. Repair the code so all oracle property tests pass."}, {"role": "user", "content": tier2_prompt}],
                temperature=0.1,
                max_tokens=2048,
                num_ctx=16384,
            )
            extracted_code = extract_code_block(repair_res["content"])
            exec_result = verify_and_execute_code(extracted_code, timeout_sec=15, use_docker=True)

        repair_history.append({"attempt": repair_count, "tier": 1 if tier1_succeeded else 2, "aci_frame": aci_frame, "success": exec_result["passed"]})

    if verbose:
        status_tag = "✅ PASSED" if exec_result["passed"] else "❌ FAILED"
        print(f"  {status_tag}: High Effort Complete (Passed: {exec_result['passed']}, Repairs: {repair_count}, Sandbox: {exec_result.get('sandbox')})")

    total_latency = round(time.perf_counter() - pipeline_start, 2)
    mem_final = get_memory_usage()

    return {
        "prompt": prompt,
        "effort_level": "high",
        "plan": plan_content,
        "final_code": extracted_code,
        "ast_valid": exec_result.get("ast_valid", False),
        "tests_passed": exec_result.get("passed", False),
        "sandbox_used": exec_result.get("sandbox", "unknown"),
        "repairs_performed": repair_count,
        "repair_history": repair_history,
        "latency_sec": {"stage1_plan": stage1_res["latency_sec"], "stage2_code": stage2_res["latency_sec"], "total": total_latency},
        "tokens_generated": stage1_res["tokens"] + stage2_res["tokens"],
        "memory": {"initial_ram_gb": mem_initial["used_gb"], "final_ram_gb": mem_final["used_gb"], "swap_used_mb": mem_final["swap_used_mb"]},
    }


def run_deepcoder_pipeline(
    prompt: str,
    reasoning_effort: str = "auto",
    max_repair_attempts: int = 2,
    verbose: bool = True,
) -> dict:
    """Run ApexDeepCoder pipeline with configurable reasoning_effort ('low', 'medium', 'high', 'auto')."""
    effort = reasoning_effort.lower().strip()
    if effort == "low":
        return _run_effort_low(prompt, verbose=verbose)
    elif effort == "medium":
        return _run_effort_medium(prompt, max_repair_attempts=1, verbose=verbose)
    elif effort == "high":
        return _run_effort_high(prompt, max_repair_attempts=max_repair_attempts, verbose=verbose)
    else:  # "auto" - Optimistic JIT Escalation
        if verbose:
            print("\n⚡ [ApexDeepCoder: Auto Effort] Starting Optimistic Fast-Path (Medium)...")
        med_res = _run_effort_medium(prompt, max_repair_attempts=1, verbose=verbose)
        if med_res["tests_passed"]:
            if verbose:
                print(f"🚀 [ApexDeepCoder: Auto Effort] Fast-Path SUCCEEDED in {med_res['latency_sec']['total']}s! Returning immediately.")
            med_res["effort_level"] = "auto (fast-path resolved)"
            return med_res

        if verbose:
            print(f"⚠️ [ApexDeepCoder: Auto Effort] Fast-Path encountered test failure. JIT Escalating to High Effort (R1 Invariants)...")
        high_res = _run_effort_high(prompt, max_repair_attempts=max_repair_attempts, verbose=verbose)
        high_res["effort_level"] = "auto (escalated to high)"
        # Combine metrics
        high_res["tokens_generated"] += med_res["tokens_generated"]
        high_res["latency_sec"]["fast_path_attempt"] = med_res["latency_sec"]["total"]
        high_res["latency_sec"]["total"] = round(high_res["latency_sec"]["total"] + med_res["latency_sec"]["total"], 2)
        return high_res


def main():
    test_prompt = (
        "Implement an Augmented Interval Tree in Python where each node stores an interval [low, high] "
        "and maintains 'max_high'. Include insert(low, high) and find_overlapping(low, high) -> list[tuple[int, int]]. "
        "Handle point intervals [x, x] and negative coordinates. "
        "Include self-contained executable oracle property tests verifying that find_overlapping() matches an O(N) brute-force linear filter."
    )
    res = run_deepcoder_pipeline(test_prompt)
    print("\n" + "=" * 68)
    print(f"RESULT: {'PASS' if res['tests_passed'] else 'FAIL'}")
    print(f"Sandbox: {res['sandbox_used']} | Latency: {res['latency_sec']['total']}s")
    print(f"RAM Used: {res['memory']['final_ram_gb']} GB (Swap: {res['memory']['swap_used_mb']} MB)")
    print("=" * 68)


if __name__ == "__main__":
    main()
