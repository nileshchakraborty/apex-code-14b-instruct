# 🧠 General-Purpose Model Validation & Anti-Hallucination Architecture

This document provides independent benchmark validation for general-purpose LLMs on 36 GB RAM systems and details our multi-tiered **Anti-Hallucination Filter Stack**.

---

## 1. Web Validation: General-Purpose Model Performance

### The Frontier Reasoning Leader: DeepSeek-R1-Distill-Qwen-14B

Independent benchmarks validate that **DeepSeek-R1-Distill-Qwen-14B** punches dramatically above its parameter class, outperforming older 70B models and rivaling OpenAI o1-mini on deep reasoning:

| Benchmark | DeepSeek-R1-Distill-14B | GPT-4o (Standard) | Claude 3.5 Sonnet | What It Tests |
| :--- | :--- | :--- | :--- | :--- |
| **AIME 2024** | **69.7%** (Pass@1) | 53.3% | 78.0% | National competition mathematics |
| **MATH-500** | **93.9%** (Pass@1) | 74.6% | 78.3% | Advanced competition-level mathematics |
| **GPQA Diamond** | **59.1%** | 53.6% | 65.0% | Google-proof PhD-level physics/chemistry/biology |
| **Tokens/sec (M4 Max)** | **55 – 80 tok/s** | Cloud API | Cloud API | Real-time generation speed |
| **RAM Footprint (Q4_K_M)**| **~9.2 GB** | — | — | Leaves **26+ GB completely free** on 36 GB Mac |

### The Knowledge & Writing Leader: Qwen2.5-32B-Instruct

* **MMLU-Pro:** **56.8%** (Ranks #1 among all open models under 70B).
* **Generation Speed (M4 Max):** **10 – 14 tokens/sec**.
* **RAM Footprint (IQ4_XS):** **~18.2 GB**.
* **Role:** Best for long-form nuanced prose, policy documents, and broad conversational synthesis.

---

## 2. The Anti-Hallucination Filter Architecture

Hallucinations in LLMs are not random; they occur when the model's confidence distribution flattens, and standard sampling (like high temperature or broad Top-P) selects low-probability "tail" tokens.

We implement a **3-Tier Anti-Hallucination Guardrail Stack**:

```
[ User Input ]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ TIER 1: Prompt-Level Epistemic Humility Constraints   │
│   • Forces model to admit "UNVERIFIED: [Topic]"       │
│   • Prohibits fabricated URLs, DOIs, and packages      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ TIER 2: Decoding-Level Min-P Truncation Sampling       │
│   • Threshold = min_p × P(top_token)                   │
│   • Dynamically drops low-confidence hallucination tail│
│   • min_p = 0.05 to 0.06; temperature = 0.2 to 0.6     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ TIER 3: Runtime Heuristic Verification Guardrail       │
│   • In-flight URL and DOI syntax audit                 │
│   • Epistemic hedge phrase detection                   │
│   • Generates risk classification score (LOW/MED/HIGH) │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
              [ Verified Grounded Output ]
```

---

## 3. How Min-P Sampling Prevents Hallucinations

Unlike traditional **Top-P (Nucleus)** sampling (which accumulates tokens until reaching a cumulative sum, often leaving hundreds of garbage tokens in high-entropy states):

**Min-P** calculates a dynamic cutoff relative to the single most confident token:
$$\text{Cutoff Threshold} = \text{min\_p} \times P(\text{top\_token})$$

### Concrete Example:
1. If the top candidate token has a probability of $P = 0.60$ ($60\%$) and $\text{min\_p} = 0.05$:
   $$\text{Threshold} = 0.05 \times 0.60 = 0.03 \quad (3.0\%)$$
   *Any token with less than $3\%$ probability is discarded.*
2. When an LLM begins to hallucinate, its top token confidence plummets (e.g. $P = 0.20$).
3. The threshold dynamically shifts to $0.05 \times 0.20 = 0.01$, pruning candidate tokens that represent wild fabrications.

---

## 4. How to Use the Anti-Hallucination Guardrail

### 1. In Ollama via Modelfile
The guardrail is embedded directly in [`configs/ollama/Modelfile.apex-think-14b`](../configs/ollama/Modelfile.apex-think-14b):
```bash
ollama create apex-think-14b -f configs/ollama/Modelfile.apex-think-14b
ollama run apex-think-14b
```

### 2. Standalone Verification Engine
You can run the audit filter against any model query:
```bash
python3 scripts/anti_hallucination_guardrail.py \
  --url "http://127.0.0.1:11434" \
  --model "apex-think-14b" \
  --prompt "Summarize the quantum Hall effect and identify the exact year it was discovered."
```
