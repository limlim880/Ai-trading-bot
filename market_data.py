"""
Market-data placeholder.

Version 1 receives calculated values from TradingView. This keeps the first
build simple and avoids connecting the app to a live broker account.

Later, this file can fetch and independently verify prices from a broker or
authorised market-data provider.
"""


def get_latest_market_price(symbol: str) -> float:
    raise NotImplementedError(
        f"Live market data is not connected yet for {symbol}."
    )
