"""The offline tower cache: built by the operator from exported licence records, read by the module.

The module has no network permission and never fetches. The operator exports the records
(FCC FM Query and TV Query results for FM and ATSC, the NOAA Weather Radio transmitter list
for NOAA) as CSV files with a header row, and runs:

    python -m reference_broadcast_towers.build_cache --fm fm.csv --tv tv.csv --noaa nwr.csv \\
        --near 38.9,-77.1 --radius-km 150 --retrieved 2026-10-26 --out towers-cache.json

CSV columns are found by header name (case and spaces ignored; aliases below), never by
position, so a column the export doesn't have is simply absent. Each row needs:
  - a call sign;
  - a position: decimal `lat`/`lon` (west and south negative), or degrees/minutes/seconds with
    a hemisphere letter (`lat_deg`, `lat_min`, `lat_sec`, `lat_dir`, and the same for `lon`);
  - FM: `frequency_mhz` (88.1-107.9); ATSC: the RF `channel` (2-36; not the virtual channel);
    NOAA: `frequency_mhz` (one of the seven NWR channels, 162.400-162.550).
Optional: `facility_id`, `datum` (NAD83, WGS84 or NAD27; absent = unknown), `rc_amsl_m` (antenna
radiation centre above mean sea level), `haat_m`, `erp_kw`, `status`, `record_date`.

What the cache keeps per transmitter: the record as given, plus where it came from (file name,
SHA-256, retrieval date) and the record's own date: the spec's rule that every position carries
its source and date, because licence records can be wrong or out of date.

`--near` is rounded to 0.1 degrees before use and only that rounded point is stored, so the
cache never holds the station's surveyed position.
"""

import csv
import hashlib
import io
import json
import math
import re

from .geometry import ground_distance

FORMAT = "gpstime-towers-cache/1"
SERVICES = ("FM", "ATSC", "NOAA")
BANDWIDTH_HZ = {"FM": 200e3, "ATSC": 6e6, "NOAA": 12.5e3}
NOAA_MHZ = (162.400, 162.425, 162.450, 162.475, 162.500, 162.525, 162.550)
REJECT = ("no_callsign", "no_position", "bad_position", "bad_frequency", "duplicate", "out_of_area")

ALIASES = {
    "callsign": ("callsign", "call", "call_sign", "station"),
    "facility_id": ("facility_id", "facid", "facility", "fac_id"),
    "frequency_mhz": ("frequency_mhz", "frequency", "freq", "freq_mhz", "mhz"),
    "channel": ("channel", "rf_channel", "rfchannel", "chan"),
    "lat": ("lat", "latitude", "lat_dd", "latdd"),
    "lon": ("lon", "long", "longitude", "lon_dd", "londd"),
    "lat_deg": ("lat_deg", "latd"), "lat_min": ("lat_min", "latm"), "lat_sec": ("lat_sec", "lats"),
    "lat_dir": ("lat_dir", "ns", "n_s"),
    "lon_deg": ("lon_deg", "lond"), "lon_min": ("lon_min", "lonm"), "lon_sec": ("lon_sec", "lons"),
    "lon_dir": ("lon_dir", "ew", "w_e", "e_w"),
    "datum": ("datum", "coord_datum", "nad"),
    "rc_amsl_m": ("rc_amsl_m", "rcamsl", "rc_amsl", "amsl_m", "height_amsl_m"),
    "haat_m": ("haat_m", "haat", "haat_h", "haat_horiz"),
    "erp_kw": ("erp_kw", "erp", "erp_h", "erp_horiz"),
    "status": ("status", "licence_status", "license_status"),
    "record_date": ("record_date", "date", "updated", "last_change"),
}


def _key(h):
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def _columns(header):
    """Our field name -> the CSV column index, for the fields the header has."""
    keys = [_key(h) for h in header]
    out = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in keys:
                out[field] = keys.index(n)
                break
    return out


def _num(v):
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _dms(deg, mins, secs, hemi, neg):
    d, m, s = _num(deg), _num(mins) or 0.0, _num(secs) or 0.0
    if d is None:
        return None
    v = abs(d) + m / 60 + s / 3600
    return -v if (str(hemi or "").strip().upper() == neg or d < 0) else v


def atsc_center_hz(ch):
    """Centre frequency of a US RF TV channel (2-36, after the repack), Hz; None otherwise."""
    if 2 <= ch <= 4:
        lo = 54 + 6 * (ch - 2)
    elif 5 <= ch <= 6:
        lo = 76 + 6 * (ch - 5)
    elif 7 <= ch <= 13:
        lo = 174 + 6 * (ch - 7)
    elif 14 <= ch <= 36:
        lo = 470 + 6 * (ch - 14)
    else:
        return None
    return (lo + 3) * 1e6


def parse_rows(text, service):
    """(records, rejected counts) from one CSV export. Records are dicts, not yet de-duplicated."""
    rejected = {r: 0 for r in REJECT}
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [], rejected
    cols = _columns(rows[0])
    out = []
    for raw in rows[1:]:
        if not any(c.strip() for c in raw):
            continue
        get = lambda f: raw[cols[f]].strip() if f in cols and cols[f] < len(raw) else ""   # noqa: E731
        call = get("callsign").upper()
        if not call:
            rejected["no_callsign"] += 1
            continue
        lat, lon = _num(get("lat")), _num(get("lon"))
        if lat is None or lon is None:
            lat = _dms(get("lat_deg"), get("lat_min"), get("lat_sec"), get("lat_dir"), "S")
            lon = _dms(get("lon_deg"), get("lon_min"), get("lon_sec"), get("lon_dir"), "W")
        if lat is None or lon is None:
            rejected["no_position"] += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            rejected["bad_position"] += 1
            continue
        freq, channel = None, None
        if service == "FM":
            mhz = _num(get("frequency_mhz"))
            freq = mhz * 1e6 if mhz is not None and 87.9 <= mhz <= 107.9 else None
        elif service == "ATSC":
            ch = _num(get("channel"))
            if ch is not None and ch == int(ch):
                channel = int(ch)
                freq = atsc_center_hz(channel)
        else:
            mhz = _num(get("frequency_mhz"))
            freq = mhz * 1e6 if mhz is not None and any(abs(mhz - f) < 1e-4 for f in NOAA_MHZ) else None
        if freq is None:
            rejected["bad_frequency"] += 1
            continue
        datum = get("datum").upper().replace(" ", "") or None
        fac = get("facility_id") or None
        out.append({
            "id": f"{service}:{fac or call}:{round(freq / 1e3)}",
            "service": service, "callsign": call, "facility_id": fac,
            "frequency_hz": freq, "bandwidth_hz": BANDWIDTH_HZ[service], "channel": channel,
            "lat": round(lat, 6), "lon": round(lon, 6), "datum": datum,
            "rc_amsl_m": _num(get("rc_amsl_m")), "haat_m": _num(get("haat_m")), "erp_kw": _num(get("erp_kw")),
            "status": get("status").upper() or None, "record_date": get("record_date") or None,
        })
    return out, rejected


def build(inputs, near, radius_km, retrieved, built_utc):
    """The cache document. inputs: [(service, file name, text)]; near: (lat, lon), rounded here."""
    center = (round(near[0], 1), round(near[1], 1))
    towers, seen, sources = [], set(), []
    rejected = {r: 0 for r in REJECT}
    for service, name, text in inputs:
        if service not in SERVICES:
            raise ValueError(f"unknown service {service!r}")
        recs, rej = parse_rows(text, service)
        for k, v in rej.items():
            rejected[k] += v
        src = {"service": service, "file": name, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
               "retrieved": retrieved, "rows_kept": 0}
        for r in recs:
            if ground_distance(center[0], center[1], r["lat"], r["lon"]) > radius_km * 1000:
                rejected["out_of_area"] += 1
                continue
            if r["id"] in seen:
                rejected["duplicate"] += 1
                continue
            seen.add(r["id"])
            r["source"] = f"{name} (retrieved {retrieved})"
            towers.append(r)
            src["rows_kept"] += 1
        sources.append(src)
    towers.sort(key=lambda r: (SERVICES.index(r["service"]), r["frequency_hz"], r["callsign"]))
    return {"format": FORMAT, "built_utc": built_utc, "area": {"center_lat": center[0], "center_lon": center[1],
            "radius_km": radius_km, "note": "centre rounded to 0.1°; not the station's position"},
            "sources": sources, "rejected": rejected, "towers": towers}


def load(path):
    """(cache dict, None) or (None, reason). Never raises for a missing or bad file."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return None, f"no tower cache at {path} (build one with build_cache.py)"
    except (OSError, ValueError) as e:
        return None, f"the tower cache could not be read: {e}"
    if not isinstance(doc, dict) or doc.get("format") != FORMAT or not isinstance(doc.get("towers"), list):
        return None, f"not a tower cache (expected format {FORMAT})"
    return doc, None
