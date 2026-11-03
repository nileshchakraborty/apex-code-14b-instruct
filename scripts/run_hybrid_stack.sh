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

SERVER_URL="http://127.0.0.1:8080/v1"
echo "🔍 Checking if host Metal server is reachable at $SERVER_URL..."

if ! curl -s --max-time 2 "http://127.0.0.1:8080/health" &> /dev/null && ! curl -s --max-time 2 "http://127.0.0.1:8080/v1/models" &> /dev/null; then
    echo "⚠️ Host Metal server is not currently running."
    echo "💡 In another terminal window, start the host Metal server:"
    echo "   bash scripts/start_host_metal_server.sh"
    echo ""
    read -p "Press [Enter] once the host server is active, or Ctrl+C to cancel..."
fi

echo "✅ Host Metal server is active."
echo "🐳 Launching Docker containerized benchmark (sandboxed)..."

docker-compose -f docker-compose.hybrid.yml run --rm hybrid-bench

echo "=========================================================="
echo "✅ Option B Hybrid Execution Completed!"
echo "=========================================================="
