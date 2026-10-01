"""gpsd interface: position (TPV), sky view (SKY), satellite table, and
maintenance of the trusted site position."""

import json
import socket
import time

from . import config

GNSS = {0: "GPS", 1: "SBAS", 2: "Galileo", 3: "BeiDou", 4: "IMES",
        5: "QZSS", 6: "GLONASS", 7: "NavIC"}

_cache = {"t": 0.0, "tpv": {}, "sky": {}, "version": {}, "device": {}}
_last_site_write = 0.0
_FIXES = []  # (epoch, lat, lon) ring of survey-accepted fixes, session-scoped


def recent_fixes():
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


def snapshot():
    """Cached gpsd view; refreshes at most every 5 s. Also feeds the
    trusted site from good 3D fixes (at most once a minute)."""
    global _last_site_write
    now = time.time()
    if now - _cache["t"] > 5:
        tpv, sky, ver, dev = _poll()
        if tpv or sky or now - _cache["t"] > 60:
            _cache.update(t=now, tpv=tpv or _cache["tpv"], sky=sky or _cache["sky"],
                          version=ver or _cache["version"], device=dev or _cache["device"])
    tpv, sky = _cache["tpv"], _cache["sky"]

    mode = tpv.get("mode")
    fix = {0: None, 1: None, 2: "2D", 3: "3D"}.get(mode)
    live = None
    if mode and mode >= 2 and "lat" in tpv:
        live = {"lat": tpv["lat"], "lon": tpv["lon"],
                "alt_msl": tpv.get("altMSL"), "alt_hae": tpv.get("altHAE", tpv.get("alt")),
                "time": tpv.get("time")}
        if mode == 3 and now - _last_site_write > 60:
            try:
                config.update_site(live["lat"], live["lon"], live["alt_msl"],
                                   live["alt_hae"], tpv.get("time"))
                _last_site_write = now
                _FIXES.append((now, live["lat"], live["lon"]))
                if len(_FIXES) > 720:
                    del _FIXES[0]
            except Exception:  # noqa: BLE001
                pass

    sats = []
    for s in sky.get("satellites", []):
        sats.append({"id": s.get("PRN"),
                     "gnss": GNSS.get(s.get("gnssid", -1),
                                      "SBAS" if (s.get("PRN") or 0) > 32 else "GPS"),
                     "el": s.get("el"), "az": s.get("az"),
                     "snr": s.get("ss", 0), "used": bool(s.get("used"))})
    sats.sort(key=lambda x: (-x["used"], -(x["snr"] or 0)))

    return {
        "fix": fix,
        "mode": mode,
        "live": live,
        "sats": sats,
        "used": sum(1 for x in sats if x["used"]),
        "visible": len(sats),
        "tdop": sky.get("tdop"),
        "hdop": sky.get("hdop"),
        "data_age_s": round(now - _cache["t"], 1),
        "gpsd_version": _cache["version"].get("release"),
        "receiver": {
            "driver": _cache["device"].get("driver"),
            "firmware": _cache["device"].get("subtype"),
            "firmware1": _cache["device"].get("subtype1"),
            "path": _cache["device"].get("path"),
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
