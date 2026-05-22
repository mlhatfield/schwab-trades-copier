# Schwab Trade Copier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Daily cron job that detects trades in a source Schwab account and proportionally mirrors them to a destination account.

**Architecture:** Uses schwab-py for OAuth + API access. Detects trades by diffing position snapshots and cross-referencing 48hr transaction history. Executes proportional market orders on destination account, sells before buys.

**Tech Stack:** Python 3.11+, schwab-py, PyYAML, launchd (Mac scheduling)

---

### Task 1: Project scaffold and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `config.example.yaml`
- Create: `tests/__init__.py`
- Create: `src/__init__.py`

**Step 1: Create requirements.txt**

```
schwab-py>=1.4.0
pyyaml>=6.0
pytest>=8.0
pytest-mock>=3.12
```

**Step 2: Create config.example.yaml**

```yaml
schwab:
  client_id: "YOUR_APP_KEY"
  client_secret: "YOUR_APP_SECRET"
  token_file: "~/.schwab-trader/tokens.json"

accounts:
  source: "12345678"
  dest:   "87654321"

execution:
  dry_run: true
  min_trade_value: 50
  allocation_tolerance: 0.01
  order_type: "MARKET"

schedule:
  time: "09:45"
```

**Step 3: Install dependencies**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Step 4: Commit**

```bash
git add requirements.txt config.example.yaml tests/__init__.py src/__init__.py
git commit -m "feat: project scaffold and dependencies"
```

---

### Task 2: Config loader

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing test**

```python
# tests/test_config.py
import pytest
from src.config import load_config

def test_load_config_returns_dict(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
schwab:
  client_id: "abc"
  client_secret: "def"
  token_file: "~/.schwab-trader/tokens.json"
accounts:
  source: "111"
  dest: "222"
execution:
  dry_run: true
  min_trade_value: 50
  allocation_tolerance: 0.01
  order_type: "MARKET"
""")
    cfg = load_config(str(cfg_file))
    assert cfg["accounts"]["source"] == "111"
    assert cfg["execution"]["dry_run"] is True

def test_load_config_expands_token_path(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
schwab:
  client_id: "abc"
  client_secret: "def"
  token_file: "~/.schwab-trader/tokens.json"
accounts:
  source: "111"
  dest: "222"
execution:
  dry_run: true
  min_trade_value: 50
  allocation_tolerance: 0.01
  order_type: "MARKET"
""")
    cfg = load_config(str(cfg_file))
    assert not cfg["schwab"]["token_file"].startswith("~")
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement**

```python
# src/config.py
import os
import yaml

def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg["schwab"]["token_file"] = os.path.expanduser(cfg["schwab"]["token_file"])
    return cfg
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_config.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: config loader with path expansion"
```

---

### Task 3: Snapshot persistence

**Files:**
- Create: `src/snapshot.py`
- Create: `tests/test_snapshot.py`

**Step 1: Write failing tests**

```python
# tests/test_snapshot.py
import json
import pytest
from src.snapshot import save_snapshot, load_snapshot

POSITIONS = {
    "AAPL": {"shares": 10.0, "market_value": 1500.0},
    "TSLA": {"shares": 5.0, "market_value": 800.0},
}

def test_roundtrip(tmp_path):
    path = str(tmp_path / "snapshot.json")
    save_snapshot(POSITIONS, path)
    loaded = load_snapshot(path)
    assert loaded == POSITIONS

def test_load_missing_returns_empty(tmp_path):
    path = str(tmp_path / "nonexistent.json")
    assert load_snapshot(path) == {}
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_snapshot.py -v
```

**Step 3: Implement**

```python
# src/snapshot.py
import json
import os

def save_snapshot(positions: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(positions, f, indent=2)

def load_snapshot(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_snapshot.py -v
```

**Step 5: Commit**

```bash
git add src/snapshot.py tests/test_snapshot.py
git commit -m "feat: snapshot save/load with missing-file safety"
```

---

### Task 4: Trade differ

**Files:**
- Create: `src/differ.py`
- Create: `tests/test_differ.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_differ.py -v
```

**Step 3: Implement**

```python
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
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_differ.py -v
```

**Step 5: Commit**

```bash
git add src/differ.py tests/test_differ.py
git commit -m "feat: trade differ with history confirmation"
```

---

### Task 5: Proportional trade executor

**Files:**
- Create: `src/trader.py`
- Create: `tests/test_trader.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_trader.py -v
```

**Step 3: Implement**

```python
# src/trader.py
import logging

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
        if not price:
            log.warning(f"No price for {sym}, skipping")
            continue

        if trade["action"] == "BUY":
            target_value = trade["pct_of_portfolio"] * dest_total_value
            if target_value < min_trade_value:
                log.info(f"Skipping {sym} BUY — below min trade value (${target_value:.2f})")
                continue
            shares = target_value / price
            orders.append({"symbol": sym, "action": "BUY", "shares": round(shares, 4)})

        elif trade["action"] == "SELL":
            holding = dest_positions.get(sym)
            if not holding:
                log.info(f"Skipping {sym} SELL — not held in dest account")
                continue
            shares = holding["shares"]
            orders.append({"symbol": sym, "action": "SELL", "shares": shares})

    # sells before buys
    orders.sort(key=lambda o: 0 if o["action"] == "SELL" else 1)
    return orders


def execute_trades(orders: list[dict], dest_account: str, client, dry_run: bool = False) -> None:
    import schwab.orders.equities as eq
    for order in orders:
        sym, action, shares = order["symbol"], order["action"], order["shares"]
        if dry_run:
            log.info(f"[DRY RUN] Would {action} {shares} shares of {sym}")
            continue
        if action == "BUY":
            spec = eq.equity_buy_market(sym, int(shares))
        else:
            spec = eq.equity_sell_market(sym, int(shares))
        client.place_order(dest_account, spec)
        log.info(f"Placed {action} {int(shares)} {sym}")
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_trader.py -v
```

**Step 5: Commit**

```bash
git add src/trader.py tests/test_trader.py
git commit -m "feat: proportional trade executor with dry-run"
```

---

### Task 6: Schwab API client wrapper

**Files:**
- Create: `src/schwab_client.py`
- Create: `tests/test_schwab_client.py`

**Step 1: Write failing tests**

```python
# tests/test_schwab_client.py
from unittest.mock import MagicMock, patch
from src.schwab_client import get_positions, get_transactions, normalize_positions

def test_normalize_positions_extracts_pct():
    raw = {
        "securitiesAccount": {
            "currentBalances": {"liquidationValue": 10000.0},
            "positions": [
                {"instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                 "marketValue": 1000.0, "longQuantity": 5.0}
            ]
        }
    }
    result = normalize_positions(raw)
    assert "AAPL" in result
    assert abs(result["AAPL"]["pct_of_portfolio"] - 0.10) < 0.001
    assert result["AAPL"]["shares"] == 5.0

def test_normalize_positions_skips_non_equity():
    raw = {
        "securitiesAccount": {
            "currentBalances": {"liquidationValue": 10000.0},
            "positions": [
                {"instrument": {"symbol": "CASH", "assetType": "CASH_EQUIVALENT"},
                 "marketValue": 500.0, "longQuantity": 500.0}
            ]
        }
    }
    result = normalize_positions(raw)
    assert result == {}
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_schwab_client.py -v
```

**Step 3: Implement**

```python
# src/schwab_client.py
import schwab
import httpx
from datetime import datetime, timedelta, timezone


def build_client(cfg: dict):
    return schwab.auth.client_from_token_file(
        cfg["schwab"]["token_file"],
        cfg["schwab"]["client_id"],
        cfg["schwab"]["client_secret"],
    )


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
    return {sym: data[sym]["quote"]["lastPrice"] for sym in symbols if sym in data}
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_schwab_client.py -v
```

**Step 5: Commit**

```bash
git add src/schwab_client.py tests/test_schwab_client.py
git commit -m "feat: schwab API client wrapper with position normalization"
```

---

### Task 7: Main orchestrator

**Files:**
- Create: `main.py`

**Step 1: Implement (no unit test — integration only)**

```python
# main.py
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
```

**Step 2: Smoke test with dry-run**

```bash
cp config.example.yaml config.yaml
# Fill in your account numbers and app credentials
python main.py --setup          # browser auth, initial snapshot
python main.py --dry-run        # next day: verify it logs trades without placing them
```

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main orchestrator tying all components together"
```

---

### Task 8: launchd plist for daily scheduling

**Files:**
- Create: `com.schwabtrader.plist`

**Step 1: Create plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.schwabtrader</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/code/schwab-trader/.venv/bin/python</string>
        <string>/Users/YOUR_USERNAME/code/schwab-trader/main.py</string>
        <string>--config</string>
        <string>/Users/YOUR_USERNAME/code/schwab-trader/config.yaml</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>45</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/.schwab-trader/logs/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/.schwab-trader/logs/launchd.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

**Step 2: Install**

Replace `YOUR_USERNAME` with your actual username, then:

```bash
cp com.schwabtrader.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.schwabtrader.plist
launchctl list | grep schwabtrader   # should show the job
```

**Step 3: Commit**

```bash
git add com.schwabtrader.plist
git commit -m "feat: launchd plist for daily 9:45am ET execution"
```

---

### Task 9: Git init and .gitignore

**Files:**
- Create: `.gitignore`

**Step 1: Create .gitignore**

```
.venv/
__pycache__/
*.pyc
config.yaml
~/.schwab-trader/
.env
```

**Step 2: Initialize repo and initial commit**

```bash
git init
git add .gitignore requirements.txt config.example.yaml src/ tests/ main.py com.schwabtrader.plist docs/
git commit -m "feat: initial schwab trade copier implementation"
```

---

## Running order summary

1. Task 9 (git init) — do this first
2. Task 1 (scaffold)
3. Tasks 2–6 (components, TDD)
4. Task 7 (orchestrator)
5. Task 8 (launchd)

## First use checklist

- [ ] Create Schwab developer app at developer.schwab.com — get `client_id` and `client_secret`
- [ ] Set callback URL to `https://127.0.0.1` in Schwab app settings
- [ ] Copy `config.example.yaml` → `config.yaml`, fill in credentials and account numbers
- [ ] Run `python main.py --setup` — completes OAuth, saves initial snapshot
- [ ] Run `python main.py --dry-run` the next trading day — verify output looks correct
- [ ] Set `dry_run: false` in `config.yaml` when ready to go live
- [ ] Install launchd plist (Task 8)
