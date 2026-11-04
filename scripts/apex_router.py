#!/usr/bin/env python3
"""Unified Intelligent Router Gateway for ApexCode & ApexThink.

Runs an OpenAI-compatible HTTP proxy on port 8000 that dynamically classifies
user intent and routes requests:
- Coding, diffs, refactoring, and FIM autocompletions -> apex-coder-14b
- Logic, reasoning, analysis, math, and writing -> apex-think-14b (with anti-hallucination guardrail)
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import socketserver
import sys
import time
import urllib.request
import psutil

# Import 2-Stage DeepCoder Pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from deepcoder_pipeline import run_deepcoder_pipeline
except ImportError:
    run_deepcoder_pipeline = None

UPSTREAM_OLLAMA = "http://127.0.0.1:11434"

CODE_INTENT_PATTERNS = [
    r"\b(?:def|function|class|struct|impl|import|from|const|let|var|val)\b",
    r"\b(?:refactor|bug|error|traceback|syntax|exception|sql|query|endpoint)\b",
    r"\b(?:python|typescript|javascript|rust|golang|c\+\+|html|css)\b",
    r"```[a-zA-Z]*",
    r"<\|fim_prefix\|>",
    r"<<<<<<< SEARCH",
]


def classify_intent(text: str) -> str:
    """Classify whether prompt is coding-related or general reasoning."""
    if "<|fim_prefix|>" in text:
        return "apex-coder-14b"

    match_count = 0
    for pattern in CODE_INTENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            match_count += 1

    # If multiple coding markers match, route to coder; otherwise reasoning
    if match_count >= 1:
        return "apex-coder-14b"
    return "apex-think-14b"


class ApexRouterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging
        sys.stderr.write(f"[{time.strftime('%X')}] {args[0]} {args[1]} {args[2]}\n")

    def do_GET(self):
        if self.path in ("/v1/models", "/api/models"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            models_data = {
                "object": "list",
                "data": [
                    {"id": "apex-auto", "object": "model", "owned_by": "apex"},
                    {"id": "apex-deepcoder", "object": "model", "owned_by": "apex"},
                    {"id": "apex-coder-14b", "object": "model", "owned_by": "apex"},
                    {"id": "apex-think-14b", "object": "model", "owned_by": "apex"},
                ],
            }
            self.wfile.write(json.dumps(models_data).encode("utf-8"))

        elif self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            mem = psutil.virtual_memory()
            health_data = {
                "status": "healthy",
                "router": "Apex Unified Gateway",
                "system_ram_used_gb": round(mem.used / 1024**3, 2),
                "system_ram_total_gb": round(mem.total / 1024**3, 2),
            }
            self.wfile.write(json.dumps(health_data).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON body"}')
            return

        requested_model = payload.get("model", "apex-auto")
        is_stream = payload.get("stream", False)

        # Extract text to classify intent
        prompt_text = ""
        if "messages" in payload:
            for msg in payload["messages"]:
                prompt_text += " " + msg.get("content", "")
        elif "prompt" in payload:
            prompt_text = payload.get("prompt", "")

        # Route determination
        if requested_model in ("apex-auto", "auto", "default", None):
            target_model = classify_intent(prompt_text)
            intent = "Code" if target_model == "apex-coder-14b" else "Reasoning"
            sys.stderr.write(f"⚡ [Smart Router] Intent classified as {intent} -> Routing to {target_model}\n")
        else:
            target_model = requested_model

        # Handle 2-Stage DeepCoder Cognitive Decomposition Pipeline
        if target_model == "apex-deepcoder" and run_deepcoder_pipeline is not None:
            sys.stderr.write(f"🧠 [Smart Router] Executing 2-Stage ApexDeepCoder Pipeline...\n")
            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                # Send initial SSE heartbeat to keep IDE socket alive
                delta_start = {
                    "id": f"chatcmpl-deepcoder-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "apex-deepcoder",
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": "🧠 *[ApexDeepCoder: Establishing SSIB Invariant Contract...]*\n\n"}}],
                }
                self.wfile.write(f"data: {json.dumps(delta_start)}\n\n".encode("utf-8"))
                self.wfile.flush()

                pipe_res = run_deepcoder_pipeline(prompt_text, max_repair_attempts=2, verbose=False)

                # Send verified production code
                final_content = f"```python\n{pipe_res['final_code']}\n```"
                delta_code = {
                    "id": f"chatcmpl-deepcoder-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "apex-deepcoder",
                    "choices": [{"index": 0, "delta": {"content": final_content}}],
                }
                self.wfile.write(f"data: {json.dumps(delta_code)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return

            pipe_res = run_deepcoder_pipeline(prompt_text, max_repair_attempts=2, verbose=False)
            response_payload = {
                "id": f"chatcmpl-deepcoder-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "apex-deepcoder",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"```python\n{pipe_res['final_code']}\n```",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": pipe_res.get("tokens_generated", 0),
                    "total_tokens": pipe_res.get("tokens_generated", 0),
                },
                "apex_metadata": {
                    "ast_valid": pipe_res.get("ast_valid"),
                    "tests_passed": pipe_res.get("tests_passed"),
                    "sandbox": pipe_res.get("sandbox_used"),
                    "repairs_performed": pipe_res.get("repairs_performed"),
                    "latency_sec": pipe_res.get("latency_sec"),
                },
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            return

        # Adjust parameters for anti-hallucination if reasoning
        payload["model"] = target_model
        if target_model == "apex-think-14b":
            if "min_p" not in payload:
                payload["min_p"] = 0.05
            if "temperature" not in payload:
                payload["temperature"] = 0.6

        # Forward request to upstream Ollama
        upstream_url = f"{UPSTREAM_OLLAMA}{self.path}"
        req = urllib.request.Request(
            upstream_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            upstream_resp = urllib.request.urlopen(req, timeout=180)
            self.send_response(upstream_resp.status)
            for header, val in upstream_resp.getheaders():
                if header.lower() in ("content-type", "cache-control", "transfer-encoding"):
                    self.send_header(header, val)
            self.end_headers()

            if is_stream:
                while True:
                    chunk = upstream_resp.read(512)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                self.wfile.write(upstream_resp.read())

        except Exception as e:
            sys.stderr.write(f"❌ Upstream error ({upstream_url}): {e}\n")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Upstream routing failed: {str(e)}"}).encode("utf-8"))


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run_router(port: int = 8090, host: str = "0.0.0.0"):
    print("=" * 64)
    print("⚡ Apex Intelligent Router Gateway")
    print(f"Listening on: http://{host}:{port}/v1")
    print(f"Upstream Engine: {UPSTREAM_OLLAMA}")
    print("Routing Rules:")
    print("  • Coding / FIM / Diffs  -> apex-coder-14b")
    print("  • Reasoning / Analysis   -> apex-think-14b (Min-P Guardrail)")
    print("=" * 64)

    server = ThreadedHTTPServer((host, port), ApexRouterHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Apex Router gracefully.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Apex Intelligent Router Gateway")
    parser.add_argument("--port", type=int, default=8090, help="Gateway port (default: 8090)")
    parser.add_argument("--host", default="0.0.0.0", help="Host binding (default: 0.0.0.0)")
    args = parser.parse_args()
    run_router(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
