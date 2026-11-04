#!/usr/bin/env python3
"""Experiment 2: Granular Microsecond Instrumentation of the LLM Inference Pipeline.

Profiles:
- Stage 1 Planning (apex-think-14b)
- Model Context & Weight Switching Overhead in Ollama
- Stage 2 Code Synthesis (apex-coder-14b)
- Sandbox Execution (Docker exec)
- Total Token Count and Tokens/Second for each stage
"""

import json
import time
import urllib.request
import subprocess

OLLAMA_URL = "http://127.0.0.1:11434"
THINK_MODEL = "apex-think-14b"
CODE_MODEL = "apex-coder-14b"

PROMPT = (
    "Implement an Augmented Interval Tree in Python where each node stores an interval [low, high] "
    "and maintains 'max_high'. Include insert(low, high) and find_overlapping(low, high) -> list[tuple[int, int]]. "
    "Handle point intervals [x, x] and negative coordinates. "
    "In your self-contained executable assert tests, verify find_overlapping against an O(N) linear filter oracle."
)

def query_ollama_streaming_profile(model: str, messages: list, temperature: float = 0.2, max_tokens: int = 2048):
    payload = {
        "model": model,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
        "stream": True,
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    t_start = time.perf_counter()
    t_first_token = None
    tokens = 0
    content = ""
    thinking_content = ""

    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue
            chunk = json.loads(line_str)
            if "message" in chunk:
                msg = chunk["message"]
                delta_content = msg.get("content", "")
                delta_thinking = msg.get("thinking", "")
                if (delta_content or delta_thinking) and t_first_token is None:
                    t_first_token = time.perf_counter()
                if delta_content:
                    content += delta_content
                    tokens += 1
                if delta_thinking:
                    thinking_content += delta_thinking
                    tokens += 1

    t_end = time.perf_counter()
    ttft = (t_first_token - t_start) if t_first_token else 0.0
    total_time = t_end - t_start
    gen_time = (t_end - t_first_token) if t_first_token else total_time
    tok_per_sec = (tokens / gen_time) if gen_time > 0 else 0.0

    return {
        "model": model,
        "tokens": tokens,
        "ttft_sec": round(ttft, 3),
        "total_sec": round(total_time, 3),
        "gen_sec": round(gen_time, 3),
        "tokens_per_sec": round(tok_per_sec, 2),
        "content": content,
        "thinking": thinking_content,
    }

def run_granular_profile():
    print("=" * 72)
    print("🔬 GRANULAR LLM PIPELINE PROFILING (Stage 1 Thinker vs Stage 2 Coder)")
    print("=" * 72)

    # 1. Stage 1: SSIB Planning via apex-think-14b
    print("\n▶ [Stage 1] Querying apex-think-14b for SSIB Invariant Contract...")
    stage1_sys = (
        "You are an expert algorithms and systems architect. Analyze the task and produce a "
        "concise Structured Semantic Invariant Block (SSIB): 1. Formal Predicates, 2. Boundary Invariants, 3. Oracle Pattern."
    )
    t0_stage1 = time.perf_counter()
    prof1 = query_ollama_streaming_profile(
        model=THINK_MODEL,
        messages=[{"role": "system", "content": stage1_sys}, {"role": "user", "content": PROMPT}],
        temperature=0.6,
        max_tokens=1024,
    )
    t_end_stage1 = time.perf_counter()

    print(f"  • TTFT (Time-To-First-Token):    {prof1['ttft_sec']} s")
    print(f"  • Generation Time:              {prof1['gen_sec']} s")
    print(f"  • Tokens Emitted:               {prof1['tokens']} tokens")
    print(f"  • Generation Speed:             {prof1['tokens_per_sec']} tok/s")
    print(f"  • Total Stage 1 Wall-Clock:     {prof1['total_sec']} s")

    # 2. Inter-Stage Transition (Model Switching / KV Allocation)
    t0_switch = time.perf_counter()
    # Check loaded models in Ollama
    ps_res = subprocess.run(["curl", "-s", f"{OLLAMA_URL}/api/ps"], capture_output=True, text=True)
    switch_overhead = time.perf_counter() - t0_switch

    # 3. Stage 2: Code Synthesis via apex-coder-14b
    print("\n▶ [Stage 2] Querying apex-coder-14b for Code Synthesis with SSIB Blueprint...")
    stage2_sys = (
        "You are an expert Python engineer. Implement the solution adhering strictly to the invariant contract. "
        "Include self-contained executable assert tests. Output code in a ```python block."
    )
    stage2_user = f"TASK:\n{PROMPT}\n\nSSIB INVARIANT BLUEPRINT:\n{prof1['content'] or prof1['thinking']}"
    prof2 = query_ollama_streaming_profile(
        model=CODE_MODEL,
        messages=[{"role": "system", "content": stage2_sys}, {"role": "user", "content": stage2_user}],
        temperature=0.2,
        max_tokens=1500,
    )

    print(f"  • TTFT (Time-To-First-Token):    {prof2['ttft_sec']} s")
    print(f"  • Generation Time:              {prof2['gen_sec']} s")
    print(f"  • Tokens Emitted:               {prof2['tokens']} tokens")
    print(f"  • Generation Speed:             {prof2['tokens_per_sec']} tok/s")
    print(f"  • Total Stage 2 Wall-Clock:     {prof2['total_sec']} s")

    # 4. Sandbox Execution
    print("\n▶ [Stage 3] Warmed Sandbox Execution (Docker Exec)...")
    # Extract code
    import re
    code_match = re.search(r"```python\s*(.*?)\s*```", prof2["content"], re.DOTALL)
    code = code_match.group(1).strip() if code_match else prof2["content"]

    t0_exec = time.perf_counter()
    exec_res = subprocess.run(["docker", "exec", "-i", "apex-sandbox-daemon", "python3", "-c", code], capture_output=True, text=True)
    t_exec = time.perf_counter() - t0_exec
    passed = (exec_res.returncode == 0)

    print(f"  • Sandbox Execution Latency:    {t_exec*1000:.2f} ms ({round(t_exec, 3)} s)")
    print(f"  • Sandbox Test Passed:          {passed}")

    total_pipeline = prof1['total_sec'] + prof2['total_sec'] + t_exec
    print("\n" + "=" * 72)
    print("📊 EXACT TIME ALLOCATION BREAKDOWN (Percentages of Wall-Clock Time)")
    print("=" * 72)
    print(f"Stage 1 (apex-think-14b reasoning):   {prof1['total_sec']:>6.2f} s  ({(prof1['total_sec']/total_pipeline)*100:>5.1f}%)")
    print(f"Stage 2 (apex-coder-14b synthesis):   {prof2['total_sec']:>6.2f} s  ({(prof2['total_sec']/total_pipeline)*100:>5.1f}%)")
    print(f"Sandbox Verification (Docker exec):   {t_exec:>6.3f} s  ({(t_exec/total_pipeline)*100:>5.2f}%)")
    print(f"TOTAL PIPELINE WALL-CLOCK:            {total_pipeline:>6.2f} s  (100.0%)")
    print("=" * 72)

if __name__ == "__main__":
    # Ensure warmed daemon is up
    subprocess.run(["docker", "rm", "-f", "apex-sandbox-daemon"], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", "apex-sandbox-daemon", "--net=none", "--memory=512m", "--entrypoint", "sleep", "apex-code-36gb:latest", "3600"], capture_output=True)
    try:
        run_granular_profile()
    finally:
        subprocess.run(["docker", "rm", "-f", "apex-sandbox-daemon"], capture_output=True)
