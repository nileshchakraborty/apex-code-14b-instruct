# ⚡ Streamed Loading, Memory-Mapping (mmap), and On-Demand Model Tiering

A common question when optimizing for 36 GB RAM systems is:
> *"Why not stream larger models (e.g. 32B or 70B) from SSD into memory on demand, layer-by-layer, rather than loading everything upfront?"*

This document breaks down the underlying hardware physics, the role of `mmap`, and how to implement a practical **Tiered On-Demand Routing** strategy.

---

## 1. The Physics of Autoregressive Decoding: RAM vs. SSD

Understanding why layer-by-layer disk streaming fails for interactive coding comes down to one metric: **Memory Bandwidth**.

In Transformer-based LLMs, generating a single token requires passing the hidden vector sequentially through **every layer in the model**. To generate **1 token**, the inference engine must read the entire model weight matrix into the matrix multiplication compute units.

$$\text{Time per Token} \approx \frac{\text{Model Weights Size (GB)}}{\text{Bus Read Bandwidth (GB/s)}}$$

### Bandwidth Comparison:

| Storage / Memory Subsystem | Real-World Read Bandwidth | Time to Read 35 GB (70B Q4) | Resulting Generation Speed |
| :--- | :--- | :--- | :--- |
| **Apple Silicon Unified RAM (M4 Max)** | **~300 to 400 GB/s** | ~0.09 seconds | **15 – 35 tokens/sec** |
| **Apple Silicon Unified RAM (M4 Pro / M3)**| **~150 to 200 GB/s** | ~0.18 seconds | **10 – 18 tokens/sec** |
| **High-End PCIe Gen4/Gen5 NVMe SSD** | **~3.5 to 5.5 GB/s** | **~7.0 to 10.0 seconds** | **0.1 to 0.15 tokens/sec** |

### The Real-World Impact on Coding:
- **In RAM (ApexCode 14B Q5_K_M):** A 250-token function generates in **~4.5 seconds** (55 tok/s).
- **Streamed Layer-by-Layer from SSD (70B Model via AirLLM):** Generating that same 250-token function takes **~29 minutes** (0.14 tok/s).
- **Hardware Degrade:** Streaming 35 GB from SSD per token for 1,000 tokens writes/reads 35,000 GB (35 Terabytes) of SSD traffic in a single afternoon, causing thermal throttling and premature NAND wear.

**Conclusion:** Layer-by-layer streaming from SSD during generation is fundamentally incompatible with interactive coding, autocomplete, or conversational chat.

---

## 2. What `mmap` (Memory-Mapping) Actually Does

Both `llama.cpp` and `mlx` use `mmap()` (Memory Mapping) by default:

```c
int fd = open("model.gguf", O_RDONLY);
void* weights = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);
```

### Why `mmap` speeds up cold load time:
1. **Instant Startup (< 100 ms):** `mmap` maps the model file directly to the process's virtual address space without sequentially allocating and copying gigabytes into heap memory. The server starts listening immediately.
2. **Kernel Page Cache Sharing:** If you stop and restart `llama-server` or multiple processes access the weights, macOS keeps the pages warm in the OS kernel buffer. The second startup takes 0 seconds.
3. **Lazy Page Faulting:** The OS reads pages from disk on-demand as each transformer layer is first touched.

### The Catch with `mmap` on Oversized Models:
If your model + KV cache exceeds your 36 GB RAM, the OS will page out inactive memory to the swap file. When the attention mechanism loops back to layer 0 for the next token, the OS must swap the pages back in from disk, stalling inference back to SSD speeds.

**Key Rule:** `mmap` provides instantaneous startup **only as long as total working set fits within available RAM**.

---

## 3. The Winning Hybrid Strategy: Tiered On-Demand Model Routing

Instead of streaming layers of an oversized model from disk per-token, the recommended architecture for 36 GB computers is **Tiered On-Demand Model Routing**:

```
[ IDE: Cursor / VS Code / Cline ]
                |
        [ Model Router ]
         /            \
(Ghost-text Tab)    (Complex Refactor / Architect)
       /                \
[ Fast Tier (0.5B / 7B) ]  [ Heavy Tier (14B / 32B) ]
Permanent in RAM (~1-5 GB)  Loaded on Demand via mmap
Always 0ms cold start       Auto-unloads after 5 min idle
```

### How to configure Tiered On-Demand in Ollama:

Keep your fast completion model resident permanently, and set a lazy 5-minute timeout on the heavier model:

```bash
# Fast autocomplete (resident permanently in memory):
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5-coder:7b",
  "keep_alive": -1
}'

# Heavy reasoning/refactor model (loads via mmap in 1.2s, unloads after 5m idle):
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5-coder:14b",
  "keep_alive": "5m"
}'
```

This delivers:
1. **Zero-latency inline code completions** at any time.
2. **Instant startup for heavy tasks** via `mmap` (~1-2 seconds cold load).
3. **Zero background RAM exhaustion** when you are not actively coding.
