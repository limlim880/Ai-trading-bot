from datetime import datetime, timedelta, timezone

from config import settings
from database import get_open_signals, update_signal_status
from telegram_alerts import send_telegram_message


def _market_closed(dt: datetime) -> bool:
    """Rough FX weekend closure: Friday 21:00 UTC to Sunday 21:00 UTC."""
    weekday = dt.weekday()  # Monday = 0 ... Sunday = 6
    if weekday == 5:
        return True
    if weekday == 4 and dt.hour >= 21:
        return True
    if weekday == 6 and dt.hour < 21:
        return True
    return False


def _trading_hours_elapsed(start: datetime, end: datetime) -> float:
    """Hours elapsed between start and end, excluding weekend closure."""
    if end <= start:
        return 0.0

    hours = 0.0
    cursor = start
    while cursor < end:
        step = min(timedelta(hours=1), end - cursor)
        midpoint = cursor + step / 2
        if not _market_closed(midpoint):
            hours += step.total_seconds() / 3600
        cursor += step
    return hours


def check_trade(symbol: str, current_price: float):
    open_signals = get_open_signals()
    now = datetime.now(timezone.utc)

    for trade in open_signals:
        if trade["symbol"] != symbol:
            continue

        trade_id = trade["id"]
        direction = trade["direction"]
        entry = trade["entry"]
        stop_loss = trade["stop_loss"]
        take_profit = trade["take_profit"]
        status = trade["status"]

        if status == "ALERT_SENT":
            created_at = datetime.fromisoformat(trade["created_at"])
            hours_pending = _trading_hours_elapsed(created_at, now)

            if hours_pending >= settings.pending_signal_expiry_hours:
                update_signal_status(
                    trade_id,
                    status="EXPIRED",
                    result="NO_ENTRY",
                )

                send_telegram_message(
                    f"⚫ SETUP EXPIRED\n\n"
                    f"{symbol} {direction}\n"
                    f"Entry ({entry}) was never reached within "
                    f"{settings.pending_signal_expiry_hours} trading hours "
                    f"of the alert. No longer being monitored."
                )
                continue

        if direction == "BUY":

            if status == "ALERT_SENT":
                if current_price >= entry:
                    status = "ACTIVE"
                    update_signal_status(trade_id, status="ACTIVE")

                    send_telegram_message(
                        f"🟢 TRADE ACTIVE\n\n"
                        f"{symbol} BUY\n"
                        f"Entry reached: {entry}\n"
                        f"Current price: {current_price}\n\n"
                        f"The trade is now being monitored."
                    )
                elif current_price <= stop_loss:
                    # Price never reached entry, so no position was ever
                    # opened. This is a setup that failed to play out, not
                    # a realised loss.
                    update_signal_status(
                        trade_id,
                        status="INVALIDATED",
                        result="NO_ENTRY",
                        exit_price=current_price,
                    )

                    send_telegram_message(
                        f"⚪ SETUP INVALIDATED\n\n"
                        f"{symbol} BUY\n"
                        f"Entry was never reached before price hit the "
                        f"stop-loss level ({stop_loss}).\n"
                        f"Current price: {current_price}"
                    )
                    continue

            if status == "ACTIVE":
                if current_price <= stop_loss:
                    update_signal_status(
                        trade_id,
                        status="STOP_LOSS_HIT",
                        result="LOSS",
                        exit_price=current_price,
                    )

                    send_telegram_message(
                        f"🔴 STOP LOSS HIT\n\n"
                        f"{symbol} BUY\n"
                        f"Stop-loss: {stop_loss}\n"
                        f"Current price: {current_price}"
                    )

                elif current_price >= take_profit:
                    update_signal_status(
                        trade_id,
                        status="TARGET_HIT",
                        result="WIN",
                        exit_price=current_price,
                    )

                    send_telegram_message(
                        f"✅ TARGET HIT\n\n"
                        f"{symbol} BUY\n"
                        f"Target: {take_profit}\n"
                        f"Current price: {current_price}"
                    )

        if direction == "SELL":

            if status == "ALERT_SENT":
                if current_price <= entry:
                    status = "ACTIVE"
                    update_signal_status(trade_id, status="ACTIVE")

                    send_telegram_message(
                        f"🔴 TRADE ACTIVE\n\n"
                        f"{symbol} SELL\n"
                        f"Entry reached: {entry}\n"
                        f"Current price: {current_price}\n\n"
                        f"The trade is now being monitored."
                    )
                elif current_price >= stop_loss:
                    update_signal_status(
                        trade_id,
                        status="INVALIDATED",
                        result="NO_ENTRY",
                        exit_price=current_price,
                    )

                    send_telegram_message(
                        f"⚪ SETUP INVALIDATED\n\n"
                        f"{symbol} SELL\n"
                        f"Entry was never reached before price hit the "
                        f"stop-loss level ({stop_loss}).\n"
                        f"Current price: {current_price}"
                    )
                    continue

            if status == "ACTIVE":
                if current_price >= stop_loss:
                    update_signal_status(
                        trade_id,
                        status="STOP_LOSS_HIT",
                        result="LOSS",
                        exit_price=current_price,
                    )

                    send_telegram_message(
                        f"🔴 STOP LOSS HIT\n\n"
                        f"{symbol} SELL\n"
                        f"Stop-loss: {stop_loss}\n"
                        f"Current price: {current_price}"
                    )

                elif current_price <= take_profit:
                    update_signal_status(
                        trade_id,
                        status="TARGET_HIT",
                        result="WIN",
                        exit_price=current_price,
                    )

                    send_telegram_message(
                        f"✅ TARGET HIT\n\n"
                        f"{symbol} SELL\n"
                        f"Target: {take_profit}\n"
                        f"Current price: {current_price}"
                    )