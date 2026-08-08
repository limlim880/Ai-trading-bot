"""
market_data.py

Baseline market-data store: right now this is only "the latest price
TradingView/you told us about via POST /price-update", persisted in
SQLite so it survives a restart.

This module is intentionally thin. Stage 7 ("Independent Market-Data
Verification") replaces/extends it with Python independently fetching
candles from a real market-data provider and computing its own EMA/RSI/
ATR/trend, so TradingView stops being the sole source of truth. Keeping
this as its own module now (instead of inlining price storage in app.py)
means that upgrade won't require touching app.py's routing logic.
"""

from __future__ import annotations

from typing import Optional

import database


def update_price(symbol: str, price: float, bid: Optional[float] = None, ask: Optional[float] = None) -> None:
    database.upsert_latest_price(symbol.upper(), price, bid, ask)


def get_latest_price(symbol: str) -> Optional[dict]:
    return database.get_latest_price(symbol.upper())
