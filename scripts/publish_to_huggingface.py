#!/usr/bin/env python3
"""Publish ApexCode-14B models, GGUF weights, and Model Cards to Hugging Face Hub.

Uses huggingface_hub to create the repository and upload weights with resume support.
"""

import argparse
import os
import sys
from huggingface_hub import HfApi, login


def publish(
    repo_id: str,
    model_dir: str = "./models",
    model_card_path: str = "./huggingface/MODEL_CARD.md",
    private: bool = False,
    token: str = None,
):
    print("=" * 64)
    print("🤗 Publishing ApexCode-36GB to Hugging Face Hub")
    print(f"Target Repository: {repo_id}")
    print(f"Model Directory:   {model_dir}")
    print(f"Model Card:        {model_card_path}")
    print(f"Visibility:        {'Private' if private else 'Public'}")
    print("=" * 64)

    api = HfApi(token=token)

    try:
        user_info = api.whoami()
        print(f"✅ Authenticated as: {user_info.get('name', 'Unknown')}")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("💡 Run 'huggingface-cli login' first or provide --token.")
        sys.exit(1)

    # Step 1: Create repository on Hugging Face if it doesn't exist
    try:
        api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
        print(f"✅ Repository {repo_id} verified on Hugging Face Hub.")
    except Exception as e:
        print(f"❌ Failed to create/verify repo: {e}")
        sys.exit(1)

    # Step 2: Upload Model Card (README.md)
    if os.path.isfile(model_card_path):
        print("📄 Uploading Model Card (README.md)...")
        api.upload_file(
            path_or_fileobj=model_card_path,
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
            commit_message="docs: add comprehensive model card and Ollama integration details",
        )
        print("✅ README.md published.")
    else:
        print(f"⚠️ Model card not found at {model_card_path}, skipping README upload.")

    # Step 3: Upload Ollama Modelfile
    modelfile_path = "./configs/ollama/Modelfile.apex-coder-14b"
    if os.path.isfile(modelfile_path):
        print("⚙️ Uploading Ollama Modelfile...")
        api.upload_file(
            path_or_fileobj=modelfile_path,
            path_in_repo="Modelfile",
            repo_id=repo_id,
            repo_type="model",
            commit_message="feat: add 36GB-optimized Ollama Modelfile",
        )

    # Step 4: Scan and upload model weights (.gguf / .safetensors)
    if not os.path.isdir(model_dir):
        print(f"⚠️ Model directory '{model_dir}' does not exist.")
        print("   If you only wanted to publish the Model Card, you are done!")
        return

    valid_extensions = (".gguf", ".safetensors", ".json", ".txt")
    files_to_upload = [
        f for f in os.listdir(model_dir) if f.lower().endswith(valid_extensions) and not f.startswith(".")
    ]

    if not files_to_upload:
        print(f"ℹ️ No weight files found in '{model_dir}'.")
        print("💡 Download or generate weights with 'bash scripts/download_models.sh' to upload them.")
        return

    print(f"\n📦 Found {len(files_to_upload)} files to upload from {model_dir}:")
    for f in files_to_upload:
        file_path = os.path.join(model_dir, f)
        size_gb = os.path.getsize(file_path) / (1024**3)
        print(f"   • {f} ({size_gb:.2f} GB)")

    for f in files_to_upload:
        file_path = os.path.join(model_dir, f)
        print(f"\n🚀 Uploading {f}...")
        api.upload_file(
            path_or_fileobj=file_path,
            path_in_repo=f,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"feat: upload {f}",
        )
        print(f"✅ Finished uploading {f}")

    print("\n" + "=" * 64)
    print("🎉 Deployment to Hugging Face Complete!")
    print(f"🔗 View on Hub: https://huggingface.co/{repo_id}")
    print(f"⚡ 1-Click Ollama Command: ollama run hf.co/{repo_id}:Q5_K_M")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(description="Publish ApexCode to Hugging Face Hub")
    parser.add_argument(
        "--repo-id",
        default="nileshc90/apex-code-14b-instruct",
        help="Target Hugging Face repository ID (e.g. username/repo-name)",
    )
    parser.add_argument("--model-dir", default="./models", help="Directory containing .gguf weights")
    parser.add_argument(
        "--model-card", default="./huggingface/MODEL_CARD.md", help="Path to Model Card README"
    )
    parser.add_argument("--private", action="store_true", help="Make repository private")
    parser.add_argument("--token", default=None, help="Hugging Face API token (optional)")
    args = parser.parse_args()

    publish(
        repo_id=args.repo_id,
        model_dir=args.model_dir,
        model_card_path=args.model_card,
        private=args.private,
        token=args.token,
    )


if __name__ == "__main__":
    main()
