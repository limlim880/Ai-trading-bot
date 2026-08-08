import database


def test_insert_and_get_signal(temp_db):
    uid = database.insert_signal(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry": 1.0855,
            "stop_loss": 1.0830,
            "take_profit": 1.0915,
            "score": 90,
            "score_breakdown": {"trend_4h": 15},
            "rejection_reasons": [],
        }
    )
    record = database.get_signal(uid)
    assert record is not None
    assert record["symbol"] == "EURUSD"
    assert record["status"] == "ALERT_SENT"
    assert record["score_breakdown"] == {"trend_4h": 15}


def test_has_active_duplicate_blocks_second_alert_sent_signal(temp_db):
    database.insert_signal(
        {"symbol": "EURUSD", "direction": "BUY", "entry": 1.0, "stop_loss": 0.99, "take_profit": 1.02}
    )
    assert database.has_active_duplicate("EURUSD", "BUY") is True


def test_has_active_duplicate_ignores_other_direction(temp_db):
    database.insert_signal(
        {"symbol": "EURUSD", "direction": "BUY", "entry": 1.0, "stop_loss": 0.99, "take_profit": 1.02}
    )
    assert database.has_active_duplicate("EURUSD", "SELL") is False


def test_has_active_duplicate_ignores_terminal_status(temp_db):
    uid = database.insert_signal(
        {"symbol": "EURUSD", "direction": "BUY", "entry": 1.0, "stop_loss": 0.99, "take_profit": 1.02}
    )
    database.update_signal(uid, status="TARGET_HIT")
    assert database.has_active_duplicate("EURUSD", "BUY") is False


def test_update_signal_status(temp_db):
    uid = database.insert_signal(
        {"symbol": "GBPUSD", "direction": "SELL", "entry": 1.3, "stop_loss": 1.31, "take_profit": 1.28}
    )
    database.update_signal(uid, status="ACTIVE", activated_at="2026-08-08T13:00:00+00:00")
    record = database.get_signal(uid)
    assert record["status"] == "ACTIVE"
    assert record["activated_at"] == "2026-08-08T13:00:00+00:00"


def test_get_active_signals_only_returns_non_terminal(temp_db):
    database.insert_signal(
        {"symbol": "EURUSD", "direction": "BUY", "entry": 1.0, "stop_loss": 0.99, "take_profit": 1.02}
    )
    closed_uid = database.insert_signal(
        {"symbol": "GBPUSD", "direction": "BUY", "entry": 1.3, "stop_loss": 1.29, "take_profit": 1.32}
    )
    database.update_signal(closed_uid, status="EXPIRED")

    active = database.get_active_signals()
    assert len(active) == 1
    assert active[0]["symbol"] == "EURUSD"
