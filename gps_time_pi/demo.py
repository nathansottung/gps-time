"""Deterministic-ish demo data for desktop UI development.

Demo mode must not require gpsd, chrony, a Raspberry Pi, Skyfield, or network
access.  It exercises the same HTTP APIs and dashboard renderer as real mode.
Values are intentionally labelled as sample data in the UI.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone


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
        "state": ["SYNCHRONIZED", "GPS/PPS · Stratum 1 · sample data"],
        "quality": {
            "system_time_s": system_s,
            "last_offset_s": 118e-9,
            "rms_offset_s": rms,
            "root_delay_s": 0.0,
            "root_dispersion_s": dispersion,
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
        "fmt": {
            "system_pair": "145 ns fast ± 485 ns",
            "rms": "312 ns",
            "root_dispersion": "485 ns",
            "root_delay": "0 ns",
        },
        "sources": sources,
        "sourcestats": "Sample source statistics for desktop demo mode.",
        "clients": [
            {"host": "192.168.10.21", "ntp_packets": 18421, "dropped": "0", "last": "7"},
            {"host": "192.168.10.42", "ntp_packets": 9218, "dropped": "0", "last": "18"},
            {"host": "192.168.10.77", "ntp_packets": 4101, "dropped": "0", "last": "61"},
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
        "cpu_temp_c": 44.2,
        "versions": {"app": "demo", "chrony": "chrony 4.x (sample)", "gpsd": "3.x (sample)",
                     "receiver": {"driver": "u-blox", "firmware": "MAX-M8Q sample", "path": "/dev/ttyAMA0"},
                     "python": "desktop demo"},
    }


def almanac_api(_qs=None) -> dict:
    now = datetime.now().astimezone()
    start = now.replace(hour=6, minute=47, second=15, microsecond=0)
    noon = now.replace(hour=13, minute=6, second=43, microsecond=0)
    end = now.replace(hour=19, minute=24, second=17, microsecond=0)
    daylight = (end - start).total_seconds()
    return {
        "available": True,
        "demo": True,
        "sun": {
            "available": True,
            "date": now.date().isoformat(),
            "tz": str(now.tzinfo),
            "events": {"sunrise": start.isoformat(), "sunset": end.isoformat()},
            "noon": noon.isoformat(), "daylight_s": daylight, "bar": [], "notes": [],
        },
        "delta_yesterday": -182.8,
        "delta_tomorrow": -181.7,
        "moon": {"available": True, "phase": "Waxing crescent", "illum": 28.4,
                 "rise": (start + timedelta(hours=3)).isoformat(),
                 "set": (end + timedelta(hours=3)).isoformat()},
        "night": {"available": True},
        "sky": {},
        "sky_when": now.strftime("%Y-%m-%d %H:%M %Z"),
        "position_provenance": "demo",
        "position_age": None,
        "neighbors": {
            "yesterday": {"sunrise": (start - timedelta(days=1, seconds=56.7)).isoformat(),
                          "sunset": (end - timedelta(days=1, seconds=-126.1)).isoformat(),
                          "daylight_s": daylight + 182.8},
            "tomorrow": {"sunrise": (start + timedelta(days=1, seconds=56.9)).isoformat(),
                         "sunset": (end + timedelta(days=1, seconds=-124.8)).isoformat(),
                         "daylight_s": daylight - 181.7},
        },
    }


def history() -> dict:
    now = time.time()
    points = []
    for i in range(180):
        age = (179 - i) * 60
        off = (260e-9 * math.sin(i / 11.0)) + (80e-9 * math.sin(i / 3.1))
        points.append({"t": now - age, "offset_s": off, "err_s": 500e-9})
    return {"available": True, "points": points, "note": "sample data"}


def system_diagnostics() -> dict:
    return {
        "model": "Windows desktop demo", "kernel": "demo", "uptime_s": 12345,
        "load": [0.08, 0.12, 0.15],
        "mem": {"total_mb": 16384, "available_mb": 11820, "used_pct": 28},
        "disk": {"total_gb": 32.0, "free_gb": 24.6, "used_pct": 23},
        "cpu_mhz": 600, "core_volts": None, "throttled": None, "power": None,
        "power_note": "Sample diagnostics in desktop demo mode.",
        "ramlog": {"path": "/run/chrony-log/tracking.log", "in_ram": True,
                   "size_kb": 84.2, "flushed_age_s": 723},
    }
