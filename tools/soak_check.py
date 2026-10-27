#!/usr/bin/env python3
"""Read-only soak check of a GPS Time station before tagging a stable release.

    python tools/soak_check.py http://<station> [--expect 1.4.0-rc.11] [--days 3]

Only HTTP GETs: /api, /api/timing-chain, /api/stability, /api/evidence, /api/ping, and
/api/almanac as load during the round-trip test; for the record, /api/system and /api/sdr.
Nothing on the station is changed. Prints a report; exit status 0 when every criterion is
clean, 1 when not, 2 when the station can't be read.

The criteria are fixed before a run (docs/provenance/change-log.md, #95) so a result can't
be argued into passing:

  version     /api versions.app is the expected version
  runtime     the PPS poller has run at least --days (one read a second since the service start)
  timing      timing status GPS_PPS now
  outages     no outage event since the service start, except the installer's own: "PPS NOT USED
              BY CHRONY" with healthy pulses within 5 minutes of the start (install.sh restarts chrony)
  pulses      missed + unread <= 1e-4 of reads; late reads <= 1e-3 of reads; longest gap < 2.5 s
  rtt         /api/ping from here: median < 50 ms and max < 250 ms, idle and under /api/almanac load
  stability   available; ADEV at 1, 10, 100, 1000 s present; ADEV(1 s) in [1e-9, 1e-5];
              PPS selected >= 99 % of the seconds series; gaps <= 0.1 % of its samples

The record (v1.6.0, owner 2026-10-27) follows the criteria and is never one: the SDR load
(each SDR unit's CPU now, over --window seconds, and since its start; memory; restarts), the
load averages, the USB dongles and the power flags, the SoC temperature, and the PPS jitter
figures beside them (chrony's PPS standard deviation, the RMS offset, ADEV and TDEV at 1 s).
It is printed as [REC] lines, changes no exit status, and says UNKNOWN for what the station
doesn't report (a station before v1.6.0 has no /api/sdr).
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.request

INSTALLER_GRACE_S = 300
RECORD_WINDOW_S = 30.0


def get(base, path, timeout=20):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read())


def _val(m):
    return m.get("value") if isinstance(m, dict) else m


def ping_ms(base, n=20, load=False, fetch=get):
    """Round trips of /api/ping in ms; with load, two threads request /api/almanac meanwhile."""
    stop = threading.Event()

    def hammer():
        while not stop.is_set():
            try:
                fetch(base, "/api/almanac?tz=UTC", 30)
            except Exception:  # noqa: BLE001 - load only; failures don't matter here
                pass
    threads = [threading.Thread(target=hammer, daemon=True) for _ in range(2)] if load else []
    for t in threads:
        t.start()
    out = []
    try:
        for i in range(n):
            t0 = time.perf_counter()
            fetch(base, f"/api/ping?n={i}")
            out.append((time.perf_counter() - t0) * 1000)
            time.sleep(0.2)
    finally:
        stop.set()
    return out


def installer_restart(event, started):
    """The event install.sh causes by restarting chrony: PPS not yet selected, pulses healthy, at the start."""
    at = (event.get("evidence") or {}).get("at_start") or {}
    return (event.get("classification") == "PPS NOT USED BY CHRONY" and at.get("pulse_health") == "HEALTHY"
            and (event.get("start_epoch") or 0) <= started + INSTALLER_GRACE_S)


def evaluate(core, chain, stab, evid, idle_ms, loaded_ms, expect, days=3.0, now=None):
    """[(name, ok, detail)] for the station's answers. Pure: no I/O, so it can be tested."""
    now = time.time() if now is None else now
    out = []

    def check(name, ok, detail):
        out.append((name, bool(ok), detail))

    v = (core.get("versions") or {}).get("app")
    check("version", v == expect, f"{v} (expected {expect})")

    pps = chain.get("pps") or {}
    poller = pps.get("poller") or {}
    polls = poller.get("polls") or 0
    check("runtime", polls >= days * 86400, f"{polls} PPS reads = {polls / 86400:.2f} days since the service started (need {days:g})")

    q = core.get("quality") or {}
    code = (chain.get("status") or {}).get("code")
    check("timing", code == "GPS_PPS", f"status {code}; stratum {q.get('stratum')}; reference {q.get('reference')}")

    ev = chain.get("events") or {}
    started = now - polls
    since = [e for e in ev.get("recent") or [] if (e.get("start_epoch") or 0) >= started - 60]
    real = [e for e in since if not installer_restart(e, started)]
    # no "events" in the answer is UNKNOWN, not "no outages"
    check("outages", "events" in chain and not ev.get("open") and not real,
          f"open: {bool(ev.get('open'))}; since the service started: {len(real)} (+{len(since) - len(real)} installer restart); "
          f"evidence files: {len(evid.get('files') or [])}"
          + "".join(f"\n        - {e.get('type')} {e.get('start_utc')} {e.get('duration_s')} s, {e.get('classification')}"
                    for e in real[:10]))

    missed, unread = _val(pps.get("missed_pulses")) or 0, _val(pps.get("unread_pulses")) or 0
    late, gap = poller.get("late_polls") or 0, poller.get("max_poll_gap_s")
    frac = (missed + unread) / polls if polls else 1.0
    check("pulses", polls > 0 and frac <= 1e-4 and late <= 1e-3 * polls and gap is not None and gap < 2.5,
          f"missed {missed}, unread {unread} ({frac:.2e} of reads); late reads {late}; longest gap {gap} s")

    ok_rtt = bool(idle_ms and loaded_ms) and all(statistics.median(x) < 50 and max(x) < 250 for x in (idle_ms, loaded_ms))
    check("rtt", ok_rtt, "no samples" if not (idle_ms and loaded_ms) else
          f"idle median {statistics.median(idle_ms):.1f} ms, max {max(idle_ms):.1f} ms; under /api/almanac load "
          f"median {statistics.median(loaded_ms):.1f} ms, max {max(loaded_ms):.1f} ms")

    sec = (stab.get("series") or {}).get("seconds") or {}
    adev = {k.get("label"): (k.get("point") or {}).get("adev") for k in stab.get("key_points") or []}
    a1 = adev.get("1 s")
    samples, gaps, sel = sec.get("samples") or 0, sec.get("gaps") or 0, sec.get("pps_selected_fraction")
    check("stability",
          stab.get("available") and all(adev.get(t) for t in ("1 s", "10 s", "100 s", "1000 s"))
          and a1 is not None and 1e-9 <= a1 <= 1e-5 and sel is not None and sel >= 0.99
          and samples > 0 and gaps <= 1e-3 * samples,
          "ADEV " + ", ".join(f"{k} {v:.2e}" if v else f"{k} —" for k, v in adev.items())
          + f"; seconds series {samples} samples, {gaps} gaps, PPS selected {sel}")
    return out


def _num(v, fmt, unit=""):
    return "UNKNOWN" if v is None else f"{v:{fmt}}{unit}"


def _ns(v):
    return "UNKNOWN" if v is None else f"{v * 1e9:.0f} ns"


def _sdr_units(sdr):
    units = sdr.get("units") if isinstance(sdr, dict) else None
    return [u for u in units if isinstance(u, dict)] if isinstance(units, list) else None


def record(core, chain, stab, system, sdr_a, sdr_b, dt):
    """[(name, detail)] for the soak record: the SDR load and the timing figures beside it.
    Never a criterion. Pure: no I/O, so it can be tested."""
    out = []
    units_a, units_b = _sdr_units(sdr_a), _sdr_units(sdr_b)
    if units_b is None:
        out.append(("sdr", "UNKNOWN: no SDR status from this station (/api/sdr: before v1.6.0, or systemctl unreadable)"))
    else:
        before = {u.get("unit"): _val(u.get("cpu_s")) for u in units_a or []}
        running = [u for u in units_b if _val(u.get("active")) == "active"]
        lines, total = [], 0.0
        for u in units_b:
            name = u.get("unit")
            now_s, was_s = _val(u.get("cpu_s")), before.get(name)
            rate = None
            if now_s is not None and was_s is not None and dt and dt > 0 and now_s >= was_s:
                rate = 100.0 * (now_s - was_s) / dt
                total += rate
            lines.append(f"\n        - {name}: {_val(u.get('active')) or 'UNKNOWN'}; CPU {_num(rate, '.1f', ' %')} over the "
                         f"last {dt:.0f} s, {_num(_val(u.get('cpu_avg_pct')), '.1f', ' %')} since its start; "
                         f"{_num(_val(u.get('memory_mib')), '.0f', ' MiB')}; restarts {_num(_val(u.get('restarts')), 'd')}")
        out.append(("sdr", f"{len(running)} of {len(units_b)} units running; CPU of all of them {total:.1f} % of one core "
                           f"over the last {dt:.0f} s" + "".join(lines)))
    load = system.get("load") if isinstance(system, dict) else None
    out.append(("cpu", "load averages " + (" / ".join(f"{x:.2f}" for x in load) + " (1, 5, 15 min)"
                                           if isinstance(load, list) and len(load) == 3 else "UNKNOWN")))
    dongles = sdr_b.get("dongles") if isinstance(sdr_b, dict) else None
    thr = system.get("throttled") if isinstance(system, dict) else None
    power = ("UNKNOWN" if not isinstance(thr, dict) else
             f"throttled flags {thr.get('raw')}" + (": " + ", ".join(f["label"] for f in thr.get("flags") or [] if f.get("active"))
                                                     if thr.get("any_now") or thr.get("any_ever") else " (none now or since boot)"))
    if isinstance(dongles, list):
        ds = "; ".join(f"{d.get('serial') or 'UNKNOWN'} ({d.get('role') or 'no role'}) {_num(_val(d.get('speed_mbps')), 'd', ' Mb/s')}"
                       + (" DVB-T driver holds it" if _val(d.get("dvb_driver")) else "") for d in dongles)
        out.append(("usb", f"{len(dongles)} RTL-SDR{'s' if len(dongles) != 1 else ''}" + (f": {ds}" if ds else "") + f"; {power}"))
    else:
        out.append(("usb", f"RTL-SDRs UNKNOWN; {power}"))
    out.append(("temperature", f"SoC {_num(core.get('cpu_temp_c'), '.1f', ' °C')} now"))
    pps = (chain.get("chrony") or {}).get("pps") or {}
    adev = {k.get("label"): (k.get("point") or {}) for k in stab.get("key_points") or []}
    one = adev.get("1 s") or {}
    out.append(("pps jitter", f"chrony PPS std dev {_ns(_val(pps.get('std_dev_s')))}; RMS offset "
                              f"{_ns((core.get('quality') or {}).get('rms_offset_s'))}; ADEV(1 s) "
                              f"{_num(one.get('adev'), '.2e')}; TDEV(1 s) {_ns(one.get('tdev_s'))}"))
    return out


def report(base, results, when=None, rec=()):
    when = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(when))
    clean = all(ok for _, ok, _ in results)
    lines = [f"Soak check of {base} at {when}"]
    lines += [f"[{'OK ' if ok else 'NO '}] {name}: {detail}" for name, ok, detail in results]
    lines.append("CLEAN" if clean else "NOT CLEAN")
    if rec:
        lines.append("Record (not criteria; no effect on CLEAN):")
        lines += [f"[REC] {name}: {detail}" for name, detail in rec]
    return "\n".join(lines), clean


def record_from(base, core, chain, stab, window, fetch=get):
    """The record's own GETs; anything unreadable is UNKNOWN in the record, never an error."""
    def maybe(path):
        try:
            return fetch(base, path)
        except Exception:  # noqa: BLE001 - the record never fails the check
            return None
    system, sdr_a = maybe("/api/system"), maybe("/api/sdr")
    t0 = time.monotonic()
    if _sdr_units(sdr_a):
        time.sleep(window)
    sdr_b = maybe("/api/sdr") if _sdr_units(sdr_a) else sdr_a
    try:
        return record(core, chain, stab, system or {}, sdr_a, sdr_b, time.monotonic() - t0 if _sdr_units(sdr_a) else 0.0)
    except Exception as e:  # noqa: BLE001
        return [("record", f"UNKNOWN: {e}")]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only soak check of a GPS Time station (HTTP GETs only).")
    ap.add_argument("base", help="station URL, e.g. http://192.0.2.10")
    ap.add_argument("--expect", required=True, help="the version the station must report, e.g. 1.4.0-rc.11")
    ap.add_argument("--days", type=float, default=3.0, help="minimum run time since the service start (default 3)")
    ap.add_argument("--window", type=float, default=RECORD_WINDOW_S,
                    help="seconds between the two SDR samples for the record's CPU now (default 30)")
    a = ap.parse_args(argv)
    base = a.base.rstrip("/")
    try:
        core, chain = get(base, "/api"), get(base, "/api/timing-chain")
        stab, evid = get(base, "/api/stability"), get(base, "/api/evidence")
        idle, loaded = ping_ms(base), ping_ms(base, load=True)
    except Exception as e:  # noqa: BLE001
        print(f"station not readable at {base}: {e}")
        return 2
    results = evaluate(core, chain, stab, evid, idle, loaded, a.expect, a.days)
    text, clean = report(base, results, rec=record_from(base, core, chain, stab, a.window))
    print(text)
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
