# 🎛️ Hardware Acceleration & Memory Bandwidth Reference

This reference provides exact compute and bandwidth characteristics across Apple Silicon (Metal), Intel/AMD x86_64 (Vulkan/AVX2), and ARM64 platforms.

---

## 1. Apple Silicon macOS (Metal Unified Memory)

- **Compute Architecture**: Unified Memory Architecture (UMA) where CPU, GPU, and Neural Engine share high-speed LPDDR5.
- **Bandwidth**:
  - M1/M2/M3/M4 Base: 100–150 GB/s
  - Pro: 150–200 GB/s
  - Max: 300–400 GB/s
  - Ultra: 800 GB/s
- **Optimal Quantizations**:
  - 14B models: `Q5_K_M` (~9.8 GB weights + 3 GB KV cache = ~13 GB). Yields 40–55 tok/s on M-Max.
  - 32B models: `Q4_K_M` (~19 GB weights + 5 GB KV cache = ~24 GB).
- **Execution Flags**:
  - `-ngl 99`: Fully offload all transformer layers to Metal.
  - `--flash-attn`: Drastically reduces memory footprint for attention tensors.
  - `--cache-type-k q8_0 --cache-type-v q8_0`: Halves KV cache memory with zero loss in perplexity.

---

## 2. Intel/AMD x86_64 with Discrete GPU (Vulkan)

- **Compute Architecture**: Dedicated GDDR6 VRAM connected via PCIe 3.0/4.0 x8/x16.
- **Bandwidth**:
  - AMD Radeon Pro 5300M/5500M (4 GB GDDR6): 192 GB/s.
  - NVIDIA RTX 3060/4060: 288–360 GB/s.
- **Vulkan Discovery**:
  - Query devices: `/usr/local/bin/llama-bench --list-devices`
  - Ensure discrete GPU (`RADV` or `NVIDIA`) is selected over integrated graphics (`Intel UHD 630`).
- **Optimal Quantizations**:
  - 7B models: `IQ3_M` (~3.57 GB) fits entirely in 4.0 GB VRAM. Throughput: 20–26 tok/s.
  - 3B models: `Q4_K_M` (~2.10 GB) leaves ~1.9 GB headroom for speculative draft model.
- **Execution Flags**:
  - `-ngl 99`: Fit layers to VRAM.
  - `-b 256 -ub 64`: Optimized batch and micro-batch size for 4 GB GDDR6 cards.
  - `--cache-type-k q8_0 --cache-type-v q8_0`.

---

## 3. Intel/AMD x86_64 Pure CPU & DDR4 RAM

- **Compute Architecture**: Host CPU reading weights across dual-channel DDR4-2666 / DDR4-3200 buses.
- **Bandwidth Bottleneck**: Dual-channel DDR4 tops out at 25–40 GB/s peak, effective streaming ~18–25 GB/s.
- **Math Rule**:
  - A 9.8 GB model on a 20 GB/s bus can NEVER exceed:
    $$\frac{20\text{ GB/s}}{9.8\text{ GB}} \approx 2.0\text{ tok/s}$$
  - A 1.1 GB model on a 20 GB/s bus achieves:
    $$\frac{20\text{ GB/s}}{1.1\text{ GB}} \approx 18–22\text{ tok/s}$$
- **Optimal Strategy**:
  - Deploy small models (1.5B or 3B) for pure CPU workloads.
  - Pin `--threads` strictly to physical core count (e.g. 8 threads on an 8-core CPU; avoid hyperthreads).

---

## 4. Linux ARM64 (AWS Graviton, Ampere Altra, Raspberry Pi 5)

- **Compute Architecture**: ARMv8.2-A / ARMv9 cores with NEON SIMD and DotProduct instructions.
- **Bandwidth**: 25–60 GB/s depending on memory channels.
- **Build Flags**:
  - Compile llama.cpp with `GGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16`.
- **Optimal Quantizations**:
  - 1.5B to 3B models in `Q4_K_M` or `Q5_K_M`.
