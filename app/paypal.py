"""PayPal REST client (sandbox by default). Reads transactions via Transaction Search; falls back with a clear error if not enabled."""
import base64
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import httpx
from .ledger import Txn

BASE = {"sandbox": "https://api-m.sandbox.paypal.com", "live": "https://api-m.paypal.com"}


class PayPalError(RuntimeError):
    pass


def _env() -> str:
    env = os.getenv("PAYPAL_ENV", "sandbox")
    if env != "sandbox":
        raise PayPalError("This hackathon build only supports the PayPal sandbox (no real money).")
    return env


def token() -> str:
    cid, sec = os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")
    if not cid or not sec:
        raise PayPalError("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET not set (see .env.example)")
    r = httpx.post(BASE[_env()] + "/v1/oauth2/token", data={"grant_type": "client_credentials"}, auth=(cid, sec), timeout=20)
    if r.status_code != 200:
        raise PayPalError(f"PayPal auth failed ({r.status_code})")
    return r.json()["access_token"]


def parse_transactions(payload: dict) -> list[Txn]:
    """Map PayPal Transaction Search 'transaction_details' to Txn. Only incoming (positive) payments."""
    out = []
    for d in payload.get("transaction_details", []):
        info, payer = d.get("transaction_info", {}), d.get("payer_info", {})
        amt = info.get("transaction_amount", {})
        value = float(amt.get("value", 0))
        # Income = completed payments received (event codes T00xx). Excludes funding/initial balance (T19xx), transfers and reversals.
        if value <= 0 or not str(info.get("transaction_event_code", "")).startswith("T00") or info.get("transaction_status") != "S":
            continue
        fee = abs(float(info.get("fee_amount", {}).get("value", 0)))
        name = (payer.get("payer_name") or {}).get("alternate_full_name") or payer.get("email_address") or "Unknown payer"
        out.append(Txn(id=info.get("transaction_id", ""), date=info.get("transaction_initiation_date", "")[:10], payer=name,
                       currency=amt.get("currency_code", "USD"), gross=value, fee=fee,
                       note=info.get("transaction_subject") or info.get("transaction_note") or ""))
    return out


def fetch_transactions(days: int = 30) -> list[Txn]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=min(days, 31))  # API limit: 31 days per request
    r = httpx.get(BASE[_env()] + "/v1/reporting/transactions", timeout=30,
                  headers={"Authorization": "Bearer " + token()},
                  params={"start_date": start.strftime("%Y-%m-%dT%H:%M:%S-0000"), "end_date": end.strftime("%Y-%m-%dT%H:%M:%S-0000"),
                          "fields": "transaction_info,payer_info", "page_size": 100})
    if r.status_code == 403:
        raise PayPalError("Transaction Search is not enabled for this PayPal app. Enable it in the app's features on developer.paypal.com.")
    r.raise_for_status()
    return parse_transactions(r.json())


def create_test_order(amount: str, currency: str, note: str, return_url: str, cancel_url: str) -> dict:
    """Sandbox only: create an order; a sandbox buyer approves it, then capture_order() completes the payment."""
    r = httpx.post(BASE[_env()] + "/v2/checkout/orders", timeout=30, headers={"Authorization": "Bearer " + token()},
                   json={"intent": "CAPTURE", "purchase_units": [{"description": note[:120], "amount": {"currency_code": currency, "value": amount}}],
                         "payment_source": {"paypal": {"experience_context": {"return_url": return_url, "cancel_url": cancel_url, "user_action": "PAY_NOW"}}}})
    r.raise_for_status()
    j = r.json()
    remember_order(j["id"])
    link = next(l["href"] for l in j["links"] if l["rel"] in ("payer-action", "approve"))
    return {"order_id": j["id"], "approve_url": link}


def capture_order(order_id: str) -> str:
    r = httpx.post(BASE[_env()] + f"/v2/checkout/orders/{order_id}/capture", timeout=30,
                   headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"}, content=b"{}")
    r.raise_for_status()
    return r.json().get("status", "")


ORDERS = Path(__file__).resolve().parent.parent / "data" / "orders.json"


def remember_order(order_id: str) -> None:
    ids = json.loads(ORDERS.read_text()) if ORDERS.exists() else []
    if order_id not in ids:
        ORDERS.parent.mkdir(exist_ok=True)
        ORDERS.write_text(json.dumps(ids + [order_id]))


def parse_order(o: dict) -> list[Txn]:
    """Completed captures of one PayPal order -> Txn (Transaction Search can lag, so the app also reads its own orders)."""
    out = []
    for pu in o.get("purchase_units", []):
        for c in pu.get("payments", {}).get("captures", []):
            if c.get("status") != "COMPLETED":
                continue
            fee = c.get("seller_receivable_breakdown", {}).get("paypal_fee", {}).get("value", "0")
            name = ((o.get("payer") or {}).get("name") or {})
            out.append(Txn(id=c["id"], date=c.get("create_time", "")[:10], payer=" ".join(filter(None, [name.get("given_name"), name.get("surname")])) or "PayPal buyer",
                           currency=c["amount"]["currency_code"], gross=float(c["amount"]["value"]), fee=float(fee), note=pu.get("description", "")))
    return out


def known_order_ids() -> list[str]:
    """Orders created locally (data/orders.json) plus any listed in PAYPAL_ORDER_IDS (comma-separated; lets a hosted demo show sandbox payments)."""
    ids = json.loads(ORDERS.read_text()) if ORDERS.exists() else []
    ids += [i.strip() for i in os.getenv("PAYPAL_ORDER_IDS", "").split(",") if i.strip()]
    return list(dict.fromkeys(ids))


def fetch_orders() -> list[Txn]:
    ids = known_order_ids()
    if not ids:
        return []
    tok, out = token(), []
    for oid in ids:
        r = httpx.get(BASE[_env()] + f"/v2/checkout/orders/{oid}", headers={"Authorization": "Bearer " + tok}, timeout=20)
        if r.status_code == 200:
            out += parse_order(r.json())
    return out
