"""Promote a tested desktop demo dashboard layout into the packaged default."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from gps_time_pi import dashboard

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="source", default=str(ROOT / ".dev" / "dashboard.json"))
    args = ap.parse_args()
    src = Path(args.source)
    if not src.exists():
        raise SystemExit(f"dashboard file not found: {src}")
    cfg = dashboard.validate(json.loads(src.read_text(encoding="utf-8")))
    text = json.dumps(cfg, indent=2) + "\n"
    for target in (ROOT / "config" / "dashboard.default.json", ROOT / "gps_time_pi" / "data" / "dashboard.default.json"):
        target.write_text(text, encoding="utf-8")
        print(target)

if __name__ == "__main__":
    main()
