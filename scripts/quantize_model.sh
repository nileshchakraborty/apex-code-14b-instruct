#!/usr/bin/env bash
# Quantization Pipeline for Custom Fine-Tuned Checkpoints
# Converts merged Hugging Face safetensors to GGUF and creates Q4_K_M, Q5_K_M, and Q8_0 quants.

set -euo pipefail

INPUT_MODEL="${1:-./output/merged_apex_coder_14b}"
OUTPUT_DIR="${2:-./models}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-$HOME/llama.cpp}"

mkdir -p "$OUTPUT_DIR"

if [[ ! -d "$INPUT_MODEL" ]]; then
    echo "❌ Input Hugging Face model directory not found at: $INPUT_MODEL"
    echo "Usage: bash scripts/quantize_model.sh <hf_model_dir> <output_dir>"
    exit 1
fi

echo "=========================================================="
echo "⚙️ Quantizing Custom Model: $INPUT_MODEL"
echo "Output Directory: $OUTPUT_DIR"
echo "=========================================================="

FP16_GGUF="${OUTPUT_DIR}/apex_coder_14b_f16.gguf"
Q5_GGUF="${OUTPUT_DIR}/apex_coder_14b_q5_k_m.gguf"
Q4_GGUF="${OUTPUT_DIR}/apex_coder_14b_q4_k_m.gguf"

# Step 1: Convert Hugging Face Safetensors to GGUF (FP16)
echo "🔄 Step 1/3: Converting Hugging Face model to GGUF FP16..."
python3 "${LLAMA_CPP_DIR}/convert_hf_to_gguf.py" "$INPUT_MODEL" --outfile "$FP16_GGUF" --outtype f16

# Step 2: Quantize to Q5_K_M (Recommended Primary)
echo "🔄 Step 2/3: Quantizing to Q5_K_M..."
llama-quantize "$FP16_GGUF" "$Q5_GGUF" q5_k_m

# Step 3: Quantize to Q4_K_M (Low Memory / Massive Context)
echo "🔄 Step 3/3: Quantizing to Q4_K_M..."
llama-quantize "$FP16_GGUF" "$Q4_GGUF" q4_k_m

echo "🧹 Cleaning up intermediate uncompressed FP16 file to conserve SSD space..."
rm -f "$FP16_GGUF"

echo "=========================================================="
echo "✅ Quantization complete!"
echo "Primary Q5_K_M: $Q5_GGUF ($(du -h "$Q5_GGUF" | cut -f1))"
echo "Compact Q4_K_M: $Q4_GGUF ($(du -h "$Q4_GGUF" | cut -f1))"
echo "=========================================================="
