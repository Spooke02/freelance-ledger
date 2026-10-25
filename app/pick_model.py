"""Find a Gemini model your key can call and write it to .env.

Usage:  python -m app.pick_model          (tests candidates, prints the first that works)
        python -m app.pick_model --write  (also saves AI_BASE_URL / AI_MODEL into .env)
Needs AI_API_KEY in .env. Never prints the key.
"""
import sys
from pathlib import Path

import httpx

ENV = Path(__file__).resolve().parent.parent / ".env"
BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
CANDIDATES = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash"]


def read_env() -> dict:
    out = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def try_model(model: str, key: str) -> tuple[bool, str]:
    r = httpx.post(BASE + "/chat/completions", timeout=40, headers={"Authorization": "Bearer " + key},
                   json={"model": model, "max_tokens": 5, "messages": [{"role": "user", "content": "Reply with: ok"}]})
    return r.status_code == 200, f"HTTP {r.status_code}"


def main() -> int:
    key = read_env().get("AI_API_KEY", "")
    if not key:
        print("AI_API_KEY is missing in .env")
        return 1
    for m in CANDIDATES:
        ok, info = try_model(m, key)
        print(f"{m}: {info}")
        if ok:
            print(f"\nWorks: {m}")
            if "--write" in sys.argv:
                lines = [l for l in ENV.read_text(encoding="utf-8").splitlines() if not l.startswith(("AI_BASE_URL=", "AI_MODEL="))]
                ENV.write_text("\n".join(lines + [f"AI_BASE_URL={BASE}", f"AI_MODEL={m}"]) + "\n", encoding="utf-8")
                print("Saved AI_BASE_URL and AI_MODEL to .env")
            return 0
    print("\nNo candidate worked. Check the key in AI Studio, or look at the rate-limits page there.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
