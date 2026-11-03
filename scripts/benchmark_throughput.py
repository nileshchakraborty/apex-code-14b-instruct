#!/usr/bin/env python3
"""Benchmark throughput and latency for ApexCode Server.

Sends representative coding prompts, evaluates Time-To-First-Token (TTFT),
and calculates tokens generated per second.
"""

import argparse
import json
import time
import urllib.request
import psutil

PROMPTS = [
    {
        "name": "Algorithm (LRU Cache)",
        "prompt": "Implement a high-concurrency LRU Cache in Python with O(1) get/put, thread safety, and expiry TTL.",
    },
    {
        "name": "Refactoring & Type Safety",
        "prompt": "Refactor a complex recursive tree traversal into an iterative generator using Python typing and boundary error handling.",
    },
    {
        "name": "Full-Stack Web API",
        "prompt": "Write a complete FastAPI endpoint with Pydantic v2 schemas for an authenticated user checkout pipeline with rate limiting.",
    },
]


def test_endpoint(base_url: str, prompt_data: dict, model_name: str, max_tokens: int = 512):
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior systems engineer. Output high-performance production code only.",
            },
            {"role": "user", "content": prompt_data["prompt"]},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
    }

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)

    start_time = time.perf_counter()
    first_token_time = None
    token_count = 0

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            for line in response:
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
                except json.JSONDecodeError:
                    continue

    except Exception as e:
        return {"name": prompt_data["name"], "error": str(e)}

    total_time = time.perf_counter() - start_time
    ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else 0
    generation_time = total_time - (ttft_ms / 1000)
    tok_per_sec = (token_count / generation_time) if generation_time > 0 else 0

    return {
        "name": prompt_data["name"],
        "tokens": token_count,
        "ttft_ms": round(ttft_ms, 2),
        "total_time_sec": round(total_time, 2),
        "tokens_per_sec": round(tok_per_sec, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="ApexCode Throughput Benchmark")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Base URL of OpenAI server")
    parser.add_argument("--model", default="qwen2.5-coder-14b-instruct", help="Model alias")
    parser.add_argument("--tokens", type=int, default=384, help="Tokens to generate per prompt")
    args = parser.parse_args()

    print("=" * 64)
    print("📊 Benchmarking ApexCode Server Throughput")
    print(f"Target URL: {args.url}")
    print(f"Model: {args.model}")
    mem = psutil.virtual_memory()
    print(f"Memory: Used {mem.used / 1024**3:.1f} GB / Total {mem.total / 1024**3:.1f} GB")
    print("=" * 64)

    results = []
    for p in PROMPTS:
        print(f"\n🏃 Running: {p['name']}...")
        res = test_endpoint(args.url, p, args.model, args.tokens)
        if "error" in res:
            print(f"   ❌ Error: {res['error']}")
        else:
            print(f"   ⚡ TTFT: {res['ttft_ms']} ms | Tokens: {res['tokens']} | Speed: {res['tokens_per_sec']} tok/s")
            results.append(res)

    if results:
        avg_speed = sum(r["tokens_per_sec"] for r in results) / len(results)
        avg_ttft = sum(r["ttft_ms"] for r in results) / len(results)
        print("\n" + "=" * 64)
        print("🏆 Final Benchmark Summary")
        print("=" * 64)
        print(f"Average Generation Speed: {avg_speed:.2f} tokens/second")
        print(f"Average Time To First Token: {avg_ttft:.2f} ms")
        print("=" * 64)


if __name__ == "__main__":
    main()
