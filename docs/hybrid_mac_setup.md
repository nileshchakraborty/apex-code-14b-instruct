# 🍏 Option B: Hybrid macOS + Docker Architecture

The **Option B Hybrid Architecture** delivers the absolute best experience on Apple Silicon Macs (M-Series chips with Unified Memory):
1. **Host-Level Inference:** Full hardware access to the Apple Metal GPU and 300+ GB/s unified memory bandwidth (**50–65 tokens/sec**).
2. **Containerized Tooling & Evaluation:** Data pipelines, test runners, and benchmarks execute inside isolated Docker containers, preventing rogue scripts from thrashing host memory or polluting Python packages.

```
+-------------------------------------------------------------------------------+
|                       macOS Host (Apple Silicon - 36 GB RAM)                  |
|                                                                               |
|  [ Native Metal Inference Engine ]  <──────────┐ (OpenAI HTTP API :8080)      |
|    • llama-server or Ollama                    │                              |
|    • Direct Metal GPU offload                  │                              |
|    • 300+ GB/s memory bandwidth                │                              |
|    • ~12.8 GB total RAM usage                  │                              |
+------------------------------------------------│------------------------------+
                                                 │
                                                 │ host.docker.internal:8080
                                                 │
+────────────────────────────────────────────────┴──────────────────────────────+
|                      Docker Sandbox (Linux VM / Container)                    |
|                                                                               |
|  [ Tooling & Benchmarks ]           [ Dataset Synthesis & Training ]          |
|    • scripts/benchmark_throughput.py   • training/prepare_code_datasets.py    |
|    • Memory Limit: 4 GB                • Memory Limit: 8 GB                   |
|    • Isolated dependencies             • Sandboxed file system writes         |
+-------------------------------------------------------------------------------+
```

---

## 🚀 Step-by-Step Setup

### Step 1: Install Host Metal Server (One-Time)
If you haven't installed `llama.cpp` on macOS:
```bash
brew install llama.cpp
```
*(Alternatively, you can use the installed `ollama` daemon).*

### Step 2: Download the Quantized Weights
```bash
bash scripts/download_models.sh
```

### Step 3: Launch Native Host Metal Server
In your first terminal tab:
```bash
bash scripts/start_host_metal_server.sh
```
*Your server is live at `http://127.0.0.1:8080/v1` with full Apple Metal GPU acceleration.*

### Step 4: Run Isolated Tooling & Benchmarks in Docker
In a second terminal tab:
```bash
# Run isolated throughput benchmark via Docker
docker-compose -f docker-compose.hybrid.yml run --rm hybrid-bench

# Or generate synthetic code datasets inside the Docker sandbox
docker-compose -f docker-compose.hybrid.yml run --rm dataset-tool
```

---

## 🔒 Failure Isolation Safeguards in Option B

1. **Host Protection from Script Memory Leaks:**
   Any training or data synthesis script running inside Docker is bounded by `deploy.resources.limits.memory: 8G`. Even if an automated script encounters an infinite loop or data leak, Docker terminates only the container.
2. **Zero Python Host Contamination:**
   Your host macOS stays clean. You don't need to install Hugging Face libraries, PyTorch builds, or tokenizers on your host machine.
3. **Full Metal GPU Speeds:**
   Because `llama-server` runs on the host, you bypass Docker Desktop's virtualized CPU bottleneck and retain the full **55+ tokens/second** generation speed.
