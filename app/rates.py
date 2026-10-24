"""INR exchange rate for a date via the free Frankfurter API (ECB reference rates). Cached per (date, currency)."""
import httpx
from functools import lru_cache


@lru_cache(maxsize=512)
def inr_rate(currency: str, day: str) -> float:
    if currency == "INR":
        return 1.0
    r = httpx.get(f"https://api.frankfurter.dev/v1/{day}", params={"base": currency, "symbols": "INR"}, timeout=15, follow_redirects=True)
    r.raise_for_status()
    return float(r.json()["rates"]["INR"])
