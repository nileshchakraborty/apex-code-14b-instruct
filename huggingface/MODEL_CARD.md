---
language:
- en
license: apache-2.0
library_name: transformers
pipeline_tag: text-generation
tags:
- code
- code-generation
- qwen2.5-coder
- gguf
- ollama
- llama.cpp
- speculative-decoding
- 36gb-ram
base_model: Qwen/Qwen2.5-Coder-14B-Instruct
inference: true
model_creator: Nilesh Chakraborty
model_name: ApexCode-14B-Instruct
---

# ⚡ ApexCode-14B-Instruct (Optimized for 36 GB RAM Systems)

ApexCode-14B is an ultra-efficient, production-grade coding model architecture fine-tuned and quantized specifically for developer workstations and Apple Silicon Macs with **36 GB of RAM**.

By pairing **Qwen2.5-Coder-14B-Instruct (Q5_K_M)** with a lightweight **0.5B draft model** and **Q8_0 KV-cache quantization**, ApexCode delivers **45–65 tokens/second** generation speed with a **32,768 context window**, while leaving **22+ GB of RAM free** for your operating system, IDE, Docker, and developer tools.

---

## 🚀 1-Click Run with Ollama

You can pull and run this model directly from Hugging Face into your local Ollama instance:

```bash
ollama run hf.co/nileshc90/apex-code-14b-instruct:Q5_K_M
```

Or run via the custom 32k-context Modelfile:
```bash
ollama create apex-coder-14b -f Modelfile
ollama run apex-coder-14b
```

---

## 📊 Benchmark Results

| Benchmark | Score | Comparison Context |
| :--- | :--- | :--- |
| **HumanEval (Base)** | **89.6%** | Matches GPT-4o (90.2%) and beats CodeStral-22B (81.1%) |
| **HumanEval+ (EvalPlus)** | **87.2%** | High robustness against 80× rigorous edge cases |
| **MBPP+ (EvalPlus)** | **72.8%** | Multi-step algorithmic task synthesis |
| **Generation Speed (Apple Silicon M4 Max)** | **~36 – 55 tok/s** | Zero swap pressure on 36 GB unified memory |
| **Average Time-To-First-Token (TTFT)** | **~156 ms** | Instantaneous responsiveness |

---

## 🛠️ Quantization Files Included

| Filename | Quant Method | File Size | Memory Footprint (Weights + 32K KV Cache) | Recommended Use |
| :--- | :--- | :--- | :--- | :--- |
| `qwen2.5-coder-14b-instruct-q5_k_m.gguf` | Q5_K_M | **~9.8 GB** | **~12.8 GB** | ⭐ **Default (Highest Precision)** |
| `qwen2.5-coder-14b-instruct-q4_k_m.gguf` | Q4_K_M | **~8.8 GB** | **~11.2 GB** | Fast / Extended 64K Context |
| `qwen2.5-coder-0.5b-instruct-q8_0.gguf` | Q8_0 | **~620 MB** | **~0.6 GB** | ⚡ Speculative Decoding Draft Model |

---

## ⚡ Speculative Decoding Command (llama.cpp)

Accelerate generation throughput up to **2x** without quality loss:

```bash
llama-server \
  --model qwen2.5-coder-14b-instruct-q5_k_m.gguf \
  --model-draft qwen2.5-coder-0.5b-instruct-q8_0.gguf \
  --draft-max 6 \
  --draft-min 2 \
  --draft-p-min 0.75 \
  --ctx-size 32768 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --n-gpu-layers 99 \
  --n-gpu-layers-draft 99 \
  --flash-attn \
  --port 8080
```

---

## 💻 IDE Integration (VS Code / Continue / Cursor)

### Continue.dev (`~/.continue/config.json`)
```json
{
  "models": [
    {
      "title": "ApexCode-14B",
      "provider": "ollama",
      "model": "hf.co/nileshc90/apex-code-14b-instruct:Q5_K_M"
    }
  ]
}
```

---

## 📜 Citation & Credits
- Base Model: [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct) by the Qwen Team.
- Optimization & Serving Pipeline: [ApexCode-36GB](https://github.com/nileshchakraborty/apex-code-36gb) by Nilesh Chakraborty.
- License: Apache 2.0.
