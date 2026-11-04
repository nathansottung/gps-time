"""Airband bookmarks for the web SDR, from the FAA's NASR data, kept offline (docs/deploy/websdr.md).

Owner's rc.3 list and design (2026-11-04): the bookmarks carry the NASR cycle they came from and are
flagged once that's more than 28 days old; an admin "refresh now" fetches the current cycle, as
the TLE cache is refreshed by hand.

  - Built in, always there and the same everywhere: 121.5 MHz guard, 122.75 air-to-air, 123.025
    helicopter air-to-air, 122.9 MULTICOM. No download, no location.
  - From NASR: the FAA's 28-day "FRQ" CSV for the current cycle
    (https://nfdc.faa.gov/webContent/28DaySub/extra/<DD>_<Mon>_<YYYY>_FRQ_CSV.zip), VHF airband
    (118.000-136.975 MHz, AM) within RADIUS_KM of the station's site under its privacy mode
    (config.privacy_site: exact, or rounded to 0.1°). In hidden mode nothing is fetched: nearby
    airports would show where the station is.

Only `python -m gps_time_pi.airband refresh` downloads, run by gps-time-airband-fetch.service (the
admin action refresh_airband starts it); the web service never fetches. The result is one small
JSON file beside config.json (written atomically, once per refresh) and an OpenWebRX+ bookmarks file
it links to. The column names in the FAA file are read by header; if the expected ones aren't there
the refresh fails and says so, and the previous bookmarks stay.
"""
import argparse
import csv
import io
import json
import math
import os
import sys
import time
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config
from .labels import q

FORMAT = "gps-time.airband-bookmarks/1"
ANCHOR = date(2026, 10, 29)            # a NASR cycle effective date (FAA, checked 2026-11-04)
CYCLE_DAYS = 28
RADIUS_KM = 80.0
MAX_ZIP = 64 * 1024 * 1024
URL = "https://nfdc.faa.gov/webContent/28DaySub/extra/{day:02d}_{mon}_{year}_FRQ_CSV.zip"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")   # not the locale's
USER_AGENT = "gps-time-pi airband refresh (+https://github.com/nathansottung/gps-time)"
LOW_HZ, HIGH_HZ = 118_000_000, 136_975_000
_DIR = Path(os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")).parent
PATH = Path(os.environ.get("GTP_AIRBAND", _DIR / "airband-bookmarks.json"))
OWRX_PATH = Path(os.environ.get("GTP_AIRBAND_OWRX", _DIR / "airband-openwebrx.json"))
STATUS_PATH = Path(os.environ.get("GTP_AIRBAND_STATUS", _DIR / "airband-refresh.json"))

BUILT_IN = [
    {"name": "Guard (emergency)", "frequency_hz": 121_500_000, "use": "emergency", "source": "built-in"},
    {"name": "Air-to-air", "frequency_hz": 122_750_000, "use": "air-to-air", "source": "built-in"},
    {"name": "Helicopter air-to-air", "frequency_hz": 123_025_000, "use": "air-to-air", "source": "built-in"},
    {"name": "MULTICOM", "frequency_hz": 122_900_000, "use": "MULTICOM", "source": "built-in"},
]
# Header names in the FAA's FRQ CSV, and accepted alternatives.
COLUMNS = {"freq": ("FREQ",), "use": ("FREQ_USE",), "lat": ("LAT_DECIMAL", "SERVICED_LAT_DECIMAL"),
           "lon": ("LONG_DECIMAL", "LON_DECIMAL", "SERVICED_LONG_DECIMAL"),
           "facility": ("SERVICED_FACILITY", "FACILITY"), "name": ("SERVICED_FAC_NAME", "FAC_NAME")}


class AirbandError(Exception):
    pass


def cycle(on=None):
    """The NASR cycle in effect on a date: (effective date, next one)."""
    on = on or datetime.now(timezone.utc).date()
    k = math.floor((on - ANCHOR).days / CYCLE_DAYS)
    start = ANCHOR + timedelta(days=CYCLE_DAYS * k)
    return start, start + timedelta(days=CYCLE_DAYS)


def url_for(effective):
    return URL.format(day=effective.day, mon=MONTHS[effective.month - 1], year=effective.year)


def distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _col(header, key):
    for name in COLUMNS[key]:
        if name in header:
            return name
    return None


def parse_frq(text, site, radius_km=RADIUS_KM):
    """Bookmarks from the FRQ CSV: VHF airband within radius_km of site. AirbandError on an unknown layout."""
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    cols = {k: _col(header, k) for k in COLUMNS}
    missing = [COLUMNS[k][0] for k in ("freq", "lat", "lon") if not cols[k]]
    if missing:
        raise AirbandError(f"the FAA file has no {', '.join(missing)} column (columns: {', '.join(header[:12])}…)")
    seen, out = set(), []
    for row in reader:
        try:
            hz = round(float(row[cols["freq"]]) * 1e6)
            lat, lon = float(row[cols["lat"]]), float(row[cols["lon"]])
        except (TypeError, ValueError):
            continue
        if not (LOW_HZ <= hz <= HIGH_HZ):
            continue
        d = distance_km(site["lat"], site["lon"], lat, lon)
        if d > radius_km:
            continue
        fac = (row.get(cols["facility"]) or "").strip() if cols["facility"] else ""
        name = (row.get(cols["name"]) or "").strip() if cols["name"] else ""
        use = (row.get(cols["use"]) or "").strip() if cols["use"] else ""
        key = (fac, hz, use)
        if key in seen:
            continue
        seen.add(key)
        label = " ".join(x for x in (fac, use or name) if x) or f"{hz / 1e6:.3f}"
        out.append({"name": label[:60], "frequency_hz": hz, "use": use or None, "facility": fac or None,
                    "distance_km": round(d), "source": "nasr"})
    out.sort(key=lambda b: (b["distance_km"], b["facility"] or "", b["frequency_hz"]))
    return out


def owrx_bookmarks(rows):
    """OpenWebRX+'s bookmark format: name, frequency (Hz), modulation."""
    return [{"name": r["name"], "frequency": r["frequency_hz"], "modulation": "am"} for r in rows]


def _write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _download(url, opener=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with (opener or urllib.request.urlopen)(req, timeout=120) as r:
        data = r.read(MAX_ZIP + 1)
    if len(data) > MAX_ZIP:
        raise AirbandError("the FAA file is larger than expected")
    return data


def refresh(cfg=None, today=None, fetch=_download, radius_km=RADIUS_KM, now=None):
    """Download the current cycle's FRQ file and write the bookmarks. Returns the new document."""
    cfg = config.load() if cfg is None else cfg
    site, mode = config.privacy_site(cfg, cfg.get("site"))
    if site is None:
        raise AirbandError("hidden privacy mode (or no site yet): nearby airports would show where the station is, "
                           "so nothing is fetched" if mode == "hidden" else "the station has no surveyed site yet")
    effective, _next = cycle(today)
    url = url_for(effective)
    try:
        blob = fetch(url)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = [n for n in z.namelist() if n.upper().endswith("FRQ.CSV")]
            if not names:
                raise AirbandError("the FAA zip has no FRQ.csv")
            text = z.read(names[0]).decode("utf-8-sig", errors="replace")
    except zipfile.BadZipFile:
        raise AirbandError("the FAA download isn't a zip") from None
    except OSError as e:
        raise AirbandError(f"download failed: {e}") from None
    rows = parse_frq(text, site, radius_km)
    doc = {"format": FORMAT, "nasr_cycle": effective.isoformat(), "fetched_utc": _iso(now), "source": url,
           "radius_km": radius_km, "site_precision": mode, "bookmarks": rows}
    _write_json(PATH, doc)
    _write_json(OWRX_PATH, owrx_bookmarks(BUILT_IN + rows))
    return doc


def _iso(t=None):
    return datetime.fromtimestamp(t or time.time(), timezone.utc).isoformat(timespec="seconds")


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def status(cfg, today=None):
    """The /api/airband answer: the built-ins, the NASR bookmarks with their cycle, and staleness."""
    today = today or datetime.now(timezone.utc).date()
    doc = _read(PATH)
    if not (isinstance(doc, dict) and doc.get("format") == FORMAT):
        doc = None
    last = _read(STATUS_PATH)
    hidden = (cfg or {}).get("location_display") == "hidden"
    current, _next = cycle(today)
    nasr = None
    if doc:
        eff = date.fromisoformat(doc["nasr_cycle"])
        age = (today - eff).days
        nasr = {"cycle": doc["nasr_cycle"], "fetched_utc": doc.get("fetched_utc"), "radius_km": doc.get("radius_km"),
                "site_precision": doc.get("site_precision"), "count": len(doc.get("bookmarks") or []),
                "age_days": q(age, "days", "calculated", "since the cycle's effective date"),
                "stale": age > CYCLE_DAYS, "bookmarks": doc.get("bookmarks") or []}
    return {"built_in": BUILT_IN, "nasr": nasr, "current_cycle": current.isoformat(),
            "refresh_allowed": not hidden,
            "refresh_note": ("hidden privacy mode: no refresh (nearby airports would show where the station is)"
                             if hidden else "Refresh fetches the current NASR cycle's frequency file from the FAA "
                                            "on the station; the web service itself never downloads."),
            "last_refresh": last if isinstance(last, dict) else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Airband bookmarks from the FAA's NASR data (offline once fetched).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="download the current NASR cycle's frequencies and write the bookmarks")
    sub.add_parser("cycle", help="print the current NASR cycle and its download URL")
    a = ap.parse_args(argv)
    if a.cmd == "cycle":
        eff, nxt = cycle()
        print(f"current cycle {eff} (next {nxt}): {url_for(eff)}")
        return 0
    try:
        doc = refresh()
    except AirbandError as e:
        _write_json(STATUS_PATH, {"ok": False, "at_utc": _iso(), "error": str(e)})
        print(f"Airband bookmarks not refreshed: {e}. The previous ones stay.", file=sys.stderr)
        return 1
    _write_json(STATUS_PATH, {"ok": True, "at_utc": _iso(), "cycle": doc["nasr_cycle"], "count": len(doc["bookmarks"])})
    print(f"Airband bookmarks: cycle {doc['nasr_cycle']}, {len(doc['bookmarks'])} within {doc['radius_km']:.0f} km.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
