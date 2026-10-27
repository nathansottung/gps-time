"""Build the offline tower cache from exported licence records (see cache.py). Run by the operator.

    python -m reference_broadcast_towers.build_cache --downloads ~/towers-downloads \\
        --near 38.9,-77.1 --radius-km 150 --out towers-cache.json

--downloads reads what fetch.py downloaded (its manifest gives each file's retrieval date and
SHA-256). Files can also be given one by one (--fm, --tv, --noaa, with --retrieved): FCC text
output, the NOAA ccl-data.js file, or CSV with a header row.

No network access: it reads the files given and writes one JSON file (atomically).
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import cache, fetch


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fm", action="append", default=[], help="FM records (FCC FM Query text output, or CSV)")
    ap.add_argument("--tv", action="append", default=[], help="ATSC records (FCC TV Query text output, or CSV with the RF channel)")
    ap.add_argument("--noaa", action="append", default=[], help="NOAA Weather Radio transmitters (ccl-data.js, or CSV)")
    ap.add_argument("--downloads", default=None, help="a folder written by fetch.py (uses its manifest)")
    ap.add_argument("--near", required=True, help="LAT,LON of the area; rounded to 0.1° before use")
    ap.add_argument("--radius-km", type=float, default=150.0)
    ap.add_argument("--retrieved", default=None, help="date the records were exported (YYYY-MM-DD); "
                    "with --downloads, each file's date comes from the manifest")
    ap.add_argument("--out", required=True)
    ap.add_argument("--comment", default=None, help="a note stored in the cache (e.g. where the records came from)")
    ap.add_argument("--built-utc", default=None, help=argparse.SUPPRESS)   # reproducible fixtures
    a = ap.parse_args(argv)
    try:
        lat, lon = (float(x) for x in a.near.split(","))
    except ValueError:
        ap.error("--near must be LAT,LON")
    inputs = [(svc, Path(p).name, Path(p).read_text(encoding="utf-8-sig"), a.retrieved)
              for svc, paths in (("FM", a.fm), ("ATSC", a.tv), ("NOAA", a.noaa)) for p in paths]
    if a.downloads:
        files = fetch.read_manifest(a.downloads).get("files", {})
        if not files:
            ap.error(f"no {fetch.MANIFEST} in {a.downloads} (run fetch.py first)")
        for key in sorted(files):
            m = files[key]
            path = Path(a.downloads) / m["file"]
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if hashlib.sha256(path.read_bytes()).hexdigest() != m["sha256"]:
                ap.error(f"{path} does not match its manifest entry (changed since it was downloaded)")
            inputs.append((m["service"], m["file"], text, m["retrieved_utc"][:10], m["sha256"]))
    if not inputs:
        ap.error("give --downloads, or at least one of --fm, --tv, --noaa")
    if any(i[3] is None for i in inputs):
        ap.error("--retrieved is needed for files given with --fm, --tv or --noaa")
    built = a.built_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = cache.build(inputs, (lat, lon), a.radius_km, None, built)
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
