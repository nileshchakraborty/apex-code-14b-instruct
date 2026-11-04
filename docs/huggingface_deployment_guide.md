# 🤗 Hugging Face Deployment Guide for ApexCode-36GB

This guide walks through deploying ApexCode-36GB to the **Hugging Face Model Hub**, enabling **1-click Ollama pulls**, and deploying an **Interactive Space Playground**.

---

## 1. Authentication

Your Hugging Face CLI is already authenticated as user: `nileshc90`.
You can verify your authentication status at any time:
```bash
hf auth whoami
```

---

## 2. Deploying Model Weights & Model Card to the Hub

To make your model available for the open-source community:

```bash
cd /Users/nileshchakraborty/workspace/apex-code-36gb

# Publish Model Card (README.md) and Ollama Modelfile to your HF account:
python3 scripts/publish_to_huggingface.py \
  --repo-id "nileshc90/apex-code-14b-instruct" \
  --model-card "./huggingface/MODEL_CARD.md"
```

### Uploading GGUF Quantized Weights:
If you have downloaded or generated `.gguf` files in `./models`:
```bash
python3 scripts/publish_to_huggingface.py \
  --repo-id "nileshc90/apex-code-14b-instruct" \
  --model-dir "./models"
```

Once uploaded, your repository will be live at:
`https://huggingface.co/nileshc90/apex-code-14b-instruct`

---

## 3. The 1-Click Hugging Face + Ollama Integration

Hugging Face and Ollama natively support direct model pulling. Any developer in the world can run your model directly without manual downloads:

```bash
# Pull and run your Q5_K_M quant directly from Hugging Face
ollama run hf.co/nileshc90/apex-code-14b-instruct:Q5_K_M

# Or run the fast Q4_K_M quant
ollama run hf.co/nileshc90/apex-code-14b-instruct:Q4_K_M
```

---

## 4. Deploying an Interactive Demo to Hugging Face Spaces

You can deploy an interactive Gradio web playground ([huggingface/app.py](file:///Users/nileshchakraborty/workspace/apex-code-36gb/huggingface/app.py)) directly as a Hugging Face Space:

### Method A: Automated via Hugging Face Hub CLI
```bash
# Create a new Gradio Space
python3 -c "
from huggingface_hub import HfApi
api = HfApi()
api.create_repo(repo_id='nileshc90/apex-code-playground', repo_type='space', space_sdk='gradio', exist_ok=True)
api.upload_file(path_or_fileobj='huggingface/app.py', path_in_repo='app.py', repo_id='nileshc90/apex-code-playground', repo_type='space')
api.upload_file(path_or_fileobj='huggingface/requirements.txt', path_in_repo='requirements.txt', repo_id='nileshc90/apex-code-playground', repo_type='space')
print('✅ Space deployed: https://huggingface.co/spaces/nileshc90/apex-code-playground')
"
```

### Method B: Via Git Push
```bash
git clone https://huggingface.co/spaces/nileshc90/apex-code-playground /tmp/hf-space
cp huggingface/app.py /tmp/hf-space/app.py
cp huggingface/requirements.txt /tmp/hf-space/requirements.txt
cd /tmp/hf-space
git add .
git commit -m "feat: initial release of ApexCode-14B interactive playground"
git push
```

---

## 5. Hugging Face Inference Endpoints (Production Cloud API)

For teams requiring an autoscaling cloud HTTP API:
1. In the Hugging Face web console, navigate to **Inference Endpoints** -> **New Endpoint**.
2. Select your repository: `nileshc90/apex-code-14b-instruct` (or `Qwen/Qwen2.5-Coder-14B-Instruct` with your LoRA adapter).
3. Select Container: **Text Generation Inference (TGI)** or **vLLM**.
4. Hardware: 1x NVIDIA L4 (24GB VRAM) or 1x A10G.
5. Deploy. You will receive an OpenAI-compatible endpoint URL for production CI/CD pipelines.
