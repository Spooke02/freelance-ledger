from datetime import date

from app import ai, main, paypal
from app.ai import _rule_category
from app.ledger import Txn, financial_year, summarise, to_inr
from app.paypal import parse_order, parse_transactions


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
                    "transaction_id": "T1", "transaction_event_code": "T0006", "transaction_status": "S",
                    "transaction_initiation_date": "2026-10-02T10:00:00+0000",
                    "transaction_amount": {"currency_code": "USD", "value": "100.00"},
                    "fee_amount": {"currency_code": "USD", "value": "-4.50"},
                    "transaction_subject": "Website",
                },
                "payer_info": {"email_address": "a@b.c"},
            },
            {
                "transaction_info": {
                    "transaction_id": "T2", "transaction_event_code": "T0006", "transaction_status": "S",
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


def test_parse_ignores_initial_balance_funding():
    p = {"transaction_details": [{"transaction_info": {"transaction_id": "F", "transaction_event_code": "T1900", "transaction_status": "S",
         "transaction_initiation_date": "2026-10-24T00:00:00+0000", "transaction_amount": {"currency_code": "USD", "value": "5000.00"}}}]}
    assert parse_transactions(p) == []


def test_parse_order_reads_completed_capture_only():
    o = {"payer": {"name": {"given_name": "John", "surname": "Doe"}}, "purchase_units": [{"description": "Website build", "payments": {"captures": [
        {"id": "C1", "status": "COMPLETED", "create_time": "2026-10-25T01:00:00Z", "amount": {"currency_code": "USD", "value": "250.00"},
         "seller_receivable_breakdown": {"paypal_fee": {"value": "11.15"}}},
        {"id": "C2", "status": "PENDING", "create_time": "2026-10-25T01:00:00Z", "amount": {"currency_code": "USD", "value": "9.00"}}]}}]}
    t = parse_order(o)
    assert len(t) == 1 and t[0].id == "C1" and t[0].fee == 11.15 and t[0].payer == "John Doe" and t[0].note == "Website build"


def test_ai_uses_openai_compatible_provider_when_configured(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "http://x/v1")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setattr(ai, "_openai_compatible", lambda prompt, n: '["Web/design", "Other"]')
    assert ai.categorise(["site", "zzz"]) == (["Web/design", "Other"], "test-model")


def test_ai_falls_back_to_rules_on_bad_output(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "http://x/v1")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setattr(ai, "_openai_compatible", lambda prompt, n: "not json")
    cats, engine = ai.categorise(["Python data pipeline"])
    assert engine == "rules" and cats == ["Software/automation"]


def test_ask_without_model_says_so(monkeypatch):
    for k in ("AI_BASE_URL", "AI_MODEL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    text, engine = ai.ask("who paid most?", {"fy": "2026-27"}, [])
    assert engine == "rules" and "No AI model" in text


def test_ask_uses_model_when_configured(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "http://x/v1")
    monkeypatch.setenv("AI_MODEL", "m")
    monkeypatch.setattr(ai, "_openai_compatible", lambda prompt, n: "Contoso paid most.")
    assert ai.ask("who paid most?", {}, []) == ("Contoso paid most.", "m")


def test_ai_results_are_cached(monkeypatch):
    ai._CACHE.clear()
    monkeypatch.setenv("AI_BASE_URL", "http://x/v1")
    monkeypatch.setenv("AI_MODEL", "m")
    calls = []
    monkeypatch.setattr(ai, "_openai_compatible", lambda prompt, n: calls.append(1) or '["Other"]')
    ai.categorise(["zzz"]); ai.categorise(["zzz"])
    assert len(calls) == 1
    ai._CACHE.clear()


def test_ask_rate_limit_per_ip():
    main._ASKS.clear()
    assert all(main._allow_ask("1.2.3.4") for _ in range(main.ASK_LIMIT))
    assert not main._allow_ask("1.2.3.4")
    assert main._allow_ask("5.6.7.8")
    main._ASKS.clear()


def test_known_order_ids_merges_env_and_dedupes(monkeypatch, tmp_path):
    monkeypatch.setattr(paypal, "ORDERS", tmp_path / "none.json")
    monkeypatch.setenv("PAYPAL_ORDER_IDS", "A, B ,A")
    assert paypal.known_order_ids() == ["A", "B"]
