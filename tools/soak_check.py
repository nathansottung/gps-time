#!/usr/bin/env python3
"""Read-only soak check of a GPS Time station before tagging a stable release.

    python tools/soak_check.py http://<station> [--expect 1.4.0-rc.11] [--days 3]

Only HTTP GETs: /api, /api/timing-chain, /api/stability, /api/evidence, /api/ping, and
/api/almanac as load during the round-trip test. Nothing on the station is changed.
Prints a report; exit status 0 when every criterion is clean, 1 when not, 2 when the
station can't be read.

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
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.request

INSTALLER_GRACE_S = 300


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


def report(base, results, when=None):
    when = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(when))
    clean = all(ok for _, ok, _ in results)
    lines = [f"Soak check of {base} at {when}"]
    lines += [f"[{'OK ' if ok else 'NO '}] {name}: {detail}" for name, ok, detail in results]
    lines.append("CLEAN" if clean else "NOT CLEAN")
    return "\n".join(lines), clean


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only soak check of a GPS Time station (HTTP GETs only).")
    ap.add_argument("base", help="station URL, e.g. http://192.0.2.10")
    ap.add_argument("--expect", required=True, help="the version the station must report, e.g. 1.4.0-rc.11")
    ap.add_argument("--days", type=float, default=3.0, help="minimum run time since the service start (default 3)")
    a = ap.parse_args(argv)
    base = a.base.rstrip("/")
    try:
        core, chain = get(base, "/api"), get(base, "/api/timing-chain")
        stab, evid = get(base, "/api/stability"), get(base, "/api/evidence")
        idle, loaded = ping_ms(base), ping_ms(base, load=True)
    except Exception as e:  # noqa: BLE001
        print(f"station not readable at {base}: {e}")
        return 2
    text, clean = report(base, evaluate(core, chain, stab, evid, idle, loaded, a.expect, a.days))
    print(text)
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
