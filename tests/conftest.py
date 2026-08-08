import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point DATABASE_PATH at a throwaway file for this test, and clear the
    cached Settings singleton so the new env var actually takes effect."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")

    import config

    config.get_settings.cache_clear()

    import database

    database.init_db()
    yield db_path
    config.get_settings.cache_clear()


def valid_buy_payload(**overrides) -> dict:
    payload = {
        "secret": "test-secret",
        "symbol": "eurusd",
        "direction": "BUY",
        "timeframe_trend": "4H",
        "timeframe_setup": "1H",
        "price": 1.0855,
        "entry": 1.0855,
        "stop_loss": 1.0830,
        "take_profit": 1.0915,
        "ema20_1h": 1.0851,
        "ema50_1h": 1.0842,
        "ema200_1h": 1.0810,
        "ema20_4h": 1.0848,
        "ema50_4h": 1.0820,
        "ema200_4h": 1.0790,
        "rsi_1h": 54.2,
        "atr_1h": 0.0012,
        "trend_4h": "bullish",
        "market_structure": "higher_high_higher_low",
        "pullback_to_ema": True,
        "confirmation_candle": True,
        "near_support_resistance": True,
        "high_impact_news_nearby": False,
        "spread_normal": True,
        "timestamp": "2026-08-08T12:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def valid_sell_payload(**overrides) -> dict:
    payload = {
        "secret": "test-secret",
        "symbol": "eurusd",
        "direction": "SELL",
        "timeframe_trend": "4H",
        "timeframe_setup": "1H",
        "price": 1.0800,
        "entry": 1.0800,
        "stop_loss": 1.0825,
        "take_profit": 1.0740,
        "ema20_1h": 1.0805,
        "ema50_1h": 1.0815,
        "ema200_1h": 1.0850,
        "ema20_4h": 1.0810,
        "ema50_4h": 1.0830,
        "ema200_4h": 1.0870,
        "rsi_1h": 46.0,
        "atr_1h": 0.0012,
        "trend_4h": "bearish",
        "market_structure": "lower_high_lower_low",
        "pullback_to_ema": True,
        "confirmation_candle": True,
        "near_support_resistance": True,
        "high_impact_news_nearby": False,
        "spread_normal": True,
        "timestamp": "2026-08-08T12:00:00+00:00",
    }
    payload.update(overrides)
    return payload
