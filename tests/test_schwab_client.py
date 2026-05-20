# tests/test_schwab_client.py
from unittest.mock import MagicMock, patch
from src.schwab_client import normalize_positions

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
