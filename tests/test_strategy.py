import strategy
from conftest import valid_buy_payload, valid_sell_payload
from models import TradingViewWebhookPayload


def test_valid_buy_passes_all_gates():
    payload = TradingViewWebhookPayload(**valid_buy_payload())
    passed, reasons = strategy.validate_buy(payload)
    assert passed is True
    assert reasons == []


def test_buy_fails_when_trend_not_bullish():
    payload = TradingViewWebhookPayload(**valid_buy_payload(trend_4h="neutral"))
    passed, reasons = strategy.validate_buy(payload)
    assert passed is False
    assert any("trend" in r.lower() for r in reasons)


def test_buy_fails_when_ema_alignment_wrong():
    payload = TradingViewWebhookPayload(**valid_buy_payload(ema20_1h=1.0800))  # now below ema50
    passed, reasons = strategy.validate_buy(payload)
    assert passed is False
    assert any("ema alignment" in r.lower() for r in reasons)


def test_buy_fails_when_rsi_below_50():
    payload = TradingViewWebhookPayload(**valid_buy_payload(rsi_1h=42.0))
    passed, reasons = strategy.validate_buy(payload)
    assert passed is False
    assert any("rsi" in r.lower() for r in reasons)


def test_buy_fails_without_confirmation_candle():
    payload = TradingViewWebhookPayload(**valid_buy_payload(confirmation_candle=False))
    passed, reasons = strategy.validate_buy(payload)
    assert passed is False
    assert any("confirmation candle" in r.lower() for r in reasons)


def test_valid_sell_passes_all_gates():
    payload = TradingViewWebhookPayload(**valid_sell_payload())
    passed, reasons = strategy.validate_sell(payload)
    assert passed is True
    assert reasons == []


def test_sell_fails_when_trend_not_bearish():
    payload = TradingViewWebhookPayload(**valid_sell_payload(trend_4h="bullish"))
    passed, reasons = strategy.validate_sell(payload)
    assert passed is False
    assert any("trend" in r.lower() for r in reasons)


def test_sell_fails_when_structure_not_lower_lows():
    payload = TradingViewWebhookPayload(
        **valid_sell_payload(market_structure="higher_high_higher_low")
    )
    passed, reasons = strategy.validate_sell(payload)
    assert passed is False
    assert any("structure" in r.lower() for r in reasons)


def test_score_signal_full_marks_for_clean_buy_setup():
    payload = TradingViewWebhookPayload(**valid_buy_payload())
    score, breakdown = strategy.score_signal(payload, risk_reward=3.0)
    assert score == 100
    assert sum(breakdown.values()) == score


def test_score_signal_partial_credit_for_unknown_support_resistance():
    payload = TradingViewWebhookPayload(**valid_buy_payload(near_support_resistance=None))
    score, breakdown = strategy.score_signal(payload, risk_reward=3.0)
    assert breakdown["support_resistance"] == 5  # half of 10
    assert score == 95


def test_score_signal_zero_rr_points_at_minimum_rr():
    payload = TradingViewWebhookPayload(**valid_buy_payload())
    score, breakdown = strategy.score_signal(payload, risk_reward=2.0)
    assert breakdown["risk_reward"] == 0
