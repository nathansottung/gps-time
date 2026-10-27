"""Download the national FCC FM and TV lists and the NOAA Weather Radio list. Run by the operator.

    python -m reference_broadcast_towers.fetch --dir ~/towers-downloads

Then build the cache from what was downloaded (build_cache.py --downloads DIR).

Privacy: these are the whole-country lists, so no location goes into any request. The area
is chosen afterwards, offline, by build_cache.py from the rounded site.

The module itself never fetches (it has no network permission): this is an operator tool, like
the TLE fetch. It writes each file atomically, then `fetch-manifest.json` with each URL, the
retrieval time (UTC), the size and the SHA-256. A failed download leaves the previous file and
manifest entry as they were.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "gps-time-tower-fetch/1 (+https://github.com/nathansottung/gps-time)"
# The FCC query tools' text output (list=4), every record in the country. The field key is the
# FCC's "Text output option for AM, FM, and TV Queries" page (see cache.FCC_FM, cache.FCC_TV).
SOURCES = {
    "fm": ("FM", "fm.txt", "https://transition.fcc.gov/fcc-bin/fmq?serv=FM&list=4&size=9"),
    "tv": ("ATSC", "tv.txt", "https://transition.fcc.gov/fcc-bin/tvq?chan=0&cha2=36&serv=&list=4&size=9"),
    # The data file behind https://www.weather.gov/nwr/station_listing
    "noaa": ("NOAA", "nwr.js", "https://www.weather.gov/source/nwr/JS/ccl-data.js"),
}
MANIFEST = "fetch-manifest.json"
MAX_BYTES = 64 * 1024 * 1024
MIN_ROWS = {"fm": 1000, "tv": 1000, "noaa": 100}      # a short reply is an error page, not a list


def _rows(key, text):
    from . import cache
    if key == "noaa":
        return text.count('"callsign"')
    return sum(1 for ln in text.splitlines() if ln.startswith("|")) if cache.detect(text) == "fcc" else 0


def download(url, timeout=120, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(req, timeout=timeout) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"larger than {MAX_BYTES} bytes")
    return data


def _write(path, data):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_manifest(folder):
    try:
        return json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"files": {}}


def fetch(folder, keys=tuple(SOURCES), fetcher=download, now=None):
    """Download each list into folder. Returns (manifest, problems)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(folder)
    manifest.setdefault("files", {})
    problems = []
    for key in keys:
        service, name, url = SOURCES[key]
        try:
            data = fetcher(url)
            text = data.decode("utf-8", errors="replace")
            n = _rows(key, text)
            if n < MIN_ROWS[key]:
                raise ValueError(f"only {n} records (expected at least {MIN_ROWS[key]}): not the list")
        except Exception as e:      # noqa: BLE001 — report and keep the previous file
            problems.append(f"{key}: {url}: {e}")
            continue
        _write(folder / name, data)
        manifest["files"][key] = {
            "service": service, "file": name, "url": url, "records": n, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "retrieved_utc": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        }
    _write(folder / MANIFEST, (json.dumps(manifest, indent=1) + "\n").encode("utf-8"))
    return manifest, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="folder for the downloads (kept out of git)")
    ap.add_argument("--only", choices=sorted(SOURCES), action="append", help="download only these lists")
    a = ap.parse_args(argv)
    manifest, problems = fetch(a.dir, tuple(a.only or SOURCES))
    for key, m in sorted(manifest["files"].items()):
        print(f"{key}: {m['records']} records, {m['bytes']} bytes, retrieved {m['retrieved_utc']}")
    for p in problems:
        print(f"problem: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
