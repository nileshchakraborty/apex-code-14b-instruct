#!/usr/bin/env python3
"""Dataset Preprocessor and Synthesizer for ApexCode.

Creates a balanced training corpus containing:
1. Fill-In-The-Middle (FIM) samples for IDE autocomplete.
2. Surgical Search/Replace Diffs for fast multi-file editing.
3. Agentic Tool-Calling pairs for autonomous coding workflows.
4. Bug-fixing and unit-test synthesis.
"""

import argparse
import json
import os
import random

SAMPLE_FIM_TEMPLATES = [
    {
        "prefix": "def binary_search(arr: list[int], target: int) -> int:\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        ",
        "middle": "mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1",
        "suffix": "\n    return -1\n",
    },
    {
        "prefix": "import asyncio\nimport httpx\n\nasync def fetch_status(url: str) -> int:\n    async with httpx.AsyncClient() as client:\n        ",
        "middle": "response = await client.get(url, timeout=5.0)\n        return response.status_code",
        "suffix": "\n",
    },
]

SAMPLE_DIFF_TEMPLATES = [
    {
        "instruction": "Fix the division by zero vulnerability and add type hints in the calculate_ratio function.",
        "input_code": "def calculate_ratio(numerator, denominator):\n    return numerator / denominator",
        "output_diff": """<<<<<<< SEARCH
def calculate_ratio(numerator, denominator):
    return numerator / denominator
=======
def calculate_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        raise ValueError("Denominator cannot be zero.")
    return numerator / denominator
>>>>>>> REPLACE""",
    },
    {
        "instruction": "Refactor process_batch to handle empty list gracefully without IndexError.",
        "input_code": "def process_batch(items):\n    first = items[0]\n    return [x + first for x in items]",
        "output_diff": """<<<<<<< SEARCH
def process_batch(items):
    first = items[0]
    return [x + first for x in items]
=======
def process_batch(items: list[int]) -> list[int]:
    if not items:
        return []
    first = items[0]
    return [x + first for x in items]
>>>>>>> REPLACE""",
    },
]

SAMPLE_DPO_PAIRS = [
    {
        "prompt": "Write a python function to check if a string is a palindrome ignoring non-alphanumeric characters.",
        "chosen": """def is_palindrome(text: str) -> bool:
    cleaned = ''.join(c.lower() for c in text if c.isalnum())
    return cleaned == cleaned[::-1]
""",
        "rejected": """Sure! I would be glad to help you with that! Here is a python function that checks if a string is a palindrome while ignoring non-alphanumeric characters:

```python
def is_palindrome(text):
    # TODO: this could be optimized later
    cleaned = ''
    for c in text:
        if c.isalnum():
            cleaned += c.lower()
    return cleaned == cleaned[::-1]
```
I hope this code helps you with your project! Feel free to ask if you have more questions.""",
    }
]


def format_fim_prompt(prefix: str, suffix: str, middle: str) -> dict:
    """Format into Qwen2.5-Coder native FIM tokens."""
    formatted_text = f"<|fim_prefix|>{prefix}<|fim_suffix|>{suffix}<|fim_middle|>{middle}<|endoftext|>"
    return {"text": formatted_text}


def format_sft_conversation(instruction: str, context: str, response: str) -> dict:
    """Format into standard ChatML conversation."""
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are ApexCode, a concise, production-grade coding engine. Output clean code or search-replace diffs only.",
            },
            {
                "role": "user",
                "content": f"{instruction}\n\n```\n{context}\n```" if context else instruction,
            },
            {"role": "assistant", "content": response},
        ]
    }


def generate_dataset(output_dir: str, num_samples: int = 100):
    os.makedirs(output_dir, exist_ok=True)
    sft_path = os.path.join(output_dir, "apex_code_sft.jsonl")
    dpo_path = os.path.join(output_dir, "apex_code_dpo.jsonl")

    print(f"Generating synthetic code samples in {output_dir}...")

    # Write SFT samples
    with open(sft_path, "w", encoding="utf-8") as f_sft:
        # FIM samples
        for item in SAMPLE_FIM_TEMPLATES:
            f_sft.write(json.dumps(format_fim_prompt(item["prefix"], item["suffix"], item["middle"])) + "\n")

        # Diff samples
        for item in SAMPLE_DIFF_TEMPLATES:
            f_sft.write(
                json.dumps(
                    format_sft_conversation(item["instruction"], item["input_code"], item["output_diff"])
                )
                + "\n"
            )

    # Write DPO samples
    with open(dpo_path, "w", encoding="utf-8") as f_dpo:
        for item in SAMPLE_DPO_PAIRS:
            f_dpo.write(json.dumps(item) + "\n")

    print(f"✅ Generated SFT dataset at: {sft_path}")
    print(f"✅ Generated DPO dataset at: {dpo_path}")


def main():
    parser = argparse.ArgumentParser(description="ApexCode Dataset Generator")
    parser.add_argument("--output-dir", default="./datasets", help="Output directory")
    args = parser.parse_args()
    generate_dataset(args.output_dir)


if __name__ == "__main__":
    main()
