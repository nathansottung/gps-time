"""gpsd interface: position (TPV), sky view (SKY), satellite table, and
maintenance of the trusted site position.

Collection contract (CHG-001):

* gpsd is polled by one background collector thread (`start_collector`),
  never by HTTP request handling. `snapshot()` only reads the cache, so
  browser/API traffic cannot change how often GNSS data is sampled.
* A TPV/SKY report is "fresh" only when it arrived in the most recent poll.
  Empty polls never refresh cached data or its age; ages come from a
  monotonic clock.
* A survey sample is identified by its receiver epoch (TPV `time`). Only a
  fresh, valid 3D fix whose epoch is strictly later than the last accepted
  epoch can advance the survey, at most once per SURVEY_MIN_SPACING_S.
  Everything else is counted as a rejection reason, never as evidence.
"""

import json
import math
import re
import socket
import threading
import time
from datetime import datetime, timezone

from . import config

GNSS = {0: "GPS", 1: "SBAS", 2: "Galileo", 3: "BeiDou", 4: "IMES",
        5: "QZSS", 6: "GLONASS", 7: "NavIC"}

POLL_INTERVAL_S = 5.0        # collector cadence
TPV_STALE_S = 10.0           # older TPV is shown as stale, not as a live fix
SKY_STALE_S = 10.0
SURVEY_MIN_SPACING_S = 60.0  # at most one survey sample per minute

_STATE_LOCK = threading.Lock()   # guards _cache / _ingest / _FIXES
_POLL_LOCK = threading.Lock()    # single-flight: one gpsd poll + ingest at a time
_cache = {"tpv": {}, "tpv_rx": None, "sky": {}, "sky_rx": None,
          "version": {}, "device": {}, "polls": 0}
_REJECT_REASONS = ("no_tpv", "no_3d_fix", "invalid", "repeat_epoch",
                   "older_epoch", "rate_limited")
_ingest = {"last_epoch": None, "last_accept_mono": None, "accepted": 0,
           "rejected": dict.fromkeys(_REJECT_REASONS, 0), "last_reason": None}
_FIXES = []  # (epoch, lat, lon) ring of survey-accepted fixes, session-scoped
_collector = {"thread": None, "stop": None}
_monotonic = time.monotonic  # indirection so tests can drive a fake clock


def recent_fixes():
    with _STATE_LOCK:
        return list(_FIXES)


def _poll(timeout=3.0):
    """Grab the latest TPV and SKY from gpsd, plus VERSION/DEVICES metadata."""
    tpv, sky = {}, {}
    ver, dev = {}, {}
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=2) as s:
            s.sendall(b'?WATCH={"enable":true,"json":true}\n')
            s.settimeout(1.5)
            buf, deadline = b"", time.time() + timeout
            while time.time() < deadline and not (tpv and sky):
                try:
                    buf += s.recv(65536)
                except socket.timeout:
                    break
                *lines, buf = buf.split(b"\n")
                for line in lines:
                    try:
                        obj = json.loads(line)
                    except Exception:  # noqa: BLE001
                        continue
                    if obj.get("class") == "TPV" and obj.get("mode", 0) >= 2:
                        tpv = obj
                    elif obj.get("class") == "TPV" and not tpv:
                        tpv = obj
                    elif obj.get("class") == "SKY" and obj.get("satellites"):
                        sky = obj
                    elif obj.get("class") == "VERSION":
                        ver = obj
                    elif obj.get("class") == "DEVICES" and obj.get("devices"):
                        dev = obj["devices"][0]
    except Exception:  # noqa: BLE001
        pass
    return tpv, sky, ver, dev


_ISO = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.\d+)?Z$")


def parse_epoch(text):
    """gpsd TPV time ('2026-09-20T12:00:00.000Z') -> UTC epoch seconds, or None."""
    m = _ISO.match(text or "") if isinstance(text, str) else None
    if not m:
        return None
    y, mo, d, h, mi, s = (int(g) for g in m.groups()[:6])
    try:  # datetime validates ranges (timegm would silently normalize them)
        whole = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).timestamp()
    except (ValueError, OverflowError):
        return None
    return whole + (float(m.group(7)) if m.group(7) else 0.0)


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _candidate(tpv):
    """Validate a fresh TPV as a survey sample: (epoch, fields) or (None, reason)."""
    if not tpv:
        return None, "no_tpv"
    if tpv.get("mode") != 3:
        return None, "no_3d_fix"
    lat, lon = tpv.get("lat"), tpv.get("lon")
    epoch = parse_epoch(tpv.get("time"))
    if not (_finite(lat) and _finite(lon)) or abs(lat) > 90 or abs(lon) > 180 or epoch is None:
        return None, "invalid"
    alt_msl = tpv.get("altMSL")
    alt_hae = tpv.get("altHAE", tpv.get("alt"))
    return epoch, {"lat": float(lat), "lon": float(lon),
                   "alt_msl": float(alt_msl) if _finite(alt_msl) else None,
                   "alt_hae": float(alt_hae) if _finite(alt_hae) else None,
                   "time": tpv.get("time")}


def _reject(reason):
    _ingest["rejected"][reason] += 1
    _ingest["last_reason"] = reason


def poll_once():
    """One collector step: poll gpsd, refresh only what actually arrived,
    and offer the fresh TPV (if any) to the survey. Returns the ingest reason."""
    with _POLL_LOCK:
        tpv, sky, ver, dev = _poll()
        now = _monotonic()
        with _STATE_LOCK:
            _cache["polls"] += 1
            if tpv:
                _cache["tpv"], _cache["tpv_rx"] = tpv, now
            if sky:
                _cache["sky"], _cache["sky_rx"] = sky, now
            if ver:
                _cache["version"] = ver
            if dev:
                _cache["device"] = dev

            epoch, fields = _candidate(tpv)   # only this poll's TPV is eligible
            if epoch is None:
                _reject(fields)
                return fields
            last = _ingest["last_epoch"]
            if last is not None and epoch <= last:
                reason = "repeat_epoch" if epoch == last else "older_epoch"
                _reject(reason)
                return reason
            since = _ingest["last_accept_mono"]
            if since is not None and now - since < SURVEY_MIN_SPACING_S:
                _reject("rate_limited")
                return "rate_limited"
            # claim the epoch before the (possibly slow) persistence call
            _ingest["last_epoch"], _ingest["last_accept_mono"] = epoch, now
        try:
            config.update_site(fields["lat"], fields["lon"], fields["alt_msl"],
                               fields["alt_hae"], fields["time"])
        except Exception:  # noqa: BLE001
            return "persist_error"
        with _STATE_LOCK:
            _ingest["accepted"] += 1
            _ingest["last_reason"] = "accepted"
            _FIXES.append((epoch, fields["lat"], fields["lon"]))
            if len(_FIXES) > 720:
                del _FIXES[0]
        return "accepted"


def _collector_loop(stop, interval):
    while not stop.is_set():
        try:
            poll_once()
        except Exception:  # noqa: BLE001 — the collector must never die
            pass
        stop.wait(interval)


def start_collector(interval=POLL_INTERVAL_S):
    """Start the background GNSS collector (idempotent)."""
    t = _collector["thread"]
    if t is not None and t.is_alive():
        return t
    stop = threading.Event()
    t = threading.Thread(target=_collector_loop, args=(stop, interval),
                         name="gnss-collector", daemon=True)
    _collector.update(thread=t, stop=stop)
    t.start()
    return t


def stop_collector(timeout=5.0):
    t, stop = _collector["thread"], _collector["stop"]
    if stop is not None:
        stop.set()
    if t is not None:
        t.join(timeout)
    _collector.update(thread=None, stop=None)


def ingest_status():
    with _STATE_LOCK:
        return {"accepted_this_session": _ingest["accepted"],
                "rejected_this_session": dict(_ingest["rejected"]),
                "last_reason": _ingest["last_reason"],
                "collector_running": bool(_collector["thread"] and _collector["thread"].is_alive())}


def _age(rx, now):
    return None if rx is None else round(now - rx, 1)


def snapshot():
    """Read-only view of the collector cache. Never polls gpsd and never
    touches the survey. A fix older than TPV_STALE_S is reported as
    `last_fix` with its age, not as a live `fix`."""
    now = _monotonic()
    with _STATE_LOCK:
        tpv, sky = dict(_cache["tpv"]), dict(_cache["sky"])
        tpv_age, sky_age = _age(_cache["tpv_rx"], now), _age(_cache["sky_rx"], now)
        version, device = dict(_cache["version"]), dict(_cache["device"])

    tpv_stale = tpv_age is None or tpv_age > TPV_STALE_S
    sky_stale = sky_age is None or sky_age > SKY_STALE_S
    mode = tpv.get("mode")
    last_fix = {0: None, 1: None, 2: "2D", 3: "3D"}.get(mode)
    live = None
    if not tpv_stale and mode and mode >= 2 and "lat" in tpv:
        live = {"lat": tpv["lat"], "lon": tpv["lon"],
                "alt_msl": tpv.get("altMSL"), "alt_hae": tpv.get("altHAE", tpv.get("alt")),
                "time": tpv.get("time")}

    sats = []
    for s in sky.get("satellites", []):
        sats.append({"id": s.get("PRN"),
                     "gnss": GNSS.get(s.get("gnssid", -1),
                                      "SBAS" if (s.get("PRN") or 0) > 32 else "GPS"),
                     "el": s.get("el"), "az": s.get("az"),
                     "snr": s.get("ss", 0), "used": bool(s.get("used"))})
    sats.sort(key=lambda x: (-x["used"], -(x["snr"] or 0)))

    return {
        "fix": None if tpv_stale else last_fix,
        "mode": None if tpv_stale else mode,
        "live": live,
        "last_fix": last_fix,
        "last_fix_time": tpv.get("time"),
        "stale": tpv_stale,
        "sky_stale": sky_stale,
        "sats": sats,
        "used": sum(1 for x in sats if x["used"]),
        "visible": len(sats),
        "tdop": sky.get("tdop"),
        "hdop": sky.get("hdop"),
        "data_age_s": tpv_age,
        "sky_age_s": sky_age,
        "gpsd_version": version.get("release"),
        "receiver": {
            "driver": device.get("driver"),
            "firmware": device.get("subtype"),
            "firmware1": device.get("subtype1"),
            "path": device.get("path"),
        },
    }


def observing_site():
    """The position astronomy should use: live fix if present, else the
    trusted stored site (honestly labeled). Returns (site, provenance)."""
    snap = snapshot()
    cfg = config.load()
    if snap["live"]:
        return snap["live"], "live"
    if cfg.get("site"):
        return cfg["site"], "stored"
    return None, "none"
