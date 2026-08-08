"""
telegram_alerts.py

All outbound Telegram messaging. Every "send a notification" call in the
rest of the app goes through this module so message formatting and error
handling live in exactly one place.

If TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are not configured, calls here
log a warning and return False instead of raising -- this lets the rest of
the app (and the test suite) run without real Telegram credentials, and
means a Telegram outage never takes down webhook processing or the trade
journal.
"""

from __future__ import annotations

import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str) -> bool:
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing) -- skipping send.")
        return False

    url = TELEGRAM_API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        response = httpx.post(
            url,
            json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        # Never log the token/chat id. Only log the failure itself.
        logger.error("Telegram send failed: %s", exc)
        return False


def notify_test() -> bool:
    return send_message("Test message from your AI trading assistant. Telegram integration is working.")


def notify_setup(explanation: str) -> bool:
    return send_message(f"\U0001F4C8 <b>NEW SETUP</b>\n\n{explanation}")


def notify_rejected(symbol: str, direction: str, reasons: list[str]) -> bool:
    reason_lines = "\n".join(f"- {r}" for r in reasons)
    return send_message(
        f"❌ <b>SIGNAL REJECTED</b>\n{symbol} {direction}\n\nReasons:\n{reason_lines}"
    )


def notify_blocked(symbol: str, direction: str, reason: str) -> bool:
    return send_message(f"⛔ <b>SIGNAL BLOCKED</b>\n{symbol} {direction}\n\n{reason}")


def notify_active(symbol: str, direction: str, entry: float, price: float) -> bool:
    return send_message(
        f"▶️ <b>TRADE ACTIVE</b>\n{symbol} {direction}\nEntry: {entry}\nCurrent price: {price}"
    )


def notify_target_hit(symbol: str, direction: str, exit_price: float, potential_profit: float) -> bool:
    return send_message(
        f"✅ <b>TARGET HIT</b>\n{symbol} {direction}\nExit price: {exit_price}\n"
        f"Potential profit if this size was used: ${potential_profit:.2f}"
    )


def notify_stop_hit(symbol: str, direction: str, exit_price: float, potential_loss: float) -> bool:
    return send_message(
        f"\U0001F534 <b>STOP LOSS HIT</b>\n{symbol} {direction}\nExit price: {exit_price}\n"
        f"Planned loss: ${potential_loss:.2f}"
    )


def notify_expired(symbol: str, direction: str, entry: float, generated_at: str, reason: str) -> bool:
    return send_message(
        f"⏳ <b>SETUP EXPIRED</b>\n{symbol} {direction}\nEntry: {entry}\n"
        f"Generated: {generated_at}\nReason: {reason}"
    )


def notify_invalidated(symbol: str, direction: str, reason: str) -> bool:
    return send_message(
        f"\U0001F6AB <b>SETUP CANCELLED</b>\n{symbol} {direction} is no longer valid.\nReason:\n{reason}"
    )
