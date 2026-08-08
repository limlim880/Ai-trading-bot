from models import RiskResult


def calculate_trade_risk(
    account_balance: float,
    risk_percent: float,
    entry: float,
    stop_loss: float,
    take_profit: float,
    pip_size: float,
    pip_value_per_standard_lot: float,
) -> RiskResult:
    if account_balance <= 0:
        raise ValueError("Account balance must be greater than zero.")
    if not 0 < risk_percent <= 5:
        raise ValueError("Risk percent must be greater than zero and no more than 5%.")
    if pip_size <= 0 or pip_value_per_standard_lot <= 0:
        raise ValueError("Pip values must be greater than zero.")

    risk_amount = account_balance * (risk_percent / 100)

    stop_distance_price = abs(entry - stop_loss)
    target_distance_price = abs(take_profit - entry)

    if stop_distance_price == 0:
        raise ValueError("Entry and stop-loss cannot be the same.")

    stop_distance_pips = stop_distance_price / pip_size
    target_distance_pips = target_distance_price / pip_size
    risk_reward_ratio = target_distance_pips / stop_distance_pips

    position_size_lots = risk_amount / (
        stop_distance_pips * pip_value_per_standard_lot
    )

    potential_profit = (
        target_distance_pips
        * pip_value_per_standard_lot
        * position_size_lots
    )

    return RiskResult(
        account_balance=round(account_balance, 2),
        risk_percent=round(risk_percent, 3),
        risk_amount=round(risk_amount, 2),
        stop_distance_price=round(stop_distance_price, 6),
        stop_distance_pips=round(stop_distance_pips, 1),
        target_distance_pips=round(target_distance_pips, 1),
        risk_reward_ratio=round(risk_reward_ratio, 2),
        position_size_lots=round(position_size_lots, 3),
        potential_profit=round(potential_profit, 2),
    )
