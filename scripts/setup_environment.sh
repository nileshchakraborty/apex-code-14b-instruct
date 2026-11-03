#!/usr/bin/env bash
# Environment Setup for ApexCode-36GB
# Checks hardware RAM, installs dependencies via uv/pip, and configures runtimes.

set -euo pipefail

echo "=========================================================="
echo "⚡ ApexCode-36GB: System Environment Setup"
echo "=========================================================="

OS_TYPE="$(uname -s)"
ARCH_TYPE="$(uname -m)"

echo "Detected OS: $OS_TYPE ($ARCH_TYPE)"

# Hardware RAM Check
if [[ "$OS_TYPE" == "Darwin" ]]; then
    TOTAL_RAM_BYTES=$(sysctl -n hw.memsize)
    TOTAL_RAM_GB=$((TOTAL_RAM_BYTES / 1024 / 1024 / 1024))
    echo "Detected Unified System RAM: ${TOTAL_RAM_GB} GB"
elif [[ "$OS_TYPE" == "Linux" ]]; then
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
    echo "Detected System RAM: ${TOTAL_RAM_GB} GB"
else
    echo "⚠️ Unsupported OS: $OS_TYPE. Please run on macOS or Linux."
    exit 1
fi

if [[ "$TOTAL_RAM_GB" -lt 30 ]]; then
    echo "⚠️ Notice: System has ${TOTAL_RAM_GB}GB RAM. 36GB is recommended for ApexCode-14B."
    echo "   Consider using ApexCode-7B or IQ4_XS quantizations if RAM is under 32GB."
fi

# Ensure Python 3.10+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found. Please install Python 3.10 or higher."
    exit 1
fi

# Setup Virtual Environment using uv or python3 -m venv
if command -v uv &> /dev/null; then
    echo "📦 Using 'uv' for ultra-fast dependency installation..."
    uv venv .venv
    source .venv/bin/activate
    uv pip install -e .
else
    echo "📦 Using python3 -m venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e .
fi

# Check for llama.cpp / llama-server
if command -v llama-server &> /dev/null; then
    echo "✅ Found llama-server in PATH."
elif [[ "$OS_TYPE" == "Darwin" ]] && command -v brew &> /dev/null; then
    echo "💡 llama-server not found. You can install it with Metal support via Homebrew:"
    echo "   brew install llama.cpp"
fi

# Check for Ollama
if command -v ollama &> /dev/null; then
    echo "✅ Found Ollama in PATH."
else
    echo "💡 Ollama not found. Install from https://ollama.com if you prefer the Ollama backend."
fi

mkdir -p models datasets checkpoints

echo "=========================================================="
echo "✅ Environment configured successfully!"
echo "Next step: Run 'bash scripts/download_models.sh'"
echo "=========================================================="
