# tests/test_differ.py
from src.differ import diff_positions, merge_with_history, build_trade_list

YESTERDAY = {
    "AAPL": {"shares": 10.0, "market_value": 1500.0, "pct_of_portfolio": 0.10},
    "TSLA": {"shares": 5.0,  "market_value": 800.0,  "pct_of_portfolio": 0.05},
}
TODAY = {
    "AAPL": {"shares": 15.0, "market_value": 2250.0, "pct_of_portfolio": 0.12},
    "MSFT": {"shares": 3.0,  "market_value": 1200.0, "pct_of_portfolio": 0.08},
}

def test_diff_detects_new_symbol():
    trades = diff_positions(YESTERDAY, TODAY)
    msft = next(t for t in trades if t["symbol"] == "MSFT")
    assert msft["action"] == "BUY"

def test_diff_detects_gone_symbol():
    trades = diff_positions(YESTERDAY, TODAY)
    tsla = next(t for t in trades if t["symbol"] == "TSLA")
    assert tsla["action"] == "SELL"

def test_diff_detects_increased_position():
    trades = diff_positions(YESTERDAY, TODAY)
    aapl = next(t for t in trades if t["symbol"] == "AAPL")
    assert aapl["action"] == "BUY"

def test_diff_unchanged_symbol_excluded():
    same = {**YESTERDAY}
    trades = diff_positions(same, same)
    assert trades == []

def test_merge_confirms_matching_history():
    diffs = [{"symbol": "AAPL", "action": "BUY", "pct_of_portfolio": 0.12, "source": "diff"}]
    history = [{"symbol": "AAPL", "action": "BUY"}]
    result = merge_with_history(diffs, history)
    assert result[0]["confirmed"] is True
    assert result[0]["source"] == "both"

def test_merge_unconfirmed_when_no_history_match():
    diffs = [{"symbol": "AAPL", "action": "BUY", "pct_of_portfolio": 0.12, "source": "diff"}]
    result = merge_with_history(diffs, [])
    assert result[0]["confirmed"] is False

def test_merge_includes_history_only_trades():
    diffs = []
    history = [{"symbol": "GOOG", "action": "BUY", "pct_of_portfolio": 0.03}]
    result = merge_with_history(diffs, history)
    goog = next(t for t in result if t["symbol"] == "GOOG")
    assert goog["source"] == "history"
    assert goog["confirmed"] is True
