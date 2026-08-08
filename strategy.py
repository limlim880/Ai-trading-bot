"""
strategy.py

The "Four-Hour Trend Pullback Strategy": hard-gate validation (a setup
either meets the BUY/SELL logic or it doesn't) plus a separate 100-point
quality score used for ranking/display (Stage 8, Stage 13 watchlist).

Design choice: validation and scoring are deliberately separate.
- validate_buy()/validate_sell() answer "does this even qualify as a real
  setup under our rules?" -- a yes/no gate.
- score_signal() answers "how good is this qualifying setup, relative to
  other qualifying setups?" -- a 0-100 quality number.
A setup that fails validation is REJECTED regardless of its score. A score
is NEVER a probability of winning -- see ai_explanation.py and README for
that disclaimer, it must always accompany any displayed score.

News and spread are intentionally NOT part of either function in this
module. Per the project's core safety requirement, those two gates must be
computed independently by Python (Stage 5 / Stage 6), not trusted from the
TradingView payload. app.py applies them as a separate, later gate.
"""

from __future__ import annotations

from models import Direction, MarketStructure, TradingViewWebhookPayload

SCORE_WEIGHTS = {
    "trend_4h": 15,
    "market_structure": 15,
    "ema_alignment": 15,
    "pullback_quality": 15,
    "rsi_confirmation": 10,
    "confirmation_candle": 10,
    "support_resistance": 10,
    "risk_reward": 10,
}
assert sum(SCORE_WEIGHTS.values()) == 100


def validate_buy(p: TradingViewWebhookPayload) -> tuple[bool, list[str]]:
    """BUY LOGIC gate, straight from the spec."""
    reasons: list[str] = []

    if p.trend_4h != "bullish":
        reasons.append("4-hour trend is not bullish.")
    if not (p.price > (p.ema200_4h if p.ema200_4h is not None else p.ema200_1h)):
        reasons.append("Price is not above the 200 EMA.")
    if not (p.ema20_1h > p.ema50_1h > p.ema200_1h):
        reasons.append("EMA alignment failed: need 20 EMA > 50 EMA > 200 EMA.")
    if p.market_structure != MarketStructure.higher_high_higher_low:
        reasons.append("Market structure does not show higher-highs/higher-lows.")
    if not p.pullback_to_ema:
        reasons.append("Price has not pulled back to the 20/50 EMA.")
    if p.rsi_1h < 50:
        reasons.append(f"RSI has not recovered above/around 50 (got {p.rsi_1h}).")
    if not p.confirmation_candle:
        reasons.append("No bullish confirmation candle has closed.")

    return (len(reasons) == 0, reasons)


def validate_sell(p: TradingViewWebhookPayload) -> tuple[bool, list[str]]:
    """SELL LOGIC gate -- mirror image of the BUY conditions."""
    reasons: list[str] = []

    if p.trend_4h != "bearish":
        reasons.append("4-hour trend is not bearish.")
    if not (p.price < (p.ema200_4h if p.ema200_4h is not None else p.ema200_1h)):
        reasons.append("Price is not below the 200 EMA.")
    if not (p.ema20_1h < p.ema50_1h < p.ema200_1h):
        reasons.append("EMA alignment failed: need 20 EMA < 50 EMA < 200 EMA.")
    if p.market_structure != MarketStructure.lower_high_lower_low:
        reasons.append("Market structure does not show lower-highs/lower-lows.")
    if not p.pullback_to_ema:
        reasons.append("Price has not pulled back to the 20/50 EMA.")
    if p.rsi_1h > 50:
        reasons.append(f"RSI has not dropped back below/around 50 (got {p.rsi_1h}).")
    if not p.confirmation_candle:
        reasons.append("No bearish confirmation candle has closed.")

    return (len(reasons) == 0, reasons)


def validate_direction(p: TradingViewWebhookPayload) -> tuple[bool, list[str]]:
    if p.direction == Direction.BUY:
        return validate_buy(p)
    return validate_sell(p)


def score_signal(p: TradingViewWebhookPayload, risk_reward: float) -> tuple[int, dict[str, int]]:
    """0-100 quality score. Assumes the setup has already passed
    validate_direction() -- this only differentiates *how well* it qualifies.
    """
    breakdown: dict[str, int] = {}
    is_buy = p.direction == Direction.BUY

    # Trend alignment: full marks if trend + price-vs-200EMA agree cleanly.
    trend_ok = (p.trend_4h == "bullish") if is_buy else (p.trend_4h == "bearish")
    breakdown["trend_4h"] = SCORE_WEIGHTS["trend_4h"] if trend_ok else 0

    # Market structure
    structure_ok = (
        p.market_structure == MarketStructure.higher_high_higher_low
        if is_buy
        else p.market_structure == MarketStructure.lower_high_lower_low
    )
    breakdown["market_structure"] = SCORE_WEIGHTS["market_structure"] if structure_ok else 0

    # EMA alignment
    ema_ok = (p.ema20_1h > p.ema50_1h > p.ema200_1h) if is_buy else (p.ema20_1h < p.ema50_1h < p.ema200_1h)
    breakdown["ema_alignment"] = SCORE_WEIGHTS["ema_alignment"] if ema_ok else 0

    # Pullback quality: full marks for a clean pullback into the zone.
    breakdown["pullback_quality"] = SCORE_WEIGHTS["pullback_quality"] if p.pullback_to_ema else 0

    # RSI confirmation: full marks close to 50-60 (buy) / 40-50 (sell),
    # scaled down the further RSI sits from that zone.
    if is_buy:
        rsi_points = SCORE_WEIGHTS["rsi_confirmation"] if p.rsi_1h >= 50 else max(
            0, SCORE_WEIGHTS["rsi_confirmation"] - int((50 - p.rsi_1h))
        )
    else:
        rsi_points = SCORE_WEIGHTS["rsi_confirmation"] if p.rsi_1h <= 50 else max(
            0, SCORE_WEIGHTS["rsi_confirmation"] - int((p.rsi_1h - 50))
        )
    breakdown["rsi_confirmation"] = max(0, min(SCORE_WEIGHTS["rsi_confirmation"], rsi_points))

    # Confirmation candle
    breakdown["confirmation_candle"] = SCORE_WEIGHTS["confirmation_candle"] if p.confirmation_candle else 0

    # Support/resistance: this field is optional (Python doesn't
    # independently verify S/R until Stage 7). Give half credit ("unknown")
    # when the field wasn't supplied, rather than pretending it's confirmed.
    if p.near_support_resistance is None:
        breakdown["support_resistance"] = SCORE_WEIGHTS["support_resistance"] // 2
    else:
        breakdown["support_resistance"] = (
            SCORE_WEIGHTS["support_resistance"] if p.near_support_resistance else 0
        )

    # Risk:reward -- full marks at 3:1 or better, scaled down to 0 at 2:1
    # (the hard minimum enforced elsewhere).
    if risk_reward >= 3.0:
        rr_points = SCORE_WEIGHTS["risk_reward"]
    elif risk_reward <= 2.0:
        rr_points = 0
    else:
        rr_points = round(SCORE_WEIGHTS["risk_reward"] * (risk_reward - 2.0))
    breakdown["risk_reward"] = max(0, min(SCORE_WEIGHTS["risk_reward"], rr_points))

    score = sum(breakdown.values())
    return score, breakdown
