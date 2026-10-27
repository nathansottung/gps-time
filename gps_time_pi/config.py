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
_LOCK = threading.RLock()  # re-entrant: survey updates hold it across save()
_CACHE = None
_LAST_WRITE = 0.0
PERSIST_INTERVAL_S = 900  # survey updates hit disk at most every 15 min

M_PER_DEG_LAT = 111320.0

DEFAULTS = {
    "location_display": "exact",   # exact | rounded | hidden
    "site": None,
    "timezone": None,              # IANA name: operator override for local-time display; None = automatic
    "sky_quality_share": False,    # opt-in: the sky-quality summary in the capability record and the export
}


PREV_SUFFIX = ".prev"
_STATUS = {"loaded_from": None, "corrupt_moved_to": None, "last_write_utc": None,
           "last_write_error": None}


def _utc_stamp():
    import time as _time
    return _time.strftime("%Y%m%dT%H%M%SZ", _time.gmtime())


def _read_json(path):
    """Parsed dict, or raise ValueError if the file exists but isn't a JSON object."""
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(str(e)) from e
    if not isinstance(data, dict):
        raise ValueError("config is not a JSON object")
    return data


def _set_aside(path):
    """Move an unreadable file out of the way, keeping its bytes for inspection."""
    target = f"{path}.corrupt-{_utc_stamp()}"
    n = 1
    while os.path.exists(target):
        target = f"{path}.corrupt-{_utc_stamp()}-{n}"
        n += 1
    os.replace(path, target)
    return target


def load():
    """Load config.json. An unreadable file is set aside (never overwritten) and
    the previous checkpoint (config.json.prev) is used if it is readable."""
    global _CACHE
    with _LOCK:
        if _CACHE is None:
            cfg, source = {}, "defaults"
            try:
                cfg, source = _read_json(_PATH), "config"
            except FileNotFoundError:
                pass
            except ValueError:
                _STATUS["corrupt_moved_to"] = _set_aside(_PATH)
            except OSError as e:
                _STATUS["last_write_error"] = f"read failed: {e}"
            if source != "config":
                try:
                    cfg, source = _read_json(_PATH + PREV_SUFFIX), "previous_checkpoint"
                except (OSError, ValueError):
                    pass
            _STATUS["loaded_from"] = source
            out = dict(DEFAULTS)
            out.update(cfg)
            _CACHE = out
        return _CACHE


def persistence_status():
    """Where the config came from, any corrupt file set aside, last write."""
    with _LOCK:
        return dict(_STATUS, path=_PATH, previous_checkpoint=_PATH + PREV_SUFFIX)


def _fsync_dir(directory):
    if os.name != "posix":          # directory fsync is a POSIX concept
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path, text):
    """Write text to path via temp file + fsync + rename (+ directory fsync)."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".config-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    _fsync_dir(directory)


def _write(cfg):
    os.makedirs(os.path.dirname(os.path.abspath(_PATH)), exist_ok=True)
    text = json.dumps(cfg, indent=2)            # serialize first: a failure leaves files untouched
    try:
        with open(_PATH, encoding="utf-8") as f:
            current = f.read()
        json.loads(current)
    except (OSError, ValueError):
        current = None                          # nothing valid to keep as the previous checkpoint
    if current is not None and current != text:
        _atomic_write(_PATH + PREV_SUFFIX, current)
    _atomic_write(_PATH, text)


def save(cfg, force=True):
    """Update the cache; write to disk immediately when force (settings
    changes), or at most every PERSIST_INTERVAL_S for survey updates.
    Each write keeps the previous good file as config.json.prev."""
    global _CACHE, _LAST_WRITE
    import time as _time
    with _LOCK:
        _CACHE = cfg
        now = _time.time()
        if not force and now - _LAST_WRITE < PERSIST_INTERVAL_S:
            return
        try:
            _write(cfg)
        except Exception as e:
            _STATUS["last_write_error"] = f"{_utc_stamp()}: {e}"
            raise
        _STATUS["last_write_utc"] = _utc_stamp()
        _STATUS["last_write_error"] = None
        _LAST_WRITE = now


def flush():
    """Write any cached state now (used at shutdown)."""
    with _LOCK:
        if _CACHE is not None:
            save(_CACHE, force=True)


import atexit


@atexit.register
def _flush_on_exit():
    try:
        flush()
    except Exception:
        pass


def _handle_sigterm(signum, frame):
    """systemd stops the service with SIGTERM; Python's default action exits
    without running atexit, which lost up to PERSIST_INTERVAL_S of survey data."""
    try:
        flush()
    finally:
        raise SystemExit(0)


def install_signal_handlers():
    """Install the SIGTERM flush handler. Must be called from the main thread."""
    import signal
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigterm)


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


INGEST_RULE = "fresh-epoch-v1"


def update_site(lat, lon, alt_msl, alt_hae, when):
    """Fold a fresh 3D fix into the running site survey.

    Callers must only pass genuinely fresh, previously unseen receiver epochs
    (see gps.poll_once). Samples accumulated before that rule existed are
    preserved but recorded as legacy: the first update under the rule stores
    how many samples were already in the survey."""
    with _LOCK:
        return _update_site(lat, lon, alt_msl, alt_hae, when)


def _update_site(lat, lon, alt_msl, alt_hae, when):
    cfg = load()
    site = cfg.get("site") or {}
    if site.get("ingest_rule") != INGEST_RULE:
        legacy = site.get("n_lat", 0)
        if legacy == 0 and site.get("lat") is not None:
            legacy = 1  # pre-survey plain mean: _welford counts it as one sample
        site["legacy_samples_before_fresh_gating"] = legacy
        site["ingest_rule"] = INGEST_RULE
        site.setdefault("n_fresh", 0)
    # a pre-survey site (plain means, no counters) migrates transparently:
    # its existing mean becomes the first sample of the survey.
    for key, val in (("lat", lat), ("lon", lon),
                     ("alt_msl", alt_msl), ("alt_hae", alt_hae)):
        _welford(site, key, val)
    site["n_fresh"] = site.get("n_fresh", 0) + 1
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
    with _LOCK:
        cfg = load()
        cfg["site"] = None
        save(cfg)


def site_stats(cfg):
    """Survey diagnostics: sample count, standard error of the mean and
    per-sample scatter, in meters. Sparse until two samples exist."""
    site = cfg.get("site")
    if not site:
        return {"n": 0, "n_fresh": 0, "n_legacy": 0, "ingest_rule": None}
    n = site.get("n_lat", 0)
    gated = site.get("ingest_rule") == INGEST_RULE
    counts = {"n": n,
              "n_fresh": site.get("n_fresh", 0) if gated else 0,
              "n_legacy": site.get("legacy_samples_before_fresh_gating", 0) if gated else n,
              "ingest_rule": site.get("ingest_rule")}
    if n < 2:
        return counts

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
    return {**counts,
            "se_lat_m": se_lat, "se_lon_m": se_lon, "se_alt_m": se_alt,
            "sd_lat_m": sd_lat, "sd_lon_m": sd_lon, "sd_alt_m": sd_alt,
            "se_horiz_m": horiz, "updated": site.get("updated")}


def privacy_site(cfg, site):
    """The site that position-revealing calculations may use under the privacy
    mode. Sunrise/sunset, solar noon, day length, moon and object rise/set,
    the sky map and local sidereal time are all functions of the position, so
    computing them from more precision than the mode exposes would leak it.

    Returns (site_or_None, mode):
      exact   -> the site unchanged
      rounded -> the same rounding as displayed_location() (1 decimal ≈ 11 km,
                 MSL altitude to 10 m, no ellipsoidal height)
      hidden  -> None: nothing may be computed from the position
    """
    mode = cfg.get("location_display", "exact")
    if not site or mode == "hidden":
        return None, mode
    if mode == "rounded":
        alt = site.get("alt_msl")
        return {"lat": round(site["lat"], 1), "lon": round(site["lon"], 1),
                "alt_msl": None if alt is None else round(alt, -1),
                "updated": site.get("updated")}, mode
    return site, mode


def privacy_sats(cfg, sats):
    """Satellite list under the privacy mode. Azimuth/elevation of several
    satellites at a known time, with a public GNSS almanac, constrain the
    receiver position, so hidden mode drops them (null); exact and rounded keep
    them. IDs, constellation, C/N0 and used flags are kept in every mode."""
    if cfg.get("location_display") != "hidden":
        return sats
    return [{**s, "el": None, "az": None} for s in sats]


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
