#!/usr/bin/env python3
"""Experiment 4: Empirical Proof of Reflexion Repair on Single-Pass Invariant vs 2-Stage.

Tests if 1 ACI Reflexion repair converts the initial failure into a PASS, and measures total latency.
"""

import json
import re
import subprocess
import time
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11434"
CODE_MODEL = "apex-coder-14b"
CONTAINER_NAME = "apex-sandbox-daemon"

PROB = {
    "prompt": (
        "Implement an Augmented Interval Tree in Python where each node stores [low, high] and maintains 'max_high'. "
        "Include insert(low, high) and find_overlapping(low, high) -> list[tuple[int, int]]. "
        "Handle point intervals [x, x] and negative coordinates. "
        "In your executable assert tests, verify find_overlapping against an O(N) linear filter oracle: "
        "set(tree.find_overlapping(q_low, q_high)) == set(iv for iv in all_intervals if iv[0] <= q_high and iv[1] >= q_low)."
    ),
    "schema": (
        "MANDATORY CLRS FORMAL INVARIANT SCHEMA:\n"
        "1. Overlap Predicate: (node.low <= q_high) and (q_low <= node.high)\n"
        "2. Left-Subtree Prune: if node.left is not None and node.left.max_high >= q_low, search left subtree.\n"
        "3. Right-Subtree Prune: if node.right is not None and node.low <= q_high, search right subtree.\n"
        "4. Subtree Update: node.max_high = max(node.high, node.left.max_high if node.left else -inf, node.right.max_high if node.right else -inf)\n"
    )
}

def query_ollama(messages: list, temperature: float = 0.2):
    payload = {"model": CODE_MODEL, "messages": messages, "stream": False, "options": {"temperature": temperature, "num_predict": 1800}}
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", ""), round(time.perf_counter() - t0, 2), data.get("eval_count", 0)

def extract_code(text: str) -> str:
    m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if m: return m.group(1).strip()
    return text.strip()

def run_in_sandbox(code: str):
    res = subprocess.run(["docker", "exec", "-i", CONTAINER_NAME, "python3", "-c", code], capture_output=True, text=True)
    return (res.returncode == 0), res.stderr.strip()

def run_test():
    print("=" * 72)
    print("🔬 EXPERIMENT 4: SINGLE-PASS + ACI REFLEXION REPAIR EMPIRICAL PROOF")
    print("=" * 72)

    # Pass 1: Single-pass Invariant Injection
    t_start = time.perf_counter()
    full_prompt = f"{PROB['prompt']}\n\n{PROB['schema']}"
    code_raw, lat_p1, tok_p1 = query_ollama([
        {"role": "system", "content": "You are a principal algorithms engineer. Implement code strictly following invariants with self-contained tests inside ```python block."},
        {"role": "user", "content": full_prompt}
    ])
    code1 = extract_code(code_raw)
    passed1, err1 = run_in_sandbox(code1)

    print(f"Pass 1: {'✅ PASS' if passed1 else '❌ FAIL'} in {lat_p1}s ({tok_p1} tokens)")
    if not passed1:
        print(f"Pass 1 Stderr snippet: {err1.splitlines()[-1] if err1 else 'Unknown'}")
        print("▶ Invoking 1 ACI Diagnostic Reflexion Repair...")

        # Repair prompt
        repair_prompt = (
            f"Your Python code failed execution with the following traceback:\n"
            f"```\n{err1}\n```\n\n"
            f"CURRENT CODE:\n```python\n{code1}\n```\n\n"
            "Diagnose the error, fix the root cause, and return the complete corrected code inside a ```python block."
        )
        rep_raw, lat_rep, tok_rep = query_ollama([
            {"role": "system", "content": "You are an expert debugger. Fix the code so all tests pass."},
            {"role": "user", "content": repair_prompt}
        ], temperature=0.1)
        code2 = extract_code(rep_raw)
        passed2, err2 = run_in_sandbox(code2)
        total_time = round(time.perf_counter() - t_start, 2)
        print(f"Reflexion Attempt 1: {'✅ PASS' if passed2 else '❌ FAIL'} in {lat_rep}s ({tok_rep} tokens)")
        print(f"Total Latency with 1 Reflexion: {total_time}s | Total Tokens: {tok_p1 + tok_rep}")
        if not passed2:
            print(f"Final Error: {err2.splitlines()[-1] if err2 else 'Unknown'}")
    else:
        print("Pass 1 passed directly without needing reflexion!")

if __name__ == "__main__":
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", CONTAINER_NAME, "--net=none", "--memory=512m", "--entrypoint", "sleep", "apex-code-36gb:latest", "3600"], capture_output=True)
    try:
        run_test()
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
