#!/usr/bin/env python3
"""ApexCode Speculative Server Launcher.

Detects hardware memory, verifies quantized model weights, and orchestrates
the low-latency speculative decoding server (14B target + 0.5B draft).
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import psutil


def get_system_ram_gb() -> float:
    """Return total physical RAM in gigabytes."""
    return psutil.virtual_memory().total / (1024**3)


def check_models(target_path: str, draft_path: str) -> bool:
    """Verify presence of both model weights."""
    target_ok = os.path.isfile(target_path)
    draft_ok = os.path.isfile(draft_path)
    if not target_ok:
        print(f"❌ Target model not found at: {target_path}")
    if not draft_ok:
        print(f"❌ Draft model not found at: {draft_path}")
    return target_ok and draft_ok


def launch_server(
    target_model: str,
    draft_model: str,
    host: str = "127.0.0.1",
    port: int = 8080,
    ctx_size: int = 32768,
    draft_tokens: int = 6,
):
    ram_gb = get_system_ram_gb()
    os_name = platform.system()
    arch = platform.machine()

    print("=" * 64)
    print("⚡ ApexCode-36GB Speculative Inference Engine")
    print("=" * 64)
    print(f"🖥️  System Platform: {os_name} ({arch})")
    print(f"🧠 Detected Physical RAM: {ram_gb:.1f} GB")

    if ram_gb < 30.0:
        print("⚠️ Warning: System has less than 30 GB RAM. Setting context to 16,384 to stay within limits.")
        ctx_size = min(ctx_size, 16384)

    # Check for llama-server
    llama_server_bin = shutil.which("llama-server")
    if not llama_server_bin:
        print("❌ Error: 'llama-server' binary not found in PATH.")
        if os_name == "Darwin":
            print("💡 Install on macOS with: brew install llama.cpp")
        else:
            print("💡 Build or install llama.cpp from: https://github.com/ggerganov/llama.cpp")
        sys.exit(1)

    if not check_models(target_model, draft_model):
        print("\n📥 Please download the required model files first by running:")
        print("   bash scripts/download_models.sh")
        sys.exit(1)

    cmd = [
        llama_server_bin,
        "--model", target_model,
        "--model-draft", draft_model,
        "--draft-max", str(draft_tokens),
        "--draft-min", "2",
        "--draft-p-min", "0.75",
        "--ctx-size", str(ctx_size),
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
        "--n-gpu-layers", "99",
        "--n-gpu-layers-draft", "99",
        "--flash-attn",
        "--alias", "qwen2.5-coder-14b-instruct",
        "--host", host,
        "--port", str(port),
    ]

    print("\n🚀 Executing Launch Command:")
    print(" ".join(cmd))
    print(f"\n📡 OpenAI API Endpoint: http://{host}:{port}/v1")
    print("Press Ctrl+C to stop.\n" + "=" * 64 + "\n")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down ApexCode Server gracefully.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Server exited with error code {e.returncode}")
        sys.exit(e.returncode)


def main():
    parser = argparse.ArgumentParser(description="ApexCode Speculative Inference Server")
    parser.add_argument(
        "--target-model",
        default="./models/qwen2.5-coder-14b-instruct-q5_k_m.gguf",
        help="Path to primary 14B GGUF model",
    )
    parser.add_argument(
        "--draft-model",
        default="./models/qwen2.5-coder-0.5b-instruct-q8_0.gguf",
        help="Path to 0.5B draft GGUF model",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host binding")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--ctx-size", type=int, default=32768, help="Context window token size")
    parser.add_argument("--draft-tokens", type=int, default=6, help="Max speculative candidate tokens")
    args = parser.parse_args()

    launch_server(
        target_model=args.target_model,
        draft_model=args.draft_model,
        host=args.host,
        port=args.port,
        ctx_size=args.ctx_size,
        draft_tokens=args.draft_tokens,
    )


if __name__ == "__main__":
    main()
