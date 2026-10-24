"""Pure ledger logic: financial year, INR conversion, GST-threshold status, paperwork flags. No network."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
from typing import Iterable

GST_THRESHOLD_INR = 2_000_000  # services, most states; Rs 10 lakh in special-category states (configurable)


@dataclass
class Txn:
    id: str
    date: str            # YYYY-MM-DD
    payer: str
    currency: str
    gross: float         # amount received before PayPal fee
    fee: float = 0.0
    note: str = ""
    category: str = ""   # filled by ai.py
    inr_rate: float = 0.0
    has_firc: bool = False   # user marks that the e-FIRA/FIRC is on file


def financial_year(d: date) -> int:
    """Indian FY starts 1 April; returns the starting calendar year (FY 2026-27 -> 2026)."""
    return d.year if d.month >= 4 else d.year - 1


def to_inr(t: Txn) -> dict:
    rate = 1.0 if t.currency == "INR" else t.inr_rate
    return {"gross_inr": round(t.gross * rate, 2), "fee_inr": round(t.fee * rate, 2),
            "net_inr": round((t.gross - t.fee) * rate, 2)}


def summarise(txns: Iterable[Txn], fy: int, threshold: float = GST_THRESHOLD_INR) -> dict:
    rows = [t for t in txns if financial_year(date.fromisoformat(t.date)) == fy and t.gross > 0]
    gross = sum(to_inr(t)["gross_inr"] for t in rows)
    fees = sum(to_inr(t)["fee_inr"] for t in rows)
    pct = gross / threshold if threshold else 0
    status = "OVER threshold" if pct >= 1 else "Near threshold (80%+)" if pct >= 0.8 else "Watch: over half" if pct >= 0.5 else "OK"
    return {"fy": f"{fy}-{str(fy + 1)[2:]}", "count": len(rows), "gross_inr": round(gross, 2), "fees_inr": round(fees, 2),
            "net_inr": round(gross - fees, 2), "threshold_inr": threshold, "threshold_pct": round(pct, 4), "status": status,
            "missing_firc": [t.id for t in rows if t.currency != "INR" and not t.has_firc]}


def to_dict(t: Txn) -> dict:
    return {**asdict(t), **to_inr(t)}
