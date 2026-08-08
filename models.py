from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


Direction = Literal["BUY", "SELL"]


class TradingViewSignal(BaseModel):
    secret: str
    symbol: str = Field(min_length=3, max_length=20)
    timeframe: str = Field(default="60", min_length=1, max_length=10)
    direction: Direction

    current_price: float = Field(gt=0)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)

    ema_20: float = Field(gt=0)
    ema_50: float = Field(gt=0)
    ema_200: float = Field(gt=0)
    rsi: float = Field(ge=0, le=100)
    atr: float = Field(gt=0)

    higher_timeframe_trend: Literal["BULLISH", "BEARISH", "SIDEWAYS"]
    confirmation_candle: bool
    market_structure_confirmed: bool
    support_resistance_confirmed: bool
    high_impact_news_nearby: bool = False
    spread_normal: bool = True

    pip_size: float = Field(default=0.0001, gt=0)
    pip_value_per_standard_lot: float = Field(default=10.0, gt=0)

    strategy_name: str = "Four-Hour Trend Pullback"
    note: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalise_symbol(cls, value: str) -> str:
        return value.replace("/", "").replace(" ", "").upper()

    @model_validator(mode="after")
    def validate_trade_levels(self):
        if self.direction == "BUY":
            if not self.stop_loss < self.entry < self.take_profit:
                raise ValueError(
                    "For a BUY signal, stop_loss must be below entry and "
                    "take_profit must be above entry."
                )
        else:
            if not self.take_profit < self.entry < self.stop_loss:
                raise ValueError(
                    "For a SELL signal, take_profit must be below entry and "
                    "stop_loss must be above entry."
                )
        return self


class SignalEvaluation(BaseModel):
    accepted: bool
    score: int
    positive_reasons: list[str]
    rejection_reasons: list[str]


class RiskResult(BaseModel):
    account_balance: float
    risk_percent: float
    risk_amount: float
    stop_distance_price: float
    stop_distance_pips: float
    target_distance_pips: float
    risk_reward_ratio: float
    position_size_lots: float
    potential_profit: float

class PriceUpdate(BaseModel):
    secret: str
    symbol: str
    current_price: float = Field(gt=0)

    @field_validator("symbol")
    @classmethod
    def normalise_price_symbol(cls, value: str) -> str:
        return value.replace("/", "").replace(" ", "").upper()