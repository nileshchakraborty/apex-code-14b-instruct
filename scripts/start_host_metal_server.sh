#!/usr/bin/env bash
# Host Metal Server Launcher for macOS Apple Silicon
# Runs native Metal-accelerated inference on the host with full 300+ GB/s unified memory access.

set -euo pipefail

HOST="0.0.0.0"
PORT="${PORT:-8080}"
MODEL_DIR="${MODEL_DIR:-./models}"
TARGET_MODEL="${MODEL_DIR}/qwen2.5-coder-14b-instruct-q5_k_m.gguf"
DRAFT_MODEL="${MODEL_DIR}/qwen2.5-coder-0.5b-instruct-q8_0.gguf"
CTX_SIZE="${CTX_SIZE:-32768}"

echo "=========================================================="
echo "🍎 ApexCode-36GB: Native Apple Metal Host Server"
echo "=========================================================="

# Check if on macOS
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "⚠️ This script is optimized for macOS Apple Silicon (M-Series)."
fi

# Detect Apple Silicon chip
CHIP_NAME="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'Apple Silicon')"
TOTAL_RAM_GB=$(($(sysctl -n hw.memsize) / 1024 / 1024 / 1024))
echo "💻 Hardware: $CHIP_NAME | Unified RAM: ${TOTAL_RAM_GB} GB"

# Check if Ollama is currently active or preferred
OLLAMA_ACTIVE=false
if curl -s http://127.0.0.1:11434/api/version &> /dev/null; then
    OLLAMA_ACTIVE=true
fi

# Determine server engine
if [[ "${ENGINE:-auto}" == "ollama" ]] || { [[ "${ENGINE:-auto}" == "auto" ]] && [[ "$OLLAMA_ACTIVE" == "true" ]]; }; then
    SERVER_BIN="ollama"
    echo "✅ Detected active Ollama engine (llama.cpp Metal backend)."
elif command -v llama-server &> /dev/null; then
    SERVER_BIN="llama-server"
    echo "✅ Found native llama-server with Metal acceleration."
elif command -v ollama &> /dev/null; then
    SERVER_BIN="ollama"
    echo "ℹ️ Using Ollama with native Metal acceleration."
else
    echo "❌ Neither 'llama-server' nor 'ollama' found."
    echo "💡 Recommended: Install llama.cpp via Homebrew or install Ollama:"
    echo "   brew install llama.cpp"
    exit 1
fi

if [[ "$SERVER_BIN" == "llama-server" ]]; then
    if [[ ! -f "$TARGET_MODEL" ]] || [[ ! -f "$DRAFT_MODEL" ]]; then
        echo "⚠️ Model files not detected in $MODEL_DIR."
        echo "   Please download them by running: bash scripts/download_models.sh"
        exit 1
    fi

    echo "🚀 Starting native Metal Speculative Server on http://${HOST}:${PORT}"
    echo "   - Primary Model: $TARGET_MODEL"
    echo "   - Draft Model:   $DRAFT_MODEL"
    echo "   - Acceleration:  Apple Metal GPU (offload 99 layers)"
    echo "   - Context:       $CTX_SIZE tokens (Q8_0 KV Cache)"
    echo "----------------------------------------------------------"

    exec llama-server \
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
      --flash-attn \
      --alias "qwen2.5-coder-14b-instruct" \
      --host "$HOST" \
      --port "$PORT"

elif [[ "$SERVER_BIN" == "ollama" ]]; then
    echo "🚀 Configuring Ollama with native Metal + llama.cpp acceleration..."
    # Ensure Ollama daemon is active
    if ! curl -s http://127.0.0.1:11434/api/tags &> /dev/null; then
        echo "Starting Ollama daemon in background..."
        ollama serve &
        sleep 2
    fi

    MODEL_TAG="apex-coder-14b"
    if ! ollama list | grep -q "$MODEL_TAG"; then
        echo "📥 Initializing '$MODEL_TAG' from configs/ollama/Modelfile.apex-coder-14b..."
        ollama create "$MODEL_TAG" -f configs/ollama/Modelfile.apex-coder-14b
    else
        echo "✅ Model '$MODEL_TAG' is ready in Ollama."
    fi

    echo "=========================================================="
    echo "🎉 Ollama Metal Server Ready!"
    echo "   - OpenAI API Endpoint: http://127.0.0.1:11434/v1"
    echo "   - Model ID:            $MODEL_TAG"
    echo "   - Acceleration:        Apple Metal GPU (via llama.cpp backend)"
    echo "   - Memory Context:      32,768 tokens"
    echo "=========================================================="
fi
