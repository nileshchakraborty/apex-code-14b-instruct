# 🏗️ ApexCode-36GB: System Architecture & Design Philosophy

## 1. Problem Statement & Constraints

High-end developer laptops and compact workstations frequently ship with **36 GB of Unified RAM** (e.g. Apple Silicon M3/M4 Pro and Max chips with 36GB memory). In an active coding workflow:
1. **OS + WindowServer + Display compositing:** Consumes ~3.5 GB – 5.0 GB.
2. **Modern IDE (VS Code / JetBrains / Cursor) with LSP:** Consumes ~2.0 GB – 3.5 GB.
3. **Local Dev Server / Docker / Chrome with DevTools:** Consumes ~4.0 GB – 8.0 GB.
4. **Remaining Safe Unified Memory Ceiling:** **18 GB – 24 GB**.

Attempting to run a 32B or 70B parameter model pushes total memory allocation beyond 32 GB. The operating system immediately begins swapping memory pages to the SSD (`/private/var/vm/sleepimage` or swapfile). When an LLM swaps, memory bandwidth plummets from **150–300 GB/s (unified bus)** to **3–5 GB/s (SSD NVMe read/write)**, causing token generation speed to collapse by 95% (from 30+ t/s down to 1–2 t/s).

Conversely, running a standard 7B model leaves memory underutilized while sacrificing reasoning capabilities on multi-step refactoring, architecture design, and complex debugging tasks.

ApexCode-36GB targets the mathematically optimal configuration: **14B Parameter Primary Model with 0.5B Speculative Draft Decoding and Q8 KV Cache**.

---

## 2. Memory Budget Calculus

For a transformer architecture with $L$ layers, hidden dimension $D$, $N_{heads}$ attention heads, and context length $C$:

### Weight Memory ($M_{weights}$)
$$M_{weights} = N_{params} \times b_{eff}$$
Where $b_{eff}$ is the effective bits-per-weight.
- For **Qwen2.5-Coder-14B** ($14.7 \times 10^9$ parameters):
  - At **FP16** (16 bits/param): $14.7 \times 2 = 29.4 \text{ GB}$ (Exceeds safe 22 GB ceiling).
  - At **Q8_0** (8.5 bits/param): $\approx 15.6 \text{ GB}$.
  - At **Q5_K_M** (5.5 bits/param): $\approx 9.8 \text{ GB}$ (Perplexity degradation $< 0.03$).
  - At **Q4_K_M** (4.5 bits/param): $\approx 8.8 \text{ GB}$ (Perplexity degradation $< 0.08$).

### Key-Value (KV) Cache Memory ($M_{KV}$)
For Grouped-Query Attention (GQA) with $L=48$ layers, $N_{KV}=8$ KV heads, $d_{head}=128$, and context length $C=32,768$:
$$M_{KV} = 2 \times L \times N_{KV} \times d_{head} \times C \times b_{KV}$$
- With standard **FP16 KV Cache** ($b_{KV}=2$ bytes):
  $$M_{KV}^{FP16} = 2 \times 48 \times 8 \times 128 \times 32768 \times 2 \approx 6.44 \text{ GB}$$
- With **Q8_0 Quantized KV Cache** ($b_{KV}=1$ byte):
  $$M_{KV}^{Q8\_0} = 2 \times 48 \times 8 \times 128 \times 32768 \times 1 \approx 3.22 \text{ GB}$$
- With **Q4_0 Quantized KV Cache** ($b_{KV}=0.5$ bytes):
  $$M_{KV}^{Q4\_0} = 2 \times 48 \times 8 \times 128 \times 32768 \times 0.5 \approx 1.61 \text{ GB}$$

### Speculative Draft Model Memory ($M_{draft}$)
- **Qwen2.5-Coder-0.5B** in Q8_0:
  $$M_{draft} \approx 0.62 \text{ GB}$$
  Its KV cache for $K=8$ speculative tokens is negligible ($< 5 \text{ MB}$).

### Total Peak Consumption
$$M_{total} = M_{weights}(14B) + M_{draft}(0.5B) + M_{KV}^{Q8\_0}(32k) + M_{compute}$$
$$M_{total} = 9.8 \text{ GB} + 0.62 \text{ GB} + 3.22 \text{ GB} + 0.8 \text{ GB} = \mathbf{14.44 \text{ GB}}$$

**$14.44 \text{ GB}$ fits with supreme comfort into a 36 GB machine**, leaving **21.56 GB of completely unconstrained RAM** for developer workflows.

---

## 3. Speculative Decoding Mechanics

Autoregressive token generation in LLMs is strictly memory-bandwidth bound:
$$T_{generation} \propto \frac{\text{Model Size (Bytes)}}{\text{Memory Bandwidth (GB/s)}}$$

Speculative decoding circumvents this bandwidth bottleneck:
1. **Proposal Phase (Fast):** The 0.5B draft model quickly predicts $K$ speculative tokens in sequence ($t_1, t_2, \dots, t_K$). Because the 0.5B model is tiny (~0.6 GB), it runs at **>250 tokens/sec**.
2. **Verification Phase (Parallel):** The 14B target model verifies all $K$ tokens in a **single parallel forward pass**, consuming the same memory bandwidth as generating a single token.
3. **Acceptance Criterion:** Any token that matches the probability distribution of the 14B model is accepted. In programming tasks (where code has rigid syntax like braces, keywords, and repetitive identifiers), speculative acceptance rate $\alpha$ typically exceeds **70%–85%**.

```
Draft Model (0.5B):  Generates 6 tokens -> [def, calculate, _, total, (, items]
Target Model (14B): Direct validation in 1 parallel pass
                     Verification:   [  OK ,    OK    , OK,   OK  , OK,   OK  ] -> All 6 accepted!
Speedup Factor:      ~2.1x over single-token autoregression
```

---

## 4. Fine-Tuning Recipe for Coding Excellence

To maximize coding performance beyond baseline instruct weights:

1. **Fill-In-The-Middle (FIM) Formatting:**
   Essential for instant inline code completion in VS Code:
   ```
   <|fim_prefix|>def add(a, b):<|fim_suffix|>    return result<|fim_middle|>
   ```
2. **Unified Diff / Search-Replace Editing:**
   Training the model to output compact diff chunks rather than rewriting 500-line files:
   ```diff
   <<<<<<< SEARCH
   function oldMethod() { ... }
   =======
   function newMethod() { ... }
   >>>>>>> REPLACE
   ```
3. **Agentic Tool Calling & JSON Schemas:**
   Fine-tuned on structured function calls (`execute_bash`, `read_file`, `write_file`).
4. **Direct Preference Optimization (DPO):**
   Aligned with preference pairs penalizing:
   - Extraneous chat banter ("Sure, here is your code...")
   - Hallucinated imports or deprecated APIs
   - Incomplete code blocks with `// TODO: implement later`
