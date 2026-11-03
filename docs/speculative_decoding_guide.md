# ⚡ Speculative Decoding Guide for 36 GB Setups

Speculative decoding is the single most effective software optimization to boost local LLM generation speed on unified memory systems.

---

## 1. What is Speculative Decoding?

In standard autoregressive decoding, generating $N$ tokens requires $N$ sequential memory passes over the entire model weights:
$$\text{Memory Transferred} = N \times M_{\text{model}}$$

On an Apple M4/M3/M2 chip with 150 GB/s bandwidth, reading a 10 GB model weight file takes ~66 milliseconds per token (limiting speed to ~15 tokens/sec).

With **Speculative Decoding**:
1. A small draft model (Qwen2.5-Coder-0.5B, ~600 MB) generates $K=6$ candidate tokens in just ~10 ms.
2. The primary model (Qwen2.5-Coder-14B, ~9.8 GB) processes all 6 tokens concurrently in a **single forward pass** (~66 ms).
3. If all 6 tokens are accepted, you generated 6 tokens in 76 ms ($\approx 79 \text{ tokens/sec}$), achieving a **~2x acceleration**!

Because acceptance is determined using exact rejection sampling against the 14B model's probability distribution, the output distribution is **mathematically identical** to running the 14B model alone. There is **zero loss of quality**.

---

## 2. Choosing Target and Draft Pairings

For 36 GB hardware configurations, the ideal pairings are:

| Setup Tier | Primary Model | Draft Model | RAM Used | Tokens/Sec | Quality Profile |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Flagship)** | **Qwen2.5-Coder-14B-Q5_K_M** | **Qwen2.5-Coder-0.5B-Q8_0** | **~12.8 GB** | **50 – 65 t/s** | Best reasoning & architecture |
| **Tier 2 (Hyper-Speed)** | Qwen2.5-Coder-7B-Q8_0 | Qwen2.5-Coder-0.5B-Q8_0 | ~8.4 GB | 90 – 120 t/s | Ultra-responsive inline typing |

---

## 3. Running Speculative Decoding with llama-server

You can launch native speculative decoding using `llama-server` (part of `llama.cpp`):

```bash
llama-server \
  --model models/qwen2.5-coder-14b-instruct-q5_k_m.gguf \
  --model-draft models/qwen2.5-coder-0.5b-instruct-q8_0.gguf \
  --draft-max 6 \
  --draft-min 2 \
  --draft-p-min 0.75 \
  --ctx-size 32768 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --n-gpu-layers 99 \
  --threads 8 \
  --host 127.0.0.1 \
  --port 8080
```

### Parameter Breakdown:
- `--model-draft`: Path to the 0.5B draft model weights.
- `--draft-max 6`: Proposes up to 6 speculative tokens per cycle.
- `--draft-min 2`: Minimum proposal length before triggering validation.
- `--draft-p-min 0.75`: Prunes speculative candidates when probability confidence falls below 75%.
- `--cache-type-k q8_0 --cache-type-v q8_0`: Quantizes the KV cache to 8-bit, saving 50% memory.
- `--n-gpu-layers 99`: Offloads all layers to Apple Metal GPU or CUDA.
