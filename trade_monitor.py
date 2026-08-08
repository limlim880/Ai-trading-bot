"""
trade_monitor.py

Checks pending (ALERT_SENT) and open (ACTIVE) signals against the latest
known price and transitions their status, sending Telegram notifications
on every transition.

Called from POST /price-update right now (Stage 1 baseline). Stage 4
("Faster Trade Monitoring") adds a scheduled poller so this runs on a
timer against live market data instead of only reacting to inbound
webhooks.

EXPIRY IS NAIVE HERE ON PURPOSE. It uses PENDING_SIGNAL_EXPIRY_HOURS as a
straight wall-clock timer, which is wrong across a weekend market closure
(it burns expiry time while the market isn't even open). This is called
out explicitly rather than silently shipped as correct -- Stage 2 replaces
it with trading-time-aware expiry. Do not rely on exact expiry timing
before that stage lands.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import database
import market_data
import telegram_alerts
from config import get_settings

logger = logging.getLogger(__name__)


def _entry_reached(direction: str, entry: float, price: float) -> bool:
    if direction == "BUY":
        return price <= entry
    return price >= entry


def _target_hit(direction: str, take_profit: float, price: float) -> bool:
    if direction == "BUY":
        return price >= take_profit
    return price <= take_profit


def _stop_hit(direction: str, stop_loss: float, price: float) -> bool:
    if direction == "BUY":
        return price <= stop_loss
    return price >= stop_loss


def _is_naively_expired(created_at_iso: str, expiry_hours: float) -> bool:
    created_at = datetime.fromisoformat(created_at_iso)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= created_at + timedelta(hours=expiry_hours)


def check_active_signals() -> list[dict]:
    """Runs one monitoring pass over all ALERT_SENT / ACTIVE signals.
    Returns the list of signals that changed status, for logging/testing.
    """
    settings = get_settings()
    changed: list[dict] = []

    for signal in database.get_active_signals():
        latest = market_data.get_latest_price(signal["symbol"])
        if latest is None:
            continue
        price = latest["price"]
        direction = signal["direction"]

        database.update_signal(signal["signal_uid"], last_checked_price=price)

        if signal["status"] == "ALERT_SENT":
            if _is_naively_expired(signal["created_at"], settings.PENDING_SIGNAL_EXPIRY_HOURS):
                database.update_signal(signal["signal_uid"], status="EXPIRED")
                telegram_alerts.notify_expired(
                    symbol=signal["symbol"],
                    direction=direction,
                    entry=signal["entry"],
                    generated_at=signal["created_at"],
                    reason=(
                        "Naive time-based expiry window elapsed "
                        f"({settings.PENDING_SIGNAL_EXPIRY_HOURS}h). Note: this timer does not "
                        "yet account for weekend market closure (Stage 2)."
                    ),
                )
                changed.append({**signal, "status": "EXPIRED"})
                continue

            if _entry_reached(direction, signal["entry"], price):
                database.update_signal(
                    signal["signal_uid"],
                    status="ACTIVE",
                    activated_at=datetime.now(timezone.utc).isoformat(),
                )
                telegram_alerts.notify_active(signal["symbol"], direction, signal["entry"], price)
                changed.append({**signal, "status": "ACTIVE"})

        elif signal["status"] == "ACTIVE":
            if _target_hit(direction, signal["take_profit"], price):
                database.update_signal(
                    signal["signal_uid"],
                    status="TARGET_HIT",
                    exit_at=datetime.now(timezone.utc).isoformat(),
                    exit_price=price,
                    result="WIN",
                    profit_loss=signal.get("potential_profit"),
                )
                telegram_alerts.notify_target_hit(
                    signal["symbol"], direction, price, signal.get("potential_profit") or 0.0
                )
                changed.append({**signal, "status": "TARGET_HIT"})
            elif _stop_hit(direction, signal["stop_loss"], price):
                loss = signal.get("risk_amount") or 0.0
                database.update_signal(
                    signal["signal_uid"],
                    status="STOP_LOSS_HIT",
                    exit_at=datetime.now(timezone.utc).isoformat(),
                    exit_price=price,
                    result="LOSS",
                    profit_loss=-loss,
                )
                telegram_alerts.notify_stop_hit(signal["symbol"], direction, price, loss)
                changed.append({**signal, "status": "STOP_LOSS_HIT"})

    return changed
