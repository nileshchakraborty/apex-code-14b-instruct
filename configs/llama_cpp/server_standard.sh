#!/usr/bin/env bash
# ApexCode Standard Server Launcher (Single Model without Speculation)

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-./models}"
MODEL="${MODEL_DIR}/qwen2.5-coder-14b-instruct-q5_k_m.gguf"
PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"
CTX_SIZE="${CTX_SIZE:-32768}"

if [[ ! -f "$MODEL" ]]; then
    echo "❌ Model not found at $MODEL. Run 'bash scripts/download_models.sh' first."
    exit 1
fi

echo "🚀 Launching ApexCode Standard Server on http://${HOST}:${PORT}"

llama-server \
  --model "$MODEL" \
  --ctx-size "$CTX_SIZE" \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --n-gpu-layers 99 \
  --threads 8 \
  --flash-attn \
  --alias "qwen2.5-coder-14b-instruct" \
  --host "$HOST" \
  --port "$PORT"
