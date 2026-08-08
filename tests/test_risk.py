import risk


def test_risk_reward_calculation():
    rr = risk.calculate_risk_reward(entry=1.0855, stop_loss=1.0830, take_profit=1.0915)
    # stop distance = 0.0025, target distance = 0.0060 -> rr = 2.4
    assert round(rr, 2) == 2.4


def test_risk_reward_zero_stop_distance_is_safe():
    rr = risk.calculate_risk_reward(entry=1.0855, stop_loss=1.0855, take_profit=1.0915)
    assert rr == 0.0


def test_build_risk_report_position_sizing():
    report = risk.build_risk_report(
        entry=1.0855, stop_loss=1.0830, take_profit=1.0915,
        account_balance=10_000, risk_percent=0.5,
    )
    assert report.risk_amount == 50.0  # 0.5% of 10,000
    assert report.stop_distance == round(0.0025, 6)
    assert report.risk_reward == 2.4
    # position_size = risk_amount / stop_distance = 50 / 0.0025 = 20000
    assert report.position_size == 20_000.0
    # potential_profit = position_size * target_distance = 20000 * 0.006 = 120
    assert report.potential_profit == 120.0
    assert report.potential_loss == 50.0


def test_build_risk_report_degenerate_stop_returns_zeroes():
    report = risk.build_risk_report(
        entry=1.0855, stop_loss=1.0855, take_profit=1.0915,
        account_balance=10_000, risk_percent=0.5,
    )
    assert report.position_size == 0.0
    assert report.risk_reward == 0.0


def test_portfolio_risk_gates_pass():
    ok, reasons = risk.check_portfolio_risk_gates(
        open_trades_count=1,
        daily_loss_percent_used=0.2,
        weekly_loss_percent_used=0.5,
        max_concurrent_trades=2,
        max_daily_loss_percent=1.0,
        max_weekly_loss_percent=3.0,
    )
    assert ok is True
    assert reasons == []


def test_portfolio_risk_gates_blocks_on_max_concurrent_trades():
    ok, reasons = risk.check_portfolio_risk_gates(
        open_trades_count=2,
        daily_loss_percent_used=0.0,
        weekly_loss_percent_used=0.0,
        max_concurrent_trades=2,
        max_daily_loss_percent=1.0,
        max_weekly_loss_percent=3.0,
    )
    assert ok is False
    assert "concurrent" in reasons[0].lower()


def test_portfolio_risk_gates_blocks_on_daily_loss():
    ok, reasons = risk.check_portfolio_risk_gates(
        open_trades_count=0,
        daily_loss_percent_used=1.0,
        weekly_loss_percent_used=0.0,
        max_concurrent_trades=2,
        max_daily_loss_percent=1.0,
        max_weekly_loss_percent=3.0,
    )
    assert ok is False
    assert any("daily loss" in r.lower() for r in reasons)
