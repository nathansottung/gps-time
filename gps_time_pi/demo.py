"""Deterministic-ish demo data for desktop UI development.

Demo mode must not require gpsd, chrony, a Raspberry Pi, Skyfield, or network
access.  It exercises the same HTTP APIs as real mode.
Values are intentionally labelled as sample data in the UI.
"""

from __future__ import annotations

import math
import os
import time
from datetime import date, datetime, timedelta, timezone

from . import __version__, system


def _satellite(i: int, now: float) -> dict:
    az = int((i * 43 + now / 12) % 360)
    el = max(5, int(10 + 58 * abs(math.sin((i * 0.71) + now / 900))))
    snr = int(22 + 23 * abs(math.sin((i * 1.17) + now / 500)))
    systems = ["GPS", "GPS", "Galileo", "GLONASS", "BeiDou", "GPS"]
    return {"id": 3 + i * 4, "gnss": systems[i % len(systems)], "el": el,
            "az": az, "snr": snr, "used": snr > 28 and el > 12}


def core_api() -> dict:
    now = datetime.now(timezone.utc)
    t = now.timestamp()
    wave = math.sin(t / 41.0)
    system_s = 145e-9 + 65e-9 * wave
    rms = 312e-9
    dispersion = 485e-9
    freq_ppm = 2.14 + 0.04 * math.sin(t / 900)
    sats = [_satellite(i, t) for i in range(10)]
    used = sum(1 for s in sats if s["used"])
    sources = [
        {"mode": "#", "state": "*", "state_label": "selected", "name": "GPS",
         "stratum": 0, "poll": 0, "reach": "377", "lastrx": "0", "sample": "+0ns[ +21ns] +/- 30ns"},
        {"mode": "#", "state": "?", "state_label": "not selectable", "name": "NMEA",
         "stratum": 0, "poll": 4, "reach": "377", "lastrx": "1", "sample": "+35ms[ +35ms] +/- 20ms"},
        {"mode": "^", "state": "+", "state_label": "combined", "name": "pool.ntp.org",
         "stratum": 2, "poll": 6, "reach": "377", "lastrx": "24", "sample": "+781us[+822us] +/- 14ms"},
    ]
    return {
        "demo": True,
        "epoch_ms": now.timestamp() * 1000,
        "utc": now.strftime("%Y-%m-%d %H:%M:%S.%f UTC"),
        "quality": {
            "system_time_s": system_s,
            "last_offset_s": 118e-9,
            "rms_offset_s": rms,
            "root_delay_s": 0.0,
            "root_dispersion_s": dispersion,
            "max_error_bound_s": abs(system_s) + dispersion,      # + ½ root delay (0 here); chrony.max_error_bound
            "frequency": f"{freq_ppm:.3f} ppm fast",
            "frequency_ppm": freq_ppm,
            "residual_freq": "-0.003 ppm",
            "skew": "0.018 ppm",
            "update_interval": "1.0 seconds",
            "leap": "Normal",
            "stratum": "1",
            "reference": "PPS",
            "ref_time": now.strftime("%a %b %d %H:%M:%S %Y"),
        },
        "sources": sources,
        "sourcestats": "Sample source statistics for desktop demo mode.",
        "clients": [
            {"host": "192.0.2.21", "ntp_packets": 18421, "dropped": "0", "last": "7"},
            {"host": "192.0.2.42", "ntp_packets": 9218, "dropped": "0", "last": "18"},
            {"host": "192.0.2.77", "ntp_packets": 4101, "dropped": "0", "last": "61"},
        ],
        "gps": {"fix": "3D", "sats": sats, "used": used, "visible": len(sats),
                "tdop": 0.72, "hdop": 0.83, "last_fix": "3D",
                "last_fix_time": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "stale": False,
                "data_age_s": 1.2, "sky_stale": False, "sky_age_s": 1.2},
        "location": {"mode": "exact", "lat": 38.9217, "lon": -77.0669,
                     "alt_msl": 92.0, "alt_hae": 59.5},
        "survey": {"n": 18432, "n_fresh": 16020, "n_legacy": 2412,
                   "ingest_rule": "fresh-epoch-v1", "se_horiz_m": 0.18, "se_alt_m": 0.44,
                   "sd_lat_m": 2.1, "sd_lon_m": 2.8, "sd_alt_m": 4.2,
                   "updated": now.isoformat()},
        "position_provenance": "demo",
        "sidereal": "18:42:13",
        "astro_available": True,
        "astro_reason": None,
        "cpu_temp_c": 44.2,
        "versions": {"app": __version__, "chrony": "chrony 4.x (sample)", "gpsd": "3.x (sample)",
                     "receiver": {"driver": "u-blox", "firmware": "MAX-M8Q sample", "path": "/dev/ttyAMA0"},
                     "python": "desktop demo"},
    }


def _demo_date(qs):
    """The requested ?date=YYYY-MM-DD, else today (local)."""
    try:
        return date.fromisoformat((qs or {}).get("date", [""])[0])
    except (ValueError, TypeError, IndexError):
        return datetime.now().astimezone().date()


# Demo sky: the bundled chart stars and constellation lines placed with a plain
# equatorial-to-horizontal conversion for the example site (US Naval Observatory). No
# precession, nutation or refraction: shapes for the sky map, not positions to observe by.
_DEMO_LAT, _DEMO_LON = 38.9217, -77.0669
_DEMO_BODIES = {"Moon": (250.0, -20.0), "Jupiter": (110.0, 22.5), "Saturn": (350.0, -6.0)}   # RA, Dec (degrees)


def _altaz(ra, dec, lst_deg):
    h = math.radians((lst_deg - ra) % 360)
    lat, d = math.radians(_DEMO_LAT), math.radians(dec)
    alt = math.asin(math.sin(lat) * math.sin(d) + math.cos(lat) * math.cos(d) * math.cos(h))
    az = math.atan2(-math.cos(d) * math.sin(h), math.sin(d) * math.cos(lat) - math.cos(d) * math.cos(h) * math.sin(lat))
    return round(math.degrees(alt), 1), round(math.degrees(az) % 360, 1)


def _lst_deg(when):
    jd = when.timestamp() / 86400.0 + 2440587.5
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0) + _DEMO_LON) % 360


def _target_radec(target):
    if not target:
        return None
    if target["kind"] == "planet":
        return _DEMO_BODIES.get(target["name"], (200.0, -10.0))
    return target["ra"], target["dec"]


def sky_api(when, target=None) -> dict:
    import json as _json
    here = os.path.join(os.path.dirname(__file__), "data")
    lst = _lst_deg(when)
    with open(os.path.join(here, "stars.json")) as f:
        stars = [[*_altaz(ra, dec, lst), mag] for ra, dec, mag in _json.load(f)]
    with open(os.path.join(here, "constellations.json")) as f:
        lines = [[list(_altaz(ra, dec, lst)) for ra, dec in line] for c in _json.load(f) for line in c["lines"]]
    bodies = {k: list(_altaz(ra, dec, lst)) for k, (ra, dec) in _DEMO_BODIES.items()}
    rd = _target_radec(target)
    return {"available": True, "demo": True,
            "stars": [x for x in stars if x[0] > -1], "lines": lines,
            "bodies": {k: v for k, v in bodies.items() if v[0] > -1},
            "target": list(_altaz(rd[0], rd[1], lst)) if rd else None}


def object_api(target, day, when) -> dict:
    """Synthetic object card in astro.object_report's shape (demo only)."""
    rd = _target_radec(target)
    alt, az = _altaz(rd[0], rd[1], _lst_deg(when))
    tz = datetime.now().astimezone().tzinfo
    base = datetime(day.year, day.month, day.day, tzinfo=tz)

    def at(h, m, d=0):
        return (base + timedelta(days=d, hours=h, minutes=m)).isoformat(timespec="minutes")
    never_up = rd[1] < _DEMO_LAT - 90
    circumpolar = rd[1] > 90 - _DEMO_LAT
    return {"available": True, "demo": True, "now_alt": alt, "now_az": round(az),
            "rise": None if never_up or circumpolar else at(17, 40),
            "transit": None if never_up else at(23, 55),
            "transit_alt": round(90 - abs(_DEMO_LAT - rd[1]), 1) if not never_up else None,
            "set": None if never_up or circumpolar else at(6, 10, 1),
            "circumpolar": circumpolar, "never_up": never_up,
            "dark_windows": [] if never_up else [{"start": at(20, 53), "end": at(5, 18, 1), "dur_s": 30300.0}],
            "moonless_windows": [] if never_up else [{"start": at(23, 10), "end": at(5, 18, 1), "dur_s": 22080.0}],
            "min_alt_deg": 15, "tz": str(tz)}


def _demo_when(qs, day, tz):
    """?at=HH:MM on the requested day, else now (today) or 22:00 (another day)."""
    raw = (qs or {}).get("at", ["now"])[0]
    try:
        hh, mm = (int(x) for x in raw.split(":"))
        return datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
    except (ValueError, TypeError):
        now = datetime.now().astimezone()
        return now if now.date() == day else datetime(day.year, day.month, day.day, 22, 0, tzinfo=tz)


def almanac_api(qs=None) -> dict:
    """Synthetic almanac for the desktop demo: fixed clock times on the requested date,
    with the day bar, the night bar and moon details in the shapes astro.py returns."""
    tz = datetime.now().astimezone().tzinfo
    day = _demo_date(qs)
    base = datetime(day.year, day.month, day.day, tzinfo=tz)

    def at(h, m, s=0, d=0):
        return base + timedelta(days=d, hours=h, minutes=m, seconds=s)

    ev = {"astro_dawn": at(5, 18, 40), "naut_dawn": at(5, 49, 2), "civil_dawn": at(6, 19, 31),
          "sunrise": at(6, 47, 15), "sunset": at(19, 24, 17), "civil_dusk": at(19, 51, 59),
          "naut_dusk": at(20, 22, 30), "astro_dusk": at(20, 52, 51)}
    start, noon, end = ev["sunrise"], at(13, 6, 43), ev["sunset"]
    daylight = (end - start).total_seconds()
    order = [(0, base), (1, ev["astro_dawn"]), (2, ev["naut_dawn"]), (3, ev["civil_dawn"]), (4, ev["sunrise"]),
             (3, ev["sunset"]), (2, ev["civil_dusk"]), (1, ev["naut_dusk"]), (0, ev["astro_dusk"])]
    bar = []
    for i, (state, t0) in enumerate(order):
        t1 = order[i + 1][1] if i + 1 < len(order) else at(0, 0, d=1)
        bar.append({"state": state, "start": t0.isoformat(timespec="seconds"),
                    "frac": (t1 - t0).total_seconds() / 86400})

    when = _demo_when(qs, day, tz)
    from . import catalog
    tq = (qs or {}).get("target", [""])[0].strip()
    target = catalog.lookup(tq) if tq else None

    n0, n1 = end, at(6, 48, 12, d=1)                 # sunset to next sunrise
    span = (n1 - n0).total_seconds()

    def f(t):
        return (t - n0).total_seconds() / span

    moonset = at(23, 10, d=0)
    dark0, dark1 = moonset, at(5, 19, 30, d=1)
    nb = {"available": True, "defined": True, "sunset": n0.isoformat(), "sunrise": n1.isoformat(), "span_s": span,
          "sun_segments": [{"stage": 3, "f0": 0.0, "f1": f(ev["civil_dusk"])},
                           {"stage": 2, "f0": f(ev["civil_dusk"]), "f1": f(ev["naut_dusk"])},
                           {"stage": 1, "f0": f(ev["naut_dusk"]), "f1": f(ev["astro_dusk"])},
                           {"stage": 0, "f0": f(ev["astro_dusk"]), "f1": f(at(5, 19, 30, d=1))},
                           {"stage": 1, "f0": f(at(5, 19, 30, d=1)), "f1": f(at(5, 50, d=1))},
                           {"stage": 2, "f0": f(at(5, 50, d=1)), "f1": f(at(6, 20, d=1))},
                           {"stage": 3, "f0": f(at(6, 20, d=1)), "f1": 1.0}],
          "moon_up": [{"f0": 0.0, "f1": f(moonset)}],
          "dark": [{"f0": f(dark0), "f1": f(dark1), "start": dark0.isoformat(timespec="minutes"),
                    "end": dark1.isoformat(timespec="minutes")}],
          "dark_total_s": (dark1 - dark0).total_seconds(),
          "midnight": {"f": f(at(0, 0, d=1)), "label": "midnight · " + at(0, 0, d=1).strftime("%a %d")},
          "astro_note": None, "tz": str(tz)}
    return {
        "available": True,
        "demo": True,
        "sun": {
            "available": True,
            "date": day.isoformat(),
            "tz": str(tz),
            "events": {k: v.isoformat() for k, v in ev.items()},
            "noon": noon.isoformat(), "daylight_s": daylight, "bar": bar, "notes": [],
        },
        "delta_yesterday": -182.8,
        "delta_tomorrow": -181.7,
        "moon": {"available": True, "phase": "Waxing crescent", "illum": 28.4,
                 "rise": at(13, 2).isoformat(), "transit": at(18, 4).isoformat(), "transit_alt": 31.6,
                 "set": moonset.isoformat(), "age_days": 5.2, "up_s": (moonset - at(13, 2)).total_seconds()},
        "night": nb,
        "sky": sky_api(when, target),
        "sky_when": when.strftime("%Y-%m-%d %H:%M %Z"),
        "position_provenance": "demo",
        "position_age": None,
        "neighbors": {
            "yesterday": {"sunrise": (start - timedelta(days=1, seconds=56.7)).isoformat(),
                          "sunset": (end - timedelta(days=1, seconds=-126.1)).isoformat(),
                          "noon": (noon - timedelta(days=1, seconds=-34.7)).isoformat(),
                          "daylight_s": daylight + 182.8},
            "tomorrow": {"sunrise": (start + timedelta(days=1, seconds=56.9)).isoformat(),
                         "sunset": (end + timedelta(days=1, seconds=-124.8)).isoformat(),
                         "noon": (noon + timedelta(days=1, seconds=-34.0)).isoformat(),
                         "daylight_s": daylight - 181.7},
        },
    }


def history() -> dict:
    now = time.time()
    points = []
    for i in range(180):
        age = (179 - i) * 60
        off = (260e-9 * math.sin(i / 11.0)) + (80e-9 * math.sin(i / 3.1))
        sd = 90e-9 + 40e-9 * abs(math.sin(i / 7.0))
        # chrony 4.x tracking.log columns by name (chrony.TRACKING_COLUMNS); sample values
        points.append({"t": now - age, "offset_s": off, "offset_sd_s": sd, "remaining_correction_s": off / 4,
                       "root_delay_s": 1e-9, "root_dispersion_s": 6e-6 + sd, "max_error_s": 2.4e-5 + 3 * sd,
                       "freq_ppm": 10.3, "skew_ppm": 0.009, "leap": "N", "n_combined": 1, "stratum": 1, "source": "PPS"})
    return {"available": True, "points": points, "note": "sample data", "skipped_lines": 0,
            "columns": ["date", "time", "ip", "stratum", "freq_ppm", "skew_ppm", "offset_s", "leap", "n_combined",
                        "offset_sd_s", "remaining_correction_s", "root_delay_s", "root_dispersion_s", "max_error_s"]}


_STABILITY = None


def stability() -> dict:
    """Sample /api/stability payload: the real estimators run on synthetic
    phase data (white phase noise plus a slow wander), computed once."""
    global _STABILITY
    if _STABILITY is None:
        import random
        from . import stability as st
        rng = random.Random(1420)
        seconds = [rng.gauss(0.0, 250e-9) for _ in range(st.RING_S)]
        last, mean, wander = [], [], 0.0
        for _ in range(5 * 1440):
            wander += rng.gauss(0.0, 6e-9)
            last.append(wander + rng.gauss(0.0, 250e-9))
            mean.append(wander + rng.gauss(0.0, 250e-9 / math.sqrt(60)))
        points = st.analyze(seconds, st.TAUS_SECONDS, 1.0, series="seconds")
        points += st.analyze(last, st.TAUS_MINUTES, 60.0, mean_phase=mean, series="minutes")
        flags = [True]
        series = {"seconds": st.Recorder._series_info(seconds, flags * len(seconds), 1.0, st.RING_S),
                  "minutes": st.Recorder._series_info(last, flags * len(last), 60.0, st.RING_MINUTES)}
        _STABILITY = st.build_report(points, series, None)
        _STABILITY["notes"] = ["sample data"]
    return {**_STABILITY, "since_utc": datetime.fromtimestamp(time.time() - 5 * 86400, timezone.utc)
            .isoformat(timespec="seconds")}


def satellites() -> dict:
    """Sample /api/satellites payload, written by hand: demo mode must not need
    orbital elements, the sgp4 package or the network. Times are relative to now."""
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def at(minutes, seconds=0):
        return (now + timedelta(minutes=minutes, seconds=seconds)).isoformat(timespec="seconds")

    def pt(minutes, seconds, az, alt, rng, state):
        return {"utc": at(minutes, seconds), "azimuth_deg": az, "altitude_deg": alt, "range_km": rng, "state": state}

    epoch = now - timedelta(days=1, hours=7)
    iss = {"norad": 25544, "name": "ISS (ZARYA)", "group": "stations", "epoch_utc": epoch.isoformat(timespec="seconds"),
           "age_days": 1.29, "stale": False, "age_note": None, "available": True, "reason": None,
           "provenance": "modeled", "azimuth_deg": 212.4, "altitude_deg": -31.6, "above_horizon": False,
           "range_km": 7480.2, "height_km": 418, "angular_speed_deg_s": 0.051, "state": "SUNLIT",
           "sunlit_fraction": 1.0, "could_be_seen": False}
    css = {**iss, "norad": 48274, "name": "CSS (TIANHE)", "azimuth_deg": 78.9, "altitude_deg": -12.3,
           "range_km": 4310.5, "height_km": 384, "angular_speed_deg_s": 0.118, "state": "UMBRA", "sunlit_fraction": 0.0}
    passes = [
        {"rise": pt(42, 10, 318.2, 0.0, 2368.4, "SUNLIT"), "culmination": pt(47, 6, 41.7, 48.3, 548.9, "SUNLIT"),
         "set": pt(52, 0, 124.6, 0.0, 2371.0, "UMBRA"), "in_progress": False, "duration_s": 590,
         "shadow_changes": [
             {"utc": at(48, 39), "kind": "penumbra entry", "from": "SUNLIT", "to": "PENUMBRA", "azimuth_deg": 96.1, "altitude_deg": 31.4},
             {"utc": at(48, 51), "kind": "umbra entry", "from": "PENUMBRA", "to": "UMBRA", "azimuth_deg": 99.8, "altitude_deg": 28.9}],
         "visible": {"start_utc": at(44, 14), "end_utc": at(48, 50), "duration_s": 276,
                     "max_altitude_deg": 48.3, "max_azimuth_deg": 41.7},
         "sun_altitude_deg": -16.3, "provenance": "predicted"},
        {"rise": pt(139, 2, 291.5, 0.0, 2370.1, "SUNLIT"), "culmination": pt(143, 8, 232.0, 10.9, 1489.3, "UMBRA"),
         "set": pt(147, 15, 173.4, 0.0, 2369.7, "UMBRA"), "in_progress": False, "duration_s": 493,
         "shadow_changes": [
             {"utc": at(140, 27), "kind": "penumbra entry", "from": "SUNLIT", "to": "PENUMBRA", "azimuth_deg": 281.0, "altitude_deg": 3.9},
             {"utc": at(140, 39), "kind": "umbra entry", "from": "PENUMBRA", "to": "UMBRA", "azimuth_deg": 279.2, "altitude_deg": 4.6}],
         "visible": None, "sun_altitude_deg": -33.3, "provenance": "predicted"},
    ]
    return {
        "available": True, "reason": None, "provenance": "external",
        "meaning": ("Predictions from orbital elements. 'Could be seen' means above 10°, not in the Earth's umbra, "
                    "and the Sun at least 6° below the horizon. It says nothing about brightness, cloud or obstructions."),
        "as_of_utc": now.isoformat(timespec="seconds"),
        "cache": {"dir": "(sample cache)", "satellites": 2,
                  "groups": [{"group": "stations", "file": "stations.tle", "count": 2, "rejected": 0,
                              "source": "(sample data)", "fetched_utc": (now - timedelta(hours=9)).isoformat(timespec="seconds"),
                              "newest_epoch_utc": epoch.isoformat(timespec="seconds"),
                              "oldest_epoch_utc": epoch.isoformat(timespec="seconds")}],
                  "newest_epoch_utc": epoch.isoformat(timespec="seconds"), "newest_age_days": 1.29,
                  "oldest_age_days": 1.29, "stale_after_days": 14.0, "problems": [], "provenance": "external"},
        "featured": [iss, css], "satellite": iss, "passes": passes, "matches": [], "window_hours": 24.0,
        "demo": {"note": "synthetic data — not a prediction"},
    }


def evidence(eid=None) -> dict:
    """Sample /api/evidence: one outage, written by the real store into a temporary directory."""
    import tempfile
    from . import evidence as ev
    now = time.time()
    # The sample outage starts on the hour, so its id stays the same between the
    # index call and the read call that names it (an id from the current second
    # changed between the two calls when a second boundary fell in between).
    hour = int(now // 3600) * 3600
    d = os.path.join(tempfile.gettempdir(), "gtp-demo-evidence")
    for name in (os.listdir(d) if os.path.isdir(d) else []):
        os.remove(os.path.join(d, name))
    start, end = hour - 3 * 3600, hour - 3 * 3600 + 3363
    store = ev.Store(directory=d, clock=lambda: now, tracking_files=[])
    event = {"schema": "gps-time.event/1", "id": f"pps-outage-{int(start)}", "type": "PPS_OUTAGE",
             "start_epoch": start, "start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(timespec="seconds"),
             "end_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(timespec="seconds"), "duration_s": 3363,
             "open": False, "classification": "GNSS RECEPTION ANOMALY", "classification_provenance": "inferred",
             "notes": ["sample data"]}
    store.write(event, "closed")
    out = store.index() if eid is None else (store.read(eid) or {"available": False, "reason": f"no evidence file for {eid!r}"})
    if eid is None:
        out["dir"] = "(sample data)"
    return out


def oscillator() -> dict:
    """Sample /api/oscillator payload: the real log fed two synthetic days (a
    crystal at about -0.3 ppm per degree C with the SoC warming by day)."""
    out = oscillator_log().report()
    out["storage"] = {**out["storage"], "path": "(sample data)"}
    out["problems"] = ["sample data"]
    return out


def oscillator_log():
    """The demo oscillator log itself (for the profile export in demo mode)."""
    import tempfile
    from . import oscillator as osc
    now = time.time()
    clock = [now - 2 * 86400]
    temp = [50.0]
    # Its own folder: the log also looks for profile files next to itself, and the demo saves none.
    folder = os.path.join(tempfile.gettempdir(), "gtp-demo-oscillator")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "oscillator-log.csv")
    try:
        os.remove(path)
    except OSError:
        pass
    log = osc.Log(path=path, clock=lambda: clock[0], temp_reader=lambda: temp[0],
                  identity={"serial_sha256": "0000000000000000", "model": "demo board"})
    for i in range(2 * 1440):
        clock[0] = now - 2 * 86400 + i * 60
        temp[0] = 50.0 + 6.0 * math.sin(2 * math.pi * (i / 1440.0 - 0.3)) + 0.3 * math.sin(i / 7.0)
        freq = 10.9 - 0.3 * (temp[0] - 50.0) + 0.002 * math.sin(i / 3.0)
        log.add({"Frequency": f"{abs(freq):.3f} ppm {'fast' if freq >= 0 else 'slow'}",
                 "Skew": "0.008 ppm", "Residual freq": "-0.000 ppm"}, True)
    return log


def ntp_service() -> dict:
    """Sample /api/ntp-service payload: the real tracker fed synthetic counters
    (about 14 requests a minute, a few dropped), two hours of history."""
    from . import ntpservice
    now = time.time()
    clock = [now]
    state = {"rx": 48210, "drop": 37}
    tracker = ntpservice.Tracker(clock=lambda: clock[0], reader=lambda: {
        "ntp_received": state["rx"], "ntp_dropped": state["drop"], "cmd_received": 412, "cmd_dropped": 0,
        "client_log_dropped": 0, "nts_ke_accepted": 0, "nts_ke_dropped": 0,
        "ntp_authenticated": 0, "ntp_interleaved": 96})
    for i in range(121):
        clock[0] = now - (120 - i) * 60
        state["rx"] += 12 + int(4 * (1 + math.sin(i / 7.0)))
        state["drop"] += 1 if i % 45 == 44 else 0
        tracker.update()
    out = tracker.report()
    out["note"] += " Sample data."
    return out


REFERENCE_SCENARIOS = ("agree", "disagree", "unreachable", "none")


def references(scenario="agree") -> dict:
    """Sample /api/references payload: the real logic on synthetic chronyc rows.
    Scenarios: agree (default), disagree, unreachable, none."""
    from . import chrony, references as refs
    if scenario not in REFERENCE_SCENARIOS:
        scenario = "agree"
    now = time.time()
    servers = [("192.0.2.10", 1, 0.0021, 0.018, 0.031), ("192.0.2.20", 1, -0.0034, 0.022, 0.038),
               ("198.51.100.7", 2, 0.0009, 0.015, 0.024)]
    shift = 0.180 if scenario == "disagree" else 0.0
    reach = "0" if scenario == "unreachable" else "377"

    def fmt(seconds):
        return f"{seconds * 1e6:+.0f}us" if abs(seconds) < 0.1 else f"{seconds * 1e3:+.0f}ms"

    def rows_at(i):
        lines = [_SRC_HDR.rstrip("\n"), _PPS_SEL, _NMEA_OK]
        for k, (addr, stratum, off, err, _delay) in enumerate(servers if scenario != "none" else []):
            o = off + shift + 0.0006 * math.sin(i / 9.0 + k)
            last = "-" if reach == "0" else "30"
            lines.append(f"^? {addr:<27} {stratum:>3} {8:>3} {reach:>5} {last:>5} {fmt(o):>8}[{fmt(o):>8}] +/- {err * 1e3:.0f}ms")
        return chrony.parse_sources("\n".join(lines) + "\n", local_addrs=frozenset())

    clock = [now - 180 * 300]
    ntp = {addr: {"peer_delay_s": delay, "root_delay_s": 0.0004} for addr, _s, _o, _e, delay in servers}
    tracker = refs.Tracker(clock=lambda: clock[0], ntpdata_reader=lambda: ntp)
    for i in range(181):                      # 15 h of history, one point every 5 min
        clock[0] = now - (180 - i) * 300
        tracker.update(rows_at(i), True)
    out = tracker.report()
    out["demo"] = {"scenario": scenario, "scenarios": list(REFERENCE_SCENARIOS), "note": "synthetic data — not a measurement"}
    return out


def timescales(now: float) -> dict:
    """Sample /api/timescales payload: the real calculation on the real clock,
    with a sample leap-second table (valid for another 200 days) and no IERS file."""
    from . import timescales as ts
    table = {"entries": ts._builtin_entries(), "updated": now - 120 * 86400, "expires": now + 200 * 86400,
             "source": "file", "path": "(sample leap-second list)", "problems": []}
    return {**ts.scales(table, now),
            "leap_seconds": ts.leap_status(table, now, "Normal"),
            "ut1": ts.ut1(now, path=os.path.join(os.path.dirname(__file__), "no-iers-file-in-demo"))}


def system_diagnostics() -> dict:
    return {
        "model": "Windows desktop demo", "kernel": "demo", "uptime_s": 12345,
        "load": [0.08, 0.12, 0.15],
        "mem": {"total_mb": 16384, "available_mb": 11820, "used_pct": 28},
        "disk": {"total_gb": 32.0, "free_gb": 24.6, "used_pct": 23},
        "cpu_mhz": 600, "core_volts": None, "power": None,
        # sample: under-voltage and throttling latched since boot, nothing now
        "throttled": system.decode_throttled("0x50000"),
        "power_note": "Sample diagnostics in desktop demo mode.",
        "ramlog": {"path": "/run/chrony-log/tracking.log", "in_ram": True,
                   "size_kb": 84.2, "flushed_age_s": 723},
    }


# ── timing chain demo scenarios ────────────────────────────────────────────
# Each scenario drives the real TimingChainService (parsers, state machine,
# banner, event tracker) with synthetic inputs over a short scripted timeline.
# Nothing is written to disk (event tracker has no checkpoint path).

_SRC_HDR = ("MS Name/IP address         Stratum Poll Reach LastRx Last sample\n"
            "===============================================================================\n")
_STATS_HDR = ("Name/IP Address            NP  NR  Span  Frequency  Freq Skew  Offset  Std Dev\n"
              "==============================================================================\n")
_PPS_SEL = "#* GPS                           0   4   377    13   +184ns[ +259ns] +/-  203ns"
_PPS_NOSAMPLE = "#? GPS                           0   4     0     -     +0ns[   +0ns] +/-    0ns"
_PPS_REJECT = "#x GPS                           0   4   377    12  +3125us[+3125us] +/-  210ns"
_PPS_RECOVER = "#? GPS                           0   4     7     3   +912ns[+1004ns] +/-  220ns"
_NMEA_OK = "#- NMEA                          0   4   377    14    +35ms[  +35ms] +/-  100ms"
_NMEA_SEL = "#* NMEA                          0   4   377    14    +35ms[  +35ms] +/-  100ms"
_NMEA_STALE = "#? NMEA                          0   4     0    17m   +35ms[  +35ms] +/-  100ms"
_NET_SEL = "^* 192.0.2.10                    2   6   377    41   +781us[ +822us] +/-   14ms"
_NET_OK = "^- 192.0.2.10                    2   6   377    41   +781us[ +822us] +/-   14ms"
_STATS = (_STATS_HDR +
          "GPS                        25  12   384     +0.000      0.012     +0ns   164ns\n"
          "NMEA                       32  17   496     +2.181      6.144    +35ms  1271us\n"
          "192.0.2.10                 10   6   644     -0.033      0.106  +1035us   178us\n")
_REFCFG = {"pps": {"driver": "PPS", "param": "/dev/pps0", "refid": "GPS", "lock": "NMEA",
                   "noselect": False, "prefer": True, "poll": None, "offset_s": 0.0},
           "nmea": {"driver": "SHM", "param": "0", "refid": "NMEA", "lock": None,
                    "noselect": True, "prefer": False, "poll": None, "offset_s": 0.1},
           "source": "chrony.conf"}


def _tracking(ref, stratum=1, leap="Normal"):
    return (f"Reference ID    : 47505300 ({ref})\nStratum         : {stratum}\n"
            f"System time     : 0.000000045 seconds fast of NTP time\n"
            f"Last offset     : +0.000000031 seconds\nRMS offset      : 0.000000312 seconds\n"
            f"Frequency       : 2.140 ppm slow\nRoot delay      : 0.000000001 seconds\n"
            f"Root dispersion : 0.000012000 seconds\nLeap status     : {leap}\n")


def _gnss(healthy):
    if not healthy:
        return {"data_age_s": 45.0, "stale": True, "sky_stale": True, "sky_age_s": 45.0,
                "fix": None, "sats": [], "tdop": None}
    sats = [{"id": 2 + i, "gnss": "GPS" if i < 6 else "GLONASS", "snr": s, "used": i < 9}
            for i, s in enumerate([43, 41, 38, 36, 34, 32, 31, 29, 27, 22])]
    return {"data_age_s": 0.8, "stale": False, "sky_stale": False, "sky_age_s": 0.8,
            "fix": "3D", "sats": sats, "tdop": 0.73}


TIMING_SCENARIOS = {
    "pps_selected": dict(desc="Normal: PPS selected by chrony", pulses="healthy", gnss=True,
                         sources=[_PPS_SEL, _NMEA_OK, _NET_OK], ref="GPS"),
    "pps_path_anomaly": dict(desc="GNSS healthy, kernel PPS events stopped 2 days ago, network failover",
                             pulses="lost", gnss=True, sources=[_PPS_NOSAMPLE, _NMEA_OK, _NET_SEL],
                             ref="192.0.2.10", stratum=3, outage_s=2 * 86400 + 4 * 3600),
    "pps_unused_nmea_stale": dict(desc="PPS pulses reach Linux; NMEA lock refclock stale; chrony not using PPS",
                                  pulses="healthy", gnss=True, sources=[_PPS_NOSAMPLE, _NMEA_STALE, _NET_SEL],
                                  ref="192.0.2.10", stratum=3, outage_s=3 * 3600),
    "pps_rejected": dict(desc="PPS pulses present; chrony marks the PPS refclock as a falseticker",
                         pulses="healthy", gnss=True, sources=[_PPS_REJECT, _NMEA_OK, _NET_SEL],
                         ref="192.0.2.10", stratum=3, outage_s=900),
    "network_failover": dict(desc="GNSS telemetry and PPS both unavailable; network failover",
                             pulses="lost", gnss=False, sources=[_PPS_NOSAMPLE, _NMEA_STALE, _NET_SEL],
                             ref="192.0.2.10", stratum=3, outage_s=5400),
    "holdover": dict(desc="No source selected; holdover", pulses="lost", gnss=False,
                     sources=[_PPS_NOSAMPLE, _NMEA_STALE], ref="GPS", outage_s=1200),
    "recovering": dict(desc="PPS pulses returned after a loss; chrony not yet selecting PPS",
                       pulses="recover", gnss=True, sources=[_PPS_RECOVER, _NMEA_OK, _NET_SEL],
                       ref="192.0.2.10", stratum=3, outage_s=2400),
    "device_missing": dict(desc="No /dev/pps0; NMEA refclock disciplining the clock", pulses="missing",
                           gnss=True, sources=[_PPS_NOSAMPLE, _NMEA_SEL, _NET_OK], ref="NMEA", outage_s=600),
    "chrony_unknown": dict(desc="chrony status unavailable", pulses="healthy", gnss=True, sources=None, ref=None),
    "acquiring": dict(desc="Booted 6 minutes ago; PPS not yet selected (not an outage)", pulses="healthy",
                      gnss=True, sources=[_PPS_RECOVER, _NMEA_OK, _NET_SEL], ref="192.0.2.10", stratum=3,
                      boot_ago_s=360),
}


def timing_chain(scenario="pps_selected"):
    from . import timing_chain as tc
    from .pps import PPSMonitor

    sc = TIMING_SCENARIOS.get(scenario) or TIMING_SCENARIOS["pps_selected"]
    end = time.time()
    outage = sc.get("outage_s")
    clock = [end - (outage or 0) - 25]
    now = lambda: clock[0]                                        # noqa: E731
    lost_at = clock[0] - 5
    seq0 = 100_000

    def reader():
        t = clock[0]
        if sc["pulses"] == "missing":
            return "missing", None, None
        if sc["pulses"] == "lost" or (sc["pulses"] == "recover" and t < end - 12):
            return "ok", lost_at, seq0
        return "ok", float(int(t)) + 1.2e-7, seq0 + int(t - lost_at)

    def device_state():
        if scenario == "chrony_unknown":
            return True, None
        return (sc["pulses"] != "missing"), None

    def chrony_reader():
        if sc["sources"] is None:
            return {"tracking_ok": False, "tracking_text": "", "sources_ok": False, "sources_text": "",
                    "sourcestats_ok": False, "sourcestats_text": ""}
        return {"tracking_ok": True, "tracking_text": _tracking(sc["ref"], sc.get("stratum", 1)),
                "sources_ok": True, "sources_text": _SRC_HDR + "\n".join(sc["sources"]) + "\n",
                "sourcestats_ok": True, "sourcestats_text": _STATS}

    svc = tc.TimingChainService(
        monitor=PPSMonitor(device="/dev/pps0", clock=now, reader=reader, device_state=device_state),
        tracker=tc.EventTracker(None, clock=now, debounce_s=0,
                                boot=(end - sc.get("boot_ago_s", 7 * 86400), "demo-boot")),
        chrony_reader=chrony_reader, gnss_reader=lambda: _gnss(sc["gnss"]),
        refclock_reader=lambda: _REFCFG,
        boot_config_reader=lambda: {"gpio": 18, "assert_edge": "rising", "source": "demo"},
        clock=now)
    times = ([clock[0]] if outage else []) + [end - 20 + i for i in range(21)]
    chain = None
    for t in times:
        clock[0] = t
        chain = svc.tick(refresh_chrony=True)
    chain["demo"] = {"scenario": scenario if scenario in TIMING_SCENARIOS else "pps_selected",
                     "description": sc["desc"], "scenarios": sorted(TIMING_SCENARIOS),
                     "note": "synthetic data — not a measurement"}
    return chain


def sdr_status() -> dict:
    """/api/sdr in demo mode: synthetic, in the station's shapes (gps_time_pi/sdr.py)."""
    from .labels import q

    def unit(name, what, cpu_s, avg, mem):
        return {"unit": name, "what": what, "active": q("active", None, "observed", "demo"), "sub": "running",
                "enabled": "enabled", "restarts": q(0, "count", "observed"),
                "cpu_s": q(cpu_s, "s", "observed"), "cpu_avg_pct": q(avg, "% of one core", "calculated"),
                "memory_mib": q(mem, "MiB", "observed")}

    def dongle(port, serial, role):
        return {"port": port, "serial": serial, "product": "RTL2838UHIDIR", "role": role,
                "speed_mbps": q(480, "Mb/s", "observed"), "dvb_driver": q(False, None, "observed")}
    return {
        "installed": True,
        "units": [unit("gps-time-rtl-tcp.service", "rtl_tcp (PPS markers)", 812.4, 6.3, 9.8),
                  unit("gps-time-readsb.service", "readsb (1090 MHz)", 2950.1, 22.8, 21.4),
                  unit("gps-time-dump978.service", "dump978-fa (978 MHz)", 4120.7, 31.9, 18.2),
                  unit("gps-time-skyaware978.service", "skyaware978 (978 MHz)", 61.0, 0.5, 4.1),
                  unit("gps-time-modules.service", "module supervisor", 140.2, 1.1, 58.0)],
        "dongles": [dongle("1-1.1", "00000pps", "PPS markers"), dongle("1-1.2", "00001090", "1090 MHz"),
                    dongle("1-1.3", "00000978", "978 MHz")],
        "feeds": [{"band": "1090", "path": "/run/readsb/aircraft.json", "present": True,
                   "age_s": q(0.6, "s", "observed"), "aircraft": q(23, "count", "observed"), "fresh": True},
                  {"band": "978", "path": "/run/skyaware978/aircraft.json", "present": True,
                   "age_s": q(1.4, "s", "observed"), "aircraft": q(3, "count", "observed"), "fresh": True}],
        "note": "Demo: synthetic values, not a station's.",
    }
