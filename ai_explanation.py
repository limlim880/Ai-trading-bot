"""
ai_explanation.py

Deterministic, template-based explanation builder. This is NOT an LLM call
(that's Stage 12, and per the spec it must only be added once the
quantitative system is reliable, and must never be allowed to invent
prices/indicators/news/probabilities).

Every number in the generated text is read directly from the structured
data passed in -- nothing here is inferred or guessed. That's what keeps
this module safe to swap for a real AI layer later: the contract ("here is
the structured data, produce human-readable prose from exactly this") stays
the same.
"""

from __future__ import annotations


def build_setup_explanation(
    symbol: str,
    direction: str,
    score: int,
    score_breakdown: dict[str, int],
    risk_report: dict,
    trend_4h: str,
    rsi_1h: float,
) -> str:
    rr = risk_report["risk_reward"]
    potential_loss = risk_report["potential_loss"]
    potential_profit = risk_report["potential_profit"]

    lines = [
        f"{symbol} {direction} setup qualifies.",
        f"Four-hour trend: {trend_4h}. One-hour RSI: {rsi_1h}.",
        f"Setup score: {score}/100 (not a win probability).",
        f"Risk-to-reward: 1:{rr:.2f}.",
        "",
        f"Potential planned loss if stop is hit: ${potential_loss:.2f}",
        f"Potential profit if target is reached: ${potential_profit:.2f}",
        "",
        "This is a recommendation, not an executed trade. You decide whether to take it.",
    ]
    return "\n".join(lines)


def build_rejection_explanation(symbol: str, direction: str, reasons: list[str]) -> str:
    reason_lines = "\n".join(f"- {r}" for r in reasons)
    return f"{symbol} {direction} does not qualify.\n\nReasons:\n{reason_lines}"


def build_score_disclaimer() -> str:
    return (
        "The setup score reflects how many of the strategy's quality criteria were met. "
        "It is not a probability of winning and has not yet been calibrated against "
        "historical outcomes."
    )
