# FreelanceLedger

Indian freelancers paid through PayPal in dollars, euros or pounds face three recurring chores: converting each payment to INR, watching the
GST registration threshold, and keeping the e-FIRA/FIRC paperwork for foreign inward remittances. FreelanceLedger reads a freelancer's PayPal
payments, converts them to INR using the ECB rate for the payment date, tracks progress through the financial year (April-March) against the
GST threshold, and lists foreign payments that still lack paperwork. AI categorises each payment and explains the position in plain language.

**Record-keeping only. Not tax, legal or financial advice. Confirm with a Chartered Accountant.**

## How PayPal is used
- Auth: PayPal REST OAuth2 client-credentials (sandbox only; this build refuses `PAYPAL_ENV=live`).
- Data: Transaction Search API (`/v1/reporting/transactions`), incoming payments only, with the fee from each transaction.
- If Transaction Search is not enabled on the PayPal app, the UI says so and the demo data keeps working.

## How AI is used
- Any OpenAI-compatible endpoint (`AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`): e.g. Google Gemini's free tier, Groq, OpenRouter or a local Ollama model. Or `ANTHROPIC_API_KEY` for Claude.
- The model categorises each payment note and writes a 3-sentence plain-language explanation of the freelancer's position.
- Without any key, a deterministic rule-based fallback is used, so the app runs for anyone. The UI shows which engine produced each result.

## AG Grid
The payments table uses [AG Grid Community](https://www.ag-grid.com/) (sortable, filterable columns, INR amounts, an e-FIRA checkbox cell renderer).

## Run it
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # add PayPal SANDBOX keys (developer.paypal.com); optional ANTHROPIC_API_KEY
python -m uvicorn app.main:app --port 8000
# open http://127.0.0.1:8000  (choose "Demo data" or "PayPal sandbox")
pytest -q
```
Never commit `.env`. Only sandbox credentials are supported.

## Notes and limits
- FX: Frankfurter (ECB reference rates), per payment date. Your bank's actual rate may differ; the e-FIRA is the document of record.
- GST threshold defaults to INR 20 lakh (INR 10 lakh in special-category states): change `GST_THRESHOLD_INR` in `app/ledger.py`.
- Demo data is fictional. License: MIT.

## Deploy on Render
`render.yaml` defines a free web service. In Render: New > Blueprint > select this repo, then enter `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` (PayPal sandbox)
and `AI_API_KEY` (Gemini) in the dashboard. The free plan sleeps when idle (first request can take about a minute) and its disk is not persistent.
The AI question box is limited to 10 questions per hour per visitor (`ASK_LIMIT_PER_HOUR`).
