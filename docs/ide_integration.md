# 💻 IDE Integration Guide

ApexCode provides an OpenAI-compatible HTTP API endpoint (`http://127.0.0.1:8080/v1` or Ollama's `http://127.0.0.1:11434/v1`). You can plug it into any modern coding tool.

---

## 1. Continue.dev (VS Code & JetBrains)

Install the **Continue** extension from the VS Code Marketplace or JetBrains Plugins.
Open `~/.continue/config.json` and insert:

```json
{
  "models": [
    {
      "title": "ApexCode-14B Speculative",
      "provider": "openai",
      "model": "qwen2.5-coder-14b-instruct",
      "apiBase": "http://127.0.0.1:8080/v1",
      "apiKey": "none",
      "contextLength": 32768
    }
  ],
  "tabAutocompleteModel": {
    "title": "ApexCode Autocomplete",
    "provider": "openai",
    "model": "qwen2.5-coder-14b-instruct",
    "apiBase": "http://127.0.0.1:8080/v1",
    "apiKey": "none"
  }
}
```

---

## 2. Cline / Roo-Code (Autonomous Autonomous Coding Agent)

1. Open the **Cline** settings panel in VS Code.
2. Select **OpenAI Compatible** as the API provider.
3. Set **Base URL:** `http://127.0.0.1:8080/v1`
4. Set **API Key:** `none`
5. Set **Model ID:** `qwen2.5-coder-14b-instruct`
6. Set **Max Context Window:** `32768`

---

## 3. Aider CLI (Terminal Pair Programming)

Install Aider:
```bash
pip install -U aider-chat
```

Run with ApexCode:
```bash
aider \
  --openai-api-base http://127.0.0.1:8080/v1 \
  --openai-api-key none \
  --model openai/qwen2.5-coder-14b-instruct \
  --edit-format diff
```
*Note: Using `--edit-format diff` forces Aider to use search/replace diff chunks, which is tailored for our fine-tuning profile and minimizes generation latency.*

---

## 4. Cursor IDE

1. In Cursor, open **Settings -> Features -> Models**.
2. Add a Custom OpenAI Model.
3. Configure:
   - **Model Name:** `apex-coder-14b`
   - **OpenAI Base URL:** `http://127.0.0.1:8080/v1`
   - **API Key:** `none`
4. Disable other cloud models to test local speed and zero-data-leakage performance.
