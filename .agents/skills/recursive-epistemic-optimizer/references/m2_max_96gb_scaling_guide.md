# 🚀 Apple Silicon M2 Max (96 GB) Scaling & Deployment Blueprint
## High-Throughput Frontier Inference & Recursive Multi-Agent Swarm Orchestration

This guide details the exact procedures for deploying frontier-class non-restricted coding models and scaling **Recursive Multi-Agent Swarms (RecursiveMAS)** on an **Apple Silicon M2 Max with 96 GB Unified Memory**.

---

## 🖥️ 1. Hardware Architecture & Performance Envelope

| Metric | Apple Silicon M4 Max (Dev Machine) | Apple Silicon M2 Max (Production Scaling Machine) |
| :--- | :--- | :--- |
| **Unified Memory** | 36 GB LPDDR5X | **96 GB LPDDR5** |
| **Memory Bus Bandwidth** | ~300 GB/s | **~400 GB/s** (512-bit bus) |
| **CPU Configuration** | 14 Cores (10 Performance + 4 Efficiency) | **12 Cores (8 Performance + 4 Efficiency)** |
| **GPU Cores** | 32 Cores | **38 Cores Metal 3** |
| **Max Safe Model Footprint** | ~14B (Q5_K_M) + 0.5B draft | **70B (Q4_K_M) to 123B (Q3_K_M)** |
| **Concurrent Subagents** | 4 parallel workers | **8 parallel workers** |
| **Max Recursive Depth ($N$)** | $N = 3$ | **$N = 5$** |
| **KV-Cache Budget** | 8k tokens | **32k–64k tokens (FP16 or Q8_0)** |

---

## 🧠 2. Frontier Non-Restricted Models for 96 GB RAM

Strict adherence to the **non-Chinese, non-Russian, non-georestricted** policy:

### 1. Meta Llama 3.3 70B Instruct (Primary Sonnet-Parity Workhorse)
- **Origin**: USA (Meta AI, open weights)
- **Quantization**: `Q4_K_M` (~42.5 GB) or `Q5_K_M` (~48.7 GB)
- **Draft Speculative Model**: `Llama-3.2-1B-Instruct` (`Q8_0`, ~1.2 GB)
- **Inference Speed**: ~18–24 tok/s with speculative decoding over Metal GPU
- **Capabilities**: Sonnet 3.5-grade reasoning (MMLU 88.6%, HumanEval 88.4%)

### 2. Mistral Large 2 (123B) (Extreme Coding & Agentic Benchmark Match)
- **Origin**: France / European Union (Mistral AI, open weights)
- **Quantization**: `Q3_K_M` (~58.2 GB) or `Q4_K_S` (~69.0 GB)
- **Inference Speed**: ~9–12 tok/s over Metal GPU
- **Capabilities**: HumanEval 92.0% (exact match with Claude 3.5 Sonnet frontier scores)

### 3. Mistral Codestral 22B / Small 24B (High-Velocity Micro-Worker Backbone)
- **Origin**: France / European Union (Mistral AI)
- **Quantization**: `Q8_0` or `FP16` (~24 GB)
- **Inference Speed**: ~45–60 tok/s
- **Use Case**: Subagents handling atomic micro-tasks, fast AST repairs, and I/O extraction

---

## ⚡ 3. macOS Kernel Tuning: Unlocking 80 GB Wired Memory

By default, macOS allocates at most ~67% of physical RAM to the GPU/wired memory ceiling (~64 GB on a 96 GB Mac). To prevent swapping when serving a 70B model alongside 8 concurrent subagents, increase the wired memory limit to **80 GB (85,899,345,920 bytes)**:

```bash
# Set GPU wired allocation limit to 80 GB
sudo sysctl iogpu.wired_mem_limit=85899345920

# Persist across reboots (optional)
echo "iogpu.wired_mem_limit=85899345920" | sudo tee -a /etc/sysctl.conf
```

Verify that memory swap remains strictly 0.0 MB:
```bash
sysctl vm.swapusage
# Expected: vm.swapusage: total = 0.00M  used = 0.00M  free = 0.00M
```

---

## 🚀 4. Launching the Local Model Server with Speculative Decoding

### Option A: llama-server (High-Performance Metal with Draft Speculation)

```bash
# 1. Download Llama-3.3-70B and Llama-3.2-1B draft
huggingface-cli download bartowski/Llama-3.3-70B-Instruct-GGUF Llama-3.3-70B-Instruct-Q4_K_M.gguf --local-dir models/
huggingface-cli download bartowski/Llama-3.2-1B-Instruct-GGUF Llama-3.2-1B-Instruct-Q8_0.gguf --local-dir models/

# 2. Launch high-throughput server on Metal
llama-server \
  -m models/Llama-3.3-70B-Instruct-Q4_K_M.gguf \
  -md models/Llama-3.2-1B-Instruct-Q8_0.gguf \
  --draft-max 8 \
  -ngl 99 \
  -c 32768 \
  --port 8080 \
  --host 127.0.0.1 \
  --threads 8 \
  --cont-batching \
  --parallel 4
```

### Option B: Ollama (Zero-Config High-Throughput)

```bash
# Run Llama 3.3 70B directly
ollama run llama3.3:70b
```

---

## 🐝 5. Configuring Recursive Swarms on the 96 GB Machine

Run the hardware profiler to confirm optimal M2 Max parameters:
```bash
python3 scripts/hardware_model_profiler.py
```

Run the RecursiveMAS scheduler in production multi-agent mode:
```bash
python3 scripts/recursive_task_scheduler.py --mode auto
```

Or execute full LiveCodeBench benchmarking:
```bash
python3 scripts/test_livecodebench_eval.py \
  --count 25 \
  --pipeline recursive_swarm \
  --output tests/lcb_m2max_96gb_results.json
```
