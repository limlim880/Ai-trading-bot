"""
models.py

Pydantic schemas for everything that crosses a boundary in this system:
- inbound TradingView webhook payloads
- inbound price-update payloads
- outbound / internal representations used by strategy, risk and the DB layer

Keeping these in one file makes it easy to see exactly what data the system
trusts as input, which matters a lot given the "don't trust TradingView's
news/spread flags" requirement.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TrendState(str, Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class MarketStructure(str, Enum):
    higher_high_higher_low = "higher_high_higher_low"
    lower_high_lower_low = "lower_high_lower_low"
    mixed = "mixed"
    unclear = "unclear"


class SignalStatus(str, Enum):
    ALERT_SENT = "ALERT_SENT"
    ACTIVE = "ACTIVE"
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class TradingViewWebhookPayload(BaseModel):
    """What the Pine Script alert is expected to send.

    IMPORTANT: `high_impact_news_nearby` and `spread_normal` are accepted
    here but are NOT trusted as gating decisions anywhere in this codebase.
    They are stored for reference only until Stage 5 (economic calendar)
    and Stage 6 (real spread verification) give Python its own independent
    checks. See strategy.py / app.py for where this is enforced.
    """

    secret: str

    symbol: str
    direction: Direction

    timeframe_trend: str = "4H"
    timeframe_setup: str = "1H"

    price: float = Field(gt=0, description="Price at the moment the alert fired")
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)

    ema20_1h: float
    ema50_1h: float
    ema200_1h: float
    ema20_4h: Optional[float] = None
    ema50_4h: Optional[float] = None
    ema200_4h: Optional[float] = None

    rsi_1h: float = Field(ge=0, le=100)
    atr_1h: float = Field(ge=0)

    trend_4h: TrendState
    market_structure: MarketStructure
    pullback_to_ema: bool
    confirmation_candle: bool
    near_support_resistance: Optional[bool] = None

    # Untrusted placeholders -- see docstring above.
    high_impact_news_nearby: bool = False
    spread_normal: bool = True

    timestamp: str = Field(description="ISO-8601 timestamp set by TradingView")

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def _parse_timestamp(cls, v: str) -> str:
        # Raises a clear validation error if TradingView ever sends a
        # malformed timestamp, instead of failing later in a confusing way.
        _ = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class PriceUpdatePayload(BaseModel):
    """Payload for POST /price-update -- used to drive trade monitoring."""

    secret: str
    symbol: str
    price: float = Field(gt=0)
    bid: Optional[float] = Field(default=None, gt=0)
    ask: Optional[float] = Field(default=None, gt=0)
    timestamp: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.strip().upper()


class SignalEvaluation(BaseModel):
    """Result of running strategy + risk logic over a webhook payload."""

    qualifies: bool
    score: int
    score_breakdown: dict[str, int]
    hard_gate_reasons: list[str]        # reasons a BUY/SELL condition failed
    rejection_reasons: list[str]        # full set of reasons it was rejected
    risk_report: dict
