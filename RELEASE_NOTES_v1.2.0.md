# ⚡ ApexCode Release v1.2.0: Bare-Metal Vulkan GPU Acceleration & DiffCodeGen Suite

ApexCode Release `v1.2.0` introduces native discrete GPU acceleration via Vulkan for legacy Intel + AMD hardware architectures, DiffCodeGen behavioral clustering (*arXiv:2605.20473*), and automated Karpathy-style static analysis tool repair.

---

### 🚀 Key Highlights & Breakthroughs

1. **Hardware-Native Discrete GPU Acceleration (AMD Radeon Pro GDDR6 + Vulkan)**
   - Resolves the DDR4 memory bandwidth bottleneck (~25 GB/s) on legacy Intel Core i9-9880H bare-metal machines.
   - Leverages native `llama-server` on `0.0.0.0:8080` targeting the AMD Radeon Pro 5300M/5500M discrete GPU (4 GB GDDR6 @ 192 GB/s).
   - Generates tokens at **18–26 tokens/second** (up from 1.3 tok/s on CPU-only Docker), collapsing total benchmark wall-clock time from **42.4 minutes down to 5.6 minutes (7.6x overall speedup)**.
   - Pinned CPU execution strictly preserves thermal safety ($\le 72^\circ\text{C}$, well below the $88^\circ\text{C}$ homelab watchdog ceiling).

2. **DiffCodeGen Behavioral Clustering Engine (*arXiv:2605.20473*)**
   - Implements coverage-guided test-time scaling without noisy LLM-as-a-judge overhead.
   - Samples $K=3$ diverse candidate solutions and runs them against generic boundary test probes in isolated sandboxes (`apex-sandbox-daemon`, `--net=none`, 512MB RAM cap).
   - Constructs an execution equivalence matrix and selects the medoid of the consensus behavioral cluster.

3. **Karpathy-Style Software 3.0 External AST Linter Tool Calls**
   - Deterministic AST visitor (`scripts/ast_linter_tool.py`) audits generated code for common competitive programming bugs:
     - Repeated `sys.stdin.read()` inside iteration loops (causes premature EOF).
     - Inadvertent float division (`/`) in integer indexing or slicing.
     - Hardcoded consecutive array access chains (`a[0] * a[1] * ...`) when array length varies dynamically.
     - Slow line-by-line I/O warnings.
   - Dispatches structured violation traces back to the model for single-shot surgical repair.

4. **Zero-Contamination Boundary**
   - Strictly prohibits private test inspection or problem-specific heuristics.
   - All benchmarks evaluated under black-box zero-shot execution.

---

### 📊 Benchmark Scorecard: Legacy Hardware (Intel i9-9880H + 32GB RAM + AMD Navi 14)

LiveCodeBench 25-problem evaluation slice:

| Configuration | Engine / Hardware | Generation Throughput | Total 25-Prob Wall Clock | Pass@1 Accuracy | Peak CPU Temp |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Docker Baseline (14B)** | Software AVX2 CPU | 1.30 tok/s | 42.4 minutes | 16.0% (4/25) | 90°C (Watchdog kill) |
| **Zero-Shot Vulkan (7B)** | AMD Navi 14 GDDR6 | 26.38 tok/s | 4.5 minutes | 28.0% (7/25) | 71°C (Safe) |
| **ApexCode v1.2.0 (Optimized)** | AMD Navi 14 + AST Linter | **18.0 – 26.4 tok/s** | **5.6 minutes** | **32.0% (8/25)** | **72°C (Safe)** |

---

### 📦 Hugging Face & Model Hub Artifacts
- **Repository**: `nileshc90/apex-code-14b-instruct`
- **Model Presets**:
  - `apex-code-7b-vulkan` (IQ3_M quantized GGUF, 3.57 GB)
  - `apex-code-3b-vulkan` (Q4_K_M quantized GGUF, 2.10 GB)
  - `apex-code-1.5b-vulkan` (Q4_K_M quantized GGUF, 1.11 GB)
