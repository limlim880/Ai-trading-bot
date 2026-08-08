"""
risk.py

Position sizing and risk/reward math, plus the account-level risk gates
(max concurrent trades, max daily/weekly loss).

KNOWN SIMPLIFICATION: position size is computed as
    risk_amount / stop_distance
which treats 1 unit of the traded instrument's price move as 1 unit of
account currency. This is exactly correct when your account currency is
the same as the pair's quote currency (e.g. a USD account trading
EURUSD/GBPUSD/AUDUSD, where the quote currency is USD). It is NOT accurate
for pairs like USDJPY on a USD account, or for any pair where account
currency != quote currency, because that needs a pip-value conversion
through the current cross rate. This is intentionally left simple for the
baseline system and must be revisited in Stage 6/7 once real broker/market
data is wired in. Every risk report this module returns is clearly labeled
as "planned"/"potential" for that reason -- never treat these numbers as
broker-guaranteed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


def calculate_stop_distance(entry: float, stop_loss: float) -> float:
    return abs(entry - stop_loss)


def calculate_target_distance(entry: float, take_profit: float) -> float:
    return abs(take_profit - entry)


def calculate_risk_reward(entry: float, stop_loss: float, take_profit: float) -> float:
    """Reward:risk ratio, e.g. 2.0 means "1:2"."""
    stop_distance = calculate_stop_distance(entry, stop_loss)
    if stop_distance == 0:
        return 0.0
    target_distance = calculate_target_distance(entry, take_profit)
    return round(target_distance / stop_distance, 4)


@dataclass
class RiskReport:
    account_balance: float
    risk_percent: float
    risk_amount: float           # maximum planned loss in account currency
    stop_distance: float
    target_distance: float
    risk_reward: float
    position_size: float         # units, see module docstring for caveat
    potential_profit: float      # if target is reached
    potential_loss: float        # if stop is hit (== risk_amount)

    def to_dict(self) -> dict:
        return asdict(self)


def build_risk_report(
    entry: float,
    stop_loss: float,
    take_profit: float,
    account_balance: float,
    risk_percent: float,
) -> RiskReport:
    stop_distance = calculate_stop_distance(entry, stop_loss)
    target_distance = calculate_target_distance(entry, take_profit)
    risk_amount = round(account_balance * (risk_percent / 100.0), 2)

    if stop_distance <= 0:
        # Degenerate input (entry == stop). Return a zeroed-out report
        # rather than dividing by zero -- the caller (strategy/app) is
        # responsible for rejecting a signal with an invalid stop.
        return RiskReport(
            account_balance=account_balance,
            risk_percent=risk_percent,
            risk_amount=risk_amount,
            stop_distance=0.0,
            target_distance=target_distance,
            risk_reward=0.0,
            position_size=0.0,
            potential_profit=0.0,
            potential_loss=0.0,
        )

    position_size = round(risk_amount / stop_distance, 4)
    potential_profit = round(position_size * target_distance, 2)
    rr = calculate_risk_reward(entry, stop_loss, take_profit)

    return RiskReport(
        account_balance=account_balance,
        risk_percent=risk_percent,
        risk_amount=risk_amount,
        stop_distance=round(stop_distance, 6),
        target_distance=round(target_distance, 6),
        risk_reward=rr,
        position_size=position_size,
        potential_profit=potential_profit,
        potential_loss=risk_amount,
    )


def check_portfolio_risk_gates(
    open_trades_count: int,
    daily_loss_percent_used: float,
    weekly_loss_percent_used: float,
    max_concurrent_trades: int,
    max_daily_loss_percent: float,
    max_weekly_loss_percent: float,
) -> tuple[bool, list[str]]:
    """Account-level safety gates. These apply regardless of how good an
    individual setup looks -- per the spec's "no trade recommendation when
    safety gates fail" rule.
    """
    reasons: list[str] = []

    if open_trades_count >= max_concurrent_trades:
        reasons.append(
            f"Maximum concurrent trades reached ({open_trades_count}/{max_concurrent_trades})."
        )
    if daily_loss_percent_used >= max_daily_loss_percent:
        reasons.append(
            f"Daily loss limit reached ({daily_loss_percent_used:.2f}%/{max_daily_loss_percent:.2f}%)."
        )
    if weekly_loss_percent_used >= max_weekly_loss_percent:
        reasons.append(
            f"Weekly loss limit reached ({weekly_loss_percent_used:.2f}%/{max_weekly_loss_percent:.2f}%)."
        )

    return (len(reasons) == 0, reasons)
