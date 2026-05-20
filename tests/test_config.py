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
