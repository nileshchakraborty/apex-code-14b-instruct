# 🏛️ Dual-Model Implementation Plan: ApexCode-14B & ApexThink-14B

This document defines the production implementation plan for running a **Dual-Model Local AI System** tailored for 36 GB RAM computers:
1. **ApexCode-14B:** Specializes in real-time code generation, inline tab ghost-text autocompletion (FIM), and surgical unified diff editing.
2. **ApexThink-14B:** Specializes in general-purpose intelligence, deep chain-of-thought (`<think>`) reasoning, mathematics, research analysis, and anti-hallucination factuality.

---

## 1. Mathematical Memory Budget for Dual 14B Setup

A key advantage of selecting **14B** for both roles is that **both models can comfortably coexist within a 36 GB unified memory budget**:

```
+--------------------------------------------------------------------------------+
|                         Total Unified System RAM: 36 GB                        |
+---------------------------------------------------+----------------------------+
|             Active AI Runtime: ~21.2 GB           |    Host Headroom: ~14.8 GB |
|  +---------------------------------------------+  |  +----------------------+  |
|  | ApexCode-14B (Q4_K_M)                       |  |  | macOS Kernel (3.5 GB)|  |
|  | ~8.9 GB                                     |  |  +----------------------+  |
|  +---------------------------------------------+  |  | VS Code / IDE (2.5GB)|  |
|  +---------------------------------------------+  |  +----------------------+  |
|  | ApexThink-14B (Q4_K_M)                      |  |  | Docker & Web (5.0 GB)|  |
|  | ~9.2 GB                                     |  |  +----------------------+  |
|  +---------------------------------------------+  |  | Dynamic Buffer(3.8GB)|  |
|  | Shared KV Cache Buffer (~3.1 GB total)      |  |  +----------------------+  |
+---------------------------------------------------+----------------------------+
```

| Memory Allocation Strategy | RAM Required | Best Use Case |
| :--- | :--- | :--- |
| **Strategy A: Simultaneous Resident (Zero Latency)** | **~21.2 GB** | Default on 36 GB machines. Both models stay warm in RAM. 0ms model switching time. |
| **Strategy B: Dynamic On-Demand Swapping (`keep_alive: 5m`)** | **~12.5 GB peak** | Best when running heavy local Docker containers, rendering videos, or running heavy local builds. |

---

## 2. System Architecture: The Unified API Gateway

Instead of requiring developers to manually switch ports or model names across different IDE extensions, we deploy a **Unified Smart Router Gateway** on `http://127.0.0.1:8000/v1`:

```
                 [ VS Code / Continue.dev / Cursor / Terminal CLI ]
                                         │
                                         ▼ (Unified Port :8000)
                     ┌───────────────────────────────────────┐
                     │    Apex Intelligent Router Gateway    │
                     └───────────────────┬───────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼ (Intent Classification)                       ▼
    [ Coding / Diff / FIM Autocomplete ]          [ Logic / Reasoning / Writing / Math ]
                 │                                               │
                 ▼                                               ▼
     ┌───────────────────────┐                       ┌───────────────────────┐
     │     ApexCode-14B      │                       │     ApexThink-14B     │
     │  (Qwen2.5-Coder-14B)  │                       │  (DeepSeek-R1-14B)    │
     │   ~36–55 tokens/sec   │                       │   ~55–80 tokens/sec   │
     └───────────────────────┘                       │   <think> CoT Reason  │
                                                     │   Min-P Guardrail     │
                                                     └───────────────────────┘
```

---

## 3. Five-Phase Implementation Roadmap

### Phase 1: Model Pull & Ollama Profiles Initialization
1. Pull base `deepseek-r1:14b` weights into Ollama.
2. Build `apex-think-14b` from [Modelfile.apex-think-14b](../configs/ollama/Modelfile.apex-think-14b) with `min_p 0.05` and anti-hallucination system prompt.
3. Verify both models (`apex-coder-14b` and `apex-think-14b`) in `ollama list`.

### Phase 2: Deploy Unified Smart Router Gateway
1. Implement [scripts/apex_router.py](../scripts/apex_router.py) listening on `0.0.0.0:8000`.
2. Intercepts OpenAI-compatible requests:
   * Requests containing `<|fim_prefix|>`, file paths, or coding directives are routed to **ApexCode-14B**.
   * General queries, math, analysis, and reasoning prompts are routed to **ApexThink-14B** through the anti-hallucination verification filter.

### Phase 3: IDE & Developer Workflow Integration
1. Configure `~/.continue/config.json` with multi-model slots:
   * **Tab Autocomplete:** `apex-coder-14b` (Ghost-text speed)
   * **Chat (Code):** `apex-coder-14b`
   * **Chat (Deep Architecture & Reasoning):** `apex-think-14b`
2. Provide simple CLI shortcuts:
   * `apex code "write quicksort"`
   * `apex think "analyze geopolitical causes of inflation"`

### Phase 4: Failure Isolation & Docker Sandbox (Option B)
1. Add `apex-router` to `docker-compose.hybrid.yml`.
2. Enforce memory boundary of `22G` on the container layer.

### Phase 5: Verification & End-to-End Stress Test
1. Run combined test: code refactoring on Model A while reasoning on Model B.
2. Verify host memory stays under 24 GB and swap stays at 0.0 MB.
