# 🚀 Universal Model Replication Transcript (Mac / Intel / ARM)

This transcript is an end-to-end, copy-pasteable execution playbook designed for a fresh AI coding session. It enables you or an autonomous agent to build, optimize, serve, benchmark, and publish **any model family** (Qwen, Llama, DeepSeek, Mistral, Gemma, Phi) across **Apple Silicon (Mac Metal), Intel/AMD x86_64 (Vulkan/AVX2), and ARM64**.

---

## 📋 Master Session Initialization Prompt

Copy and paste the prompt below into a fresh agent session:

```markdown
You are task-assigned to execute an end-to-end model creation, hardware optimization, behavioral conditioning, and benchmarking pipeline across our compute infrastructure.

### Model & Hardware Parameters
- BASE_MODEL: [e.g., Qwen/Qwen2.5-Coder-7B-Instruct or meta-llama/Llama-3.2-3B-Instruct]
- DRAFT_MODEL: [e.g., Qwen/Qwen2.5-Coder-0.5B-Instruct or unsloth/Llama-3.2-1B-Instruct]
- MODEL_NAME: [e.g., apex-code-7b-v2]
- TARGET_ARCH: [mac-metal | intel-vulkan | x86-cpu | arm64-neon]
- HARDWARE_DEVICE: [Apple Silicon M-series | Intel Core i9 + AMD Radeon dGPU | AWS Graviton / ARM64]
- GGUF_QUANT_TARGET: [IQ3_M | Q4_K_M | Q5_K_M]
- GGUF_QUANT_DRAFT: [Q8_0 | Q4_K_M]
- BENCHMARK_SUITE: [LiveCodeBench 25p / HumanEval / MBPP]
- HF_REPO_ID: [e.g., <your-hf-username>/<your-model-repo>]

### Execution Protocol
1. Hardware Topology & Memory Budgeting:
   - Detect GPU/CPU compute devices, available VRAM, and RAM bandwidth.
   - Enforce thermal guardrails (CPU <= 80°C, zero swap churn).
2. Weight Ingestion & Quantization:
   - Download or quantize target & draft GGUFs according to the memory budget table.
3. High-Performance Server Configuration:
   - Configure multi-model router `presets.ini` with flash attention, quantized KV cache (q8_0), and speculative decoding.
   - Launch native `llama-server` background service on port 8080.
4. Behavioral Conditioning & Test-Time Compute (TTC):
   - Deploy zero-contamination Karpathy Software 3.0 AST Linter (`scripts/ast_linter_tool.py`) with single-shot self-repair.
   - Deploy DiffCodeGen behavioral clustering (`scripts/diff_codegen_cluster.py`) with synthetic boundary probes.
   - Connect via clean decoding pipeline (`scripts/clean_decoding_pipeline.py`).
5. Air-Gapped Benchmarking:
   - Spin up warm isolated Docker sandbox (`apex-sandbox-daemon`, `--network none`, `--memory 512m`, `--cpus 2.0`).
   - Run the benchmark suite under zero-contamination guidelines.
6. Automated Publishing & Release:
   - Git commit, tag, and create a GitHub release via `gh`.
   - Update model card README.md and upload benchmark JSON to Hugging Face Hub.
```

---

## 🛠️ Step-by-Step Transcript Execution

### Step 1: Hardware Topology & Memory Bandwidth Profiling

Run this inspection command to automatically determine the hardware profile:

```bash
# Detect Operating System & Architecture
ARCH=$(uname -m)
OS=$(uname -s)

echo "=== System Architecture: $OS $ARCH ==="

if [ "$OS" = "Darwin" ]; then
    echo "Hardware: Apple Silicon Mac (Metal acceleration)"
    sysctl -n machdep.cpu.brand_string
    sysctl -n hw.memsize | awk '{print "Unified RAM: " $1/1024/1024/1024 " GB"}'
elif [ "$OS" = "Linux" ]; then
    if command -v /usr/local/bin/llama-bench >/dev/null 2>&1; then
        echo "=== Vulkan / Compute Devices ==="
        /usr/local/bin/llama-bench --list-devices
    fi
    echo "=== CPU Info ==="
    lscpu | grep "Model name\|CPU(s):"
    free -h
fi
```

#### Hardware Matrix Guidelines:

| Architecture | Accelerator | Optimal Model Size | KV Cache | Recommended Flags |
| :--- | :--- | :--- | :--- | :--- |
| **Mac (Apple Silicon)** | Metal (UMA) | 7B–32B (Q5_K_M / Q4_K_M) | `q8_0` | `-ngl 99 -fa --threads 8` |
| **Intel/AMD Linux (dGPU)** | Vulkan (GDDR6) | 3B–7B (Q4_K_M / IQ3_M) | `q8_0` | `-ngl 99 -fa -b 256 -ub 64` |
| **Intel/AMD Linux (RAM/CPU)** | AVX2 / DDR4 | 1.5B–3B (Q4_K_M) | `f16` | `-ngl 0 --threads 8 (physical cores)` |
| **ARM64 Linux (e.g. Graviton)**| NEON / UMA | 3B–7B (Q4_K_M) | `q8_0` | `-ngl 0 --threads $(nproc)` |

---

### Step 2: Model Acquisition & Multi-Model Presets

#### 2.1 Download Target and Draft Weights
```bash
mkdir -p $HOME/models

# Download Target Model GGUF (e.g. Qwen2.5-Coder-7B in IQ3_M or Q4_K_M)
curl -L -o $HOME/models/target-model.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"

# Download Draft Model GGUF (e.g. Qwen2.5-Coder-0.5B in Q8_0)
curl -L -o $HOME/models/draft-model.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q8_0.gguf"
```

#### 2.2 Configure Native Router (`$HOME/models/presets.ini`)
```ini
# Presets configuration for llama-server
[Target-Model]
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

#### 2.3 Launch Inference Server

- **On macOS (Metal)**:
```bash
llama-server \
  --models-dir $HOME/models \
  --models-preset $HOME/models/presets.ini \
  --models-max 1 \
  --host 0.0.0.0 \
  --port 8080 &
```

- **On Linux (Systemd Service with Vulkan)**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart llama-server.service
curl -s http://127.0.0.1:8080/v1/models | jq .
```

---

### Step 3: Zero-Contamination Behavioral Conditioning (AST Linter & Clustering)

#### 3.1 Karpathy Software 3.0 External AST Linter (`scripts/ast_linter_tool.py`)
```python
#!/usr/bin/env python3
"""
Universal AST Linter Tool: Detects CP logic defects with zero test leakage.
"""
import ast
import re
from typing import Dict, Any, List

class CPVisitor(ast.NodeVisitor):
    def __init__(self):
        self.in_loop = 0
        self.repeated_stdin_read = False
        self.float_divisions = []

    def visit_For(self, node: ast.For):
        self.in_loop += 1
        self.generic_visit(node)
        self.in_loop -= 1

    def visit_While(self, node: ast.While):
        self.in_loop += 1
        self.generic_visit(node)
        self.in_loop -= 1

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "read" and isinstance(node.func.value, ast.Attribute):
                if node.func.value.attr == "stdin" and self.in_loop > 0:
                    self.repeated_stdin_read = True
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, ast.Div):
            self.float_divisions.append(getattr(node, "lineno", 0))
        self.generic_visit(node)

def audit_code(code: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"valid": False, "violations": [{"type": "SYNTAX_ERROR", "line": e.lineno, "message": str(e)}]}

    visitor = CPVisitor()
    visitor.visit(tree)
    violations = []

    if visitor.repeated_stdin_read:
        violations.append({
            "type": "REPEATED_STDIN_READ_IN_LOOP",
            "message": "Calling `sys.stdin.read()` inside a loop causes subsequent iterations to read EOF. Read tokens once with `data = sys.stdin.read().split()` and iterate with an index pointer."
        })

    if re.search(r"\w+\[0\]\s*\*\s*\w+\[1\]\s*\*\s*\w+\[2\]", code):
        violations.append({
            "type": "HARDCODED_ARRAY_LENGTH_PRODUCT",
            "message": "Do not hardcode index multiplications like `a[0] * a[1] * a[2]...`. The array length varies across test cases. Compute products dynamically using a loop or `math.prod(a)`."
        })

    return {"valid": len(violations) == 0, "violations": violations}

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

#### 3.2 DiffCodeGen Behavioral Clustering Engine (`scripts/diff_codegen_cluster.py`)
```python
#!/usr/bin/env python3
"""
DiffCodeGen Behavioral Clustering Engine (arXiv:2605.20473)
Clusters candidate outputs against synthetic boundary probes and selects the medoid.
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
        return (proc.returncode == 0, proc.stdout.strip() if proc.returncode == 0 else f"ERR: {proc.stderr[:60]}")
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"ERR: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except OSError: pass

def cluster_and_select_medoid(candidates: List[str], probes: List[str] = None) -> Tuple[int, str, Dict[str, Any]]:
    if not probes:
        probes = ["1\n1", "1\n0", "2\n1 2", "3\n1 2 3", "0\n"]
    if len(candidates) <= 1:
        return 0, (candidates[0] if candidates else ""), {"cluster_size": len(candidates)}

    K = len(candidates)
    exec_matrix, succ_matrix = [], []
    for code in candidates:
        outs, succs = [], []
        for p in probes:
            s, o = execute_in_sandbox(code, p)
            succs.append(s)
            outs.append(o)
        exec_matrix.append(outs)
        succ_matrix.append(succs)

    agreement = [[0] * K for _ in range(K)]
    for i in range(K):
        for j in range(K):
            if i == j:
                agreement[i][j] = len(probes)
            else:
                agreement[i][j] = sum(1 for p in range(len(probes)) if succ_matrix[i][p] and succ_matrix[j][p] and exec_matrix[i][p] == exec_matrix[j][p])

    consensus = [sum(agreement[i]) for i in range(K)]
    validity = [sum(1 for s in succ_matrix[i] if s) for i in range(K)]
    scores = [consensus[i] + 2 * validity[i] for i in range(K)]
    best_idx = int(max(range(K), key=lambda i: scores[i]))
    return best_idx, candidates[best_idx], {"selected_idx": best_idx, "consensus_scores": consensus}
```

---

### Step 4: Air-Gapped Benchmarking

#### 4.1 Launch Isolated Docker Sandbox
```bash
docker run -d --name apex-sandbox-daemon \
  --network none \
  --memory 512m \
  --cpus 2.0 \
  --restart always \
  python:3.12-slim sleep infinity
```

#### 4.2 Execute Evaluation Slice
```bash
PYTHONPATH=".:LiveCodeBench" \
OLLAMA_URL="http://127.0.0.1:8080" \
CODE_MODEL="apex-code-target" \
python3 scripts/test_livecodebench_eval.py \
  --count 25 \
  --offset 0 \
  --pipeline clean \
  --output tests/lcb_benchmark_results.json
```

---

### Step 5: Git, GitHub & Hugging Face Publishing

#### 5.1 Git Commit & Tag
```bash
git add RELEASE_NOTES_*.md configs/ scripts/ tests/*.json
git commit -m "feat(pipeline): complete multi-hardware model optimization, DiffCodeGen clustering, and AST linter"
git tag -a v1.2.0 -m "Release v1.2.0: Multi-hardware hardware acceleration & test-time compute scaling"
git push origin main --tags
```

#### 5.2 GitHub Release
```bash
gh release create v1.2.0 \
  -F RELEASE_NOTES_v1.2.0.md \
  --title "ApexCode v1.2.0: Multi-Hardware Acceleration & Zero-Contamination Verification"
```

#### 5.3 Automated Hugging Face Hub Upload
```python
#!/usr/bin/env python3
import os
from huggingface_hub import HfApi

api = HfApi()
repo_id = os.environ.get("HF_REPO_ID", "nileshc90/apex-code-14b-instruct")

artifacts = [
    ("huggingface/MODEL_CARD.md", "README.md", "docs: update model card with benchmarks"),
    ("tests/lcb_benchmark_results.json", "benchmark_results_25p.json", "benchmark: upload LiveCodeBench metrics"),
    ("RELEASE_NOTES_v1.2.0.md", "RELEASE_NOTES.md", "docs: update release notes"),
]

for local_path, repo_path, msg in artifacts:
    if os.path.exists(local_path):
        api.upload_file(
            path_or_fileobj=local_path,
            path_in_repo=repo_path,
            repo_id=repo_id,
            repo_type="model",
            commit_message=msg,
        )
print("Published all artifacts to Hugging Face Hub!")
```
