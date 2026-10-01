"""Astronomy layer, built on Skyfield + JPL DE440s.

Isolation contract (review requirement 6): this module must never prevent
the timing core from running. All Skyfield/numpy imports are guarded; if
anything is missing or broken, `STATUS['available']` is False with a
human-readable reason, and every public function returns a stub the
templates render as "Astronomy unavailable".

Ephemeris: data/de440s.bsp, provisioned by install.sh (never downloaded
silently at runtime). Valid 1849–2150; we enforce 1850–2149 inclusive.

Coordinates accepted as J2000/ICRS; Skyfield handles precession/nutation.
"""

import os
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(__file__)
EPHEMERIS = os.environ.get("GTP_EPHEMERIS", os.path.join(_HERE, "data", "de440s.bsp"))

MIN_OBJECT_ALTITUDE_DEG = 25.0
SUN_DARK_DEG = -18.0
DATE_MIN, DATE_MAX = _date(1850, 1, 1), _date(2149, 12, 31)

STATUS = {"available": False, "reason": "not initialised"}
_S = {}


def _init():
    global STATUS
    try:
        import numpy as np  # noqa: F401
        from skyfield import almanac
        from skyfield.api import Loader, Star, wgs84
    except Exception as e:  # noqa: BLE001
        STATUS = {"available": False, "reason": f"Skyfield/NumPy not available ({e.__class__.__name__})"}
        return
    if not os.path.exists(EPHEMERIS):
        STATUS = {"available": False,
                  "reason": "Planetary ephemeris could not be loaded (de440s.bsp missing — run install.sh)"}
        return
    try:
        loader = Loader(os.path.dirname(EPHEMERIS), verbose=False)
        eph = loader(os.path.basename(EPHEMERIS))
        ts = loader.timescale(builtin=True)
    except Exception as e:  # noqa: BLE001
        STATUS = {"available": False, "reason": f"Ephemeris failed to load ({e})"}
        return
    _S.update(np=__import__("numpy"), almanac=almanac, Star=Star, wgs84=wgs84,
              eph=eph, ts=ts, earth=eph["earth"], sun=eph["sun"], moon=eph["moon"])
    STATUS = {"available": True, "reason": None}


_init()

_PLANET_KEYS = {"Mercury": "mercury", "Venus": "venus", "Mars": "mars barycenter",
                "Jupiter": "jupiter barycenter", "Saturn": "saturn barycenter",
                "Uranus": "uranus barycenter", "Neptune": "neptune barycenter",
                "Moon": "moon", "Sun": "sun"}


def _unavailable():
    return {"available": False, "reason": STATUS["reason"]}


def date_supported(d):
    return DATE_MIN <= d <= DATE_MAX


def _observer(site):
    elev = site.get("alt_hae")
    if elev is None:
        elev = site.get("alt_msl") or 0.0
    return _S["wgs84"].latlon(site["lat"], site["lon"], elevation_m=float(elev))


def _local_day(d, tzname):
    tz = ZoneInfo(tzname)
    start = datetime(d.year, d.month, d.day, tzinfo=tz)
    return start, start + timedelta(days=1), tz


def _t(dt):
    return _S["ts"].from_datetime(dt.astimezone(timezone.utc))


def _iso(t, tz):
    return t.astimezone(tz).isoformat(timespec="seconds") if t else None


def _sample_times(start, end, step_s=60):
    np = _S["np"]
    n = int((end - start).total_seconds() // step_s) + 1
    dts = [start + timedelta(seconds=i * step_s) for i in range(n)]
    return dts, _S["ts"].from_datetimes([d.astimezone(timezone.utc) for d in dts])


def _alt_series(body, observer, tarr):
    astrometric = (_S["earth"] + observer).at(tarr).observe(body).apparent()
    alt, az, _ = astrometric.altaz()
    return alt.degrees, az.degrees


def _mask_intervals(dts, mask):
    """Boolean series -> list of (start_dt, end_dt) intervals."""
    out, start = [], None
    for dt, on in zip(dts, mask):
        if on and start is None:
            start = dt
        elif not on and start is not None:
            out.append((start, dt))
            start = None
    if start is not None:
        out.append((start, dts[-1]))
    return out


def solar_day(d, site, tzname):
    """Rise/noon/set, the six twilight boundaries, daylight duration, and
    the 24-h bar segments for one local calendar day."""
    if not STATUS["available"]:
        return _unavailable()
    if not date_supported(d):
        return {"available": False,
                "reason": f"Date outside supported range {DATE_MIN}–{DATE_MAX}"}
    almanac = _S["almanac"]
    obs = _observer(site)
    start, end, tz = _local_day(d, tzname)
    f = almanac.dark_twilight_day(_S["eph"], obs)
    times, states = almanac.find_discrete(_t(start), _t(end), f)
    state0 = int(f(_t(start)))

    events = {}
    prev = state0
    for t, s in zip(times, states):
        s = int(s)
        dt = t.utc_datetime()
        key = None
        pair = (prev, s)
        names = {(0, 1): "astro_dawn", (1, 2): "naut_dawn", (2, 3): "civil_dawn",
                 (3, 4): "sunrise", (4, 3): "sunset", (3, 2): "civil_dusk",
                 (2, 1): "naut_dusk", (1, 0): "astro_dusk"}
        key = names.get(pair)
        if key and key not in events:
            events[key] = dt
        prev = s

    tt, _y = almanac.find_discrete(_t(start), _t(end),
                                   almanac.meridian_transits(_S["eph"], _S["sun"], obs))
    noon = None
    for t, y in zip(tt, _y):
        if int(y) == 1:
            noon = t.utc_datetime()
            break

    daylight = None
    if "sunrise" in events and "sunset" in events:
        daylight = (events["sunset"] - events["sunrise"]).total_seconds()
    elif state0 == 4 and not events:
        daylight = (end - start).total_seconds()
    elif state0 < 4 and "sunrise" not in events and "sunset" not in events:
        daylight = 0.0

    # 24h bar: segments of the day in twilight-state colors
    segs, cursor, prev = [], start, state0
    for t, s in zip(times, states):
        dt = t.astimezone(tz)
        segs.append({"state": prev, "start": cursor.isoformat(timespec="seconds"),
                     "frac": (dt - cursor).total_seconds() / 86400})
        cursor, prev = dt, int(s)
    segs.append({"state": prev, "start": cursor.isoformat(timespec="seconds"),
                 "frac": (end - cursor).total_seconds() / 86400})

    notes = []
    if daylight == (end - start).total_seconds():
        notes.append("Sun does not set on this date.")
    if daylight == 0.0:
        notes.append("Sun does not rise on this date.")

    return {"available": True, "date": d.isoformat(), "tz": tzname,
            "events": {k: _iso(v, tz) for k, v in events.items()},
            "noon": _iso(noon, tz), "daylight_s": daylight,
            "bar": segs, "notes": notes}


def daylight_deltas(d, site, tzname):
    """(vs yesterday, to tomorrow) in seconds; None where undefined."""
    today = solar_day(d, site, tzname)
    if not today.get("available") or today.get("daylight_s") is None:
        return None, None
    y = solar_day(d - timedelta(days=1), site, tzname)
    t = solar_day(d + timedelta(days=1), site, tzname)
    dy = today["daylight_s"] - y["daylight_s"] if y.get("available") and y.get("daylight_s") is not None else None
    dt_ = t["daylight_s"] - today["daylight_s"] if t.get("available") and t.get("daylight_s") is not None else None
    return dy, dt_


def lunar_day(d, site, tzname):
    if not STATUS["available"]:
        return _unavailable()
    if not date_supported(d):
        return {"available": False, "reason": "Date outside supported range"}
    almanac, np = _S["almanac"], _S["np"]
    obs = _observer(site)
    start, end, tz = _local_day(d, tzname)

    rt, ry = almanac.find_discrete(_t(start), _t(end),
                                   almanac.risings_and_settings(_S["eph"], _S["moon"], obs))
    rise = next((t.utc_datetime() for t, y in zip(rt, ry) if int(y) == 1), None)
    sett = next((t.utc_datetime() for t, y in zip(rt, ry) if int(y) == 0), None)

    mt, my = almanac.find_discrete(_t(start), _t(end),
                                   almanac.meridian_transits(_S["eph"], _S["moon"], obs))
    transit = transit_alt = None
    for t, y in zip(mt, my):
        if int(y) == 1:
            transit = t.utc_datetime()
            alt, _, _ = (_S["earth"] + obs).at(t).observe(_S["moon"]).apparent().altaz()
            transit_alt = round(float(alt.degrees), 1)
            break

    tmid = _t(start + timedelta(hours=12))
    phase_deg = float(almanac.moon_phase(_S["eph"], tmid).degrees)
    illum = float(almanac.fraction_illuminated(_S["eph"], "moon", tmid))
    age_days = phase_deg / 360.0 * 29.530588
    names = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
             "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"]
    idx = int(((phase_deg + 22.5) % 360) // 45)
    phase_name = names[idx]

    dts, tarr = _sample_times(start, end, 120)
    alt, _ = _alt_series(_S["moon"], obs, tarr)
    up_s = float((np.array(alt) > 0).sum()) * 120

    return {"available": True, "rise": _iso(rise, tz), "set": _iso(sett, tz),
            "transit": _iso(transit, tz), "transit_alt": transit_alt,
            "phase": phase_name, "illum": round(illum * 100, 1),
            "age_days": round(age_days, 1), "up_s": up_s, "tz": tzname}


def night(d, site, tzname):
    """The sunset(d) -> next sunrise night bar with twilight, moon-up and
    moonless astronomical darkness segments. All fractions of the actual
    elapsed UTC night (DST-safe); labels carry local time + date."""
    if not STATUS["available"]:
        return _unavailable()
    np = _S["np"]
    obs = _observer(site)
    start_day, _, tz = _local_day(d, tzname)

    sd_today = solar_day(d, site, tzname)
    sd_next = solar_day(d + timedelta(days=1), site, tzname)
    if not sd_today.get("available"):
        return sd_today
    sunset = sd_today["events"].get("sunset")
    sunrise = sd_next["events"].get("sunrise") if sd_next.get("available") else None
    if not sunset or not sunrise:
        return {"available": True, "defined": False,
                "note": "No sunset-to-sunrise night on this date at this latitude."}
    t0 = datetime.fromisoformat(sunset)
    t1 = datetime.fromisoformat(sunrise)
    span = (t1 - t0).total_seconds()

    dts, tarr = _sample_times(t0, t1, 60)
    sun_alt, _ = _alt_series(_S["sun"], obs, tarr)
    moon_alt, _ = _alt_series(_S["moon"], obs, tarr)
    sun_alt, moon_alt = np.array(sun_alt), np.array(moon_alt)

    def frac(dt):
        return (dt - t0).total_seconds() / span

    def stage(a):
        return 0 if a < -18 else 1 if a < -12 else 2 if a < -6 else 3

    stages = [stage(a) for a in sun_alt]
    segs, cursor, prev = [], dts[0], stages[0]
    for dt, s in zip(dts, stages):
        if s != prev:
            segs.append({"stage": prev, "f0": frac(cursor), "f1": frac(dt)})
            cursor, prev = dt, s
    segs.append({"stage": prev, "f0": frac(cursor), "f1": 1.0})

    moon_iv = _mask_intervals(dts, moon_alt > 0)
    dark_iv = _mask_intervals(dts, (sun_alt < SUN_DARK_DEG) & (moon_alt < 0))
    dark_total = sum((b - a).total_seconds() for a, b in dark_iv)

    midnight = None
    next_day = start_day + timedelta(days=1)
    if t0 <= next_day <= t1:
        midnight = {"f": frac(next_day),
                    "label": next_day.astimezone(tz).strftime("midnight → %b %-d")}

    astro_note = None
    if not (sun_alt < SUN_DARK_DEG).any():
        astro_note = "Astronomical darkness does not occur tonight."

    return {"available": True, "defined": True,
            "sunset": sunset, "sunrise": sunrise, "span_s": span,
            "sun_segments": segs,
            "moon_up": [{"f0": frac(a), "f1": frac(b)} for a, b in moon_iv],
            "dark": [{"f0": frac(a), "f1": frac(b),
                      "start": a.astimezone(tz).isoformat(timespec="minutes"),
                      "end": b.astimezone(tz).isoformat(timespec="minutes")}
                     for a, b in dark_iv],
            "dark_total_s": dark_total, "midnight": midnight,
            "astro_note": astro_note, "tz": tzname}


def _target_body(target):
    if target["kind"] == "planet":
        return _S["eph"][_PLANET_KEYS[target["name"]]]
    return _S["Star"](ra_hours=target["ra"] / 15.0, dec_degrees=target["dec"])


def object_report(target, d, site, tzname, obs_dt):
    """Everything the object card needs for one target on one date."""
    if not STATUS["available"]:
        return _unavailable()
    if not date_supported(d):
        return {"available": False, "reason": "Date outside supported range"}
    almanac, np = _S["almanac"], _S["np"]
    obs = _observer(site)
    start, end, tz = _local_day(d, tzname)
    body = _target_body(target)

    t_obs = _t(obs_dt)
    alt, az, _ = (_S["earth"] + obs).at(t_obs).observe(body).apparent().altaz()
    now_alt, now_az = round(float(alt.degrees), 1), round(float(az.degrees), 0)

    rt, ry = almanac.find_discrete(_t(start), _t(end),
                                   almanac.risings_and_settings(_S["eph"], body, obs))
    rise = next((t.utc_datetime() for t, y in zip(rt, ry) if int(y) == 1), None)
    sett = next((t.utc_datetime() for t, y in zip(rt, ry) if int(y) == 0), None)

    mt, my = almanac.find_discrete(_t(start), _t(end),
                                   almanac.meridian_transits(_S["eph"], body, obs))
    transit = transit_alt = None
    for t, y in zip(mt, my):
        if int(y) == 1:
            transit = t.utc_datetime()
            a2, _, _ = (_S["earth"] + obs).at(t).observe(body).apparent().altaz()
            transit_alt = round(float(a2.degrees), 1)
            break

    circumpolar = never_up = False
    if rise is None and sett is None:
        dts_c, tarr_c = _sample_times(start, end, 1800)
        alts_c, _ = _alt_series(body, obs, tarr_c)
        if min(alts_c) > 0:
            circumpolar = True
        elif max(alts_c) < 0:
            never_up = True

    dts, tarr = _sample_times(start, end, 120)
    obj_alt, _ = _alt_series(body, obs, tarr)
    sun_alt, _ = _alt_series(_S["sun"], obs, tarr)
    moon_alt, _ = _alt_series(_S["moon"], obs, tarr)
    obj_alt, sun_alt, moon_alt = map(np.array, (obj_alt, sun_alt, moon_alt))

    usable = obj_alt > MIN_OBJECT_ALTITUDE_DEG
    dark_win = _mask_intervals(dts, usable & (sun_alt < SUN_DARK_DEG))
    moonless_win = _mask_intervals(dts, usable & (sun_alt < SUN_DARK_DEG) & (moon_alt < 0))

    def wins(iv):
        return [{"start": a.astimezone(tz).isoformat(timespec="minutes"),
                 "end": b.astimezone(tz).isoformat(timespec="minutes"),
                 "dur_s": (b - a).total_seconds()} for a, b in iv]

    return {"available": True,
            "now_alt": now_alt, "now_az": now_az,
            "rise": _iso(rise, tz), "transit": _iso(transit, tz),
            "transit_alt": transit_alt, "set": _iso(sett, tz),
            "circumpolar": circumpolar, "never_up": never_up,
            "dark_windows": wins(dark_win), "moonless_windows": wins(moonless_win),
            "min_alt_deg": MIN_OBJECT_ALTITUDE_DEG, "tz": tzname}


def sidereal(site, when=None):
    if not STATUS["available"]:
        return None
    t = _S["ts"].from_datetime((when or datetime.now(timezone.utc)).astimezone(timezone.utc))
    gast = t.gast  # hours
    lst = (gast + site["lon"] / 15.0) % 24
    h = int(lst)
    m = int((lst - h) * 60)
    s = int(round(((lst - h) * 60 - m) * 60))
    if s == 60:
        s, m = 0, m + 1
    return f"{h:02d}:{m:02d}:{s:02d}"


_HERE_DATA = os.path.join(_HERE, "data")


def sky_snapshot(site, when, target=None):
    """Alt/az of chart stars, constellation lines, planets, sun, moon and
    the optional target, for the client-side SVG chart."""
    if not STATUS["available"]:
        return _unavailable()
    import json as _json
    np, Star = _S["np"], _S["Star"]
    obs = _observer(site)
    t = _S["ts"].from_datetime(when.astimezone(timezone.utc))
    place = (_S["earth"] + obs).at(t)

    with open(os.path.join(_HERE_DATA, "stars.json")) as f:
        stars = _json.load(f)
    ra = np.array([s[0] for s in stars]) / 15.0
    dec = np.array([s[1] for s in stars])
    field = Star(ra_hours=ra, dec_degrees=dec)
    alt, az, _ = place.observe(field).apparent().altaz()
    vis = [[round(float(a), 1), round(float(z), 1), stars[i][2]]
           for i, (a, z) in enumerate(zip(alt.degrees, az.degrees)) if a > -1]

    with open(os.path.join(_HERE_DATA, "constellations.json")) as f:
        cons = _json.load(f)
    pts, index = [], []
    for c in cons:
        for line in c["lines"]:
            seg = []
            for p in line:
                seg.append(len(pts))
                pts.append(p)
            index.append(seg)
    ra2 = np.array([p[0] for p in pts]) / 15.0
    dec2 = np.array([p[1] for p in pts])
    alt2, az2, _ = place.observe(Star(ra_hours=ra2, dec_degrees=dec2)).apparent().altaz()
    coords = [[round(float(a), 1), round(float(z), 1)]
              for a, z in zip(alt2.degrees, az2.degrees)]
    lines = [[coords[i] for i in seg] for seg in index]

    bodies = {}
    for name in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Moon", "Sun"):
        a, z, _ = place.observe(_S["eph"][_PLANET_KEYS[name]]).apparent().altaz()
        if a.degrees > -1:
            bodies[name] = [round(float(a.degrees), 1), round(float(z.degrees), 1)]

    tgt = None
    if target:
        a, z, _ = place.observe(_target_body(target)).apparent().altaz()
        tgt = [round(float(a.degrees), 1), round(float(z.degrees), 1)]

    return {"available": True, "stars": vis, "lines": lines,
            "bodies": bodies, "target": tgt}
