# tests/test_trader.py
from unittest.mock import MagicMock
from src.trader import calculate_dest_trades, execute_trades

TRADES = [
    {"symbol": "MSFT", "action": "BUY",  "pct_of_portfolio": 0.08, "confirmed": True, "source": "both"},
    {"symbol": "TSLA", "action": "SELL", "pct_of_portfolio": 0.00, "confirmed": True, "source": "both"},
]
DEST_POSITIONS = {
    "TSLA": {"shares": 4.0, "market_value": 640.0},
}
DEST_VALUE = 15000.0
PRICES = {"MSFT": 400.0, "TSLA": 160.0}

def test_buy_sizing():
    orders = calculate_dest_trades(TRADES, DEST_POSITIONS, DEST_VALUE, PRICES, min_trade_value=50)
    msft = next(o for o in orders if o["symbol"] == "MSFT")
    assert msft["action"] == "BUY"
    assert abs(msft["shares"] - 3.0) < 0.01  # 0.08 * 15000 / 400

def test_sell_uses_current_holding():
    orders = calculate_dest_trades(TRADES, DEST_POSITIONS, DEST_VALUE, PRICES, min_trade_value=50)
    tsla = next(o for o in orders if o["symbol"] == "TSLA")
    assert tsla["action"] == "SELL"
    assert tsla["shares"] == 4.0  # full position

def test_skips_below_min_trade_value():
    tiny_trades = [{"symbol": "X", "action": "BUY", "pct_of_portfolio": 0.001,
                    "confirmed": True, "source": "both"}]
    orders = calculate_dest_trades(tiny_trades, {}, 15000.0, {"X": 10.0}, min_trade_value=50)
    assert orders == []

def test_sells_before_buys():
    orders = calculate_dest_trades(TRADES, DEST_POSITIONS, DEST_VALUE, PRICES, min_trade_value=50)
    actions = [o["action"] for o in orders]
    assert actions.index("SELL") < actions.index("BUY")

def test_dry_run_does_not_call_api():
    client = MagicMock()
    orders = [{"symbol": "AAPL", "action": "BUY", "shares": 2.0}]
    execute_trades(orders, dest_account="222", client=client, dry_run=True)
    client.place_order.assert_not_called()
