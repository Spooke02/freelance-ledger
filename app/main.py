import json
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, ledger, paypal
from .demo import DEMO
from .rates import inr_rate

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STORE = DATA / "firc.json"
app = FastAPI(title="FreelanceLedger")


def _load_env() -> None:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _marks() -> dict:
    return json.loads(STORE.read_text()) if STORE.exists() else {}


class Mark(BaseModel):
    id: str
    value: bool


@app.post("/api/firc")
def mark(m: Mark):
    DATA.mkdir(exist_ok=True)
    marks = _marks()
    marks[m.id] = m.value
    STORE.write_text(json.dumps(marks))
    return {"ok": True}


@app.get("/api/state")
def state(source: str = "demo", fy: int | None = None):
    if source == "paypal":
        try:
            txns = paypal.fetch_orders()
            seen = {t.id for t in txns}
            try:
                txns += [t for t in paypal.fetch_transactions() if t.id not in seen]
            except paypal.PayPalError:
                if not txns:
                    raise
        except paypal.PayPalError as e:
            raise HTTPException(status_code=502, detail=str(e))
    else:
        txns = [ledger.Txn(**vars(t)) for t in DEMO]
    marks = _marks()
    for t in txns:
        if not t.inr_rate and t.currency != "INR":
            try:
                t.inr_rate = inr_rate(t.currency, t.date)
            except Exception:
                t.inr_rate = 0.0
        t.has_firc = bool(marks.get(t.id, t.has_firc))
    cats, engine = ai.categorise([t.note for t in txns])
    for t, c in zip(txns, cats):
        t.category = c
    if fy is None:
        fy = ledger.financial_year(date.today())
    summary = ledger.summarise(txns, fy)
    text, text_engine = ai.explain(summary)
    return {
        "source": source,
        "txns": [ledger.to_dict(t) for t in txns],
        "summary": summary,
        "explanation": text,
        "ai": {"categorise": engine, "explain": text_engine},
    }


class Ask(BaseModel):
    question: str
    source: str = "demo"


@app.post("/api/ask")
def ask(a: Ask):
    data = state(source=a.source)
    answer, engine = ai.ask(a.question, data["summary"], data["txns"])
    return {"answer": answer, "engine": engine}


@app.get("/api/sandbox/order")
def sandbox_order(amount: str = "100.00", currency: str = "USD", note: str = "Test freelance payment", base: str = "http://127.0.0.1:8765"):
    """Sandbox only: returns a PayPal approval link. Approve it with a SANDBOX buyer account to create a real sandbox payment."""
    try:
        return paypal.create_test_order(amount, currency, note, f"{base}/api/sandbox/return", f"{base}/")
    except paypal.PayPalError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/sandbox/return")
def sandbox_return(token: str):
    """PayPal redirects here after approval; capture the order, then show the ledger."""
    try:
        paypal.capture_order(token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Capture failed: {e}")
    return RedirectResponse("/")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
