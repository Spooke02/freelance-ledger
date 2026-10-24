"""PayPal REST client (sandbox by default). Reads transactions via Transaction Search; falls back with a clear error if not enabled."""
import base64
import os
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
        if value <= 0:
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
