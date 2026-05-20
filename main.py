import argparse
import logging
import os
import sys
from datetime import date

from src.config import load_config
from src.snapshot import save_snapshot, load_snapshot
from src.differ import build_trade_list
from src.trader import calculate_dest_trades, execute_trades
from src.schwab_client import build_client, get_positions, get_transactions, get_prices


def setup_logging(log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{date.today()}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def first_run_setup(cfg: dict) -> None:
    import schwab
    os.makedirs(os.path.dirname(cfg["schwab"]["token_file"]), exist_ok=True)
    schwab.auth.client_from_login_flow(
        cfg["schwab"]["client_id"],
        cfg["schwab"]["client_secret"],
        "https://127.0.0.1",
        cfg["schwab"]["token_file"],
    )
    print("Auth complete. Taking initial snapshot...")
    client = build_client(cfg)
    positions = get_positions(client, cfg["accounts"]["source"])
    snapshot_path = os.path.join(os.path.dirname(cfg["schwab"]["token_file"]), "snapshot.json")
    save_snapshot(positions, snapshot_path)
    print(f"Snapshot saved to {snapshot_path}. Run without --setup tomorrow to start copying.")


def run(cfg: dict) -> None:
    log = logging.getLogger(__name__)
    client = build_client(cfg)

    snapshot_path = os.path.join(os.path.dirname(cfg["schwab"]["token_file"]), "snapshot.json")
    yesterday = load_snapshot(snapshot_path)

    source_id = cfg["accounts"]["source"]
    dest_id = cfg["accounts"]["dest"]
    dry_run = cfg["execution"]["dry_run"]

    log.info(f"Fetching source positions (account {source_id})")
    today_positions = get_positions(client, source_id)

    log.info("Fetching transaction history (last 48hr)")
    history = get_transactions(client, source_id, days=2)

    log.info("Building trade list")
    trades = build_trade_list(yesterday, today_positions, history)
    log.info(f"Detected {len(trades)} trades: {[(t['symbol'], t['action']) for t in trades]}")

    if not trades:
        log.info("No trades to copy. Done.")
        save_snapshot(today_positions, snapshot_path)
        return

    log.info(f"Fetching dest positions (account {dest_id})")
    dest_positions = get_positions(client, dest_id)
    dest_value = sum(p["market_value"] for p in dest_positions.values())

    symbols = list({t["symbol"] for t in trades})
    prices = get_prices(client, symbols)

    orders = calculate_dest_trades(
        trades,
        dest_positions,
        dest_value,
        prices,
        min_trade_value=cfg["execution"]["min_trade_value"],
        allocation_tolerance=cfg["execution"]["allocation_tolerance"],
    )
    log.info(f"Placing {len(orders)} orders (dry_run={dry_run})")
    execute_trades(orders, dest_id, client, dry_run=dry_run)

    save_snapshot(today_positions, snapshot_path)
    log.info("Snapshot updated. Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Schwab trade copier")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--setup", action="store_true", help="First-run OAuth setup")
    parser.add_argument("--dry-run", action="store_true", help="Log trades without placing orders")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.dry_run:
        cfg["execution"]["dry_run"] = True

    log_dir = os.path.expanduser("~/.schwab-trader/logs")
    setup_logging(log_dir)

    if args.setup:
        first_run_setup(cfg)
    else:
        run(cfg)


if __name__ == "__main__":
    main()
