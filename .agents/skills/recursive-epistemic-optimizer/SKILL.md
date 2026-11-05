---
name: recursive-epistemic-optimizer
description: Orchestrates Recursive Multi-Agent Swarms (RecursiveMAS), HippoRAG Epistemic Memory with semantic deduplication, Smart Decision Override (Dual-Process Routing), CAR Task defect triage, and Zero-Assumption contracts for local model serving and benchmarking across Apple Silicon M4 Max (36 GB) and M2 Max (96 GB).
---

# 🧠 Recursive Epistemic Optimizer Skill

## Overview

This skill equips autonomous agents with the methods, scripts, and runtime invariant checks required to solve complex coding, competitive programming, and multi-file engineering tasks at Claude Sonnet 3.5/3.7 level using local open-weight models (strictly non-Chinese, non-Russian, non-georestricted backbones: **Meta Llama 3.3 70B**, **Mistral Large 2**, **Mistral Codestral 22B**, **Microsoft Phi-4**).

Grounding research literature:
- **RecursiveMAS** (*Yang et al., arXiv:2604.25917*): Recursive Directed Acyclic Graph (DAG) task decomposition down to depth $N$.
- **HippoRAG** (*Gutiérrez et al., Stanford / NeurIPS*): Associative knowledge graph triples with Personalized PageRank (PPR) contextual retrieval.
- **Hardware-Aware Backpressure Scheduling** (*DT2GS, NeurIPS*): Dynamic RAM/CPU throttling to prevent thrashing and OOM.

---

## 🏛️ Core Architectural Components

### 1. Smart Decision Override (Dual-Process Cognitive Router)
- **File**: `scripts/recursive_task_scheduler.py`
- Computes deterministic task complexity score $\mathcal{C}(\mathcal{T}) \in [0.0, 1.0]$.
- **Route A (System 1: Fast-Path)**: $\mathcal{C} < 0.55$ (single-file scripts, straightforward functions).
  - Direct speculative generation in $<500\text{ ms}$, 0 subagents spawned.
  - Deterministic validation by Karpathy AST Linter.
  - If valid: delivers instant solution.
  - If defect detected: calls CAR Analyzer.
- **Route B (System 2: RecursiveMAS Swarm)**: $\mathcal{C} \ge 0.55$ (multi-step algorithms, competitive programming, high constraint density).
  - Decomposes problem into atomic DAG micro-tasks down to depth $N$.
  - Executes with hardware backpressure and epistemic memory sharing.

### 2. CAR Task Engine (Cause & Analysis Request)
- **File**: `scripts/car_analyzer.py`
- Classifies any defect into:
  - **Type A (Surface Defect)**: Low blast radius (typos, standard imports, fast I/O, float division).
    - Resolution: Single-shot deterministic AST repair without spinning up agents.
  - **Type B (Root-Cause Epistemic Defect)**: High blast radius (algorithmic complexity TLE $O(N^2)$, broken invariants, missing specifications).
    - Resolution: Posts an Epistemic Defect Ticket (`CAR_DEFECT_ROOT_CAUSE`) to the Shared Memory Bus and auto-escalates to System 2 RecursiveMAS with the exact missing info as a seed.

### 3. Zero-Assumption & Strict Bounded Scope Invariant
- Every subagent operates under the non-negotiable **Invariant of Minimum Sufficient Action**:
  - Subagents must **never guess** missing specifications, assume arbitrary data schemas, or fabricate test bounds.
  - If information is missing, subagent halts and emits:
    ```json
    {
      "status": "BLOCKED_MISSING_INFO",
      "subagent_id": "subagent_worker_id",
      "missing_entity": "timestamp_format_precision",
      "blocking_reason": "Input specification does not clarify ISO8601 vs epoch milliseconds; guessing would risk test failure."
    }
    ```
  - The ticket is registered on the Epistemic Memory Bus for surgical resolution.

### 4. Shared Epistemic Memory Bus (HippoRAG + Semantic Cache)
- **File**: `scripts/epistemic_cache.py`
- **Semantic Deduplication Filter**:
  - Embeds queries into 384-dim space.
  - Checks cosine similarity against historical research.
  - $\text{sim}(q_{\text{new}}, q_{\text{cached}}) \ge 0.92 \implies$ **Instant Cache Hit (0 duplicate queries/tokens)**.
- **HippoRAG Knowledge Graph**:
  - OpenIE triples: `(Subject, Relation, Object, Confidence)`.
  - Multi-hop associative context extracted via **Personalized PageRank (PPR)**.

### 5. Epistemic Gap Arbiter & Multi-Agent Synthesizer
- **File**: `scripts/epistemic_gap_arbiter.py`
- Conducts topological audits over the knowledge graph.
- Dispatches surgical Round 2 queries strictly for open tickets and contradictions.
- Verifies final code with Karpathy AST Linter and zero-contamination DiffCodeGen clustering.

---

## 🛠️ CLI Quick Reference

```bash
# 1. Profile host hardware and get optimal concurrency/KV-cache recommendations
python3 scripts/hardware_model_profiler.py

# 2. Test Epistemic Memory Bus and HippoRAG PPR associative retrieval
python3 scripts/epistemic_cache.py

# 3. Test CAR Analyzer and Zero-Assumption scope validation
python3 scripts/car_analyzer.py

# 4. Run Cognitive Router and Recursive Task Scheduler
python3 scripts/recursive_task_scheduler.py --mode auto

# 5. Run LiveCodeBench evaluation slice with RecursiveMAS swarm
python3 scripts/test_livecodebench_eval.py \
  --count 25 \
  --pipeline recursive_swarm \
  --output tests/lcb_benchmark_recursive_swarm.json
```

---

## 🖥️ Cross-Machine Deployment (M4 Max 36GB -> M2 Max 96GB)

Refer to [`references/m2_max_96gb_scaling_guide.md`](file:///Users/nileshchakraborty/workspace/model-creator/.agents/skills/recursive-epistemic-optimizer/references/m2_max_96gb_scaling_guide.md) for full instructions on:
1. Setting the 80 GB macOS wired memory ceiling:
   `sudo sysctl iogpu.wired_mem_limit=85899345920`
2. Serving **Meta Llama 3.3 70B** with **Llama 3.2 1B draft** speculative decoding on Metal.
3. Scaling concurrent workers from 4 to 8, with recursive depth up to $N = 5$.
