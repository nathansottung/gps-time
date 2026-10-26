"""Build the offline tower cache from exported licence records (see cache.py). Run by the operator.

    python -m reference_broadcast_towers.build_cache --fm fm.csv --tv tv.csv --noaa nwr.csv \\
        --near 38.9,-77.1 --radius-km 150 --retrieved 2026-10-26 --out towers-cache.json

No network access: it reads the files given and writes one JSON file (atomically).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import cache


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fm", action="append", default=[], help="FM records (CSV with a header row)")
    ap.add_argument("--tv", action="append", default=[], help="ATSC records (CSV; RF channel, not virtual)")
    ap.add_argument("--noaa", action="append", default=[], help="NOAA Weather Radio transmitters (CSV)")
    ap.add_argument("--near", required=True, help="LAT,LON of the area; rounded to 0.1° before use")
    ap.add_argument("--radius-km", type=float, default=150.0)
    ap.add_argument("--retrieved", required=True, help="date the records were exported (YYYY-MM-DD)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--comment", default=None, help="a note stored in the cache (e.g. where the records came from)")
    ap.add_argument("--built-utc", default=None, help=argparse.SUPPRESS)   # reproducible fixtures
    a = ap.parse_args(argv)
    try:
        lat, lon = (float(x) for x in a.near.split(","))
    except ValueError:
        ap.error("--near must be LAT,LON")
    inputs = [(svc, Path(p).name, Path(p).read_text(encoding="utf-8-sig"))
              for svc, paths in (("FM", a.fm), ("ATSC", a.tv), ("NOAA", a.noaa)) for p in paths]
    if not inputs:
        ap.error("give at least one of --fm, --tv, --noaa")
    built = a.built_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = cache.build(inputs, (lat, lon), a.radius_km, a.retrieved, built)
    if a.comment:
        doc = {"comment": a.comment, **doc}
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, a.out)
    kept = {s: sum(1 for t in doc["towers"] if t["service"] == s) for s in cache.SERVICES}
    print(f"{a.out}: {len(doc['towers'])} transmitters ({', '.join(f'{k} {v}' for k, v in kept.items())}); "
          f"rejected {', '.join(f'{k} {v}' for k, v in doc['rejected'].items() if v) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
