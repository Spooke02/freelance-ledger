"""AI layer: categorise payments and explain the position in plain language.

Uses the Anthropic API when ANTHROPIC_API_KEY is set; otherwise a deterministic rule-based fallback,
so the demo runs for judges without any key.
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


def _claude(prompt: str, max_tokens: int = 600) -> str | None:
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


def categorise(notes: list[str]) -> tuple[list[str], str]:
    """Returns (categories, engine) where engine is 'claude' or 'rules'."""
    out = _claude(
        "Classify each freelance payment note into exactly one of %s. "
        "Reply with only a JSON array of strings, same order and length.\nNotes: %s" % (CATEGORIES, json.dumps(notes))
    )
    if out:
        m = re.search(r"\[.*\]", out, re.S)
        try:
            arr = json.loads(m.group(0)) if m else []
            if len(arr) == len(notes) and all(a in CATEGORIES for a in arr):
                return arr, "claude"
        except json.JSONDecodeError:
            pass
    return [_rule_category(n) for n in notes], "rules"


def explain(summary: dict) -> tuple[str, str]:
    base = (
        f"FY {summary['fy']}: {summary['count']} payments, gross INR {summary['gross_inr']:,.0f} "
        f"({summary['threshold_pct'] * 100:.1f}% of the INR {summary['threshold_inr']:,.0f} GST registration threshold). "
        f"Status: {summary['status']}. {len(summary['missing_firc'])} foreign payment(s) have no e-FIRA/FIRC marked."
    )
    out = _claude(
        "You are a careful assistant for an Indian freelancer. In 3 short sentences, explain this position in plain "
        "language and what to double-check with a CA. Do not give tax advice or guarantees.\n" + json.dumps(summary)
    )
    if out:
        return out.strip(), "claude"
    return base + " This is record-keeping, not tax advice; confirm with a CA.", "rules"
