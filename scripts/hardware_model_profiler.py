#!/usr/bin/env python3
"""
Hardware & Memory Auto-Profiler and LLM Sizing Advisor
=====================================================
Analyzes host hardware (Mac Metal, Intel/AMD Vulkan/CUDA, ARM64, or CPU/RAM)
and dynamically recommends the exact LLM parameter tier, quantization scheme,
KV-cache configuration, and speculative draft model pairing tailored to
the system's physical limits and developer workload.
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import re
from typing import Dict, Any, List, Optional

def get_system_memory() -> Dict[str, float]:
    """Returns total and available RAM in GB."""
    total_gb = 16.0
    avail_gb = 8.0

    system = platform.system()
    if system == "Darwin":
        try:
            mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
            total_gb = mem_bytes / (1024 ** 3)
            vm_stat = subprocess.check_output(["vm_stat"]).decode("utf-8")
            lines = vm_stat.splitlines()
            page_size = 4096
            free_pages = 0
            inactive_pages = 0
            for line in lines:
                if "page size of" in line:
                    parts = line.split("page size of")
                    if len(parts) > 1:
                        page_size = int(parts[1].split()[0])
                if "Pages free:" in line:
                    free_pages = int(line.split(":")[1].strip().rstrip("."))
                elif "Pages inactive:" in line:
                    inactive_pages = int(line.split(":")[1].strip().rstrip("."))
            avail_gb = ((free_pages + inactive_pages) * page_size) / (1024 ** 3)
        except Exception:
            pass
    elif system == "Linux":
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    total_gb = int(line.split()[1]) / (1024 * 1024)
                elif line.startswith("MemAvailable:"):
                    avail_gb = int(line.split()[1]) / (1024 * 1024)
        except Exception:
            pass

    return {"total_gb": round(total_gb, 2), "available_gb": round(avail_gb, 2)}

def get_cpu_info() -> Dict[str, Any]:
    """Returns CPU architecture, brand name, and physical/logical core counts."""
    system = platform.system()
    arch = platform.machine()
    logical_cores = os.cpu_count() or 4
    physical_cores = logical_cores
    brand = platform.processor() or "Generic CPU"

    if system == "Darwin":
        try:
            brand = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
            physical_cores = int(subprocess.check_output(["sysctl", "-n", "hw.physicalcpu"]).strip())
        except Exception:
            physical_cores = max(1, logical_cores // 2) if "x86" in arch else logical_cores
    elif system == "Linux":
        try:
            lscpu = subprocess.check_output(["lscpu"]).decode()
            for line in lscpu.splitlines():
                if "Model name:" in line:
                    brand = line.split(":", 1)[1].strip()
                elif "Core(s) per socket:" in line:
                    cps = int(line.split(":", 1)[1].strip())
                    physical_cores = cps
        except Exception:
            physical_cores = max(1, logical_cores // 2)

    return {
        "arch": arch,
        "brand": brand,
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
    }

def detect_gpu_devices() -> List[Dict[str, Any]]:
    """Detects discrete or integrated GPU accelerators (Metal, Vulkan, CUDA, ROCm)."""
    devices = []
    system = platform.system()

    # 1. Apple Silicon Metal Unified GPU
    if system == "Darwin" and platform.machine() == "arm64":
        mem = get_system_memory()
        cpu = get_cpu_info()
        devices.append({
            "type": "apple-silicon-metal",
            "name": cpu["brand"],
            "vram_gb": mem["total_gb"],
            "is_unified": True,
            "estimated_bandwidth_gbps": 300 if "Max" in cpu["brand"] else (150 if "Pro" in cpu["brand"] else 100)
        })
        return devices

    # 2. Linux / Vulkan devices via llama-bench
    llama_bench = shutil.which("llama-bench") or "/usr/local/bin/llama-bench"
    if os.path.exists(llama_bench):
        try:
            out = subprocess.check_output([llama_bench, "--list-devices"], stderr=subprocess.STDOUT).decode()
            # Match lines like: Vulkan0: Intel(R) UHD Graphics 630 (CFL GT2) (23978 MiB, 19058 MiB free)
            vulkan_matches = re.findall(r"Vulkan\d+:\s*(.*?)\s*\((\d+)\s*MiB,\s*(\d+)\s*MiB free\)", out)
            for dev_name, total_mib, free_mib in vulkan_matches:
                dev_name = dev_name.strip()
                is_uma = "Intel" in dev_name or "UMA" in dev_name or "Integrated" in dev_name
                # AMD Radeon Pro 5300M/5500M reports 8192 MiB virtual/shared heap in Vulkan, with 4GB GDDR6 dedicated
                vram_gb = 4.0 if ("AMD" in dev_name or "Radeon" in dev_name or "NAVI" in dev_name) else (float(total_mib) / 1024.0 if not is_uma else 1.5)
                devices.append({
                    "type": "vulkan",
                    "name": dev_name,
                    "vram_gb": round(vram_gb, 1),
                    "is_unified": is_uma,
                    "estimated_bandwidth_gbps": 192 if not is_uma else 25
                })
        except Exception:
            pass

    # 3. NVIDIA CUDA via nvidia-smi
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            out = subprocess.check_output([nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).decode()
            for line in out.splitlines():
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        devices.append({
                            "type": "cuda",
                            "name": parts[0].strip(),
                            "vram_gb": round(float(parts[1].strip()) / 1024, 2),
                            "is_unified": False,
                            "estimated_bandwidth_gbps": 360
                        })
        except Exception:
            pass

    # Sort so dedicated GPUs appear first
    devices.sort(key=lambda d: (not d.get("is_unified", False), d.get("vram_gb", 0)), reverse=True)
    return devices

def compute_llm_recommendation(
    total_ram_gb: float,
    available_ram_gb: float,
    gpu_devices: List[Dict[str, Any]],
    cpu_info: Dict[str, Any],
    workload: str = "code",
    override_vram_gb: Optional[float] = None,
    override_ram_gb: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculates the optimal model parameter tier, quantization, and serving flags
    to fit comfortably within the machine's hardware limits.
    """
    if override_ram_gb is not None:
        total_ram_gb = override_ram_gb

    has_metal = any(d["type"] == "apple-silicon-metal" for d in gpu_devices)
    dgpu = next((d for d in gpu_devices if not d.get("is_unified", False)), None)

    if override_vram_gb is not None:
        if dgpu:
            dgpu["vram_gb"] = override_vram_gb
        else:
            dgpu = {
                "type": "custom-gpu",
                "name": "Custom GPU Allocation",
                "vram_gb": override_vram_gb,
                "is_unified": False,
                "estimated_bandwidth_gbps": 250
            }

    # 1. Apple Silicon macOS
    if has_metal and override_vram_gb is None:
        ram = total_ram_gb
        if ram >= 96.0:
            target_tier = "70B"
            target_quant = "Q5_K_M"
            draft_tier = "8B"
            draft_quant = "Q8_0"
            ctx_size = 65536
            est_tok_s = "20-35"
            weight_gb = 48.5
        elif ram >= 64.0:
            target_tier = "32B"
            target_quant = "Q5_K_M"
            draft_tier = "1.5B"
            draft_quant = "Q8_0"
            ctx_size = 32768
            est_tok_s = "35-50"
            weight_gb = 22.0
        elif ram >= 32.0:
            target_tier = "14B"
            target_quant = "Q5_K_M"
            draft_tier = "0.5B"
            draft_quant = "Q8_0"
            ctx_size = 32768
            est_tok_s = "40-60"
            weight_gb = 9.8
        elif ram >= 16.0:
            target_tier = "7B"
            target_quant = "Q5_K_M"
            draft_tier = "0.5B"
            draft_quant = "Q8_0"
            ctx_size = 16384
            est_tok_s = "30-45"
            weight_gb = 5.2
        else:
            target_tier = "3B"
            target_quant = "Q4_K_M"
            draft_tier = None
            draft_quant = None
            ctx_size = 8192
            est_tok_s = "35-50"
            weight_gb = 2.1

        return {
            "tier_description": f"Apple Silicon Metal High-Throughput Tier ({ram:.0f} GB Unified Memory)",
            "target_model_tier": target_tier,
            "target_quantization": target_quant,
            "target_weight_gb": weight_gb,
            "draft_model_tier": draft_tier,
            "draft_quantization": draft_quant,
            "context_size": ctx_size,
            "kv_cache_quant": "q8_0",
            "gpu_layers": 99,
            "threads": cpu_info["physical_cores"],
            "flash_attn": True,
            "speculative_decoding": draft_tier is not None,
            "estimated_tok_s": est_tok_s,
            "free_system_headroom_gb": round(ram - weight_gb - 3.0, 1),
            "recommended_backend": "llama.cpp (Metal) or Ollama"
        }

    # 2. Dedicated GPU (Vulkan or CUDA)
    if dgpu:
        vram = dgpu["vram_gb"]
        backend = "vulkan" if dgpu["type"] == "vulkan" else "cuda"
        if vram >= 16.0:
            target_tier = "14B"
            target_quant = "Q5_K_M"
            draft_tier = "1.5B"
            draft_quant = "Q8_0"
            weight_gb = 9.8
            est_tok_s = "40-65"
        elif vram >= 8.0:
            target_tier = "7B"
            target_quant = "Q5_K_M"
            draft_tier = "0.5B"
            draft_quant = "Q8_0"
            weight_gb = 5.2
            est_tok_s = "30-45"
        elif vram >= 4.0:
            # 4GB GDDR6 (AMD Radeon Pro 5300M/5500M, GTX 1650)
            target_tier = "7B"
            target_quant = "IQ3_M"   # 3.57 GB fits completely into 4.0 GB VRAM
            draft_tier = None        # Single model maximizes VRAM stability
            draft_quant = None
            weight_gb = 3.57
            est_tok_s = "20-26"
        else:
            target_tier = "3B"
            target_quant = "Q4_K_M"
            draft_tier = None
            draft_quant = None
            weight_gb = 2.1
            est_tok_s = "25-35"

        return {
            "tier_description": f"Dedicated GPU {dgpu['name']} ({vram:.1f} GB Dedicated VRAM)",
            "target_model_tier": target_tier,
            "target_quantization": target_quant,
            "target_weight_gb": weight_gb,
            "draft_model_tier": draft_tier,
            "draft_quantization": draft_quant,
            "context_size": 8192,
            "kv_cache_quant": "q8_0",
            "gpu_layers": 99,
            "threads": cpu_info["physical_cores"],
            "flash_attn": True,
            "speculative_decoding": draft_tier is not None,
            "estimated_tok_s": est_tok_s,
            "free_system_headroom_gb": round(total_ram_gb - 2.0, 1),
            "recommended_backend": f"llama.cpp ({backend})"
        }

    # 3. Pure Host CPU & DDR4/DDR5 RAM (No dGPU or Integrated Graphics)
    if total_ram_gb >= 16.0:
        target_tier = "3B"
        target_quant = "Q4_K_M"
        weight_gb = 2.1
        est_tok_s = "10-15"
    else:
        target_tier = "1.5B"
        target_quant = "Q4_K_M"
        weight_gb = 1.1
        est_tok_s = "18-25"

    return {
        "tier_description": f"Host CPU AVX2 Execution ({total_ram_gb:.0f} GB DDR4/DDR5 RAM)",
        "target_model_tier": target_tier,
        "target_quantization": target_quant,
        "target_weight_gb": weight_gb,
        "draft_model_tier": None,
        "draft_quantization": None,
        "context_size": 8192,
        "kv_cache_quant": "f16",
        "gpu_layers": 0,
        "threads": cpu_info["physical_cores"],
        "flash_attn": False,
        "speculative_decoding": False,
        "estimated_tok_s": est_tok_s,
        "free_system_headroom_gb": round(total_ram_gb - weight_gb - 2.0, 1),
        "recommended_backend": "llama.cpp (AVX2 CPU thread pinned)"
    }

def generate_custom_configs(rec: Dict[str, Any], model_name: str) -> Dict[str, str]:
    """Generates customized presets.ini and Modelfile strings tailored to the profile."""
    target_tier_lower = rec['target_model_tier'].lower()
    target_quant_lower = rec['target_quantization'].lower()

    presets_ini = f"""# Auto-generated llama-server presets for {model_name}
# Tailored for: {rec['tier_description']}

[{model_name}-target]
model = /path/to/{model_name}-{target_tier_lower}-{target_quant_lower}.gguf
alias = {model_name},target-model
ctx-size = {rec['context_size']}
parallel = 1
n-gpu-layers = {rec['gpu_layers']}
threads = {rec['threads']}
flash-attn = {'on' if rec['flash_attn'] else 'off'}
cache-type-k = {rec['kv_cache_quant']}
cache-type-v = {rec['kv_cache_quant']}
batch-size = 256
ubatch-size = 64
"""
    if rec["speculative_decoding"] and rec["draft_model_tier"]:
        draft_tier_lower = rec['draft_model_tier'].lower()
        draft_quant_lower = rec['draft_quantization'].lower()
        presets_ini += f"""
[{model_name}-speculative]
model = /path/to/{model_name}-{target_tier_lower}-{target_quant_lower}.gguf
model-draft = /path/to/{model_name}-draft-{draft_tier_lower}-{draft_quant_lower}.gguf
alias = {model_name}-spec,target-spec
ctx-size = {rec['context_size']}
parallel = 1
n-gpu-layers = {rec['gpu_layers']}
n-gpu-layers-draft = {rec['gpu_layers']}
spec-draft-n-max = 4
threads = {rec['threads']}
flash-attn = {'on' if rec['flash_attn'] else 'off'}
cache-type-k = {rec['kv_cache_quant']}
cache-type-v = {rec['kv_cache_quant']}
batch-size = 256
ubatch-size = 64
"""

    modelfile = f"""# Auto-generated Ollama Modelfile for {model_name}
# Engineered for: {rec['tier_description']}
FROM ./{model_name}-{target_tier_lower}-{target_quant_lower}.gguf

PARAMETER num_ctx {rec['context_size']}
PARAMETER num_predict 2048
PARAMETER temperature 0.0
PARAMETER top_p 0.95
PARAMETER repeat_penalty 1.05
PARAMETER num_thread {rec['threads']}

SYSTEM \"\"\"You are {model_name}, an elite coding assistant optimized for performance and strict correctness.
RULES:
1. Always generate complete, runnable Python 3 code.
2. For competitive programming, optimize bulk I/O with `sys.stdin.read().split()`.
3. Use integer division `//` instead of float division `/` for array indexing.
4. Output your final code block inside standard ```python ``` fences.
\"\"\"
"""
    return {"presets_ini": presets_ini, "modelfile": modelfile}

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Profile system hardware and calculate optimal LLM parameters.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON analysis.")
    parser.add_argument("--model-name", default="custom-llm", help="Target model name for generated configs.")
    parser.add_argument("--vram-gb", type=float, default=None, help="Explicit VRAM override in GB.")
    parser.add_argument("--ram-gb", type=float, default=None, help="Explicit RAM override in GB.")
    parser.add_argument("--save-configs", action="store_true", help="Save generated presets.ini and Modelfile to current directory.")
    args = parser.parse_args()

    mem = get_system_memory()
    cpu = get_cpu_info()
    gpus = detect_gpu_devices()
    rec = compute_llm_recommendation(
        mem["total_gb"],
        mem["available_gb"],
        gpus,
        cpu,
        override_vram_gb=args.vram_gb,
        override_ram_gb=args.ram_gb
    )
    configs = generate_custom_configs(rec, args.model_name)

    if args.json:
        payload = {
            "hardware": {"memory": mem, "cpu": cpu, "gpus": gpus},
            "recommendation": rec,
            "configs": configs
        }
        print(json.dumps(payload, indent=2))
        return

    print("=" * 70)
    print(" 🖥️  SYSTEM HARDWARE & MEMORY PROFILE")
    print("=" * 70)
    print(f" • Operating System  : {platform.system()} ({cpu['arch']})")
    print(f" • CPU Brand         : {cpu['brand']}")
    print(f" • Physical Cores    : {cpu['physical_cores']} (Logical: {cpu['logical_cores']})")
    print(f" • System RAM        : {mem['total_gb']} GB total ({mem['available_gb']} GB currently free)")
    
    if gpus:
        print(" • Compute Devices   :")
        for g in gpus:
            dev_type = "Unified UMA" if g.get("is_unified") else "Dedicated VRAM"
            print(f"   - {g['name']} ({g['vram_gb']} GB {dev_type}, ~{g.get('estimated_bandwidth_gbps')} GB/s bandwidth)")
    else:
        print(" • Compute Devices   : None detected (Pure CPU AVX2 execution)")

    print("\n" + "=" * 70)
    print(f" 🎯 RECOMMENDED LLM CONFIGURATION: {rec['tier_description']}")
    print("=" * 70)
    print(f" • Target Model Tier : {rec['target_model_tier']} (Quant: {rec['target_quantization']}, ~{rec['target_weight_gb']} GB)")
    if rec["draft_model_tier"]:
        print(f" • Draft Speculative : {rec['draft_model_tier']} (Quant: {rec['draft_quantization']}) [ENABLED ⚡]")
    else:
        print(" • Draft Speculative : Disabled (Single forward-pass optimized)")
    print(f" • Context Size      : {rec['context_size']:,} tokens")
    print(f" • KV-Cache Type     : {rec['kv_cache_quant']}")
    print(f" • Offload Layers    : -ngl {rec['gpu_layers']} (Threads: {rec['threads']})")
    print(f" • Estimated Speed   : {rec['estimated_tok_s']} tokens/sec")
    print(f" • Free RAM Margin   : ~{rec['free_system_headroom_gb']} GB left for OS + IDE + Docker")
    print(f" • Recommended Engine: {rec['recommended_backend']}")

    if args.save_configs:
        presets_filename = f"presets.{args.model_name}.ini"
        modelfile_filename = f"Modelfile.{args.model_name}"
        with open(presets_filename, "w") as f:
            f.write(configs["presets_ini"])
        with open(modelfile_filename, "w") as f:
            f.write(configs["modelfile"])
        print("\n" + "=" * 70)
        print(" 💾 GENERATED CUSTOM CONFIGURATIONS")
        print("=" * 70)
        print(f" • Saved: {presets_filename}")
        print(f" • Saved: {modelfile_filename}")
    else:
        print("\n(Run with `--save-configs --model-name <name>` to write customized presets and Modelfile)")

if __name__ == "__main__":
    main()
