#!/usr/bin/env python3
"""Direct Preference Optimization (DPO) for ApexCode.

Aligns model outputs to eliminate conversational filler, incomplete code blocks,
and enforce strict type safety and concise diffs.
"""

import argparse
import os
import torch
from datasets import load_dataset
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import DPOTrainer


def run_dpo(
    base_model_name: str = "Qwen/Qwen2.5-Coder-14B-Instruct",
    adapter_path: str = "./checkpoints/apex_coder_lora",
    dpo_dataset_path: str = "./datasets/apex_code_dpo.jsonl",
    output_dir: str = "./checkpoints/apex_coder_dpo",
    beta: float = 0.1,
    learning_rate: float = 5e-5,
    epochs: int = 2,
):
    print("=" * 64)
    print("🎯 ApexCode DPO Alignment")
    print(f"Base Model: {base_model_name}")
    print(f"Beta: {beta} | Learning Rate: {learning_rate}")
    print("=" * 64)

    is_cuda = torch.cuda.is_available()
    torch_dtype = torch.bfloat16 if is_cuda else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load Base Model and LoRA Adapter
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        device_map="auto" if is_cuda else None,
        trust_remote_code=True,
    )

    if os.path.isdir(adapter_path):
        print(f"🔗 Loading trained LoRA adapter from {adapter_path}...")
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=True)

    if not os.path.exists(dpo_dataset_path):
        from training.prepare_code_datasets import generate_dataset

        generate_dataset(os.path.dirname(dpo_dataset_path))

    dataset = load_dataset("json", data_files=dpo_dataset_path, split="train")

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        logging_steps=5,
        save_strategy="epoch",
        fp16=not is_cuda and torch.backends.mps.is_available(),
        bf16=is_cuda,
        report_to="none",
    )

    dpo_trainer = DPOTrainer(
        model=model,
        ref_model=None,  # Implicit reference model via PEFT weights
        args=training_args,
        beta=beta,
        train_dataset=dataset,
        tokenizer=tokenizer,
        max_prompt_length=1024,
        max_length=2048,
    )

    print("🔥 Running DPO Alignment...")
    dpo_trainer.train()

    print(f"💾 Saving DPO-aligned model to {output_dir}...")
    dpo_trainer.save_model(output_dir)
    print("✅ DPO Alignment finished successfully.")


def main():
    parser = argparse.ArgumentParser(description="ApexCode DPO Script")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-14B-Instruct")
    parser.add_argument("--adapter", default="./checkpoints/apex_coder_lora")
    parser.add_argument("--dpo-data", default="./datasets/apex_code_dpo.jsonl")
    parser.add_argument("--beta", type=float, default=0.1)
    args = parser.parse_args()

    run_dpo(
        base_model_name=args.base_model,
        adapter_path=args.adapter,
        dpo_dataset_path=args.dpo_data,
        beta=args.beta,
    )


if __name__ == "__main__":
    main()
