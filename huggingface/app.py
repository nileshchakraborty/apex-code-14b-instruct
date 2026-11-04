"""ApexCode-14B Interactive Code Playground (Hugging Face Spaces Demo).

Gradio interface supporting:
1. Production Code Generation with syntax highlighting
2. Surgical Search/Replace Unified Diff generator
3. Live streaming with tokens/sec and latency metrics
"""

import json
import os
import time
import urllib.request
import gradio as gr

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:11434/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "apex-coder-14b")


def stream_code_generation(
    prompt: str,
    task_type: str,
    temperature: float = 0.2,
    max_tokens: int = 512,
):
    if not prompt.strip():
        yield "⚠️ Please enter a coding instruction or prompt.", "0.0 tok/s", "0 ms"
        return

    system_instruction = (
        "You are ApexCode-14B, an elite coding model optimized for production systems. "
        "Output clean, typed, bug-free code. Avoid conversational banter."
    )

    if task_type == "Search/Replace Diff":
        system_instruction += (
            " When editing code, provide surgical <<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks."
        )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    url = f"{API_BASE.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)

    accumulated_text = ""
    start_time = time.perf_counter()
    first_token_time = None
    token_count = 0

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            for line in response:
                line_str = line.decode("utf-8").strip()
                if not line_str.startswith("data: "):
                    continue
                data_part = line_str[6:]
                if data_part == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_part)
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        token_count += 1
                        accumulated_text += delta

                        elapsed = time.perf_counter() - start_time
                        tok_per_sec = token_count / elapsed if elapsed > 0 else 0
                        ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else 0

                        yield (
                            accumulated_text,
                            f"{tok_per_sec:.1f} tok/s",
                            f"{ttft_ms:.0f} ms",
                        )
                except json.JSONDecodeError:
                    continue

    except Exception as e:
        yield f"❌ Error contacting endpoint ({API_BASE}): {str(e)}", "0.0 tok/s", "0 ms"


custom_css = """
.gradio-container { max-width: 900px !important; margin: auto; }
.output-code { font-family: 'JetBrains Mono', 'Fira Code', monospace; }
"""

with gr.Blocks(title="ApexCode-14B Playground", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.Markdown("# ⚡ ApexCode-14B Interactive Playground")
    gr.Markdown(
        "Production-grade coding assistant optimized for **36 GB RAM** hardware. "
        "Delivers **~36–55 tokens/sec** with zero memory swapping."
    )

    with gr.Row():
        with gr.Column(scale=3):
            prompt_input = gr.Textbox(
                label="Coding Prompt or Refactoring Request",
                placeholder="Write a thread-safe LRU Cache in Python with TTL expiration...",
                lines=5,
            )
            with gr.Row():
                task_dropdown = gr.Dropdown(
                    choices=["Code Generation", "Search/Replace Diff", "Unit Test Synthesis"],
                    value="Code Generation",
                    label="Task Profile",
                )
                temp_slider = gr.Slider(
                    minimum=0.0, maximum=1.0, value=0.2, step=0.05, label="Temperature"
                )
                tokens_slider = gr.Slider(
                    minimum=64, maximum=2048, value=512, step=64, label="Max Tokens"
                )

            submit_btn = gr.Button("🚀 Generate Code", variant="primary")

        with gr.Column(scale=4):
            code_output = gr.Code(label="Generated Output", language="python", lines=16)
            with gr.Row():
                speed_badge = gr.Textbox(label="Speed", value="0.0 tok/s", interactive=False)
                latency_badge = gr.Textbox(label="TTFT Latency", value="0 ms", interactive=False)

    submit_btn.click(
        fn=stream_code_generation,
        inputs=[prompt_input, task_dropdown, temp_slider, tokens_slider],
        outputs=[code_output, speed_badge, latency_badge],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
