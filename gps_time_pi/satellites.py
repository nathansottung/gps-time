"""Individual satellites from cached orbital elements (TLEs).

The elements are `external` data: someone else's tracking, good for days, not
months. They are read from files in a cache directory on the station
(GTP_TLE_DIR). Nothing in this module uses the network; getting the files is a
separate, explicit step (gps_time_pi/tle_fetch.py, or copying them over), so
every calculation here works offline once the elements are there.

For one satellite and the station's position this gives:
  - now: azimuth, altitude, range, angular speed across the sky, and whether
    it is in sunlight, penumbra or umbra (`modeled` from the elements);
  - passes: rise, culmination, set, the moments it enters or leaves the
    Earth's shadow, and the interval in which it could be seen (`predicted`).

"Could be seen" is geometry only: above 10 degrees, not in the umbra, and the
Sun at least 6 degrees below the station's horizon. It says nothing about
brightness, cloud or obstructions.

Propagation is SGP4 (the `sgp4` package, installed with Skyfield). The shadow
test and the Sun's position are this project's own (gps_time_pi/shadow.py).
"""

import json
import math
import os
import re
import threading
from datetime import datetime, timedelta, timezone

from . import shadow

TLE_DIR = os.environ.get("GTP_TLE_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json"))), "tle")
MANIFEST = "manifest.json"
STALE_DAYS = 14.0              # LEO elements older than this give poor predictions
VISIBLE_MIN_ALT_DEG = 10.0
VISIBLE_SUN_ALT_DEG = -6.0
PASS_STEP_S = 30
PASS_FINE_STEP_S = 2
MAX_PASSES = 10
FEATURED = (25544, 48274)      # ISS, CSS (Tianhe): shown first when they are in the cache
SEARCH_LIMIT = 25

try:
    from sgp4.api import Satrec, jday
    SGP4 = {"available": True, "reason": None}
except Exception as _e:  # noqa: BLE001
    SGP4 = {"available": False, "reason": f"The sgp4 package could not be imported ({_e}). It is installed with "
                                          "Skyfield by install.sh."}

NO_CACHE = ("No orbital elements on the station. They need the Internet once: run "
            "`python -m gps_time_pi.tle_fetch --group stations` on the station, or copy a TLE file into the "
            "cache directory. Calculations then work offline.")
MEANING = ("Predictions from orbital elements. 'Could be seen' means above 10°, not in the Earth's umbra, and the "
           "Sun at least 6° below the horizon. It says nothing about brightness, cloud or obstructions.")


# ── TLE parsing ─────────────────────────────────────────────────────────────

def tle_checksum(line):
    """The modulo-10 checksum of the first 68 characters of a TLE line."""
    return sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in line[:68]) % 10


def valid_tle_line(line, number):
    return (len(line) == 69 and line[0] == str(number) and line[1] == " "
            and line[68].isdigit() and tle_checksum(line) == int(line[68]))


def tle_epoch(line1):
    """Epoch of the elements as Unix seconds (columns 19-32: YYDDD.dddddddd)."""
    yy = int(line1[18:20])
    year = 2000 + yy if yy < 57 else 1900 + yy
    day = float(line1[20:32])
    return (datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1.0)).timestamp()


def parse_tle_text(text):
    """Element sets from 2-line or 3-line (name first) TLE text.
    Returns (list of {'norad', 'name', 'line1', 'line2', 'epoch'}, number of rejected sets).
    A set whose length, line number, checksum or catalogue number is wrong is rejected."""
    lines = [l.rstrip("\r\n") for l in text.splitlines() if l.strip()]
    sets, rejected, i = [], 0, 0
    while i < len(lines):
        if lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            name, l1, l2 = None, lines[i], lines[i + 1]
            i += 2
        elif i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            name, l1, l2 = lines[i].strip(), lines[i + 1], lines[i + 2]
            if name.startswith("0 "):
                name = name[2:].strip()
            i += 3
        else:
            i += 1
            continue
        l1, l2 = l1.rstrip(), l2.rstrip()
        if not (valid_tle_line(l1, 1) and valid_tle_line(l2, 2) and l1[2:7] == l2[2:7] and l1[2:7].strip().isdigit()):
            rejected += 1
            continue
        try:
            epoch = tle_epoch(l1)
        except ValueError:
            rejected += 1
            continue
        norad = int(l1[2:7])
        sets.append({"norad": norad, "name": name or f"NORAD {norad}", "line1": l1, "line2": l2, "epoch": epoch})
    return sets, rejected


# ── cache ───────────────────────────────────────────────────────────────────

_CACHE = {"key": None, "value": None}
_CACHE_LOCK = threading.Lock()


def _iso(unix_s):
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=unix_s)).isoformat(timespec="seconds")


def load_cache(directory=None):
    """Every element set in the cache directory's *.tle files.
    Returns {'dir', 'sats': {norad: set}, 'groups': [...], 'problems': [...]}.
    Re-read only when a file changes. Never raises."""
    directory = directory or TLE_DIR
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".tle"))
        key = (directory, tuple((n, os.stat(os.path.join(directory, n)).st_mtime_ns) for n in names),
               os.stat(os.path.join(directory, MANIFEST)).st_mtime_ns
               if os.path.exists(os.path.join(directory, MANIFEST)) else None)
    except OSError:
        return {"dir": directory, "sats": {}, "groups": [], "problems": []}
    with _CACHE_LOCK:
        if _CACHE["key"] == key:
            return _CACHE["value"]
    manifest, problems = {}, []
    try:
        with open(os.path.join(directory, MANIFEST), encoding="utf-8") as f:
            manifest = json.load(f)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        problems.append(f"{MANIFEST}: {e}")
    sats, groups = {}, []
    for n in names:
        group = n[:-4]
        try:
            with open(os.path.join(directory, n), encoding="ascii", errors="replace") as f:
                sets, rejected = parse_tle_text(f.read())
        except OSError as e:
            problems.append(f"{n}: {e.strerror or e}")
            continue
        for s in sets:
            old = sats.get(s["norad"])
            if old is None or s["epoch"] > old["epoch"]:        # the newer elements win
                sats[s["norad"]] = {**s, "group": group}
        info = manifest.get(group) if isinstance(manifest, dict) else None
        info = info if isinstance(info, dict) else {}
        epochs = [s["epoch"] for s in sets]
        groups.append({"group": group, "file": n, "count": len(sets), "rejected": rejected,
                       "source": info.get("source"), "fetched_utc": info.get("fetched_utc"),
                       "newest_epoch_utc": _iso(max(epochs)) if epochs else None,
                       "oldest_epoch_utc": _iso(min(epochs)) if epochs else None})
        if rejected:
            problems.append(f"{n}: {rejected} element set(s) rejected (bad length, checksum or number)")
    value = {"dir": directory, "sats": sats, "groups": groups, "problems": problems}
    with _CACHE_LOCK:
        _CACHE.update(key=key, value=value)
    return value


# ── geometry ────────────────────────────────────────────────────────────────

def _satrec(elements):
    return Satrec.twoline2rv(elements["line1"], elements["line2"])


def position_ecef(sat, when):
    """Earth-fixed position (km) of an SGP4 satellite at a UTC datetime, or
    None when SGP4 reports an error (decayed, or elements too old to use).
    SGP4's TEME frame is turned by Greenwich sidereal time; polar motion is ignored."""
    w = when.astimezone(timezone.utc)
    jd, fr = jday(w.year, w.month, w.day, w.hour, w.minute, w.second + w.microsecond / 1e6)
    err, r, _v = sat.sgp4(jd, fr)
    if err != 0 or any(math.isnan(c) for c in r):
        return None
    theta = math.radians(shadow.gmst_deg(jd + fr))
    c, s = math.cos(theta), math.sin(theta)
    return (c * r[0] + s * r[1], -s * r[0] + c * r[1], r[2])


def look(obs, sat, when, sun=None):
    """What the station sees of one satellite at one moment, or None on an SGP4 error."""
    pos = position_ecef(sat, when)
    if pos is None:
        return None
    rel = tuple(pos[i] - obs.pos[i] for i in range(3))
    az, alt = obs.altaz(rel)
    sun_unit, sun_dist = sun or shadow.sun_ecef(when)
    state, fraction = shadow.shadow_state(pos, sun_unit, sun_dist)
    return {"t": when, "az": az, "alt": alt, "range_km": math.sqrt(sum(c * c for c in rel)),
            "height_km": math.sqrt(sum(c * c for c in pos)) - shadow.R_EARTH_KM,
            "state": state, "sunlit_fraction": fraction, "rel": rel,
            "sun_alt": obs.altaz(sun_unit)[1]}


def angular_speed(obs, sat, when):
    """Speed across the sky in degrees per second (from two looks one second apart)."""
    a, b = look(obs, sat, when), look(obs, sat, when + timedelta(seconds=1))
    if not a or not b:
        return None
    dot = sum(x * y for x, y in zip(a["rel"], b["rel"])) / (a["range_km"] * b["range_km"])
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def _visible(p):
    return p["alt"] >= VISIBLE_MIN_ALT_DEG and p["state"] != shadow.UMBRA and p["sun_alt"] <= VISIBLE_SUN_ALT_DEG


def _refine(obs, sat, t0, t1, test):
    """The moment between t0 and t1 (to about half a second) at which test(look) changes."""
    first = test(look(obs, sat, t0))
    for _ in range(12):
        mid = t0 + (t1 - t0) / 2
        p = look(obs, sat, mid)
        if p is None:
            break
        if test(p) == first:
            t0 = mid
        else:
            t1 = mid
    return t0 + (t1 - t0) / 2


def _point(p):
    return {"utc": p["t"].isoformat(timespec="seconds"), "azimuth_deg": round(p["az"], 1),
            "altitude_deg": round(p["alt"], 1), "range_km": round(p["range_km"], 1), "state": p["state"]}


def passes(obs, sat, start, hours=24.0, max_passes=MAX_PASSES):
    """Passes above the horizon starting within `hours` of `start`.

    Each pass: rise, culmination, set (time, azimuth, altitude, range, shadow
    state), the shadow changes during it, and the interval in which it could
    be seen (None if there is none). A pass already under way at `start` has
    rise None; one still up at the end of the search has set None."""
    out, t, end = [], start, start + timedelta(hours=hours)
    prev = look(obs, sat, t)
    if prev is None:
        return out
    step = timedelta(seconds=PASS_STEP_S)
    current = [prev] if prev["alt"] > 0 else None
    rise = None
    while t < end or current is not None:
        if t >= end + timedelta(hours=2):           # a pass that never ends within reason (high orbit)
            break
        t += step
        p = look(obs, sat, t)
        if p is None:
            break
        if current is None and p["alt"] > 0:
            if prev["t"] >= end:
                break
            rise = _refine(obs, sat, prev["t"], t, lambda q: q is not None and q["alt"] > 0)
            current = [look(obs, sat, rise), p]
        elif current is not None and p["alt"] <= 0:
            set_t = _refine(obs, sat, prev["t"], t, lambda q: q is not None and q["alt"] > 0)
            out.append(_describe_pass(obs, sat, rise, set_t, current))
            current, rise = None, None
            if len(out) >= max_passes:
                break
        elif current is not None:
            current.append(p)
        prev = p
    if current is not None and len(out) < max_passes:
        out.append(_describe_pass(obs, sat, rise, None, current))
    return out


def _describe_pass(obs, sat, rise, set_t, coarse):
    t0 = rise or coarse[0]["t"]
    t1 = set_t or coarse[-1]["t"]
    n = max(2, int((t1 - t0).total_seconds() // PASS_FINE_STEP_S) + 1)
    n = min(n, 4000)
    pts = [p for p in (look(obs, sat, t0 + (t1 - t0) * (i / (n - 1))) for i in range(n)) if p]
    top = max(pts, key=lambda p: p["alt"])
    changes = []
    for a, b in zip(pts, pts[1:]):
        if a["state"] != b["state"]:
            when = _refine(obs, sat, a["t"], b["t"], lambda q, s=a["state"]: q is not None and q["state"] == s)
            kind = ("umbra entry" if b["state"] == shadow.UMBRA else
                    "shadow exit" if b["state"] == shadow.SUNLIT else
                    "penumbra entry" if a["state"] == shadow.SUNLIT else "umbra exit")
            changes.append({"utc": when.isoformat(timespec="seconds"), "kind": kind,
                            "from": a["state"], "to": b["state"],
                            "azimuth_deg": round(b["az"], 1), "altitude_deg": round(b["alt"], 1)})
    vis = [p for p in pts if _visible(p)]
    visible = None
    if vis:
        best = max(vis, key=lambda p: p["alt"])
        visible = {"start_utc": vis[0]["t"].isoformat(timespec="seconds"),
                   "end_utc": vis[-1]["t"].isoformat(timespec="seconds"),
                   "duration_s": round((vis[-1]["t"] - vis[0]["t"]).total_seconds()),
                   "max_altitude_deg": round(best["alt"], 1), "max_azimuth_deg": round(best["az"], 1)}
    return {"rise": _point(pts[0]) if rise else None,
            "culmination": _point(top),
            "set": _point(pts[-1]) if set_t else None,
            "in_progress": rise is None,
            "duration_s": round((t1 - t0).total_seconds()),
            "shadow_changes": changes,
            "visible": visible,
            "sun_altitude_deg": round(top["sun_alt"], 1),
            "provenance": "predicted"}


# ── payloads ────────────────────────────────────────────────────────────────

def _age(elements, when):
    days = (when.timestamp() - elements["epoch"]) / 86400.0
    return {"norad": elements["norad"], "name": elements["name"], "group": elements.get("group"),
            "epoch_utc": _iso(elements["epoch"]), "age_days": round(days, 2),
            "stale": abs(days) > STALE_DAYS,
            "age_note": (f"Elements are {abs(days):.0f} days {'old' if days >= 0 else 'in the future'}: "
                         f"predictions are unreliable beyond about {STALE_DAYS:g} days." if abs(days) > STALE_DAYS else None)}


def now_state(obs, elements, when):
    """Where one satellite is now, with the age of its elements."""
    sat = _satrec(elements)
    p = look(obs, sat, when)
    info = _age(elements, when)
    if p is None:
        return {**info, "available": False,
                "reason": "SGP4 could not propagate these elements to this time (decayed, or far too old)."}
    speed = angular_speed(obs, sat, when)
    return {**info, "available": True, "reason": None, "provenance": "modeled",
            "azimuth_deg": round(p["az"], 1), "altitude_deg": round(p["alt"], 1),
            "above_horizon": p["alt"] > 0, "range_km": round(p["range_km"], 1),
            "height_km": round(p["height_km"]), "angular_speed_deg_s": None if speed is None else round(speed, 3),
            "state": p["state"], "sunlit_fraction": round(p["sunlit_fraction"], 3),
            "could_be_seen": _visible(p)}


def summary(cache, when):
    """Cache status for the payload: groups, counts, and how old the elements are."""
    epochs = [s["epoch"] for s in cache["sats"].values()]
    now = when.timestamp()
    return {"dir": cache["dir"], "satellites": len(cache["sats"]), "groups": cache["groups"],
            "newest_epoch_utc": _iso(max(epochs)) if epochs else None,
            "newest_age_days": round((now - max(epochs)) / 86400.0, 2) if epochs else None,
            "oldest_age_days": round((now - min(epochs)) / 86400.0, 2) if epochs else None,
            "stale_after_days": STALE_DAYS, "problems": cache["problems"], "provenance": "external"}


def search(cache, text, when, limit=SEARCH_LIMIT):
    """Satellites whose name contains `text` or whose catalogue number equals it."""
    q = (text or "").strip().upper()
    if not q:
        return []
    hits = [s for s in cache["sats"].values() if q in s["name"].upper() or q == str(s["norad"])]
    hits.sort(key=lambda s: (s["name"], s["norad"]))
    return [_age(s, when) for s in hits[:limit]]


def report(site, when, norad=None, query=None, directory=None, hours=24.0):
    """The /api/satellites payload.

    site: the position to compute for (already reduced by the privacy mode).
    norad: catalogue number of the satellite to give passes for."""
    base = {"available": False, "reason": None, "provenance": "external", "meaning": MEANING,
            "as_of_utc": when.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "cache": None, "featured": [], "satellite": None, "passes": [], "matches": []}
    if not SGP4["available"]:
        return {**base, "reason": SGP4["reason"]}
    cache = load_cache(directory)
    base["cache"] = summary(cache, when)
    if not cache["sats"]:
        return {**base, "reason": NO_CACHE}
    obs = shadow.Observer.from_site(site)
    featured = [cache["sats"][n] for n in FEATURED if n in cache["sats"]]
    out = {**base, "available": True,
           "featured": [now_state(obs, e, when) for e in featured],
           "matches": search(cache, query, when)}
    if norad is None and featured:
        norad = featured[0]["norad"]
    if norad is not None:
        elements = cache["sats"].get(norad)
        if elements is None:
            out["satellite"] = {"norad": norad, "available": False,
                                "reason": f"NORAD {norad} is not in the cached elements."}
        else:
            out["satellite"] = now_state(obs, elements, when)
            if out["satellite"]["available"]:
                out["passes"] = passes(obs, _satrec(elements), when, hours)
    out["window_hours"] = hours
    return out


def valid_group(name):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name or ""))
