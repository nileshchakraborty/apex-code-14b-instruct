#!/usr/bin/env bash
# ApexCode Hybrid Stack Orchestrator (Option B)
# Orchestrates host Metal GPU inference + Docker containerized tooling

set -euo pipefail

echo "=========================================================="
echo "⚡ ApexCode-36GB: Running Option B Hybrid Stack"
echo "=========================================================="

# Check Docker
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi

# Auto-detect whether host is running on llama-server (8080) or Ollama (11434)
TARGET_PORT="8080"
MODEL_ALIAS="qwen2.5-coder-14b-instruct"

if curl -s --max-time 2 "http://127.0.0.1:11434/api/version" &> /dev/null; then
    TARGET_PORT="11434"
    MODEL_ALIAS="apex-coder-14b"
    echo "✅ Detected active host Ollama engine (llama.cpp Metal backend) on port 11434."
elif curl -s --max-time 2 "http://127.0.0.1:8080/v1/models" &> /dev/null || curl -s --max-time 2 "http://127.0.0.1:8080/health" &> /dev/null; then
    TARGET_PORT="8080"
    MODEL_ALIAS="qwen2.5-coder-14b-instruct"
    echo "✅ Detected active native llama-server on port 8080."
else
    echo "⚠️ Neither Ollama (11434) nor llama-server (8080) appears reachable."
    echo "💡 In another terminal window, start your host server:"
    echo "   bash scripts/start_host_metal_server.sh"
    echo ""
    read -p "Press [Enter] once the host server is active, or Ctrl+C to cancel..."
    if curl -s --max-time 2 "http://127.0.0.1:11434/api/version" &> /dev/null; then
        TARGET_PORT="11434"
        MODEL_ALIAS="apex-coder-14b"
    fi
fi

echo "🐳 Launching Docker containerized benchmark (sandboxed) against host port $TARGET_PORT..."

docker-compose -f docker-compose.hybrid.yml run --rm hybrid-bench \
  --url "http://host.docker.internal:${TARGET_PORT}" \
  --model "$MODEL_ALIAS"

echo "=========================================================="
echo "✅ Option B Hybrid Execution Completed!"
echo "=========================================================="
