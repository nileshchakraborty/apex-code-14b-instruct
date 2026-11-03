# Detailed Memory Budget Breakdown for 36 GB Systems

This document provides exact mathematical formulas, benchmarks, and configurations to run a high-performance local coding LLM on 36 GB RAM machines without experiencing swapping, thermal throttling, or OOM (Out Of Memory) crashes.

---

## 1. Physical RAM Ceiling vs Allocatable RAM

On modern 36 GB systems (e.g. Apple Silicon M3/M4 Pro and Max):
- **Physical Unified RAM:** 36 GB (38,654,705,664 bytes).
- **macOS / Linux Default VRAM Cap:** By default, Apple Silicon limits a single process or Metal allocation to ~75% of unified memory (`sysctl iogpu.wired_mem_limit`), which is approximately **27.0 GB**.
- **Recommended Safe LLM Working Boundary:** **12.0 GB – 16.0 GB**.

This allocation leaves a guaranteed **20.0 GB – 24.0 GB buffer** for:
- Operating system core kernel & window server: ~3.5 GB
- Browser with multiple documentation tabs & YouTube: ~3.0 GB
- Developer IDE (VS Code / Cursor) with Language Server Protocol (LSP): ~2.5 GB
- Docker containers, Node/Go/Rust compilers, and local test runners: ~8.0 GB
- Dynamic OS page cache for lightning-fast disk I/O: ~3.0 GB

---

## 2. Comparing Quantization Formats on 14B Weights

| Format | Bits Per Weight (bpw) | Model File Size | Perplexity vs FP16 | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **FP16** | 16.0 | 29.4 GB | Baseline (1.000) | ❌ Too large for 36GB machine |
| **Q8_0** | 8.5 | 15.6 GB | 1.001 (+0.1%) | ⚠️ Safe only with short contexts (8K) |
| **Q5_K_M** | 5.5 | **9.8 GB** | 1.004 (+0.4%) | ⭐ **Recommended Target (Best Quality/Size)** |
| **Q4_K_M** | 4.5 | **8.8 GB** | 1.012 (+1.2%) | ⭐ **Optimal for 64K+ Massive Contexts** |
| **IQ4_XS** | 4.25 | 8.1 GB | 1.020 (+2.0%) | Extreme memory saving |

---

## 3. KV Cache Quantization Impact at Scale

The Key-Value (KV) cache grows linearly with context length $C$:
$$M_{KV} = 2 \times L \times N_{KV} \times d_{head} \times C \times b_{KV}$$

For Qwen2.5-Coder-14B:
- Layers ($L$): 48
- KV Heads ($N_{KV}$): 8 (Grouped Query Attention)
- Head Dimension ($d_{head}$): 128
- Bytes per head per layer: $2 \times 8 \times 128 = 2,048$ bytes/token across all layers: $2,048 \times 48 = 98,304$ bytes/token in FP16.

### KV Cache Memory Footprint by Context Length

| Context Length ($C$) | FP16 KV Cache (`b_KV=2`) | Q8_0 KV Cache (`ctk=q8_0, ctv=q8_0`) | Q4_0 KV Cache (`ctk=q4_0, ctv=q4_0`) |
| :--- | :--- | :--- | :--- |
| **8,192 tokens** | 0.77 GB | **0.38 GB** | 0.19 GB |
| **16,384 tokens** | 1.54 GB | **0.77 GB** | 0.38 GB |
| **32,768 tokens** | 3.07 GB | **1.54 GB** | 0.77 GB |
| **65,536 tokens** | 6.14 GB | **3.07 GB** | 1.54 GB |
| **131,072 tokens** | 12.29 GB | **6.14 GB** | 3.07 GB |

> **Key Takeaway:** By activating **Q8_0 KV cache** quantization (`--cache-type-k q8_0 --cache-type-v q8_0` in llama.cpp), you save **50% of the KV cache memory** with **zero measurable degradation in code syntax or logic**, allowing full repository code ingestion!

---

## 4. Speculative Decoding Memory Overhead

Speculative decoding pairs our primary target model with an ultra-lightweight draft model:
- **Draft Model:** `Qwen2.5-Coder-0.5B-Instruct-Q8_0.gguf`
- **Draft Model Size:** 620 MB (~0.6 GB)
- **Draft KV Cache (for draft window $K=8$):** Negligible (<5 MB)
- **Total Speculative Overhead:** Only **+625 MB**

In exchange for this modest 625 MB footprint, generation throughput increases by **+75% to +110%**!
