"""AI layer: categorise payments and explain the position in plain language.

Provider order: any OpenAI-compatible endpoint (AI_BASE_URL + AI_MODEL [+ AI_API_KEY]: Google Gemini free tier, Groq, OpenRouter,
local Ollama ...) -> Anthropic (ANTHROPIC_API_KEY) -> deterministic rule-based fallback, so the demo runs for judges with no key at all.
"""
import json
import os
import re

import httpx

CATEGORIES = ["Web/design", "Software/automation", "Data/analytics", "Support/retainer", "Other"]
RULES = [
    ("Web/design", r"web|site|landing|design|page"),
    ("Software/automation", r"python|script|automat|bug|api|build"),
    ("Data/analytics", r"data|dashboard|sheet|excel|report"),
    ("Support/retainer", r"retainer|support|maintenance|training"),
]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")


def _rule_category(note: str) -> str:
    for cat, pat in RULES:
        if re.search(pat, note or "", re.I):
            return cat
    return "Other"


def engine_name() -> str:
    if os.getenv("AI_BASE_URL") and os.getenv("AI_MODEL"):
        return os.getenv("AI_MODEL")
    return "claude" if os.getenv("ANTHROPIC_API_KEY") else "rules"


def _openai_compatible(prompt: str, max_tokens: int) -> str | None:
    base, model, key = os.getenv("AI_BASE_URL"), os.getenv("AI_MODEL"), os.getenv("AI_API_KEY", "")
    try:
        r = httpx.post(base.rstrip("/") + "/chat/completions", timeout=60,
                       headers={"Authorization": "Bearer " + key} if key else {},
                       json={"model": model, "max_tokens": max_tokens, "temperature": 0,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def _llm(prompt: str, max_tokens: int = 600) -> str | None:
    if os.getenv("AI_BASE_URL") and os.getenv("AI_MODEL"):
        return _openai_compatible(prompt, max_tokens)
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            timeout=40,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception:
        return None  # never block the ledger on the AI call


_CACHE: dict = {}  # successful model answers only (saves free-tier quota, makes reloads instant); cleared on restart


def categorise(notes: list[str]) -> tuple[list[str], str]:
    """Returns (categories, engine) where engine is the model name or 'rules'."""
    key = ("cat", tuple(notes))
    if key in _CACHE:
        return _CACHE[key]
    result = _categorise(notes)
    if result[1] != "rules":
        _CACHE[key] = result
    return result


def _categorise(notes: list[str]) -> tuple[list[str], str]:
    out = _llm(
        "Classify each freelance payment note into exactly one of %s. "
        "Reply with only a JSON array of strings, same order and length.\nNotes: %s" % (CATEGORIES, json.dumps(notes))
    )
    if out:
        m = re.search(r"\[.*\]", out, re.S)
        try:
            arr = json.loads(m.group(0)) if m else []
            if len(arr) == len(notes) and all(a in CATEGORIES for a in arr):
                return arr, engine_name()
        except json.JSONDecodeError:
            pass
    return [_rule_category(n) for n in notes], "rules"


def explain(summary: dict) -> tuple[str, str]:
    key = ("exp", json.dumps(summary, sort_keys=True))
    if key in _CACHE:
        return _CACHE[key]
    result = _explain(summary)
    if result[1] != "rules":
        _CACHE[key] = result
    return result


def _explain(summary: dict) -> tuple[str, str]:
    base = (
        f"FY {summary['fy']}: {summary['count']} payments, gross INR {summary['gross_inr']:,.0f} "
        f"({summary['threshold_pct'] * 100:.1f}% of the INR {summary['threshold_inr']:,.0f} GST registration threshold). "
        f"Status: {summary['status']}. {len(summary['missing_firc'])} foreign payment(s) have no e-FIRA/FIRC marked."
    )
    out = _llm(
        "You are a careful assistant for an Indian freelancer. In 3 short sentences, explain this position in plain "
        "language and what to double-check with a CA. Do not give tax advice or guarantees.\n" + json.dumps(summary)
    )
    if out:
        return out.strip(), engine_name()
    return base + " This is record-keeping, not tax advice; confirm with a CA.", "rules"


def ask(question: str, summary: dict, txns: list[dict]) -> tuple[str, str]:
    """Answer a freelancer's question about their own ledger. Needs a configured model; otherwise says so plainly."""
    ctx = {"summary": summary, "payments": [{k: t[k] for k in ("date", "payer", "category", "currency", "gross", "fee", "gross_inr", "has_firc")} for t in txns]}
    out = _llm(
        "You answer questions about ONE Indian freelancer's PayPal ledger using only the JSON below. Be concise (max 5 sentences). "
        "If the data does not contain the answer, say so. This is record-keeping, not tax advice; for tax or GST rules tell them to confirm with a CA.\n"
        f"LEDGER: {json.dumps(ctx)}\nQUESTION: {question[:500]}"
    )
    if out:
        return out.strip(), engine_name()
    return "No AI model is configured. Set AI_BASE_URL, AI_MODEL and AI_API_KEY (see .env.example) to ask questions about your ledger.", "rules"
