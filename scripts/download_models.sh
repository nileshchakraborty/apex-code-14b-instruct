#!/usr/bin/env bash
# Model Downloader for ApexCode-36GB
# Fetches primary 14B model (Q5_K_M) and 0.5B draft model (Q8_0) from Hugging Face.

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-./models}"
mkdir -p "$MODEL_DIR"

echo "=========================================================="
echo "📥 ApexCode-36GB: Model Weight Retrieval"
echo "Target Directory: $MODEL_DIR"
echo "=========================================================="

# Primary Model: Qwen2.5-Coder-14B-Instruct-Q5_K_M.gguf (~9.8 GB)
TARGET_REPO="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
TARGET_FILE="qwen2.5-coder-14b-instruct-q5_k_m.gguf"
TARGET_DEST="${MODEL_DIR}/${TARGET_FILE}"

# Draft Model: Qwen2.5-Coder-0.5B-Instruct-Q8_0.gguf (~620 MB)
DRAFT_REPO="Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF"
DRAFT_FILE="qwen2.5-coder-0.5b-instruct-q8_0.gguf"
DRAFT_DEST="${MODEL_DIR}/${DRAFT_FILE}"

download_hf_file() {
    local repo="$1"
    local filename="$2"
    local dest="$3"

    if [[ -f "$dest" ]]; then
        echo "✅ Already exists: $dest"
        return 0
    fi

    # Check if weights exist in local Ollama blob store to avoid re-downloading
    local OLLAMA_MANIFEST="$HOME/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5-coder"
    if [[ -d "$OLLAMA_MANIFEST" ]]; then
        if [[ "$filename" == *"14b"* ]] && [[ -f "$OLLAMA_MANIFEST/14b" ]]; then
            local BLOB_HASH=$(grep -o '"digest":"sha256:[^"]*"' "$OLLAMA_MANIFEST/14b" | head -1 | cut -d: -f2 | tr -d '"')
            local BLOB_FILE="$HOME/.ollama/models/blobs/sha256-$BLOB_HASH"
            if [[ -f "$BLOB_FILE" ]]; then
                echo "⚡ Found local Ollama blob for 14B! Linking instantly without re-downloading..."
                ln "$BLOB_FILE" "$dest"
                return 0
            fi
        fi
        if [[ "$filename" == *"0.5b"* ]] && [[ -f "$OLLAMA_MANIFEST/0.5b" ]]; then
            local BLOB_HASH=$(grep -o '"digest":"sha256:[^"]*"' "$OLLAMA_MANIFEST/0.5b" | head -1 | cut -d: -f2 | tr -d '"')
            local BLOB_FILE="$HOME/.ollama/models/blobs/sha256-$BLOB_HASH"
            if [[ -f "$BLOB_FILE" ]]; then
                echo "⚡ Found local Ollama blob for 0.5B! Linking instantly without re-downloading..."
                ln "$BLOB_FILE" "$dest"
                return 0
            fi
        fi
    fi

    echo "⬇️ Downloading $filename from $repo..."
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download "$repo" "$filename" --local-dir "$MODEL_DIR" --local-dir-use-symlinks False
    elif command -v curl &> /dev/null; then
        local url="https://huggingface.co/${repo}/resolve/main/${filename}"
        curl -L -o "$dest" "$url"
    else
        echo "❌ Neither huggingface-cli nor curl found. Please install one of them."
        exit 1
    fi
}

download_hf_file "$TARGET_REPO" "$TARGET_FILE" "$TARGET_DEST"
download_hf_file "$DRAFT_REPO" "$DRAFT_FILE" "$DRAFT_DEST"

echo "=========================================================="
echo "✅ Download complete!"
echo "Target Model: $TARGET_DEST ($(du -h "$TARGET_DEST" | cut -f1))"
echo "Draft Model:  $DRAFT_DEST ($(du -h "$DRAFT_DEST" | cut -f1))"
echo "=========================================================="
