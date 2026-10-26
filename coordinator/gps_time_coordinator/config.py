"""The coordinator's single config file (TOML). Path: GTC_CONFIG, default /config/coordinator.toml."""

import os
import tomllib
from pathlib import Path

DEFAULTS = {
    "server": {"bind": "0.0.0.0", "port": 8090, "max_body_bytes": 1_048_576},
    "storage": {"database": "/data/coordinator.sqlite3", "retention_days": 90},
}


def load(path=None):
    path = Path(path or os.environ.get("GTC_CONFIG", "/config/coordinator.toml"))
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    for section, values in data.items():
        if section not in cfg or not isinstance(values, dict):
            raise ValueError(f"unknown section [{section}] in {path}")
        for k, v in values.items():
            if k not in cfg[section]:
                raise ValueError(f"unknown key {section}.{k} in {path}")
            if type(v) is not type(cfg[section][k]):
                raise ValueError(f"{section}.{k} must be a {type(cfg[section][k]).__name__}")
            cfg[section][k] = v
    if not 1 <= cfg["storage"]["retention_days"] <= 3650:
        raise ValueError("storage.retention_days must be 1..3650")
    return cfg
