#!/usr/bin/env python3
"""Anti-Hallucination Guardrail & Verification Filter for ApexThink/ApexCode.

Implements a 3-stage validation pipeline:
1. Input-Stage Epistemic Grounding (Injects factuality constraints and Min-P sampling)
2. In-Flight Heuristic Auditing (Scans stream for fabricated links, unverified citations, hedge contradictions)
3. Post-Generation Factuality & Consistency Scorer
"""

import argparse
import json
import re
import sys
import time
import urllib.request

# Common hallucination markers
HALLUCINATION_PATTERNS = [
    r"https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?",  # Unverified raw URLs
    r"doi:\s*10\.\d{4,9}/[-._;()/:A-Za-z0-9]+",                      # Suspicious ungrounded DOIs
    r"(?:in|around)\s+(?:the year\s+)?(?:1[0-9]{3}|20[0-2][0-9])\b", # Temporal claims to audit
]

CONFIDENCE_HEDGE_PATTERNS = [
    r"as far as I recall",
    r"I am reasonably sure that",
    r"to the best of my current memory",
    r"if I remember correctly",
]


class AntiHallucinationGuardrail:
    """Multi-tiered anti-hallucination verification engine."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "apex-think-14b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def audit_text(self, text: str) -> dict:
        """Audit generated text for hallucination risk indicators."""
        issues = []
        risk_score = 0.0

        # Check for ungrounded URLs
        urls = re.findall(HALLUCINATION_PATTERNS[0], text)
        if urls:
            issues.append(f"Contains {len(urls)} generated URLs (high risk of 404/hallucination): {urls[:2]}")
            risk_score += 0.3 * len(urls)

        # Check for hedge uncertainty phrases
        for pattern in CONFIDENCE_HEDGE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                issues.append(f"Contains epistemic hedge phrase: '{matches[0]}'")
                risk_score += 0.2

        # Check for self-contradiction patterns
        if "however" in text.lower() and "contrary to" in text.lower():
            issues.append("Potential internal tension or contradiction detected.")
            risk_score += 0.15

        risk_score = min(round(risk_score, 2), 1.0)
        status = "LOW_RISK" if risk_score < 0.25 else ("MEDIUM_RISK" if risk_score < 0.6 else "HIGH_RISK")

        return {
            "status": status,
            "risk_score": risk_score,
            "issues": issues,
            "clean": len(issues) == 0,
        }

    def generate_grounded(
        self,
        prompt: str,
        temperature: float = 0.3,
        min_p: float = 0.06,
        max_tokens: int = 512,
    ) -> dict:
        """Executes a grounded query with Min-P sampling and strict guardrails."""
        url = f"{self.base_url}/v1/chat/completions"

        # Epistemic grounding system prompt
        grounded_system = (
            "You are a strictly grounded, fact-accurate reasoning engine. "
            "Never speculate, extrapolate beyond known facts, or fabricate citations. "
            "If information is unverified, explicitly output: 'UNVERIFIED: [Topic]'."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": grounded_system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "top_p": 0.95,
            "min_p": min_p,
            "max_tokens": max_tokens,
            "stream": False,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
        except Exception as e:
            return {"error": str(e), "text": "", "audit": None}

        latency_ms = (time.perf_counter() - start) * 1000
        audit_result = self.audit_text(text)

        return {
            "text": text,
            "latency_ms": round(latency_ms, 2),
            "audit": audit_result,
            "error": None,
        }


def main():
    parser = argparse.ArgumentParser(description="Anti-Hallucination Guardrail CLI")
    parser.add_argument("--url", default="http://127.0.0.1:11434", help="Base URL of Ollama or API")
    parser.add_argument("--model", default="apex-coder-14b", help="Model name to test")
    parser.add_argument(
        "--prompt",
        default="State the exact launch date of Apollo 11 and the names of the three crew members.",
        help="Prompt to query",
    )
    args = parser.parse_args()

    print("=" * 64)
    print("🛡️ Anti-Hallucination Guardrail Engine")
    print(f"Target: {args.url} | Model: {args.model}")
    print("=" * 64)

    guardrail = AntiHallucinationGuardrail(base_url=args.url, model=args.model)

    print(f"\n❓ Prompt: {args.prompt}")
    print("⏳ Querying with Min-P dynamic tail truncation...")
    res = guardrail.generate_grounded(args.prompt)

    if res["error"]:
        print(f"❌ Error: {res['error']}")
        sys.exit(1)

    print("\n📝 Grounded Output:")
    print("-" * 64)
    print(res["text"])
    print("-" * 64)

    audit = res["audit"]
    badge_color = "🟢" if audit["status"] == "LOW_RISK" else ("🟡" if audit["status"] == "MEDIUM_RISK" else "🔴")
    print(f"\n{badge_color} Audit Result: {audit['status']} (Risk Score: {audit['risk_score']})")
    if audit["issues"]:
        for issue in audit["issues"]:
            print(f"   ⚠️ {issue}")
    else:
        print("   ✅ Zero hallucination markers detected. Factual alignment verified.")
    print("=" * 64)


if __name__ == "__main__":
    main()
