import logging
import schwab.orders.equities as eq

log = logging.getLogger(__name__)


def calculate_dest_trades(
    trades: list[dict],
    dest_positions: dict,
    dest_total_value: float,
    prices: dict,
    min_trade_value: float = 50.0,
    allocation_tolerance: float = 0.01,
) -> list[dict]:
    orders = []
    for trade in trades:
        sym = trade["symbol"]
        price = prices.get(sym)
        if price is None:
            log.warning(f"No price for {sym}, skipping")
            continue

        if trade["action"] == "BUY":
            target_value = trade["pct_of_portfolio"] * dest_total_value
            if target_value < min_trade_value:
                log.info(f"Skipping {sym} BUY — below min trade value (${target_value:.2f})")
                continue
            shares = round(target_value / price, 4)
            orders.append({"symbol": sym, "action": "BUY", "shares": shares})

        elif trade["action"] == "SELL":
            holding = dest_positions.get(sym)
            if not holding:
                log.info(f"Skipping {sym} SELL — not held in dest account")
                continue
            orders.append({"symbol": sym, "action": "SELL", "shares": holding["shares"]})

    orders.sort(key=lambda o: 0 if o["action"] == "SELL" else 1)
    return orders


def execute_trades(orders: list[dict], dest_account: str, client, dry_run: bool = False) -> None:
    for order in orders:
        sym, action, shares = order["symbol"], order["action"], order["shares"]
        quantity = int(shares)
        if dry_run:
            log.info(f"[DRY RUN] Would {action} {quantity} shares of {sym}")
            continue
        if action == "BUY":
            spec = eq.equity_buy_market(sym, quantity)
        else:
            spec = eq.equity_sell_market(sym, quantity)
        client.place_order(dest_account, spec)
        log.info(f"Placed {action} {quantity} {sym}")
