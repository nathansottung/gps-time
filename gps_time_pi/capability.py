"""The station's capability record (SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md §1,
SPEC-OBSERVATION-FORMAT-AND-TASKING.md "Capability records"): what this station
is and can do, in the small form a coordinator join will carry. GET /api/capability.

It never holds an exact position: the location is given only in rounded mode, at
that mode's precision (one decimal of a degree); exact mode gives none ("exact
positions are never published"), and hidden mode gives none.

The sky-quality summary (from the learned sky-obstruction map, skymap.py) is
opt-in: config `sky_quality_share` (default off) and never in hidden mode. It
holds the 45° sectors only, never the grid or any time.
"""

import base64
import hashlib
import os
from datetime import datetime, timezone

from . import skymap

FORMAT = "gps-time-capability/1"
PUBLIC_KEY = os.environ.get("GTP_STATION_KEY_PUB", "/opt/gps-time-pi/station-key.pub")


def station_id(path=None):
    """The station key's fingerprint from the public key file, or None (no key, or unreadable)."""
    try:
        with open(path or PUBLIC_KEY, encoding="ascii") as f:
            raw = base64.b64decode(f.read().strip(), validate=True)
    except (OSError, ValueError):
        return None
    return "ed25519:" + hashlib.sha256(raw).hexdigest() if len(raw) == 32 else None


def location(cfg, site):
    mode = cfg.get("location_display", "exact")
    if mode == "rounded" and site:
        return {"precision": "rounded (0.1°, about 11 km)", "lat": round(site["lat"], 1),
                "lon": round(site["lon"], 1)}
    return {"precision": mode, "lat": None, "lon": None,
            "note": "hidden by the privacy setting" if mode == "hidden"
            else "exact positions are never published in the capability record; choose rounded to share one"}


def record(cfg, *, version, status, receiver, sdr, site, sky, key_path=None, now=None):
    """The record. `status` is timing_chain.timing_status(); `sdr` is /api/sdr; `sky` a SkyMap."""
    now = now or datetime.now(timezone.utc)
    dongles = (sdr or {}).get("dongles") or []
    quality, why = skymap.sky_quality_block(sky, cfg) if sky is not None else (None, "not available")
    return {
        "format": FORMAT,
        "generated_utc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "station_id": station_id(key_path),
        "software_version": version,
        "timing": {"state": (status or {}).get("code"), "source": (status or {}).get("source"),
                   "provenance": "calculated"},
        "gnss": {"driver": (receiver or {}).get("driver"), "firmware": (receiver or {}).get("firmware")},
        "sdr": {"installed": (sdr or {}).get("installed"),
                "receivers": [{"role": d.get("role")} for d in dongles if d.get("role")]},
        "location": location(cfg, site),
        "sky_quality_opt_in": bool(cfg.get("sky_quality_share")),
        "sky_quality": quality,
        "sky_quality_note": None if quality is not None else why,
        "availability": "owner only",
    }
