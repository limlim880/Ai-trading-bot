# AI Trading Assistant

A decision-support system for the **Four-Hour Trend Pullback Strategy**. It
analyses signals sent from a TradingView Pine Script alert, independently
scores and risk-checks them, records everything in a trade journal, and
sends Telegram notifications.

**This system never places trades automatically.** It only recommends. You
decide whether to act on any alert.

## Current stage

This is the **baseline system** (pre-Stage-1 in the project roadmap): local
FastAPI app, SQLite journal, Telegram alerts, hard-gate strategy validation,
100-point scoring, risk engine, naive expiry, duplicate protection.

Known, deliberate limitations (see code comments for details, tracked
against the project's staged roadmap):

- **News and spread are not independently verified yet.** `high_impact_news_nearby`
  and `spread_normal` from TradingView are stored for reference only and are
  never used to accept/reject a signal. Stage 5 (economic calendar) and
  Stage 6 (real spread verification) fix this.
- **Expiry is a naive wall-clock timer** (`PENDING_SIGNAL_EXPIRY_HOURS`). It
  does not account for weekend market closure yet. Stage 2 fixes this.
- **Position sizing assumes account currency == quote currency.** Accurate
  for e.g. a USD account trading EURUSD/GBPUSD/AUDUSD; not accurate for
  pairs like USDJPY without a pip-value conversion. Stage 6/7 fix this.
- **No pre-entry technical invalidation yet** (Stage 3).
- **TradingView's indicator values are trusted as-is.** Python does not yet
  independently recompute EMA/RSI/ATR from its own market data (Stage 7).

## Project layout

| File | Responsibility |
|---|---|
| `app.py` | FastAPI routes only -- no business logic |
| `config.py` | Environment-variable driven settings |
| `models.py` | Pydantic request/response schemas |
| `strategy.py` | BUY/SELL hard-gate validation + 100-point scoring |
| `risk.py` | Position sizing, risk:reward, portfolio risk gates |
| `telegram_alerts.py` | All outbound Telegram messages |
| `ai_explanation.py` | Deterministic (non-AI) explanation text |
| `database.py` | SQLite persistence (trade journal, latest prices) |
| `market_data.py` | Latest-price store, fed by `/price-update` |
| `trade_monitor.py` | Status transitions: entry reached / target / stop / expiry |

## Running locally

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:
- `WEBHOOK_SECRET` -- any long random string (the webhook endpoints refuse
  all requests until this is set).
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` -- optional for local testing;
  if left blank, the app logs a warning instead of sending, and still works.

### 3. Run the server

```bash
uvicorn app:app --reload --port 8000
```

Expected output ends with:
```
INFO:     Application startup complete.
```

### 4. Test it

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok", "database": true}

curl -X POST http://127.0.0.1:8000/test-telegram
```

Send a sample signal (edit `sample_signal.json`'s `secret` to match your
`.env`, and set `timestamp` to the current time -- webhook payloads older
than `WEBHOOK_MAX_AGE_SECONDS` are rejected as stale):

```bash
curl -X POST http://127.0.0.1:8000/tradingview-webhook \
  -H "Content-Type: application/json" \
  -d @sample_signal.json
```

### 5. Run the tests

```bash
pytest -v
```

## Deployment

See `DEPLOYMENT.md` for step-by-step Railway deployment instructions
(Stage 1 of the project roadmap).

## Security notes

- Secrets live only in environment variables -- never hardcoded, never
  logged.
- `/tradingview-webhook` and `/price-update` require a shared secret and
  reject stale timestamps.
- A basic in-memory rate limit applies to all POST endpoints.
