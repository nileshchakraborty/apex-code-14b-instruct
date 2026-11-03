#!/usr/bin/env bash
# ApexCode Speculative Server Launcher using llama.cpp
# Target: Qwen2.5-Coder-14B (Q5_K_M) + Draft: Qwen2.5-Coder-0.5B (Q8_0)

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-./models}"
TARGET_MODEL="${MODEL_DIR}/qwen2.5-coder-14b-instruct-q5_k_m.gguf"
DRAFT_MODEL="${MODEL_DIR}/qwen2.5-coder-0.5b-instruct-q8_0.gguf"
PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"
CTX_SIZE="${CTX_SIZE:-32768}"

if [[ ! -f "$TARGET_MODEL" ]] || [[ ! -f "$DRAFT_MODEL" ]]; then
    echo "❌ Models not found in $MODEL_DIR. Run 'bash scripts/download_models.sh' first."
    exit 1
fi

echo "🚀 Launching ApexCode Speculative Inference Server on http://${HOST}:${PORT}"
echo "🎯 Target Model: $TARGET_MODEL"
echo "⚡ Draft Model:  $DRAFT_MODEL"
echo "🧠 Context Size: $CTX_SIZE with Q8_0 KV Cache"

llama-server \
  --model "$TARGET_MODEL" \
  --model-draft "$DRAFT_MODEL" \
  --draft-max 6 \
  --draft-min 2 \
  --draft-p-min 0.75 \
  --ctx-size "$CTX_SIZE" \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --n-gpu-layers 99 \
  --n-gpu-layers-draft 99 \
  --threads 8 \
  --flash-attn \
  --alias "qwen2.5-coder-14b-instruct" \
  --host "$HOST" \
  --port "$PORT"
