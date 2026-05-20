import os
import pytest
from src.config import load_config

MINIMAL_CONFIG = """
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
"""

@pytest.fixture
def cfg_file(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(MINIMAL_CONFIG)
    return str(f)

def test_load_config_returns_dict(cfg_file):
    cfg = load_config(cfg_file)
    assert cfg["accounts"]["source"] == "111"
    assert cfg["execution"]["dry_run"] is True

def test_load_config_expands_token_path(cfg_file):
    cfg = load_config(cfg_file)
    assert os.path.isabs(cfg["schwab"]["token_file"])

def test_load_config_empty_file_raises(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    with pytest.raises(ValueError, match="empty or not valid YAML"):
        load_config(str(f))

def test_load_config_missing_key_raises(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("foo: bar\n")
    with pytest.raises(KeyError, match="Config missing required key"):
        load_config(str(f))
