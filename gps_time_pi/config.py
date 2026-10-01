"""Persistent appliance configuration.

Lives next to the code by default (override with GTP_CONFIG env var).
Holds the location-privacy mode and the trusted site position — the
surveyed-in location that keeps the almanac working when the live GPS
fix is temporarily lost.

The site position is a true long-term survey: every accepted 3D fix is
folded into a running mean and variance (Welford's algorithm), so the
standard error of the position shrinks as 1/sqrt(N) — the location
analogue of the clock walking into true time. `site_stats` reports that
precision in meters. Note the honest floor: the standard error measures
convergence of the average, but systematic GPS errors (multipath,
atmosphere) put a real-world floor around a meter or two regardless of N.
"""

import json
import math
import os
import tempfile
import threading

_PATH = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
_LOCK = threading.Lock()
_CACHE = None
_LAST_WRITE = 0.0
PERSIST_INTERVAL_S = 900  # survey updates hit disk at most every 15 min

M_PER_DEG_LAT = 111320.0

DEFAULTS = {
    "location_display": "exact",   # exact | rounded | hidden
    "site": None,
}


def load():
    global _CACHE
    if _CACHE is None:
        try:
            with open(_PATH) as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        out = dict(DEFAULTS)
        out.update(cfg if isinstance(cfg, dict) else {})
        _CACHE = out
    return _CACHE


def save(cfg, force=True):
    """Update the cache; write to disk immediately when force (settings
    changes), or at most every PERSIST_INTERVAL_S for survey updates."""
    global _CACHE, _LAST_WRITE
    import time as _time
    with _LOCK:
        _CACHE = cfg
        now = _time.time()
        if not force and now - _LAST_WRITE < PERSIST_INTERVAL_S:
            return
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_PATH))
        with os.fdopen(fd, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, _PATH)
        _LAST_WRITE = now


import atexit


@atexit.register
def _flush_on_exit():
    if _CACHE is not None:
        try:
            save(_CACHE, force=True)
        except Exception:
            pass


def _welford(site, key, x):
    """One Welford update for field `key`; means live under the plain key
    (lat/lon/alt_msl/alt_hae) so astro consumers need no changes."""
    if x is None:
        return
    mean = site.get(key)
    m2 = site.get("m2_" + key, 0.0)
    nk = site.get("n_" + key, 0)
    if mean is None:
        mean, m2, nk = x, 0.0, 0
    elif nk == 0:
        nk = 1  # legacy pre-survey mean counts as the first sample
    nk += 1
    delta = x - mean
    mean += delta / nk
    m2 += delta * (x - mean)
    site[key] = mean
    site["m2_" + key] = m2
    site["n_" + key] = nk


def update_site(lat, lon, alt_msl, alt_hae, when):
    """Fold a fresh 3D fix into the running site survey."""
    cfg = load()
    site = cfg.get("site") or {}
    # a pre-survey site (plain means, no counters) migrates transparently:
    # its existing mean becomes the first sample of the survey.
    for key, val in (("lat", lat), ("lon", lon),
                     ("alt_msl", alt_msl), ("alt_hae", alt_hae)):
        _welford(site, key, val)
    site["updated"] = when
    cfg["site"] = site
    # precision history for the convergence chart: [epoch, n, se_h_m, se_alt_m]
    import time as _time
    stats = site_stats(cfg)
    if stats.get("n", 0) >= 2:
        hist = site.setdefault("history", [])
        hist.append([round(_time.time()), stats["n"],
                     None if stats["se_horiz_m"] is None else round(stats["se_horiz_m"], 3),
                     None if stats["se_alt_m"] is None else round(stats["se_alt_m"], 3)])
        if len(hist) > 720:            # keep the file small; thin evenly
            site["history"] = hist[::2]
    save(cfg, force=False)
    return site


def reset_site():
    cfg = load()
    cfg["site"] = None
    save(cfg)


def site_stats(cfg):
    """Survey diagnostics: sample count, standard error of the mean and
    per-sample scatter, in meters. Sparse until two samples exist."""
    site = cfg.get("site")
    if not site or site.get("n_lat", 0) < 2:
        return {"n": site.get("n_lat", 0) if site else 0}

    def se_sd(key, scale):
        n = site.get("n_" + key, 0)
        m2 = site.get("m2_" + key, 0.0)
        if n < 2:
            return None, None
        var = m2 / (n - 1)
        sd = math.sqrt(max(var, 0.0)) * scale
        return sd / math.sqrt(n), sd

    lat = site.get("lat", 0.0)
    lon_scale = M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01)
    se_lat, sd_lat = se_sd("lat", M_PER_DEG_LAT)
    se_lon, sd_lon = se_sd("lon", lon_scale)
    se_alt, sd_alt = se_sd("alt_msl", 1.0)
    horiz = None
    if se_lat is not None and se_lon is not None:
        horiz = math.hypot(se_lat, se_lon)
    return {"n": site.get("n_lat", 0),
            "se_lat_m": se_lat, "se_lon_m": se_lon, "se_alt_m": se_alt,
            "sd_lat_m": sd_lat, "sd_lon_m": sd_lon, "sd_alt_m": sd_alt,
            "se_horiz_m": horiz, "updated": site.get("updated")}


def displayed_location(cfg, live):
    """Apply the privacy mode to whatever position we're exposing."""
    mode = cfg.get("location_display", "exact")
    pos = live or cfg.get("site")
    if not pos or mode == "hidden":
        return {"mode": mode, "lat": None, "lon": None}
    if mode == "rounded":
        return {"mode": mode, "lat": round(pos["lat"], 1), "lon": round(pos["lon"], 1),
                "alt_msl": None if pos.get("alt_msl") is None else round(pos["alt_msl"], -1)}
    return {"mode": mode, "lat": round(pos["lat"], 4), "lon": round(pos["lon"], 4),
            "alt_msl": pos.get("alt_msl"), "alt_hae": pos.get("alt_hae")}
