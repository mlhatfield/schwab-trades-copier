# schwab-trades-copier

A lightweight Python tool that watches one Schwab brokerage account for trades and proportionally mirrors them into another account. Runs once daily via macOS launchd.

**Use case:** You pay a trader to manage one account. This tool detects what they bought or sold and replicates those trades in your own account, sized proportionally to your account's value.

---

## How it works

1. **Detects trades** by comparing today's positions against yesterday's snapshot, cross-referenced with the last 48 hours of transaction history for confidence
2. **Sizes orders proportionally** — if the trader puts 5% of their portfolio into AAPL, it puts 5% of your portfolio into AAPL
3. **Sells before buys** — frees up cash before placing new positions
4. **Saves a new snapshot** at the end of each run for the next day's diff

---

## Requirements

- Python 3.11+
- A [Schwab developer app](https://developer.schwab.com) (free)
- Both accounts must be accessible under your Schwab login

---

## Setup

### 1. Create a Schwab developer app

1. Go to [developer.schwab.com](https://developer.schwab.com) and sign in
2. Click **Apps → Create App**
3. Set **Callback URL** to `https://127.0.0.1:8182`
4. Enable **Accounts and Trading Production**
5. Wait for status to show **Ready for Use** (can take a few minutes)
6. Copy your **App Key** (Client ID) and **Secret**

### 2. Install

```bash
git clone git@github.com:mlhatfield/schwab-trades-copier.git
cd schwab-trades-copier
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
schwab:
  client_id: "YOUR_APP_KEY"
  client_secret: "YOUR_APP_SECRET"
  token_file: "~/.schwab-trader/tokens.json"

accounts:
  source: "12345678"   # account to copy FROM (trader's account)
  dest:   "87654321"   # account to copy INTO (your account)

execution:
  dry_run: true        # set to false when ready to go live
  min_trade_value: 50  # skip trades smaller than $50
  allocation_tolerance: 0.01
  order_type: "MARKET"
```

> `config.yaml` is gitignored and will never be committed.

### 4. Authenticate (one time)

```bash
python main.py --setup
```

A browser window opens. Log in with your Schwab credentials and approve the app. The token is saved to `~/.schwab-trader/tokens.json` and refreshes automatically from then on.

### 5. Test with dry run

```bash
python main.py --dry-run
```

Logs every trade it *would* place without submitting any orders. Run this for a few days to validate the detection logic before going live.

### 6. Go live

Set `dry_run: false` in `config.yaml`, then install the launchd job to run automatically each trading day:

```bash
# Edit com.schwabtrader.plist — replace YOUR_USERNAME with your Mac username
cp com.schwabtrader.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.schwabtrader.plist
```

The job fires at **9:45am ET** daily (15 minutes after market open).

---

## Usage

```bash
# First-time OAuth setup + initial snapshot
python main.py --setup

# Normal daily run (used by launchd)
python main.py

# Preview trades without placing orders
python main.py --dry-run

# Use a custom config file
python main.py --config /path/to/config.yaml
```

---

## Project structure

```
schwab-trades-copier/
├── main.py                  # Entry point and orchestration
├── config.example.yaml      # Config template (copy to config.yaml)
├── com.schwabtrader.plist   # macOS launchd job definition
├── requirements.txt
├── src/
│   ├── config.py            # Config loader
│   ├── differ.py            # Trade detection (snapshot diff + history merge)
│   ├── schwab_client.py     # Schwab API wrapper
│   ├── snapshot.py          # Position state persistence
│   └── trader.py            # Order sizing and execution
└── tests/
    ├── test_config.py
    ├── test_differ.py
    ├── test_schwab_client.py
    ├── test_snapshot.py
    └── test_trader.py
```

---

## Trade detection logic

Trades are detected using two signals merged together:

| Signal | How | Confidence |
|--------|-----|------------|
| Position diff | Compare yesterday's snapshot to today's positions | Unconfirmed until corroborated |
| Transaction history | Pull last 48hr of TRADE transactions from the API | Confirmed |

A trade appearing in both signals is marked `confirmed: True, source: "both"`. Position-diff-only trades are flagged in the log but still executed — the position change is real evidence.

---

## Order sizing

```
buy_value  = pct_of_source_portfolio × dest_account_total_value
shares     = floor(buy_value / current_price)

sell_shares = current dest holding shares (full or proportional)
```

Orders smaller than `min_trade_value` (default $50) are skipped. Sells execute before buys to free up cash first.

---

## Logs

Each run appends to `~/.schwab-trader/logs/YYYY-MM-DD.log`. Every order decision is logged — including skipped trades and the reason.

```
2026-05-22 09:45:01 INFO Fetching source positions (account ...9017)
2026-05-22 09:45:02 INFO Detected 2 trades: [('AAPL', 'BUY'), ('TSLA', 'SELL')]
2026-05-22 09:45:02 INFO Placing 2 orders (dry_run=False)
2026-05-22 09:45:03 INFO Placed BUY 12 AAPL
2026-05-22 09:45:03 INFO Placed SELL 8 TSLA
2026-05-22 09:45:03 INFO Snapshot updated. Done.
```

---

## Running tests

```bash
.venv/bin/pytest -v
```

24 tests covering config loading, snapshot persistence, trade detection, order sizing, and the Schwab API client.

---

## Limitations

- **Whole shares only** — Schwab market orders require integer share counts; fractional shares are not supported
- **Market orders only** — orders execute at the prevailing market price at time of submission
- **Mutual funds not supported** — the Schwab API does not support placing mutual fund orders
- **Source account must be accessible** — both accounts must be visible under the same Schwab login that completed OAuth
- **Market hours** — orders must be submitted between 9:30am–3:55pm ET on trading days; rejected outside those windows

---

## License

MIT
