# src/config.py
import os
import yaml

def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg["schwab"]["token_file"] = os.path.expanduser(cfg["schwab"]["token_file"])
    return cfg
