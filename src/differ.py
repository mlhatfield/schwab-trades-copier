# src/differ.py

def diff_positions(yesterday: dict, today: dict) -> list[dict]:
    trades = []
    all_symbols = set(yesterday) | set(today)
    for sym in all_symbols:
        prev = yesterday.get(sym)
        curr = today.get(sym)
        if prev is None and curr is not None:
            trades.append({"symbol": sym, "action": "BUY",
                           "pct_of_portfolio": curr["pct_of_portfolio"], "source": "diff"})
        elif curr is None and prev is not None:
            trades.append({"symbol": sym, "action": "SELL",
                           "pct_of_portfolio": 0.0, "source": "diff"})
        elif curr["shares"] > prev["shares"]:
            trades.append({"symbol": sym, "action": "BUY",
                           "pct_of_portfolio": curr["pct_of_portfolio"], "source": "diff"})
        elif curr["shares"] < prev["shares"]:
            trades.append({"symbol": sym, "action": "SELL",
                           "pct_of_portfolio": curr["pct_of_portfolio"], "source": "diff"})
    return trades


def merge_with_history(diffs: list[dict], history: list[dict]) -> list[dict]:
    result = []
    diff_index = {(t["symbol"], t["action"]): t for t in diffs}
    history_index = {(t["symbol"], t["action"]): t for t in history}

    for key, trade in diff_index.items():
        if key in history_index:
            result.append({**trade, "confirmed": True, "source": "both"})
        else:
            result.append({**trade, "confirmed": False})

    for key, trade in history_index.items():
        if key not in diff_index:
            result.append({**trade, "confirmed": True, "source": "history"})

    return result


def build_trade_list(yesterday: dict, today: dict, history: list[dict]) -> list[dict]:
    diffs = diff_positions(yesterday, today)
    return merge_with_history(diffs, history)
