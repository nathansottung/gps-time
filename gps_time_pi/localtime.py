"""Which time zone the pages show local time in. Display only.

The system clock, chrony, logs and every timestamp in the API stay on UTC;
nothing here reads or sets the system time zone.

Order:
  1. the operator's override (config "timezone"), in every privacy mode;
  2. the zone found offline from the station's position, with the same privacy
     rule as astronomy (config.privacy_site): exact uses the site, rounded uses
     the rounded site, hidden uses nothing;
  3. none: the page then uses the browser's own zone.

A time zone narrows the position to a region, so in hidden mode it is never
derived from the position; only the override (the operator's own choice) or
the browser's zone is used.

The lookup uses tzfpy (bundled, simplified zone boundaries; no network). Like
astronomy, it is optional: if the library is missing, the zone is simply not
found and the pages fall back to the browser's zone.
"""

from __future__ import annotations

import re
from functools import lru_cache
from zoneinfo import available_timezones

from . import config

LOOKUP = {"available": False, "reason": "not initialised"}
_get_tz = None


def _init():
    global _get_tz
    try:
        from tzfpy import get_tz
    except Exception as e:  # noqa: BLE001
        LOOKUP.update(available=False,
                      reason=f"time-zone lookup library (tzfpy) not available ({e.__class__.__name__})")
        return
    _get_tz = get_tz
    LOOKUP.update(available=True, reason=None)


_init()

_ZONE_SYNTAX = re.compile(r"^[A-Za-z0-9_+\-]{1,32}(/[A-Za-z0-9_+\-]{1,32}){0,2}$")


def valid_zone(name) -> bool:
    """An IANA zone name this system knows. Where the system has no zone
    database at all (Windows without tzdata), only the syntax can be checked."""
    if not isinstance(name, str) or not _ZONE_SYNTAX.match(name):
        return False
    known = available_timezones()
    return name in known if known else True


@lru_cache(maxsize=16)
def _lookup(lat_mdeg: int, lon_mdeg: int):
    # tzfpy takes (longitude, latitude)
    name = _get_tz(lon_mdeg / 1000.0, lat_mdeg / 1000.0)
    return name if name and valid_zone(name) else None


def zone_from_position(lat, lon):
    """IANA zone for a position, or None. Cached per 0.001° (about 100 m), so a
    live fix that jitters doesn't cause a lookup on every request."""
    if _get_tz is None or lat is None or lon is None:
        return None
    try:
        return _lookup(round(float(lat) * 1000), round(float(lon) * 1000))
    except Exception:  # noqa: BLE001  (never let a display nicety break /api)
        return None


def display_zone(cfg, site):
    """The zone for local-time display, and where it came from.

    Returns {"tz", "source", "provenance", "basis", "note"}:
      source "override"  -> tz from the operator's setting
      source "position"  -> tz calculated from the (exact or rounded) site
      source None        -> tz None: the page uses the browser's zone
    """
    override = cfg.get("timezone")
    if override and valid_zone(override):
        return {"tz": override, "source": "override", "provenance": None, "basis": None,
                "note": "set by the operator"}
    psite, mode = config.privacy_site(cfg, site)
    if mode == "hidden":
        return {"tz": None, "source": None, "provenance": None, "basis": None,
                "note": "location is hidden: the zone is not derived from the position"}
    if psite is None:
        return {"tz": None, "source": None, "provenance": None, "basis": None,
                "note": "no position yet"}
    if not LOOKUP["available"]:
        return {"tz": None, "source": None, "provenance": None, "basis": None, "note": LOOKUP["reason"]}
    tz = zone_from_position(psite.get("lat"), psite.get("lon"))
    if tz is None:
        return {"tz": None, "source": None, "provenance": None, "basis": None,
                "note": "no zone found for the position"}
    return {"tz": tz, "source": "position", "provenance": "calculated", "basis": mode,
            "note": "from the station's position and bundled zone boundaries (simplified near borders)"
                    + ("; rounded position" if mode == "rounded" else "")}
