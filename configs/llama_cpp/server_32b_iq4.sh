#!/usr/bin/env bash
# ApexCode 32B Server Launcher (Optimized for 36 GB RAM Systems)
# Uses Qwen2.5-Coder-32B (IQ4_XS) with Q4_0 KV Cache to maximize intelligence without swapping.

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-./models}"
MODEL="${MODEL_DIR}/qwen2.5-coder-32b-instruct-iq4_xs.gguf"
PORT="${PORT:-8081}"
HOST="${HOST:-127.0.0.1}"
CTX_SIZE="${CTX_SIZE:-16384}"

if [[ ! -f "$MODEL" ]]; then
    echo "❌ 32B model not found at $MODEL."
    echo "Download it using:"
    echo "  huggingface-cli download Qwen/Qwen2.5-Coder-32B-Instruct-GGUF qwen2.5-coder-32b-instruct-iq4_xs.gguf --local-dir $MODEL_DIR"
    exit 1
fi

echo "=========================================================="
echo "🧠 Launching ApexCode-32B (Highest Intelligence Tier)"
echo "Model: $MODEL (~18.2 GB)"
echo "Context: $CTX_SIZE with Q4_0 KV Cache"
echo "Listening on: http://${HOST}:${PORT}/v1"
echo "=========================================================="

llama-server \
  --model "$MODEL" \
  --ctx-size "$CTX_SIZE" \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  --n-gpu-layers 99 \
  --threads 8 \
  --flash-attn \
  --spec-type ngram-mod \
  --alias "qwen2.5-coder-32b-instruct" \
  --host "$HOST" \
  --port "$PORT"
