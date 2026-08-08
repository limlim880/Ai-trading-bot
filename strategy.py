from config import settings
from models import SignalEvaluation, TradingViewSignal


APPROVED_SYMBOLS = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD"}


def evaluate_signal(signal: TradingViewSignal) -> SignalEvaluation:
    score = 0
    positive_reasons: list[str] = []
    rejection_reasons: list[str] = []

    if signal.symbol not in APPROVED_SYMBOLS:
        rejection_reasons.append(
            f"{signal.symbol} is not currently on the approved market list."
        )

    trend_matches = (
        signal.direction == "BUY"
        and signal.higher_timeframe_trend == "BULLISH"
    ) or (
        signal.direction == "SELL"
        and signal.higher_timeframe_trend == "BEARISH"
    )

    if trend_matches:
        score += 15
        positive_reasons.append("The higher-timeframe trend matches the trade direction.")
    else:
        rejection_reasons.append("The higher-timeframe trend does not match the trade.")

    if signal.direction == "BUY":
        ema_alignment = signal.ema_20 > signal.ema_50 > signal.ema_200
        rsi_confirmed = signal.rsi >= 50
    else:
        ema_alignment = signal.ema_20 < signal.ema_50 < signal.ema_200
        rsi_confirmed = signal.rsi <= 50

    if ema_alignment:
        score += 15
        positive_reasons.append("The 20, 50 and 200 EMAs are correctly aligned.")
    else:
        rejection_reasons.append("The moving averages are not correctly aligned.")

    if signal.market_structure_confirmed:
        score += 15
        positive_reasons.append("Market structure supports the trade.")
    else:
        rejection_reasons.append("Market structure is not confirmed.")

    if signal.support_resistance_confirmed:
        score += 10
        positive_reasons.append("Support or resistance confirms the setup.")
    else:
        rejection_reasons.append("Support or resistance confirmation is missing.")

    if rsi_confirmed:
        score += 10
        positive_reasons.append("RSI supports the direction.")
    else:
        rejection_reasons.append("RSI does not confirm the direction.")

    if signal.confirmation_candle:
        score += 10
        positive_reasons.append("A confirmation candle has closed.")
    else:
        rejection_reasons.append("No valid confirmation candle has closed.")

    if signal.spread_normal:
        score += 5
        positive_reasons.append("The spread is within the permitted range.")
    else:
        rejection_reasons.append("The spread is unusually high.")

    if not signal.high_impact_news_nearby:
        score += 5
        positive_reasons.append("No nearby high-impact news restriction was reported.")
    else:
        rejection_reasons.append("High-impact news is too close to the proposed entry.")

    stop_distance = abs(signal.entry - signal.stop_loss)
    target_distance = abs(signal.take_profit - signal.entry)
    risk_reward = target_distance / stop_distance if stop_distance else 0

    if round(risk_reward, 2) >= 2:
        score += 15
        positive_reasons.append(
            f"The risk-to-reward ratio is acceptable at approximately 1:{risk_reward:.2f}."
        )
    else:
        rejection_reasons.append(
            f"The risk-to-reward ratio is only 1:{risk_reward:.2f}, below the 1:2 minimum."
        )

    hard_rejection = (
        signal.symbol not in APPROVED_SYMBOLS
        or not trend_matches
        or not ema_alignment
        or not signal.market_structure_confirmed
        or not signal.confirmation_candle
        or signal.high_impact_news_nearby
        or not signal.spread_normal
        or round(risk_reward, 2) < 2
    )

    accepted = score >= settings.minimum_signal_score and not hard_rejection

    return SignalEvaluation(
        accepted=accepted,
        score=score,
        positive_reasons=positive_reasons,
        rejection_reasons=rejection_reasons,
    )
