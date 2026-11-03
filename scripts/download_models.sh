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
