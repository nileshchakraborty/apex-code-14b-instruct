#!/usr/bin/env python3
"""Experiment 3: Empirical A/B Testing: Single-Pass Invariant Injection vs 2-Stage R1 Decomposition.

Tests the two core problems:
1. Augmented Interval Tree (Algorithms)
2. Concurrent LRU Cache (Concurrency)

Compares:
- Mode A: Zero-Shot Baseline (apex-coder-14b without invariant contract)
- Mode B: Single-Pass Invariant-Injected (apex-coder-14b with explicit formal invariant schema)
- Mode C: 2-Stage Pipeline (apex-think-14b planning + apex-coder-14b synthesis)

Measures:
- Pass/Fail in Docker
- Total Latency (s)
- Total Tokens
"""

import json
import re
import subprocess
import time
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11434"
THINK_MODEL = "apex-think-14b"
CODE_MODEL = "apex-coder-14b"
CONTAINER_NAME = "apex-sandbox-daemon"

TEST_PROBLEMS = [
    {
        "id": "augmented_interval_tree",
        "name": "Augmented Interval Tree",
        "prompt": (
            "Implement an Augmented Interval Tree in Python where each node stores [low, high] and maintains 'max_high'. "
            "Include insert(low, high) and find_overlapping(low, high) -> list[tuple[int, int]]. "
            "Handle point intervals [x, x] and negative coordinates. "
            "In your executable assert tests, verify find_overlapping against an O(N) linear filter oracle: "
            "set(tree.find_overlapping(q_low, q_high)) == set(iv for iv in all_intervals if iv[0] <= q_high and iv[1] >= q_low)."
        ),
        "formal_invariant_schema": (
            "MANDATORY CLRS FORMAL INVARIANT SCHEMA:\n"
            "1. Overlap Predicate: (node.low <= q_high) and (q_low <= node.high)\n"
            "2. Left-Subtree Prune: if node.left is not None and node.left.max_high >= q_low, search left subtree.\n"
            "3. Right-Subtree Prune: if node.right is not None and node.low <= q_high, search right subtree.\n"
            "4. Subtree Update: node.max_high = max(node.high, node.left.max_high if node.left else -inf, node.right.max_high if node.right else -inf)\n"
            "5. Dynamic Oracle: assert set(tree.find_overlapping(ql, qh)) == set(iv for iv in all_ivs if iv[0] <= qh and iv[1] >= ql)\n"
        )
    },
    {
        "id": "concurrent_lru_cache",
        "name": "Concurrent LRU Cache with TTL",
        "prompt": (
            "Implement a thread-safe LRUCache in Python supporting max_size and per-key TTL. "
            "Include get(key), put(key, value, ttl=None), delete(key), and cleanup_expired(). "
            "Use threading.RLock for thread safety and an OrderedDict or doubly-linked list. "
            "In your test suite, verify that when capacity exceeds max_size (e.g. max_size=2 and 3 keys 'a','b','c' are added), "
            "the least-recently-used key ('a') is evicted, recent keys ('b','c') are retained, and expired TTL entries return None."
        ),
        "formal_invariant_schema": (
            "MANDATORY CONCURRENCY & EVICTION INVARIANT SCHEMA:\n"
            "1. Capacity Boundary: Eviction occurs if and only if len(cache) > max_size AFTER adding a new key.\n"
            "2. Lock Invariant: All mutations and reads wrap in `with self.lock:` (using threading.RLock).\n"
            "3. Recency Update: get(key) moves key to most-recently-used; expired key is treated as non-existent and removed.\n"
            "4. Eviction Target: popitem(last=False) pops the least-recently-used key when capacity exceeds max_size.\n"
        )
    }
]

def query_ollama(model: str, messages: list, temperature: float = 0.2, max_tokens: int = 1800):
    payload = {
        "model": model,
        "messages": messages,
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "stream": False,
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    lat = round(time.perf_counter() - t0, 2)
    content = data.get("message", {}).get("content", "")
    thinking = data.get("message", {}).get("thinking", "")
    tokens = data.get("eval_count", 0)
    return {"content": content, "thinking": thinking, "tokens": tokens, "latency_sec": lat}

def extract_code(text: str) -> str:
    m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if m: return m.group(1).strip()
    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m: return m.group(1).strip()
    return text.strip()

def run_in_sandbox(code: str) -> tuple:
    t0 = time.perf_counter()
    res = subprocess.run(
        ["docker", "exec", "-i", CONTAINER_NAME, "python3", "-c", code],
        capture_output=True, text=True
    )
    lat_ms = (time.perf_counter() - t0) * 1000
    passed = (res.returncode == 0)
    err = res.stderr.strip() if not passed else ""
    return passed, lat_ms, err

def run_experiment():
    print("=" * 76)
    print("🔬 EMPIRICAL EXPERIMENT: SINGLE-PASS INVARIANT vs 2-STAGE R1 vs BASELINE")
    print("=" * 76)

    # Start warmed container
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", CONTAINER_NAME, "--net=none", "--memory=512m", "--entrypoint", "sleep", "apex-code-36gb:latest", "3600"], capture_output=True)

    results = []

    for prob in TEST_PROBLEMS:
        print(f"\n========================================================================")
        print(f"TESTING: {prob['name']}")
        print(f"========================================================================")

        # ---------------------------------------------------------
        # Mode A: Baseline (Single-Shot Coder without Invariant Schema)
        # ---------------------------------------------------------
        print("▶ Mode A: Zero-Shot Baseline (apex-coder-14b)...")
        res_a = query_ollama(
            CODE_MODEL,
            [
                {"role": "system", "content": "You are an expert Python engineer. Implement clean code with self-contained tests inside ```python block."},
                {"role": "user", "content": prob["prompt"]}
            ],
            temperature=0.2
        )
        code_a = extract_code(res_a["content"])
        pass_a, lat_dock_a, err_a = run_in_sandbox(code_a)
        print(f"  Mode A Result: {'✅ PASS' if pass_a else '❌ FAIL'} | LLM Latency: {res_a['latency_sec']}s ({res_a['tokens']} tokens) | Docker: {lat_dock_a:.1f}ms")
        if not pass_a:
            print(f"  Mode A Failure: {err_a.splitlines()[-1] if err_a else 'Unknown'}")

        # ---------------------------------------------------------
        # Mode B: Single-Pass Invariant Injection (NO R1, 1 Model)
        # ---------------------------------------------------------
        print("\n▶ Mode B: Single-Pass Invariant-Injected (apex-coder-14b)...")
        prompt_b = f"{prob['prompt']}\n\n{prob['formal_invariant_schema']}"
        res_b = query_ollama(
            CODE_MODEL,
            [
                {"role": "system", "content": "You are a principal engineer. Implement clean code strictly adhering to the formal invariant schema. Include self-contained executable tests inside ```python block."},
                {"role": "user", "content": prompt_b}
            ],
            temperature=0.2
        )
        code_b = extract_code(res_b["content"])
        pass_b, lat_dock_b, err_b = run_in_sandbox(code_b)
        print(f"  Mode B Result: {'✅ PASS' if pass_b else '❌ FAIL'} | LLM Latency: {res_b['latency_sec']}s ({res_b['tokens']} tokens) | Docker: {lat_dock_b:.1f}ms")
        if not pass_b:
            print(f"  Mode B Failure: {err_b.splitlines()[-1] if err_b else 'Unknown'}")

        # ---------------------------------------------------------
        # Mode C: 2-Stage Pipeline (apex-think-14b -> apex-coder-14b)
        # ---------------------------------------------------------
        print("\n▶ Mode C: 2-Stage R1 Invariant Planning + Synthesis...")
        t0_c = time.perf_counter()
        # Stage 1: Thinker
        res_c1 = query_ollama(
            THINK_MODEL,
            [
                {"role": "system", "content": "You are an algorithms architect. Produce a compact Structured Semantic Invariant Block (SSIB)."},
                {"role": "user", "content": prob["prompt"]}
            ],
            temperature=0.6,
            max_tokens=1000
        )
        # Stage 2: Coder
        plan_text = res_c1["content"] or res_c1["thinking"]
        prompt_c2 = f"TASK:\n{prob['prompt']}\n\nSSIB PLAN:\n{plan_text}"
        res_c2 = query_ollama(
            CODE_MODEL,
            [
                {"role": "system", "content": "You are an expert engineer. Implement the code following the SSIB plan with self-contained executable tests inside ```python block."},
                {"role": "user", "content": prompt_c2}
            ],
            temperature=0.2
        )
        total_lat_c = round(time.perf_counter() - t0_c, 2)
        total_tokens_c = res_c1["tokens"] + res_c2["tokens"]
        code_c = extract_code(res_c2["content"])
        pass_c, lat_dock_c, err_c = run_in_sandbox(code_c)
        print(f"  Mode C Result: {'✅ PASS' if pass_c else '❌ FAIL'} | Total Latency: {total_lat_c}s (Stage 1: {res_c1['latency_sec']}s, Stage 2: {res_c2['latency_sec']}s) | Tokens: {total_tokens_c} | Docker: {lat_dock_c:.1f}ms")
        if not pass_c:
            print(f"  Mode C Failure: {err_c.splitlines()[-1] if err_c else 'Unknown'}")

        results.append({
            "problem": prob["name"],
            "mode_a_baseline": {"passed": pass_a, "latency": res_a["latency_sec"], "tokens": res_a["tokens"]},
            "mode_b_invariant_injected": {"passed": pass_b, "latency": res_b["latency_sec"], "tokens": res_b["tokens"]},
            "mode_c_2stage_r1": {"passed": pass_c, "latency": total_lat_c, "tokens": total_tokens_c},
        })

    # Teardown
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    print("\n" + "=" * 80)
    print("📊 EMPIRICAL COMPARISON TABLE: BASELINE vs INVARIANT-INJECTED vs 2-STAGE")
    print("=" * 80)
    print(f"{'Problem Name':<28} | {'Mode A (Baseline)':<16} | {'Mode B (Injected)':<16} | {'Mode C (2-Stage R1)':<16}")
    print("-" * 80)
    for r in results:
        a_str = f"{'✅ PASS' if r['mode_a_baseline']['passed'] else '❌ FAIL'} ({r['mode_a_baseline']['latency']}s)"
        b_str = f"{'✅ PASS' if r['mode_b_invariant_injected']['passed'] else '❌ FAIL'} ({r['mode_b_invariant_injected']['latency']}s)"
        c_str = f"{'✅ PASS' if r['mode_c_2stage_r1']['passed'] else '❌ FAIL'} ({r['mode_c_2stage_r1']['latency']}s)"
        print(f"{r['problem']:<28} | {a_str:<16} | {b_str:<16} | {c_str:<16}")
    print("=" * 80)

if __name__ == "__main__":
    run_experiment()
