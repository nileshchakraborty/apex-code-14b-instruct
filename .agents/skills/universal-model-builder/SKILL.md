---
name: universal-model-builder
description: Build, quantize, optimize, serve, condition, and benchmark any LLM family (Qwen, Llama, DeepSeek, Mistral, Gemma, Phi) across Mac (Apple Silicon Metal MPS), Intel/AMD x86_64 (Vulkan/AVX2), and Linux ARM64. Implements zero-contamination Karpathy Software 3.0 AST linting, DiffCodeGen behavioral clustering (arXiv:2605.20473), Docker sandbox execution, and automated GitHub/Hugging Face publishing.
---

# 🌐 Universal Model Builder & Hardware Optimization Skill

This skill provides an end-to-end engineering protocol to build, optimize, serve, condition, benchmark, and publish any model of any family across Apple Silicon (Metal), Intel/AMD x86_64 (Vulkan/AVX2), and Linux ARM64 environments.

---

## 🧭 Phase 1: Hardware Topology & Memory Budgeting

### 1.1 Hardware Detection
Detect the active host OS, GPU compute devices, and memory topology:

```bash
ARCH=$(uname -m)
OS=$(uname -s)

if [ "$OS" = "Darwin" ]; then
    echo "Host: Apple Silicon macOS"
    sysctl -n machdep.cpu.brand_string
    sysctl -n hw.memsize | awk '{print "Unified RAM: " $1/1024/1024/1024 " GB"}'
elif [ "$OS" = "Linux" ]; then
    if command -v /usr/local/bin/llama-bench >/dev/null 2>&1; then
        echo "=== Vulkan / Compute Accelerators ==="
        /usr/local/bin/llama-bench --list-devices
    fi
    lscpu | grep "Model name\|CPU(s):"
    free -h
fi
```

### 1.2 Memory Bandwidth & Model Selection Rules

Generation speed is fundamentally bounded by memory bandwidth:
$$\text{Max Generation Tokens/sec} \approx \frac{\text{Memory Bandwidth (GB/s)}}{\text{Model Footprint (GB)}}$$

| Architecture | Memory Bus | Bandwidth | Optimal Model Size | Quantization |
| :--- | :--- | :---: | :---: | :---: |
| **Apple Silicon (M-series)** | Unified LPDDR5 | 150–800 GB/s | **7B to 32B** | **Q5_K_M** (9.8 GB) / **Q4_K_M** (19 GB) |
| **Discrete GPU (AMD/NVIDIA)** | Dedicated GDDR6 | 192–448 GB/s | **3B to 7B** | **IQ3_M** (3.57 GB) / **Q4_K_M** (2.1 GB) |
| **Intel Core i9 / DDR4 RAM** | Dual-channel DDR4 | 25–40 GB/s | **1.5B to 3B** | **Q4_K_M** (1.1–2.1 GB) |
| **Linux ARM64 (Graviton/SBC)**| DDR4 / LPDDR4x | 20–50 GB/s | **1.5B to 3B** | **Q4_K_M** (1.1–2.1 GB) |

### 1.3 Thermal & Watchdog Guardrails
- **CPU Temperature Ceiling**: Keep CPU package temperature $\le 80^\circ\text{C}$ (homelab watchdog ceiling is $88^\circ\text{C}$).
- **SSD Swap Churn**: Maintain $0.0\text{ MB}$ swap churn during model inference.
- **Watchdog Whitelist**: If a local watchdog exists (`/usr/local/bin/homelab-watchdog.sh`), whitelist `llama-server`.

---

## 📦 Phase 2: Ingestion & Quantization Strategy

1. **Target Model**: Download pre-quantized GGUF or convert Hugging Face weights using `llama.cpp/convert_hf_to_gguf.py`.
2. **Draft Model Pairing**: For speculative decoding, select a smaller model from the same architecture family (e.g. Qwen 7B target + Qwen 0.5B draft; Llama-3 8B target + Llama-3.2 1B draft).
3. **Draft Quantization**: Use **Q8_0** (or **Q4_K_M**) for the draft model to maintain drafting accuracy while keeping memory footprint under 400–600 MB.

---

## ⚡ Phase 3: High-Performance Multi-Model Serving

### 3.1 Preset Router (`presets.ini`)
Deploy multi-model routing with quantized KV cache and speculative decoding:

```ini
[Target-Model]
model = /path/to/target-model.gguf
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
model = /path/to/target-model.gguf
model-draft = /path/to/draft-model.gguf
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

### 3.2 Launching the Server
- **Vulkan / Systemd Linux**:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart llama-server.service
  ```
- **Apple Silicon macOS (Metal)**:
  ```bash
  llama-server --models-dir $HOME/models --models-preset $HOME/models/presets.ini --models-max 1 --port 8080 &
  ```

---

## 🧠 Phase 4: Zero-Contamination Behavioral Conditioning (Test-Time Compute)

To achieve elite performance without benchmark leakage, use two complementary test-time scaling components:

### 4.1 Karpathy Software 3.0 External AST Linter (`scripts/ast_linter_tool.py`)
Deterministic static analysis catching competitive programming anti-patterns:
- **Repeated `sys.stdin.read()` inside loops**: Causes subsequent loop iterations to read EOF.
- **Float division `/` in array index contexts**: Enforces integer division `//`.
- **Hardcoded index multiplications** (e.g. `a[0] * a[1] * a[2]`): Enforces dynamic loops or `math.prod(a)`.
- **Unbuffered input in large loops**: Recommends `sys.stdin.read().split()`.
- **Automated Tool Feedback**: Generates single-shot repair prompts to self-correct in a single follow-up inference call.

### 4.2 DiffCodeGen Behavioral Clustering Engine (`scripts/diff_codegen_cluster.py`)
Implements *arXiv:2605.20473*:
- Samples $K$ diverse candidates at temperature $T=0.3-0.5$.
- Runs candidates against purely synthetic, problem-agnostic boundary arrays (`"1\n1"`, `"2\n1 2"`, `"3\n1 2 3"`).
- Computes behavioral execution agreement matrix.
- Selects the **consensus medoid candidate** with zero benchmark contamination.

---

## 📊 Phase 5: Air-Gapped Benchmarking

### 5.1 Sandbox Daemon Setup
Ensure complete isolation using a pre-warmed Docker daemon:
```bash
docker run -d --name apex-sandbox-daemon \
  --network none \
  --memory 512m \
  --cpus 2.0 \
  --restart always \
  python:3.12-slim sleep infinity
```

### 5.2 Execute Benchmark Suite
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

## 🚀 Phase 6: Automated Publishing Pipeline

1. **Git Commit & Tag**:
   ```bash
   git add RELEASE_NOTES_*.md configs/ scripts/ tests/*.json .agents/
   git commit -m "feat: complete model optimization, test-time compute, and verification"
   git tag -a v1.x.x -m "Release v1.x.x"
   git push origin main --tags
   ```
2. **GitHub Release**:
   ```bash
   gh release create v1.x.x -F RELEASE_NOTES_v1.x.x.md --title "Model Release v1.x.x"
   ```
3. **Hugging Face Hub Sync**:
   Upload updated `MODEL_CARD.md` (as `README.md`), benchmark result JSONs, and configuration files via `huggingface_hub.HfApi()`.
