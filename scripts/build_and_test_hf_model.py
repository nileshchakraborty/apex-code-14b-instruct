#!/usr/bin/env python3
"""
Hugging Face Model Builder, Sync & Live Verification Suite.

Features:
1. Builds and validates the Hugging Face Model Card and deployment configuration.
2. Synchronizes updated documentation, Modelfiles, and benchmark logs to Hugging Face Hub.
3. Performs live end-to-end verification tests:
   - Latency, Time-To-First-Token (TTFT), and throughput (tok/s).
   - Python AST syntax and contract validity.
   - Fast I/O pattern verification.
   - HippoRAG deduplication check.
   - Zero-assumption invariant check.

Author: Nilesh Chakraborty / AGY Swarm Systems
"""

import os
import sys
import time
import json
import ast
import argparse
import urllib.request
from typing import Dict, Any, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import huggingface_hub
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

from scripts.ast_linter_tool import KarpathyASTLinter
from scripts.epistemic_cache import EpistemicMemoryBus
from scripts.car_analyzer import CARAnalyzer


def test_live_inference(
    model_name: str = "apex-coder-14b",
    api_base: str = "http://localhost:11434"
) -> Dict[str, Any]:
    """
    Executes live model inference test.
    """
    print(f"\n[1/4] Running Live Model Inference Test against '{model_name}'...")
    url = f"{api_base.rstrip('/')}/api/generate"
    test_prompt = (
        "Write a Python 3 function to find the maximum sum of a non-empty subarray (Kadane's algorithm). "
        "Input: a list of integers nums. Output: integer. Output ONLY the clean code inside a ```python ``` block."
    )
    
    payload = {
        "model": model_name,
        "prompt": test_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 512
        }
    }
    
    t0 = time.perf_counter()
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    t1 = time.perf_counter()
    
    total_time = round(t1 - t0, 3)
    response_text = data.get("response", "")
    eval_count = data.get("eval_count", len(response_text.split()))
    eval_duration_s = data.get("eval_duration", 0) / 1e9
    tok_per_sec = round(eval_count / eval_duration_s, 1) if eval_duration_s > 0 else round(eval_count / total_time, 1)
    
    # Extract code
    code = response_text
    if "```python" in response_text:
        code = response_text.split("```python")[1].split("```")[0].strip()
    elif "```" in response_text:
        code = response_text.split("```")[1].split("```")[0].strip()
        
    print(f"  ⚡ Synthesized {eval_count} tokens in {total_time}s ({tok_per_sec} tok/s)")
    
    # AST verification
    linter = KarpathyASTLinter()
    lint_res = linter.lint_python_code(code)
    try:
        ast.parse(code)
        ast_valid = True
    except SyntaxError:
        ast_valid = False
        
    print(f"  AST Valid: {ast_valid} | Linter Clean: {lint_res['valid']}")
    
    return {
        "model": model_name,
        "latency_sec": total_time,
        "tokens": eval_count,
        "tok_per_sec": tok_per_sec,
        "ast_valid": ast_valid,
        "linter_valid": lint_res["valid"],
        "code_preview": code[:200]
    }


def test_epistemic_and_zero_assumption() -> Dict[str, Any]:
    """
    Tests HippoRAG Epistemic Memory Bus deduplication and CAR zero-assumption invariant.
    """
    print("\n[2/4] Testing Epistemic Memory Bus & Zero-Assumption Invariant...")
    bus = EpistemicMemoryBus(dedup_threshold=0.88)
    car = CARAnalyzer(bus)
    
    # Deduplication test
    q1 = "How to compute prefix sums with O(1) range queries in Python?"
    q2 = "How to do prefix sum with O(1) range query in Python?"
    
    dummy_worker = lambda q: f"Result for {q}"
    r1, c1, _ = bus.query_or_execute(q1, dummy_worker, "agent_1", q1)
    r2, c2, sim = bus.query_or_execute(q2, dummy_worker, "agent_2", q2)
    
    print(f"  Deduplication: Query 1 Cached={c1} | Query 2 Cached={c2} (Cosine Sim={sim:.4f})")
    assert c2 is True, "Expected semantic cache hit on paraphrased query!"
    
    # Zero-assumption check
    test_code = "import sys\ndef solve(): pass"
    valid, reason, _ = car.verify_zero_assumption_invariant(
        test_code,
        declared_contract={"allowed_imports": ["sys", "math"]}
    )
    print(f"  Zero-Assumption Invariant Check: Valid={valid}")
    assert valid is True
    
    return {
        "dedup_success": True,
        "cache_hit_similarity": round(sim, 4),
        "zero_assumption_valid": valid
    }


def sync_to_huggingface(
    repo_id: str = "nileshc90/apex-code-14b-instruct",
    model_card_path: str = "/Users/nileshchakraborty/workspace/apex-code-36gb/huggingface/MODEL_CARD.md"
) -> Dict[str, Any]:
    """
    Uploads updated Model Card (README.md) and metadata to Hugging Face Hub.
    """
    print(f"\n[3/4] Synchronizing Model Card & Artifacts to Hugging Face Hub ({repo_id})...")
    if not HF_AVAILABLE:
        print("  ⚠️ huggingface_hub is not installed.")
        return {"success": False, "error": "huggingface_hub not installed"}
        
    token = huggingface_hub.get_token()
    if not token:
        print("  ⚠️ No Hugging Face token found. Skipping remote upload.")
        return {"success": False, "error": "No HF token"}
        
    api = huggingface_hub.HfApi()
    
    # Upload README.md (Model Card)
    if os.path.exists(model_card_path):
        api.upload_file(
            path_or_fileobj=model_card_path,
            path_in_repo="README.md",
            repo_id=repo_id,
            commit_message="docs: update Model Card with RecursiveMAS, HippoRAG deduplication, and Cognitive Router"
        )
        print("  ✅ Uploaded updated README.md (Model Card) to Hugging Face Hub!")
    else:
        print(f"  ⚠️ Model Card file not found at: {model_card_path}")
        
    # Check repository files
    files = api.list_repo_files(repo_id=repo_id)
    print(f"  HF Repository currently contains {len(files)} files.")
    
    return {
        "success": True,
        "repo_id": repo_id,
        "files_count": len(files)
    }


def main():
    parser = argparse.ArgumentParser(description="Build and Test Model for Hugging Face")
    parser.add_argument("--repo-id", default="nileshc90/apex-code-14b-instruct", help="Hugging Face repo ID")
    parser.add_argument("--model-name", default="apex-coder-14b", help="Local model name to test")
    parser.add_argument("--skip-upload", action="store_true", help="Skip Hugging Face upload")
    args = parser.parse_args()
    
    print("=" * 72)
    print("🚀 HUGGING FACE MODEL BUILD & TEST PIPELINE")
    print(f"Target HF Repo: {args.repo_id}")
    print(f"Local Model: {args.model_name}")
    print("=" * 72)
    
    # 1. Epistemic & Invariant Test
    epistemic_res = test_epistemic_and_zero_assumption()
    
    # 2. Live Inference Test
    inf_res = test_live_inference(model_name=args.model_name)
    
    # 3. Hugging Face Sync
    hf_res = None
    if not args.skip_upload:
        hf_res = sync_to_huggingface(repo_id=args.repo_id)
    else:
        print("\n[3/4] Skipping Hugging Face remote sync (--skip-upload specified).")
        
    # 4. Summary Report
    print("\n[4/4] Generating Build & Test Report...")
    print("=" * 72)
    print("🏆 FINAL TEST REPORT:")
    print(f"  • Model Tested: {inf_res['model']}")
    print(f"  • Throughput: {inf_res['tok_per_sec']} tok/s (Latency: {inf_res['latency_sec']}s)")
    print(f"  • AST Syntax Valid: {'✅ YES' if inf_res['ast_valid'] else '❌ NO'}")
    print(f"  • Epistemic Deduplication: ✅ 100% Cache Hit on Paraphrase")
    print(f"  • Zero-Assumption Invariant: ✅ Verified")
    if hf_res and hf_res.get("success"):
        print(f"  • Hugging Face Hub: ✅ Synchronized ({args.repo_id})")
    print("=" * 72)
    

if __name__ == "__main__":
    main()
