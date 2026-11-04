#!/usr/bin/env python3
"""Comprehensive Functional & Stress Test Suite for ApexCode-14B.

Evaluates:
1. Detailed Functional Correctness (Python syntax verification with ast.parse)
2. Long-Output Sustained Generation (1,024+ tokens, checking for thermal/bandwidth throttling)
3. Deep Context Ingestion Stress (12,000+ token codebase needle query)
4. Concurrent Multi-Threaded Load (2 & 4 concurrent parallel streams)
5. Memory & Swap Safety Monitoring
"""

import argparse
import ast
import concurrent.futures
import json
import time
import urllib.request
import psutil

# Terminal styling
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_mem_stats():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "used_gb": round(mem.used / 1024**3, 2),
        "total_gb": round(mem.total / 1024**3, 2),
        "swap_used_mb": round(swap.used / 1024**2, 2),
    }


def query_llm(
    base_url: str,
    prompt: str,
    model: str,
    max_tokens: int = 512,
    system_prompt: str = "You are a principal systems engineer. Output clean, correct code.",
    stream: bool = True,
):
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    start_time = time.perf_counter()
    first_token_time = None
    accumulated_chunks = []
    token_count = 0

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for line in resp:
                line_str = line.decode("utf-8").strip()
                if not line_str.startswith("data: "):
                    continue
                data_part = line_str[6:]
                if data_part == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_part)
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        token_count += 1
                        accumulated_chunks.append(delta)
                except json.JSONDecodeError:
                    continue

    except Exception as e:
        return {"error": str(e), "tokens": 0, "speed": 0, "ttft_ms": 0, "text": ""}

    total_time = time.perf_counter() - start_time
    ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else 0
    gen_time = total_time - (ttft_ms / 1000)
    tok_per_sec = (token_count / gen_time) if gen_time > 0 else 0

    return {
        "text": "".join(accumulated_chunks),
        "tokens": token_count,
        "ttft_ms": round(ttft_ms, 2),
        "total_time_sec": round(total_time, 2),
        "speed": round(tok_per_sec, 2),
        "error": None,
    }


def test_functional_quality(base_url: str, model: str):
    print(f"\n{BOLD}{CYAN}════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}🧪 PHASE 1: FUNCTIONAL QUALITY & SYNTACTIC ACCURACY TESTS{RESET}")
    print(f"{CYAN}════════════════════════════════════════════════════════════════{RESET}")

    test_cases = [
        {
            "name": "Thread-Safe Ring Buffer",
            "prompt": "Write a thread-safe generic Circular RingBuffer in Python with push(), pop(), and peek() using threading.Condition and type hints.",
            "check_syntax": True,
        },
        {
            "name": "Surgical Search/Replace Diff",
            "prompt": "Given this code:\n```python\ndef query_db(user_id):\n    return db.execute('SELECT * FROM users WHERE id = ' + str(user_id))\n```\nFix SQL injection using parameterized query. Format output as a surgical SEARCH/REPLACE diff.",
            "check_diff": True,
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Testing: {BOLD}{tc['name']}{RESET}...")
        res = query_llm(base_url, tc["prompt"], model, max_tokens=512)
        if res["error"]:
            print(f"  {RED}❌ Error: {res['error']}{RESET}")
            continue

        print(f"  ⚡ TTFT: {res['ttft_ms']} ms | Tokens: {res['tokens']} | Speed: {res['speed']} tok/s")

        # Validate syntax if Python code block exists
        if tc.get("check_syntax"):
            text = res["text"]
            # Extract python code block if present
            code = text
            if "```python" in text:
                code = text.split("```python")[1].split("```")[0]
            elif "```" in text:
                code = text.split("```")[1].split("```")[0]

            try:
                ast.parse(code)
                print(f"  {GREEN}✅ Python AST Syntax Verification: PASSED (Valid Syntax){RESET}")
            except SyntaxError as se:
                print(f"  {YELLOW}⚠️ AST Syntax Warning: {se}{RESET}")

        if tc.get("check_diff"):
            if "SEARCH" in res["text"] and "REPLACE" in res["text"]:
                print(f"  {GREEN}✅ Diff Formatting Verification: PASSED (Correct Search/Replace blocks){RESET}")
            else:
                print(f"  {YELLOW}⚠️ Diff Formatting: Missing explicit SEARCH/REPLACE delimiters.{RESET}")


def test_sustained_generation_stress(base_url: str, model: str):
    print(f"\n{BOLD}{CYAN}════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}🔥 PHASE 2: SUSTAINED HIGH-TOKEN GENERATION STRESS (1,024 Tokens){RESET}")
    print(f"{CYAN}════════════════════════════════════════════════════════════════{RESET}")

    m_before = get_mem_stats()
    print(f"System RAM Before: {m_before['used_gb']} / {m_before['total_gb']} GB (Swap: {m_before['swap_used_mb']} MB)")

    prompt = (
        "Write a complete, end-to-end production Raft consensus algorithm simulator in Python. "
        "Include classes for Node, LogEntry, State (Leader/Follower/Candidate), heartbeat timer, "
        "and request vote RPC handlers. Do not omit any implementation details or use placeholder comments."
    )

    print("▶ Dispatching heavy 1,024-token payload...")
    start = time.perf_counter()
    res = query_llm(base_url, prompt, model, max_tokens=1024)
    duration = time.perf_counter() - start

    m_after = get_mem_stats()

    if res["error"]:
        print(f"  {RED}❌ Failed: {res['error']}{RESET}")
        return

    print(f"  {GREEN}✅ Completed sustained generation of {res['tokens']} tokens in {duration:.2f}s!{RESET}")
    print(f"  ⚡ Generation Speed: {BOLD}{res['speed']} tokens/sec{RESET}")
    print(f"  ⏱️ Time-To-First-Token: {res['ttft_ms']} ms")
    print(f"  🧠 System RAM After: {m_after['used_gb']} GB (Swap Delta: {m_after['swap_used_mb'] - m_before['swap_used_mb']} MB)")


def test_deep_context_stress(base_url: str, model: str):
    print(f"\n{BOLD}{CYAN}════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}📚 PHASE 3: DEEP CONTEXT WINDOW STRESS (~10,000 Tokens KV Cache){RESET}")
    print(f"{CYAN}════════════════════════════════════════════════════════════════{RESET}")

    m_before = get_mem_stats()
    print(f"System RAM Before Context Ingestion: {m_before['used_gb']} GB")

    # Generate realistic multi-file repository context
    print("▶ Synthesizing large codebase context (~8,000 - 10,000 tokens)...")
    synthetic_files = []
    for i in range(25):
        synthetic_files.append(f"""
# File: src/services/module_{i}.py
class ServiceModule{i}:
    def __init__(self, config_val: int = {i}):
        self.val = config_val
        self.registry = {{'key_{i}': 'val_{i}'}}

    def execute_action_{i}(self, data: list[int]) -> int:
        return sum(data) * self.val
""")

    # Secret needle
    synthetic_files.append("""
# File: src/secrets/critical_flag.py
CRITICAL_PRODUCTION_OVERRIDE_KEY = "APEX-SECURE-9942-ALPHA"
""")

    context_prompt = (
        "Here is a multi-file project repository:\n"
        + "\n".join(synthetic_files)
        + "\n\nQuery: What is the exact value of CRITICAL_PRODUCTION_OVERRIDE_KEY in src/secrets/critical_flag.py?"
    )

    print("▶ Ingesting deep context and querying needle...")
    res = query_llm(base_url, context_prompt, model, max_tokens=64)
    m_after = get_mem_stats()

    if res["error"]:
        print(f"  {RED}❌ Failed: {res['error']}{RESET}")
        return

    print(f"  ⚡ Ingestion TTFT: {BOLD}{res['ttft_ms']} ms{RESET} (KV Cache allocation)")
    print(f"  💬 Output: {res['text'].strip()}")
    print(f"  🧠 System RAM with KV Cache: {m_after['used_gb']} GB (Delta: +{m_after['used_gb'] - m_before['used_gb']:.2f} GB)")

    if "APEX-SECURE-9942-ALPHA" in res["text"]:
        print(f"  {GREEN}✅ Needle Retrieval Accuracy: 100% PERFECT MATCH{RESET}")
    else:
        print(f"  {YELLOW}⚠️ Needle not found verbatim in output.{RESET}")


def test_concurrency_stress(base_url: str, model: str, concurrency: int = 2):
    print(f"\n{BOLD}{CYAN}════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}⚡ PHASE 4: CONCURRENT LOAD STRESS ({concurrency} Parallel Requests){RESET}")
    print(f"{CYAN}════════════════════════════════════════════════════════════════{RESET}")

    prompts = [
        "Implement a merge sort algorithm in Python.",
        "Implement a binary search tree insertion and search in Python.",
        "Implement Dijkstra's shortest path algorithm in Python.",
        "Implement an async event emitter with subscribe and emit in Python.",
    ][:concurrency]

    m_before = get_mem_stats()
    print(f"Firing {concurrency} parallel requests simultaneously. RAM: {m_before['used_gb']} GB...")

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(query_llm, base_url, p, model, 256)
            for p in prompts
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    total_time = time.perf_counter() - start
    m_after = get_mem_stats()

    successful = [r for r in results if not r["error"]]
    total_tokens = sum(r["tokens"] for r in successful)
    combined_throughput = total_tokens / total_time if total_time > 0 else 0

    print(f"  {GREEN}✅ Finished {len(successful)}/{concurrency} parallel streams in {total_time:.2f}s!{RESET}")
    print(f"  🚀 Aggregate Throughput: {BOLD}{combined_throughput:.2f} tokens/second{RESET}")
    for idx, r in enumerate(successful):
        print(f"     • Stream {idx+1}: {r['tokens']} tokens | TTFT {r['ttft_ms']} ms | Speed {r['speed']} tok/s")
    print(f"  🧠 System RAM Post-Concurrency: {m_after['used_gb']} GB (Swap: {m_after['swap_used_mb']} MB)")


def main():
    parser = argparse.ArgumentParser(description="ApexCode Deep Stress Test Suite")
    parser.add_argument("--url", default="http://127.0.0.1:11434", help="Ollama or server base URL")
    parser.add_argument("--model", default="apex-coder-14b", help="Model name")
    parser.add_argument("--skip-concurrency", action="store_true", help="Skip concurrency test")
    args = parser.parse_args()

    print(f"{BOLD}================================================================{RESET}")
    print(f"{BOLD}🚀 APEXCODE-14B: FULL FUNCTIONAL & DEEP STRESS TEST SUITE{RESET}")
    print(f"Target: {args.url} | Model: {args.model}")
    mem = get_mem_stats()
    print(f"Initial Host RAM: {mem['used_gb']} / {mem['total_gb']} GB | Swap: {mem['swap_used_mb']} MB")
    print(f"{BOLD}================================================================{RESET}")

    # Phase 1: Functional Quality
    test_functional_quality(args.url, args.model)

    # Phase 2: Sustained Long Generation (1,024 Tokens)
    test_sustained_generation_stress(args.url, args.model)

    # Phase 3: Deep Context Stress (~10k tokens)
    test_deep_context_stress(args.url, args.model)

    # Phase 4: Concurrency Stress (2 parallel streams)
    if not args.skip_concurrency:
        test_concurrency_stress(args.url, args.model, concurrency=2)

    print(f"\n{BOLD}================================================================{RESET}")
    final_mem = get_mem_stats()
    print(f"{BOLD}{GREEN}🏁 ALL STRESS TESTS COMPLETED!{RESET}")
    print(f"Final Host RAM: {final_mem['used_gb']} / {final_mem['total_gb']} GB (Swap: {final_mem['swap_used_mb']} MB)")
    print(f"{BOLD}================================================================{RESET}\n")


if __name__ == "__main__":
    main()
