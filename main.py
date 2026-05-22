import argparse
import logging
import os
import sys
from datetime import date

from src.config import load_config
from src.snapshot import save_snapshot, load_snapshot
from src.differ import build_trade_list
from src.trader import calculate_dest_trades, execute_trades
from src.schwab_client import build_client, get_account_hashes, get_positions, get_transactions, get_prices

_REDIRECT_URI = "https://127.0.0.1:8182"


def _snapshot_path(cfg: dict) -> str:
    token_dir = os.path.dirname(cfg["schwab"]["token_file"]) or "."
    return os.path.join(token_dir, "snapshot.json")


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
    log = logging.getLogger(__name__)
    os.makedirs(os.path.dirname(cfg["schwab"]["token_file"]) or ".", exist_ok=True)
    schwab.auth.client_from_login_flow(
        cfg["schwab"]["client_id"],
        cfg["schwab"]["client_secret"],
        _REDIRECT_URI,
        cfg["schwab"]["token_file"],
        interactive=False,
    )
    log.info("Auth complete. Taking initial snapshot...")
    client = build_client(cfg)
    hashes = get_account_hashes(client)
    source_hash = hashes[cfg["accounts"]["source"]]
    positions = get_positions(client, source_hash)
    path = _snapshot_path(cfg)
    save_snapshot(positions, path)
    log.info(f"Snapshot saved to {path}. Run without --setup tomorrow to start copying.")


def run(cfg: dict) -> None:
    log = logging.getLogger(__name__)
    client = build_client(cfg)

    hashes = get_account_hashes(client)
    source_hash = hashes[cfg["accounts"]["source"]]
    dest_hash = hashes[cfg["accounts"]["dest"]]

    snapshot_path = _snapshot_path(cfg)
    yesterday = load_snapshot(snapshot_path)

    dry_run = cfg["execution"]["dry_run"]

    log.info(f"Fetching source positions (account ...{cfg['accounts']['source'][-4:]})")
    today_positions = get_positions(client, source_hash)

    log.info("Fetching transaction history (last 48hr)")
    history = get_transactions(client, source_hash, days=2)

    log.info("Building trade list")
    trades = build_trade_list(yesterday, today_positions, history)
    log.info(f"Detected {len(trades)} trades: {[(t['symbol'], t['action']) for t in trades]}")

    if not trades:
        log.info("No trades to copy. Done.")
        save_snapshot(today_positions, snapshot_path)
        return

    log.info(f"Fetching dest positions (account ...{cfg['accounts']['dest'][-4:]})")
    dest_positions = get_positions(client, dest_hash)
    dest_value = sum(p["market_value"] for p in dest_positions.values())
    if dest_value == 0.0:
        log.warning("Dest account has zero market value — no BUY orders will be sized")

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
    execute_trades(orders, dest_hash, client, dry_run=dry_run)

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
