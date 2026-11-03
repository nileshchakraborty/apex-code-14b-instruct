# 🎓 ApexCode-36GB Fine-Tuning Strategy

This guide outlines the specialized fine-tuning and alignment process designed to transform base lightweight models into the most efficient, accurate local coding assistants.

---

## 1. Core Objectives

Off-the-shelf code models often suffer from three major inefficiencies when deployed locally:
1. **Excessive Conversational Banter:** Lengthy introductions ("Sure! Here is a Python function that...") and conclusions ("I hope this helps! Let me know if you need anything else.") waste valuable compute cycles and tokens.
2. **Full-File Regeneration:** When asked to change 3 lines of code in a 400-line file, baseline models rewrite all 400 lines, slowing down the IDE and draining CPU/GPU power.
3. **Lack of Native FIM (Fill-In-The-Middle) Discipline:** Inability to reliably perform inline ghost-text code completion based on cursor position.

The ApexCode fine-tuning recipe eliminates these issues through targeted synthetic training and Direct Preference Optimization (DPO).

---

## 2. Dataset Architecture

We curate a 4-part balanced dataset:

### A. Fill-In-The-Middle (FIM) (30% weight)
Uses Qwen's native special tokens to teach cursor-level code completion:
```text
<|fim_prefix|>def compute_token_throughput(tokens: int, duration_sec: float) -> float:
    """Calculates tokens generated per second."""
    <|fim_suffix|>
    return round(tokens / duration_sec, 2)<|fim_middle|>if duration_sec <= 0:
        return 0.0
```

### B. Surgical Unified Diff / Search-Replace (35% weight)
Teaches the model to output compact diff chunks instead of whole files:
```markdown
<<<<<<< SEARCH
def process_data(items):
    return [i * 2 for i in items]
=======
def process_data(items: list[int]) -> list[int]:
    if not items:
        return []
    return [i * 2 for i in items]
>>>>>>> REPLACE
```

### C. Agentic Tool Calling & Bash Execution (20% weight)
Trains standard JSON tool calls matching OpenAI function calling standards:
- `execute_bash(command: str)`
- `read_file(path: str, start_line: int, end_line: int)`
- `write_file(path: str, content: str)`
- `grep_search(pattern: str, dir: str)`

### D. Hard Problem Solving & Unit Test Generation (15% weight)
- Derived from HumanEvalPlus, MBPP-Plus, and LeetCode Hard problems with full unit-test coverage.

---

## 3. Training Hyperparameters (QLoRA)

Using 4-bit NormalFloat (NF4) quantization with double quantization:
- **Base Model:** `Qwen/Qwen2.5-Coder-14B` (or `7B`)
- **LoRA Rank ($r$):** 32
- **LoRA Alpha ($\alpha$):** 64
- **LoRA Dropout:** 0.05
- **Target Modules:** All linear layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`)
- **Optimizer:** Paged AdamW 8-bit (`paged_adamw_8bit`)
- **Learning Rate:** $2 \times 10^{-4}$ with Cosine decay
- **Batch Size:** 4 per device with 4 gradient accumulation steps (Effective batch size = 16)
- **Sequence Length:** 4,096 tokens (packed sequences)

---

## 4. Direct Preference Optimization (DPO)

DPO aligns the model against a binary preference dataset $D = \{(x, y_w, y_l)\}$:
- **Chosen ($y_w$):** Directly outputs production code or concise search-replace diffs, correct typing, boundary checks, zero conversational fluff.
- **Rejected ($y_l$):** Chatty responses, truncated code with comments like `# TODO: implement this`, or hallucinated libraries.

### DPO Objective Function:
$$\mathcal{L}_{DPO}(\theta; \pi_{ref}) = -\mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi_{ref}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi_{ref}(y_l|x)} \right) \right]$$
Setting $\beta = 0.1$ maintains model creativity while enforcing strict syntax and brevity.
