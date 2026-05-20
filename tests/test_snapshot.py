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

def test_save_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "subdir" / "nested" / "snapshot.json")
    save_snapshot(POSITIONS, path)
    loaded = load_snapshot(path)
    assert loaded == POSITIONS
