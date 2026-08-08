"""
app.py

FastAPI application entrypoint. Deliberately thin -- every route delegates
to a dedicated module (strategy, risk, database, telegram_alerts,
trade_monitor, market_data) rather than containing business logic itself.

Endpoints:
    GET  /            basic status page
    GET  /health       health check for the deployment platform
    POST /test-telegram        sends a test message to confirm Telegram works
    POST /tradingview-webhook  receives a signal alert from TradingView
    POST /price-update         receives a price tick, drives trade monitoring
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import ai_explanation
import database
import market_data
import risk
import strategy
import telegram_alerts
import trade_monitor
from config import configure_logging, get_settings
from models import PriceUpdatePayload, TradingViewWebhookPayload

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Trading Assistant", version="0.1.0")

# --- very small in-memory rate limiter -------------------------------------
# Good enough for a single-user system behind a webhook. Tracks request
# timestamps per client IP per endpoint; not shared across multiple
# processes, which is fine since this app runs as a single instance.
_request_log: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request, bucket: str) -> None:
    key = f"{bucket}:{request.client.host if request.client else 'unknown'}"
    window_seconds = 60
    now = time.monotonic()
    log = _request_log[key]
    while log and now - log[0] > window_seconds:
        log.popleft()
    if len(log) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    log.append(now)


def _check_secret(secret: str) -> None:
    if not settings.WEBHOOK_SECRET:
        # Fail closed: an operator must deliberately configure a secret
        # before this endpoint will accept anything.
        raise HTTPException(status_code=500, detail="Server misconfigured: WEBHOOK_SECRET not set")
    if secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _check_not_stale(timestamp_iso: str) -> None:
    try:
        sent_at = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format") from None
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    age_seconds = abs((datetime.now(timezone.utc) - sent_at).total_seconds())
    if age_seconds > settings.WEBHOOK_MAX_AGE_SECONDS:
        raise HTTPException(status_code=400, detail="Stale or clock-skewed webhook payload rejected")


@app.on_event("startup")
def on_startup() -> None:
    database.init_db()
    logger.info("AI Trading Assistant started (env=%s)", settings.APP_ENV)


@app.get("/")
def root() -> dict:
    return {"service": "ai-trading-assistant", "status": "running"}


@app.get("/health")
def health() -> JSONResponse:
    """Used by the deployment platform's health check. Verifies the
    database file is reachable, not just that the process is alive."""
    try:
        database.init_db()
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check DB failure: %s", exc)
        db_ok = False
    status_code = 200 if db_ok else 503
    return JSONResponse(status_code=status_code, content={"status": "ok" if db_ok else "degraded", "database": db_ok})


@app.post("/test-telegram")
def test_telegram(request: Request) -> dict:
    _rate_limit(request, "test-telegram")
    sent = telegram_alerts.notify_test()
    if not sent:
        raise HTTPException(status_code=502, detail="Telegram not configured or send failed")
    return {"sent": True}


@app.post("/tradingview-webhook")
def tradingview_webhook(payload: TradingViewWebhookPayload, request: Request) -> dict:
    _rate_limit(request, "tradingview-webhook")
    _check_secret(payload.secret)
    _check_not_stale(payload.timestamp)

    direction = payload.direction.value
    symbol = payload.symbol

    # --- duplicate protection -------------------------------------------
    if database.has_active_duplicate(symbol, direction):
        logger.info("Duplicate signal blocked: %s %s", symbol, direction)
        return {"qualifies": False, "reason": "duplicate_active_signal"}

    # --- hard-gate strategy validation ------------------------------------
    passed, gate_reasons = strategy.validate_direction(payload)

    # --- risk math (computed regardless, so rejection messages can still
    # show the numbers) ---------------------------------------------------
    report = risk.build_risk_report(
        entry=payload.entry,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        account_balance=settings.ACCOUNT_BALANCE,
        risk_percent=settings.RISK_PER_TRADE_PERCENT,
    )

    rejection_reasons = list(gate_reasons)
    if report.risk_reward < settings.MIN_RISK_REWARD:
        rejection_reasons.append(
            f"Risk-to-reward {report.risk_reward:.2f} is below the minimum {settings.MIN_RISK_REWARD:.2f}."
        )

    # --- account-level safety gates ---------------------------------------
    active_signals = database.get_active_signals()
    open_trades_count = sum(1 for s in active_signals if s["status"] == "ACTIVE")
    gates_ok, gate_fail_reasons = risk.check_portfolio_risk_gates(
        open_trades_count=open_trades_count,
        daily_loss_percent_used=0.0,   # Stage 10 (performance analytics) will compute this from closed trades
        weekly_loss_percent_used=0.0,  # Stage 10 (performance analytics) will compute this from closed trades
        max_concurrent_trades=settings.MAX_CONCURRENT_TRADES,
        max_daily_loss_percent=settings.MAX_DAILY_LOSS_PERCENT,
        max_weekly_loss_percent=settings.MAX_WEEKLY_LOSS_PERCENT,
    )
    rejection_reasons.extend(gate_fail_reasons)

    # --- NOTE on news/spread ------------------------------------------------
    # payload.high_impact_news_nearby / payload.spread_normal are recorded
    # for reference ONLY. They are never used to gate a decision -- Stage 5
    # and Stage 6 replace this with Python's own independent checks. Until
    # then this system does not claim to filter on news or spread at all.
    news_note = "not independently verified (Stage 5 pending)"
    spread_note = "not independently verified (Stage 6 pending)"

    score, breakdown = strategy.score_signal(payload, report.risk_reward)
    qualifies = passed and gates_ok and report.risk_reward >= settings.MIN_RISK_REWARD and score >= settings.MIN_SIGNAL_SCORE
    if score < settings.MIN_SIGNAL_SCORE:
        rejection_reasons.append(f"Score {score} is below the minimum qualifying score {settings.MIN_SIGNAL_SCORE}.")

    indicators = {
        "ema20_1h": payload.ema20_1h, "ema50_1h": payload.ema50_1h, "ema200_1h": payload.ema200_1h,
        "ema20_4h": payload.ema20_4h, "ema50_4h": payload.ema50_4h, "ema200_4h": payload.ema200_4h,
        "rsi_1h": payload.rsi_1h, "atr_1h": payload.atr_1h,
        "trend_4h": payload.trend_4h.value, "market_structure": payload.market_structure.value,
    }

    signal_data = {
        "symbol": symbol,
        "direction": direction,
        "timeframe_trend": payload.timeframe_trend,
        "timeframe_setup": payload.timeframe_setup,
        "price_at_signal": payload.price,
        "entry": payload.entry,
        "stop_loss": payload.stop_loss,
        "take_profit": payload.take_profit,
        "risk_reward": report.risk_reward,
        "account_balance": report.account_balance,
        "risk_percent": report.risk_percent,
        "risk_amount": report.risk_amount,
        "position_size": report.position_size,
        "potential_profit": report.potential_profit,
        "score": score,
        "score_breakdown": breakdown,
        "indicators": indicators,
        "qualification_reasons": gate_reasons if passed else [],
        "rejection_reasons": rejection_reasons,
        "news_note": news_note,
        "spread_note": spread_note,
        "status": "ALERT_SENT" if qualifies else "REJECTED",
    }
    signal_uid = database.insert_signal(signal_data)

    if qualifies:
        explanation = ai_explanation.build_setup_explanation(
            symbol=symbol,
            direction=direction,
            score=score,
            score_breakdown=breakdown,
            risk_report=report.to_dict(),
            trend_4h=payload.trend_4h.value,
            rsi_1h=payload.rsi_1h,
        )
        telegram_alerts.notify_setup(explanation)
    else:
        telegram_alerts.notify_rejected(symbol, direction, rejection_reasons)

    return {
        "signal_uid": signal_uid,
        "qualifies": qualifies,
        "score": score,
        "score_breakdown": breakdown,
        "risk_report": report.to_dict(),
        "rejection_reasons": rejection_reasons,
    }


@app.post("/price-update")
def price_update(payload: PriceUpdatePayload, request: Request) -> dict:
    _rate_limit(request, "price-update")
    _check_secret(payload.secret)

    market_data.update_price(payload.symbol, payload.price, payload.bid, payload.ask)
    changed = trade_monitor.check_active_signals()

    return {"received": True, "symbol": payload.symbol, "signals_changed": len(changed)}
