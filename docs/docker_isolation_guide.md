# 🐳 Docker Failure Isolation & Containerization Guide

Using Docker allows you to run, test, and serve ApexCode within a sandboxed environment, isolating failures (such as Out-Of-Memory thrashing, process segfaults, or dependency conflicts) from destabilizing your host computer.

---

## 1. What Docker Isolates

| Failure Mode | Host Impact (Without Docker) | Containerized Protection (With Docker) |
| :--- | :--- | :--- |
| **Extreme Context OOM** | Host macOS/Linux triggers page swap, freezes UI and IDE | Container hit hard limit (`memory: 22G`), gracefully restarts without freezing host |
| **Process Crash / Segfault** | API server drops, manual restart required | Docker auto-restarts the service via `restart: unless-stopped` |
| **Dependency Conflicts** | Python package version collisions (Torch, Transformers) | Isolated cleanly in container image (`apex-code-36gb:latest`) |
| **File System Pollution** | Checkpoints and temp files write across host dirs | Sandboxed to container volume mount points (`/app/models`, `/app/datasets`) |

---

## 2. Platform Architecture: Linux/CUDA vs. Apple Silicon Mac

Before deploying, it is essential to understand how Docker interacts with hardware accelerators:

### A. Linux Workstations with NVIDIA GPUs (100% Native Speed)
On Linux with NVIDIA GPUs, Docker supports native GPU passthrough via the NVIDIA Container Toolkit. You get **100% GPU acceleration with zero virtualization penalty**.

### B. Apple Silicon Macs (M-Series Unified Memory)
Docker Desktop on macOS runs containers inside a lightweight Linux Virtual Machine. **Apple does not provide Metal GPU passthrough to Linux VMs in Docker.** 
* Running `llama-server` *inside* a Docker container on macOS will run on CPU (ARM NEON), generating ~6–8 tokens/sec instead of 50+ tokens/sec on Metal.

### The 2 Recommended Setups on macOS:

#### Option 1: Hybrid Architecture (Maximum Speed + Tool Isolation) ⭐ Recommended on Mac
* **Inference Server:** Run natively on the host using Apple Metal GPU (`python3 scripts/run_speculative_server.py`) to get full **55+ tokens/sec** at 300 GB/s bandwidth.
* **Tooling & Benchmarks:** Run training, dataset preparation, and automated benchmarks inside Docker, pointing to the host endpoint via `http://host.docker.internal:8080`.

#### Option 2: Full Docker Isolation (Maximum Sandboxing)
If you are testing untrusted models, evaluating untrusted code snippets, or running in an automated CI/CD pipeline, run entirely inside Docker with the `docker-compose.yml` configuration below.

---

## 3. Quickstart: Building & Running

### 1. Build the Docker Image
```bash
docker build -t apex-code-36gb:latest .
```

### 2. Start the Isolated Speculative Server
```bash
docker-compose up -d apex-server
```

### 3. Check Container Health & Memory Usage
```bash
docker ps
docker stats apex-code-server
```
You will observe that memory is strictly capped at **22 GB**, leaving a guaranteed **14 GB buffer** for your host OS.

### 4. Run Isolated Throughput Benchmark
```bash
docker-compose run --rm apex-bench
```

### 5. Stop the Service
```bash
docker-compose down
```
