# 🌐 Universal Model Creation, Optimization & Multi-Hardware Benchmarking Blueprint

This document is a complete, self-contained, reproducible operating playbook. You can copy this transcript into a **fresh agent session** or execute it directly in any workspace to build, optimize, serve, benchmark, and publish **any model of any type** (Qwen, Llama, DeepSeek, Gemma, Mistral, Phi) across **Mac (Apple Silicon Metal), Intel/AMD x86_64 (Vulkan discrete GPU / RAM), and Docker CPU environments**.

---

## 🧭 System Topology & Variable Specification

Set these environment variables at the start of any new session:

```bash
# -----------------------------------------------------------------------------
# MODEL SPECIFICATION (Adjust for your target model)
# -----------------------------------------------------------------------------
export MODEL_FAMILY="qwen2.5-coder"          # Options: qwen2.5-coder, llama-3, deepseek-r1, phi-4
export BASE_MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"
export MODEL_NAME="apex-code-7b"
export DRAFT_MODEL="Qwen/Qwen2.5-Coder-0.5B-Instruct"
export HF_REPO_ID="nileshc90/apex-code-7b-instruct"

# -----------------------------------------------------------------------------
# HARDWARE PROFILE (Auto-detected or explicitly assigned)
# -----------------------------------------------------------------------------
# Architecture options: "mac-metal" | "intel-vulkan" | "x86-cpu" | "hybrid"
export HARDWARE_PROFILE="intel-vulkan"
export VRAM_BUDGET_GB="4.0"                   # Dedicated GPU VRAM capacity
export RAM_BUDGET_GB="32.0"                   # System RAM capacity
export INFERENCE_PORT="8080"                  # llama-server router port
export SANDBOX_DAEMON_NAME="apex-sandbox-daemon"
```

```mermaid
flowchart TD
    subgraph S1["Phase 1: Ingestion & Quantization"]
        W["Hugging Face / GGUF Weights"] --> Q["Quantization (IQ3_M / Q4_K_M / Q5_K_M)"]
        Q --> P["Draft Model Pairing (0.5B Q8_0)"]
    end

    subgraph S2["Phase 2: Hardware Acceleration"]
        P --> H{"Hardware Profile"}
        H -- "Apple Silicon" --> M["Metal MPS Engine (Unified RAM)"]
        H -- "Intel / AMD Linux" --> V["Vulkan llama-server (4GB GDDR6 VRAM)"]
        H -- "Pure CPU / Docker" --> C["Pinned AVX2 CPU + DDR4 Bandwidth"]
    end

    subgraph S3["Phase 3: Test-Time Compute Scaling"]
        M & V & C --> T1["System 1: Clean Fast Greedy"]
        M & V & C --> T2["System 2: DiffCodeGen Clustering (arXiv:2605.20473)"]
        M & V & C --> T3["Karpathy Software 3.0 External AST Linter"]
    end

    subgraph S4["Phase 4: Verification & Distribution"]
        T1 & T2 & T3 --> B["LiveCodeBench Zero-Contamination Benchmark"]
        B --> G["Git Tag & GitHub Release"]
        B --> HF["Hugging Face Hub Model Card & JSON Upload"]
    end
```

---

## 📦 Phase 1: Model Acquisition, Quantization & Server Presets

### 1.1 Quantization Strategy Matrix

Select quantization based on the target execution environment:

| Target Environment | Memory Constraint | Recommended Target Quant | Recommended Draft Quant |
| :--- | :--- | :---: | :---: |
| **Apple Silicon (36 GB)** | 36 GB Unified RAM | **Q5_K_M** (14B ~ 9.8 GB) | **Q8_0** (0.5B ~ 397 MB) |
| **Discrete GPU (4 GB GDDR6)**| 4.0 GB VRAM | **IQ3_M** (7B ~ 3.57 GB) or **Q4_K_M** (3B ~ 2.1 GB) | **Q8_0** (0.5B ~ 397 MB) |
| **Intel Core i9 / DDR4 RAM** | 32 GB RAM (No dGPU) | **Q4_K_M** (3B ~ 2.1 GB) or **Q4_K_M** (1.5B ~ 1.1 GB) | None (Single forward pass) |

### 1.2 Download or Symlink GGUF Weights

```bash
# Create standard model directory
mkdir -p /home/$USER/models

# Option A: Download pre-quantized GGUF directly from Hugging Face
curl -L -o /home/$USER/models/target-model.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"

# Option B: Symlink existing Ollama blob to GGUF
# Check blobs: find /home/$USER/.ollama/models/blobs -size +1G
ln -sf /home/$USER/ollama-data/models/blobs/sha256-TARGET_BLOB_HASH /home/$USER/models/target-model.gguf
ln -sf /home/$USER/ollama-data/models/blobs/sha256-DRAFT_BLOB_HASH /home/$USER/models/draft-model.gguf
```

### 1.3 Configure Multi-Model Router (`presets.ini`)

On the host machine, configure `/home/$USER/models/presets.ini` to support native routing, speculative decoding, and quantized KV caching:

```ini
# /home/$USER/models/presets.ini

[Target-Model-GPU]
model = /home/nilesh/models/target-model.gguf
alias = target-model,apex-code-target
ctx-size = 8192
parallel = 1
n-gpu-layers = 99
batch-size = 256
ubatch-size = 64
threads = 8
flash-attn = on
cache-type-k = q8_0
cache-type-v = q8_0

[Target-Model-Speculative]
model = /home/nilesh/models/target-model.gguf
model-draft = /home/nilesh/models/draft-model.gguf
alias = target-spec,apex-code-spec
ctx-size = 8192
parallel = 1
n-gpu-layers = 99
n-gpu-layers-draft = 99
spec-draft-n-max = 4
batch-size = 256
ubatch-size = 64
threads = 8
flash-attn = on
cache-type-k = q8_0
cache-type-v = q8_0
```

---

## ⚡ Phase 2: Hardware Serving & Thermal Guardrails

### 2.1 Native Systemd Service Setup (Linux / Vulkan)

Create `/etc/systemd/system/llama-server.service`:

```ini
[Unit]
Description=llama.cpp High Performance Vulkan Multi-Model Router Server
After=network.target

[Service]
Type=simple
User=nilesh
Group=render
WorkingDirectory=/home/nilesh
ExecStart=/usr/local/bin/llama-server --models-dir /home/nilesh/models --models-preset /home/nilesh/models/presets.ini --models-max 1 --host 0.0.0.0 --port 8080 --sleep-idle-seconds 300 --cache-idle-slots
Restart=always
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Reload and activate:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server.service
```

### 2.2 Thermal Watchdog Whitelist (Prevent Rogue Process Kills)

On machines with homelab watchdogs (like Intel laptops), ensure the inference binary is whitelisted in `/usr/local/bin/homelab-watchdog.sh`:

```bash
# Verify watchdog script allows llama-server
sudo sed -i 's/EXCLUDE_LIST="/EXCLUDE_LIST="llama-server /' /usr/local/bin/homelab-watchdog.sh
```

### 2.3 Standalone Warm Sandbox Daemon (Docker Isolation)

Ensure candidate solutions run in an air-gapped, memory-capped warm container:

```bash
docker run -d --name apex-sandbox-daemon \
  --network none \
  --memory 512m \
  --cpus 2.0 \
  --restart always \
  python:3.12-slim sleep infinity
```

---

## 🧠 Phase 3: Research-Backed Test-Time Compute Pipeline

### 3.1 Karpathy Software 3.0 External AST Linter (`scripts/ast_linter_tool.py`)

This tool performs deterministic static analysis on generated Python ASTs to prevent common competitive programming failure modes. It is **100% zero-contamination** with no hardcoded problem heuristics:

```python
#!/usr/bin/env python3
"""
ApexCode Universal AST Linter Tool (Karpathy Software 3.0 External Tool Verification)
Detects structural and semantic anti-patterns in generated code without test leakage.
"""

import ast
import re
from typing import List, Dict, Any

class CPCodeAuditVisitor(ast.NodeVisitor):
    def __init__(self, code: str):
        self.code = code
        self.issues: List[Dict[str, Any]] = []
        self.in_loop = 0
        self.read_called_inside_loop = False

    def visit_For(self, node: ast.For):
        self.in_loop += 1
        self.generic_visit(node)
        self.in_loop -= 1

    def visit_While(self, node: ast.While):
        self.in_loop += 1
        self.generic_visit(node)
        self.in_loop -= 1

    def visit_Call(self, node: ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "stdin":
                if func_name == "read" and self.in_loop > 0:
                    self.read_called_inside_loop = True
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, ast.Div):
            self.issues.append({
                "type": "FLOAT_DIVISION_WARNING",
                "line": getattr(node, "lineno", 0),
                "message": "Use integer division `//` instead of float division `/` to prevent precision errors and float types in array indexing."
            })
        self.generic_visit(node)

def audit_code(code: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "valid": False,
            "violations": [{"type": "SYNTAX_ERROR", "line": e.lineno, "message": str(e)}],
        }

    violations = []
    visitor = CPCodeAuditVisitor(code)
    visitor.visit(tree)

    if visitor.read_called_inside_loop:
        violations.append({
            "type": "REPEATED_STDIN_READ_IN_LOOP",
            "message": "Calling `sys.stdin.read()` inside a loop causes subsequent iterations to read EOF. Read tokens once with `data = sys.stdin.read().split()` and iterate with an index pointer."
        })

    # Flag hardcoded index multiplications like arr[0] * arr[1] * arr[2] * ...
    if re.search(r"\w+\[0\]\s*\*\s*\w+\[1\]\s*\*\s*\w+\[2\]", code):
        violations.append({
            "type": "HARDCODED_ARRAY_LENGTH_PRODUCT",
            "message": "Do not hardcode index multiplications like `a[0] * a[1] * a[2]...`. The array length varies across test cases. Compute products dynamically using a loop or `math.prod(a)`."
        })

    # Fast I/O check
    if "sys.stdin" not in code and ("input()" in code):
        for idx, line in enumerate(code.splitlines(), 1):
            if "for " in line and "in range(" in line and "input()" in line:
                violations.append({
                    "type": "SLOW_IO_WARNING",
                    "line": idx,
                    "message": "Use `sys.stdin.read().split()` for fast bulk I/O to avoid TLE on large competitive programming inputs."
                })
                break

    return {
        "valid": len(violations) == 0,
        "violations": violations,
    }

def generate_tool_repair_prompt(code: str, audit_result: Dict[str, Any]) -> str:
    diagnostics = [f"- [{v['type']}]: {v['message']}" for v in audit_result.get("violations", [])]
    return f"""The following solution has deterministic logic/syntax defects identified by our static analysis tool:

```python
{code}
```

Static Analysis Violations:
{chr(10).join(diagnostics)}

Please fix these exact violations and provide the corrected complete Python 3 solution inside ```python ```."""
```

### 3.2 DiffCodeGen Behavioral Clustering Engine (`scripts/diff_codegen_cluster.py`)

Implements coverage-guided test-time scaling (*arXiv:2605.20473*). It samples $K$ candidates at $T=0.3$, executes them against boundary probes, and returns the medoid candidate of the consensus cluster:

```python
#!/usr/bin/env python3
"""
DiffCodeGen Behavioral Clustering Engine (arXiv:2605.20473)
Executes candidates against generic boundary probes and selects the consensus medoid.
"""

import subprocess
import tempfile
import os
from typing import List, Dict, Any, Tuple

def execute_in_sandbox(code: str, test_input: str, timeout_sec: float = 3.0) -> Tuple[bool, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        proc = subprocess.run(
            ["python3", temp_path],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()
        return False, f"RUNTIME_ERROR: {proc.stderr[:80]}"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"EXEC_ERROR: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except OSError: pass

def get_generic_probes() -> List[str]:
    return ["1\n1", "1\n0", "2\n1 2", "3\n1 2 3", "0\n"]

def cluster_and_select_medoid(candidates: List[str], probes: List[str]) -> Tuple[int, str, Dict[str, Any]]:
    if not candidates:
        return -1, "", {"error": "No candidates"}
    if len(candidates) == 1:
        return 0, candidates[0], {"cluster_size": 1, "consensus_ratio": 1.0}

    K = len(candidates)
    num_probes = len(probes)
    execution_matrix = []
    success_matrix = []

    for code in candidates:
        cand_outs, cand_succs = [], []
        for p in probes:
            succ, out = execute_in_sandbox(code, p)
            cand_succs.append(succ)
            cand_outs.append(out)
        execution_matrix.append(cand_outs)
        success_matrix.append(cand_succs)

    agreement_matrix = [[0] * K for _ in range(K)]
    for i in range(K):
        for j in range(K):
            if i == j:
                agreement_matrix[i][j] = num_probes
                continue
            matches = sum(
                1 for p in range(num_probes)
                if success_matrix[i][p] and success_matrix[j][p] and execution_matrix[i][p] == execution_matrix[j][p]
            )
            agreement_matrix[i][j] = matches

    consensus_scores = [sum(agreement_matrix[i]) for i in range(K)]
    validity_scores = [sum(1 for s in success_matrix[i] if s) for i in range(K)]
    combined_scores = [consensus_scores[i] + 2 * validity_scores[i] for i in range(K)]

    best_idx = int(max(range(K), key=lambda i: combined_scores[i]))
    return best_idx, candidates[best_idx], {
        "candidate_count": K,
        "selected_candidate_idx": best_idx,
        "consensus_scores": consensus_scores,
        "validity_scores": validity_scores,
    }
```

### 3.3 Unified Zero-Contamination Decoding Pipeline (`scripts/clean_decoding_pipeline.py`)

Wires together speculative sampling, AST linting, and OpenAI/Ollama HTTP endpoints:

```python
#!/usr/bin/env python3
"""
ApexCode Clean Decoding Pipeline with Integrated Karpathy AST Tool Repair
"""

import ast
import json
import os
import re
import time
import urllib.request
from typing import Dict, Any, Optional

from scripts.ast_linter_tool import audit_code, generate_tool_repair_prompt

OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:8080")
CODE_MODEL = os.environ.get("CODE_MODEL", "apex-code-target")

COMPETITIVE_SCAFFOLDING = """
COMPETITIVE PROGRAMMING FORMAT RULES:
1. Provide a complete, runnable Python 3 solution reading from sys.stdin and writing to sys.stdout.
2. Optimize bulk I/O with sys.stdin.read().split().
3. Output ONLY valid Python 3 code enclosed in a standard ```python ... ``` fence.
"""

def extract_python_code(text: str) -> str:
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if match: return match.group(1).strip()
    match = re.search(r"```[a-zA-Z]*\s*(.*?)\s*```", text, re.DOTALL)
    if match: return match.group(1).strip()
    return text.strip()

def query_model(prompt: str, system_prompt: str = None, temp: float = 0.0, max_tokens: int = 512) -> dict:
    if not system_prompt:
        system_prompt = "You are an elite competitive programmer. Provide only valid Python 3 code in ```python ```."
    
    endpoint = f"{OLLAMA_BASE_URL.rstrip('/')}/v1/chat/completions" if ":8080" in OLLAMA_BASE_URL else f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    is_openai = ":8080" in OLLAMA_BASE_URL or "/v1" in OLLAMA_BASE_URL

    payload = {
        "model": CODE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }

    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    latency = time.perf_counter() - t0

    if is_openai:
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = data.get("usage", {}).get("completion_tokens", 0)
    else:
        content = data.get("message", {}).get("content", "")
        tokens = data.get("eval_count", 0)

    return {"content": content, "tokens": tokens, "latency_sec": latency}

def generate_clean_solution(problem_text: str, starter_code: str = None, enable_ast_linter: bool = True) -> dict:
    prompt = f"PROBLEM SPECIFICATION:\n{problem_text}\n{COMPETITIVE_SCAFFOLDING}"
    if starter_code:
        prompt += f"\nSTARTER CODE:\n```python\n{starter_code}\n```"

    res = query_model(prompt=prompt, temp=0.0)
    code = extract_python_code(res["content"])
    total_tokens = res["tokens"]
    total_latency = res["latency_sec"]

    # External AST Linter Tool Call
    if enable_ast_linter and code:
        audit = audit_code(code)
        if not audit.get("valid", True):
            repair_prompt = generate_tool_repair_prompt(code, audit)
            repair_res = query_model(
                prompt=repair_prompt,
                system_prompt="You are an expert algorithms engineer. Fix the defects identified in the tool report.",
                temp=0.0
            )
            repaired_code = extract_python_code(repair_res["content"])
            try:
                ast.parse(repaired_code)
                code = repaired_code
                total_tokens += repair_res["tokens"]
                total_latency += repair_res["latency_sec"]
            except SyntaxError:
                pass

    return {
        "code": code,
        "tokens": total_tokens,
        "latency_sec": round(total_latency, 2)
    }
```

---

## 📊 Phase 4: Zero-Contamination Benchmark Harness

Run LiveCodeBench evaluation under strict air-gapped test-suite execution:

```bash
# Run 25-problem evaluation slice
PYTHONPATH="/Users/nileshchakraborty/workspace/LiveCodeBench:." \
OLLAMA_URL="http://192.168.1.250:8080" \
CODE_MODEL="apex-code-target" \
python3 scripts/test_livecodebench_eval.py \
  --count 25 \
  --offset 0 \
  --pipeline clean \
  --output tests/lcb_benchmark_results.json
```

---

## 🚀 Phase 5: Release Automation (Git, GitHub, Hugging Face)

### 5.1 Git Commit & Tagging

```bash
git add RELEASE_NOTES_v*.md configs/ scripts/ tests/lcb_benchmark_results*.json
git commit -m "feat(vulkan): bare-metal discrete GPU acceleration, DiffCodeGen clustering, and AST linter tool"
git tag -a v1.2.0 -m "Release v1.2.0: Bare-metal Vulkan acceleration & DiffCodeGen suite"
git push origin main --tags
```

### 5.2 GitHub Release

```bash
gh release create v1.2.0 \
  -F RELEASE_NOTES_v1.2.0.md \
  --title "ApexCode v1.2.0: Bare-Metal Vulkan GPU Acceleration & DiffCodeGen Suite"
```

### 5.3 Hugging Face Hub Upload Script

Upload Model Cards and evaluation benchmark reports using `huggingface_hub`:

```python
#!/usr/bin/env python3
"""
Automated Hugging Face Hub Publisher
"""
import os
from huggingface_hub import HfApi

api = HfApi()
repo_id = os.environ.get("HF_REPO_ID", "nileshc90/apex-code-14b-instruct")

artifacts = [
    ("huggingface/MODEL_CARD.md", "README.md", "docs: update model card with benchmarks"),
    ("tests/lcb_benchmark_results_optimized_vulkan_25p.json", "benchmark_results_25p.json", "benchmark: upload LiveCodeBench metrics"),
    ("RELEASE_NOTES_v1.2.0.md", "RELEASE_NOTES.md", "docs: update release notes"),
]

for local_path, repo_path, msg in artifacts:
    if os.path.exists(local_path):
        print(f"Uploading {local_path} -> {repo_path} ...")
        api.upload_file(
            path_or_fileobj=local_path,
            path_in_repo=repo_path,
            repo_id=repo_id,
            repo_type="model",
            commit_message=msg,
        )
print("🎉 All artifacts successfully published to Hugging Face Hub!")
```

---

## 📋 Copy-Paste Agent Replication Prompt for a New Session

When starting a fresh agent session to apply this pipeline to a new model, paste the following prompt:

````markdown
Please replicate the ApexCode test-time compute scaling and hardware acceleration pipeline for a new model:

1. **Target Model**: [SPECIFY_MODEL_NAME_OR_HUGGINGFACE_ID]
2. **Draft Model**: [SPECIFY_DRAFT_MODEL_OR_0.5B]
3. **Execution Environment**:
   - Hardware: [Mac Metal Unified RAM / Linux x86 Intel+AMD Vulkan / Docker CPU]
   - Endpoint: [http://localhost:8080 or remote host]
4. **Execution Steps**:
   - Verify hardware topology, VRAM allocation, and thermal limits (CPU temperature <= 80°C).
   - Configure native multi-model `presets.ini` with speculative decoding and q8_0 KV cache.
   - Implement the zero-contamination `scripts/ast_linter_tool.py` and `scripts/diff_codegen_cluster.py` (K=3 candidates, synthetic probes).
   - Execute the 25-problem LiveCodeBench evaluation slice.
   - Commit changes, create a git tag, create a GitHub release via `gh`, and publish the updated model card and benchmark JSON to Hugging Face Hub.
````
