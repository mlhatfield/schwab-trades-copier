# src/config.py
import os
import yaml

def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config file {path!r} is empty or not valid YAML")
    try:
        cfg["schwab"]["token_file"] = os.path.expanduser(cfg["schwab"]["token_file"])
    except KeyError as exc:
        raise KeyError(f"Config missing required key: {exc}") from exc
    return cfg
