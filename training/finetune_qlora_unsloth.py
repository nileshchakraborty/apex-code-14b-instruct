#!/usr/bin/env python3
"""Fine-tune lightweight coding LLM with QLoRA for 36 GB setups.

Optimized for Qwen2.5-Coder-14B / 7B using Hugging Face PEFT + TRL.
Exports merged model ready for GGUF quantization.
"""

import argparse
import os
import sys
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer


def train(
    model_name: str = "Qwen/Qwen2.5-Coder-14B-Instruct",
    dataset_path: str = "./datasets/apex_code_sft.jsonl",
    output_dir: str = "./checkpoints/apex_coder_lora",
    merged_output_dir: str = "./output/merged_apex_coder_14b",
    epochs: int = 3,
    lr: float = 2e-4,
    batch_size: int = 2,
    gradient_accumulation_steps: int = 8,
    max_seq_length: int = 4096,
):
    print("=" * 64)
    print(f"🚀 Initializing QLoRA Fine-Tuning for: {model_name}")
    print(f"Dataset: {dataset_path}")
    print(f"Max Sequence Length: {max_seq_length}")
    print("=" * 64)

    is_cuda = torch.cuda.is_available()
    is_mps = torch.backends.mps.is_available()

    print(f"Hardware Acceleration: CUDA={is_cuda}, MPS={is_mps}")

    # Quantization Config (4-bit NF4 on CUDA, FP16/BF16 on Apple Silicon MPS)
    if is_cuda:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        device_map = "auto"
        torch_dtype = torch.bfloat16
    else:
        bnb_config = None
        device_map = None
        torch_dtype = torch.float16 if is_mps else torch.float32

    # Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load Base Model
    print("📥 Loading base model weights...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map=device_map,
        torch_dtype=torch_dtype,
        trust_remote_code=True,
    )

    if is_cuda and bnb_config:
        model = prepare_model_for_kbit_training(model)

    # LoRA Configuration
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load Dataset
    if not os.path.exists(dataset_path):
        print(f"⚠️ Dataset not found at {dataset_path}. Generating default dataset...")
        from training.prepare_code_datasets import generate_dataset

        generate_dataset(os.path.dirname(dataset_path))

    dataset = load_dataset("json", data_files=dataset_path, split="train")

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="epoch",
        fp16=not is_cuda and is_mps,
        bf16=is_cuda,
        optim="paged_adamw_8bit" if is_cuda else "adamw_torch",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        tokenizer=tokenizer,
        args=training_args,
    )

    print("🔥 Starting fine-tuning loop...")
    trainer.train()

    print(f"💾 Saving LoRA adapter checkpoint to {output_dir}...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("==========================================================")
    print("✅ Training complete! To convert to GGUF, merge and run:")
    print("   bash scripts/quantize_model.sh")
    print("==========================================================")


def main():
    parser = argparse.ArgumentParser(description="ApexCode QLoRA Fine-Tuning")
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-14B-Instruct", help="Base model ID")
    parser.add_argument("--dataset", default="./datasets/apex_code_sft.jsonl", help="Dataset path")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    args = parser.parse_args()

    train(model_name=args.model, dataset_path=args.dataset, epochs=args.epochs, lr=args.lr)


if __name__ == "__main__":
    main()
