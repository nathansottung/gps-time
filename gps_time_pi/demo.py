"""Deterministic-ish demo data for desktop UI development.

Demo mode must not require gpsd, chrony, a Raspberry Pi, Skyfield, or network
access.  It exercises the same HTTP APIs and dashboard renderer as real mode.
Values are intentionally labelled as sample data in the UI.
"""

from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone

from . import __version__


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
        "astro_reason": None,
        "cpu_temp_c": 44.2,
        "versions": {"app": __version__, "chrony": "chrony 4.x (sample)", "gpsd": "3.x (sample)",
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
        points.append({"t": now - age, "offset_s": off, "err_s": 500e-9})
    return {"available": True, "points": points, "note": "sample data"}


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


def oscillator() -> dict:
    """Sample /api/oscillator payload: the real log fed a synthetic day (a
    crystal at about -0.3 ppm per degree C with the SoC warming by day)."""
    import tempfile
    from . import oscillator as osc
    now = time.time()
    clock = [now - 2 * 86400]
    temp = [50.0]
    path = os.path.join(tempfile.gettempdir(), "gtp-demo-oscillator.csv")
    try:
        os.remove(path)
    except OSError:
        pass
    log = osc.Log(path=path, clock=lambda: clock[0], temp_reader=lambda: temp[0],
                  identity={"serial_sha256": "demo", "model": "demo board"})
    for i in range(2 * 1440):
        clock[0] = now - 2 * 86400 + i * 60
        temp[0] = 50.0 + 6.0 * math.sin(2 * math.pi * (i / 1440.0 - 0.3)) + 0.3 * math.sin(i / 7.0)
        freq = 10.9 - 0.3 * (temp[0] - 50.0) + 0.002 * math.sin(i / 3.0)
        log.add({"Frequency": f"{abs(freq):.3f} ppm {'fast' if freq >= 0 else 'slow'}",
                 "Skew": "0.008 ppm", "Residual freq": "-0.000 ppm"}, True)
    out = log.report()
    out["storage"] = {**out["storage"], "path": "(sample data)"}
    out["problems"] = ["sample data"]
    return out


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
        "cpu_mhz": 600, "core_volts": None, "throttled": None, "power": None,
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
