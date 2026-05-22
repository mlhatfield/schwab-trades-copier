# src/schwab_client.py
import schwab
from datetime import datetime, timedelta, timezone


def build_client(cfg: dict):
    return schwab.auth.client_from_token_file(
        cfg["schwab"]["token_file"],
        cfg["schwab"]["client_id"],
        cfg["schwab"]["client_secret"],
    )


def get_account_hashes(client) -> dict[str, str]:
    """Return mapping of accountNumber -> hashValue for all linked accounts."""
    resp = client.get_account_numbers()
    resp.raise_for_status()
    return {entry["accountNumber"]: entry["hashValue"] for entry in resp.json()}


def normalize_positions(raw: dict) -> dict:
    acct = raw["securitiesAccount"]
    total = acct["currentBalances"]["liquidationValue"]
    result = {}
    for pos in acct.get("positions", []):
        inst = pos["instrument"]
        if inst.get("assetType") != "EQUITY":
            continue
        sym = inst["symbol"]
        mv = pos["marketValue"]
        result[sym] = {
            "shares": pos["longQuantity"],
            "market_value": mv,
            "pct_of_portfolio": mv / total if total else 0.0,
        }
    return result


def get_positions(client, account_number: str) -> dict:
    resp = client.get_account(account_number, fields=[client.Account.Fields.POSITIONS])
    resp.raise_for_status()
    return normalize_positions(resp.json())


def get_transactions(client, account_number: str, days: int = 2) -> list[dict]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    resp = client.get_transactions(
        account_number,
        transaction_type=client.Transactions.TransactionType.TRADE,
        start_date=start,
    )
    resp.raise_for_status()
    raw = resp.json()
    trades = []
    for tx in raw:
        for item in tx.get("transferItems", []):
            inst = item.get("instrument", {})
            if inst.get("assetType") != "EQUITY":
                continue
            amount = item.get("amount", 0)
            if amount == 0:
                continue
            trades.append({
                "symbol": inst["symbol"],
                "action": "BUY" if amount > 0 else "SELL",
            })
    return trades


def get_prices(client, symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    resp = client.get_quotes(symbols)
    resp.raise_for_status()
    data = resp.json()
    result = {}
    for sym in symbols:
        if sym not in data:
            continue
        try:
            result[sym] = data[sym]["quote"]["lastPrice"]
        except KeyError:
            pass
    return result
