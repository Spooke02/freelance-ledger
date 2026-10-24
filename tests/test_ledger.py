from datetime import date

from app.ai import _rule_category
from app.ledger import Txn, financial_year, summarise, to_inr
from app.paypal import parse_transactions


def test_financial_year_boundary():
    assert financial_year(date(2026, 3, 31)) == 2025
    assert financial_year(date(2026, 4, 1)) == 2026


def test_inr_conversion_and_fee():
    t = Txn("a", "2026-05-01", "x", "USD", 100, 10, inr_rate=80)
    assert to_inr(t) == {"gross_inr": 8000.0, "fee_inr": 800.0, "net_inr": 7200.0}


def test_summary_excludes_other_fy_and_flags_missing_firc():
    a = Txn("a", "2026-05-01", "x", "USD", 100, 0, inr_rate=80)
    b = Txn("b", "2026-02-01", "x", "USD", 999, 0, inr_rate=80, has_firc=True)  # previous FY
    c = Txn("c", "2026-06-01", "x", "INR", 5000, 0)
    s = summarise([a, b, c], 2026)
    assert s["gross_inr"] == 13000 and s["count"] == 2 and s["missing_firc"] == ["a"]


def test_threshold_status():
    assert summarise([Txn("a", "2026-05-01", "x", "INR", 1_700_000)], 2026)["status"].startswith("Near")
    assert summarise([Txn("b", "2026-05-01", "x", "INR", 2_000_001)], 2026)["status"] == "OVER threshold"


def test_parse_paypal_transactions_ignores_outgoing():
    payload = {
        "transaction_details": [
            {
                "transaction_info": {
                    "transaction_id": "T1",
                    "transaction_initiation_date": "2026-10-02T10:00:00+0000",
                    "transaction_amount": {"currency_code": "USD", "value": "100.00"},
                    "fee_amount": {"currency_code": "USD", "value": "-4.50"},
                    "transaction_subject": "Website",
                },
                "payer_info": {"email_address": "a@b.c"},
            },
            {
                "transaction_info": {
                    "transaction_id": "T2",
                    "transaction_initiation_date": "2026-10-03T10:00:00+0000",
                    "transaction_amount": {"currency_code": "USD", "value": "-20.00"},
                }
            },
        ]
    }
    out = parse_transactions(payload)
    assert len(out) == 1 and out[0].fee == 4.5 and out[0].date == "2026-10-02"


def test_rule_category():
    assert _rule_category("Python data pipeline") == "Software/automation"
    assert _rule_category("zzz") == "Other"
