#!/usr/bin/env python3
"""
Turnkey LLM Model Creator & Custom Configurator
===============================================
Takes any base model family and creates a fully optimized LLM deployment
tailored specifically to the host system's RAM/VRAM limits and architecture.
"""

import os
import sys
import argparse
import subprocess
from typing import Dict, Any

# Ensure both project root and scripts dir are on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from scripts.hardware_model_profiler import (
        get_system_memory,
        get_cpu_info,
        detect_gpu_devices,
        compute_llm_recommendation,
        generate_custom_configs,
    )
except ImportError:
    from hardware_model_profiler import (
        get_system_memory,
        get_cpu_info,
        detect_gpu_devices,
        compute_llm_recommendation,
        generate_custom_configs,
    )

MODEL_DOWNLOAD_MAP = {
    # Qwen 2.5 Coder
    ("qwen2.5-coder", "14b", "q5_k_m"): "https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/qwen2.5-coder-14b-instruct-q5_k_m.gguf",
    ("qwen2.5-coder", "14b", "q4_k_m"): "https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/qwen2.5-coder-14b-instruct-q4_k_m.gguf",
    ("qwen2.5-coder", "7b", "iq3_m"): "https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-7B-Instruct-IQ3_M.gguf",
    ("qwen2.5-coder", "7b", "q4_k_m"): "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
    ("qwen2.5-coder", "3b", "q4_k_m"): "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf",
    ("qwen2.5-coder", "1.5b", "q4_k_m"): "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    ("qwen2.5-coder", "0.5b", "q8_0"): "https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q8_0.gguf",
    # Microsoft Phi-4 (USA, MIT License)
    ("phi-4", "14b", "q5_k_m"): "https://huggingface.co/bartowski/phi-4-GGUF/resolve/main/phi-4-Q5_K_M.gguf",
    ("phi-4", "14b", "q4_k_m"): "https://huggingface.co/bartowski/phi-4-GGUF/resolve/main/phi-4-Q4_K_M.gguf",
    # Llama 3.2 & Llama 3.1 (USA, Meta)
    ("llama-3.2", "3b", "q4_k_m"): "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    ("llama-3.2", "1b", "q4_k_m"): "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
    ("llama-3.1", "8b", "q5_k_m"): "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf",
    # Mistral Small 24B (France, Mistral AI - Apache 2.0)
    ("mistral", "24b", "q4_k_m"): "https://huggingface.co/bartowski/Mistral-Small-24B-Instruct-2501-GGUF/resolve/main/Mistral-Small-24B-Instruct-2501-Q4_K_M.gguf",
    ("mistral", "24b", "q5_k_m"): "https://huggingface.co/bartowski/Mistral-Small-24B-Instruct-2501-GGUF/resolve/main/Mistral-Small-24B-Instruct-2501-Q5_K_M.gguf",
    # Mistral NeMo (France/USA, Apache 2.0)
    ("mistral", "12b", "q5_k_m"): "https://huggingface.co/bartowski/Mistral-Nemo-Instruct-2407-GGUF/resolve/main/Mistral-Nemo-Instruct-2407-Q5_K_M.gguf",
    # TII Falcon 3 (UAE - Technology Innovation Institute, Apache 2.0)
    ("falcon-3", "10b", "q5_k_m"): "https://huggingface.co/tiiuae/Falcon3-10B-Instruct-GGUF/resolve/main/falcon3-10b-instruct-q5_k_m.gguf",
    ("falcon-3", "10b", "q4_k_m"): "https://huggingface.co/tiiuae/Falcon3-10B-Instruct-GGUF/resolve/main/falcon3-10b-instruct-q4_k_m.gguf",
    # Google Gemma 2 (USA, Google)
    ("gemma-2", "27b", "q4_k_m"): "https://huggingface.co/bartowski/gemma-2-27b-it-GGUF/resolve/main/gemma-2-27b-it-Q4_K_M.gguf",
    ("llama-3.2", "1b", "q4_k_m"): "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
}

def detect_model_family(base_model_name: str) -> str:
    name = base_model_name.lower()
    if "qwen" in name:
        return "qwen2.5-coder"
    elif "llama" in name:
        return "llama-3.2"
    elif "deepseek" in name:
        return "deepseek-r1"
    elif "phi" in name:
        return "phi-4"
    elif "mistral" in name:
        return "mistral"
    elif "gemma" in name:
        return "gemma-2"
    return "custom-model"

def main():
    parser = argparse.ArgumentParser(description="Create and configure an LLM model tailored to custom RAM/VRAM limits.")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-7B-Instruct", help="Base model identifier or HF repo.")
    parser.add_argument("--name", default=None, help="Name for the newly created model.")
    parser.add_argument("--vram-gb", type=float, default=None, help="Explicit VRAM limit in GB.")
    parser.add_argument("--ram-gb", type=float, default=None, help="Explicit RAM limit in GB.")
    parser.add_argument("--output-dir", default="deployments", help="Directory where model configs will be saved.")
    args = parser.parse_args()

    model_family = detect_model_family(args.base_model)
    model_name = args.name or f"custom-{model_family.split('-')[0]}"

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Profile Hardware
    mem = get_system_memory()
    cpu = get_cpu_info()
    gpus = detect_gpu_devices()

    rec = compute_llm_recommendation(
        total_ram_gb=mem["total_gb"],
        available_ram_gb=mem["available_gb"],
        gpu_devices=gpus,
        cpu_info=cpu,
        override_vram_gb=args.vram_gb,
        override_ram_gb=args.ram_gb
    )

    configs = generate_custom_configs(rec, model_name)

    # Save Modelfile and presets.ini
    modelfile_path = os.path.join(args.output_dir, f"Modelfile.{model_name}")
    presets_path = os.path.join(args.output_dir, f"presets.{model_name}.ini")
    launcher_path = os.path.join(args.output_dir, f"start_{model_name}.sh")
    downloader_path = os.path.join(args.output_dir, f"download_{model_name}.sh")

    with open(modelfile_path, "w") as f:
        f.write(configs["modelfile"])

    with open(presets_path, "w") as f:
        f.write(configs["presets_ini"])

    # Resolve download URLs
    target_tier = rec["target_model_tier"].lower()
    target_quant = rec["target_quantization"].lower()
    download_url = MODEL_DOWNLOAD_MAP.get((model_family, target_tier, target_quant))
    if not download_url:
        download_url = f"https://huggingface.co/{args.base_model}-GGUF/resolve/main/{model_family}-{target_tier}-{target_quant}.gguf"

    # Write downloader script
    with open(downloader_path, "w") as f:
        f.write(f"""#!/usr/bin/env bash
set -e
echo "Downloading target model: {model_name} ({target_tier.upper()} {target_quant.upper()})..."
mkdir -p models
curl -L -o "models/{model_name}-{target_tier}-{target_quant}.gguf" "{download_url}"
""")
        if rec["speculative_decoding"] and rec["draft_model_tier"]:
            draft_tier = rec["draft_model_tier"].lower()
            draft_quant = rec["draft_quantization"].lower()
            draft_url = MODEL_DOWNLOAD_MAP.get((model_family, draft_tier, draft_quant), f"https://huggingface.co/{model_family}-{draft_tier}-gguf")
            f.write(f"""
echo "Downloading draft model: {model_name}-draft ({draft_tier.upper()} {draft_quant.upper()})..."
curl -L -o "models/{model_name}-draft-{draft_tier}-{draft_quant}.gguf" "{draft_url}"
""")
        f.write('echo "Download complete!"\n')

    os.chmod(downloader_path, 0o755)

    # Write launcher script
    with open(launcher_path, "w") as f:
        f.write(f"""#!/usr/bin/env bash
# Turnkey Launcher for {model_name}
# Profile: {rec['tier_description']}

if command -v llama-server >/dev/null 2>&1; then
    echo "Starting llama-server on port 8080..."
    llama-server \\
      --models-dir models \\
      --models-preset "{presets_path}" \\
      --models-max 1 \\
      --host 0.0.0.0 \\
      --port 8080
elif command -v ollama >/dev/null 2>&1; then
    echo "Creating and running Ollama model: {model_name}..."
    ollama create "{model_name}" -f "{modelfile_path}"
    ollama run "{model_name}"
else
    echo "Error: Neither llama-server nor ollama was found in PATH."
    exit 1
fi
""")
    os.chmod(launcher_path, 0o755)

    print("=" * 70)
    print(f" 🎉 LLM DEPLOYMENT TAILORED FOR YOUR SYSTEM")
    print("=" * 70)
    print(f" • Target Model      : {model_name} ({rec['target_model_tier']} {rec['target_quantization']})")
    print(f" • Hardware Target   : {rec['tier_description']}")
    print(f" • Serving Engine    : {rec['recommended_backend']}")
    print(f" • Expected Speed    : {rec['estimated_tok_s']} tokens/sec")
    print(f" • KV-Cache Type     : {rec['kv_cache_quant']}")
    print(f" • Free RAM Margin   : ~{rec['free_system_headroom_gb']} GB")
    print("\n" + "=" * 70)
    print(f" 📁 GENERATED ARTIFACTS in `{args.output_dir}/`:")
    print("=" * 70)
    print(f" 1. Modelfile        : {modelfile_path}")
    print(f" 2. Presets INI      : {presets_path}")
    print(f" 3. Model Downloader : {downloader_path}")
    print(f" 4. 1-Click Launcher : {launcher_path}")
    print("\n🚀 TO RUN:")
    print(f"   bash {downloader_path} && bash {launcher_path}\n")

if __name__ == "__main__":
    main()
