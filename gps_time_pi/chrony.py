"""chrony interface: parsers for chronyc output, the synchronization state
banner, and the tracking-log reader that powers the History page.

All chronyc calls use -n (numeric addresses, no reverse DNS) so they stay fast
and offline-safe. The parse_* functions are pure so tests can feed fixtures.
"""

import glob
import os
import re
import subprocess
from datetime import datetime, timezone


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def run_chronyc(*args):
    """Run `chronyc -n <args>`. Returns (ok, stdout). ok is False when chronyc
    is missing, times out, or exits non-zero — callers must then report UNKNOWN."""
    try:
        r = subprocess.run(["chronyc", "-n", *args], capture_output=True, text=True, timeout=3)
    except Exception:  # noqa: BLE001
        return False, ""
    return r.returncode == 0 and bool(r.stdout.strip()), r.stdout


# ── value parsers ───────────────────────────────────────────────────────────

_UNIT_S = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}
_INTERVAL_S = {"": 1, "m": 60, "h": 3600, "d": 86400, "y": 31536000}


def parse_quantity_s(text):
    """'-312ns' / '+1027us' / '35ms' -> seconds (float), or None."""
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)(ns|us|ms|s)\s*", text or "")
    return float(m.group(1)) * _UNIT_S[m.group(2)] if m else None


def parse_interval_s(text):
    """chronyc LastRx/Span: '13', '17m', '3h', '2d', '1y' -> seconds; '-' -> None."""
    m = re.fullmatch(r"\s*(\d+)([mhdy]?)\s*", text or "")
    return int(m.group(1)) * _INTERVAL_S[m.group(2)] if m else None


# chronyc source state symbols, as documented by chrony. These are chrony's own
# classifications; this module never adds a reason chrony does not report.
STATE_LABEL = {"*": "selected", "+": "combined", "-": "available",
               "?": "not selectable", "x": "false ticker", "~": "too variable"}
STATE_MEANING = {
    "*": "current best source, used to discipline the clock",
    "+": "acceptable source combined with the selected source",
    "-": "acceptable source excluded by the combining algorithm",
    "?": "connectivity lost or samples fail chrony's tests (also shown until enough samples exist)",
    "x": "chrony considers this a falseticker (time inconsistent with the majority)",
    "~": "time appears too variable",
}
MODE_LABEL = {"^": "server", "=": "peer", "#": "local reference clock"}

_SRC_ROW = re.compile(
    r"^(?P<mode>[\^=#])(?P<state>[*+\-?x~ ])\s(?P<name>\S+)\s+(?P<stratum>\d+)\s+"
    r"(?P<poll>-?\d+)\s+(?P<reach>[0-7]+)\s+(?P<lastrx>\S+)\s+(?P<sample>.*)$")
_SAMPLE = re.compile(
    r"(?P<adj>[+-]?\d+(?:\.\d+)?(?:ns|us|ms|s))\s*\[\s*(?P<meas>[+-]?\d+(?:\.\d+)?(?:ns|us|ms|s))\s*\]"
    r"\s*\+/-\s*(?P<err>\d+(?:\.\d+)?(?:ns|us|ms|s))")


def parse_sources(text):
    """Parse `chronyc -n sources` into a list of dicts (one per source)."""
    rows, started = [], False
    for line in (text or "").splitlines():
        if line.startswith("==="):
            started = True
            continue
        if not started:
            continue
        m = _SRC_ROW.match(line.rstrip())
        if not m:
            continue
        g = m.groupdict()
        state = g["state"].strip() or " "
        sm = _SAMPLE.search(g["sample"])
        reach = int(g["reach"], 8)
        rows.append({
            "mode": g["mode"], "mode_label": MODE_LABEL.get(g["mode"], g["mode"]),
            "state": state, "state_label": STATE_LABEL.get(state, state),
            "state_meaning": STATE_MEANING.get(state),
            "name": g["name"], "stratum": int(g["stratum"]), "poll": int(g["poll"]),
            "reach": g["reach"], "reach_bits": bin(reach).count("1"), "reach_int": reach,
            "lastrx": g["lastrx"], "lastrx_s": parse_interval_s(g["lastrx"]),
            "sample": g["sample"].strip(),
            "offset_s": parse_quantity_s(sm.group("adj")) if sm else None,
            "measured_offset_s": parse_quantity_s(sm.group("meas")) if sm else None,
            "error_bound_s": parse_quantity_s(sm.group("err")) if sm else None,
        })
    return rows


_STATS_ROW = re.compile(
    r"^(?P<name>\S+)\s+(?P<np>\d+)\s+(?P<nr>\d+)\s+(?P<span>\S+)\s+(?P<freq>[+-]?\d+(?:\.\d+)?)\s+"
    r"(?P<skew>\d+(?:\.\d+)?)\s+(?P<offset>\S+)\s+(?P<sd>\S+)\s*$")


def parse_sourcestats(text):
    """Parse `chronyc -n sourcestats` into {name: stats}."""
    out, started = {}, False
    for line in (text or "").splitlines():
        if line.startswith("==="):
            started = True
            continue
        m = _STATS_ROW.match(line.strip()) if started else None
        if m:
            g = m.groupdict()
            out[g["name"]] = {
                "samples": int(g["np"]), "runs": int(g["nr"]),
                "span_s": parse_interval_s(g["span"]),
                "frequency_ppm": float(g["freq"]), "skew_ppm": float(g["skew"]),
                "offset_s": parse_quantity_s(g["offset"]), "std_dev_s": parse_quantity_s(g["sd"]),
            }
    return out


def parse_tracking(text):
    """Parse `chronyc -n tracking` into {field: raw string} plus 'reference_name'."""
    out = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    m = re.search(r"\(([^)]*)\)", out.get("Reference ID", ""))
    out["reference_name"] = m.group(1) if m else None
    return out


# ── refclock configuration (read-only) ──────────────────────────────────────

CHRONY_CONF = os.environ.get("GTP_CHRONY_CONF", "/etc/chrony/chrony.conf")


def _conf_lines(path, seen=None):
    seen = seen if seen is not None else set()
    if path in seen or not os.path.isfile(path):
        return []
    seen.add(path)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    for raw in lines:
        line = raw.strip()
        if not line or line[0] in "#!;%":   # chrony comment lines
            continue
        words = line.split()
        if words[0] == "include" and len(words) > 1:
            for p in sorted(glob.glob(words[1])):
                out += _conf_lines(p, seen)
        elif words[0] == "confdir" and len(words) > 1:
            for d in words[1:]:
                for p in sorted(glob.glob(os.path.join(d, "*.conf"))):
                    out += _conf_lines(p, seen)
        else:
            out.append(words)
    return out


def refclock_config(path=None):
    """Identify the PPS and NMEA/serial refclocks from chrony's configuration.

    Refids differ between profiles (the project's PPS profile uses refid GPS for
    PPS; its NMEA-only profile uses refid GPS for NMEA), so names alone are not
    enough. Returns {'pps': {...}|None, 'nmea': {...}|None, 'source': ...}.
    """
    words_list = _conf_lines(path or CHRONY_CONF)
    pps, nmea, index = None, None, {}
    for w in words_list:
        if w[0] != "refclock" or len(w) < 3:
            continue
        driver, param = w[1].upper(), w[2]
        n = index.get(driver, 0)
        index[driver] = n + 1
        opts = {}
        i = 3
        while i < len(w):
            key = w[i]
            if key in ("refid", "lock", "poll", "dpoll", "offset", "delay", "precision", "filter", "rate", "pps"):
                opts[key] = w[i + 1] if i + 1 < len(w) else None
                i += 2
            else:
                opts[key] = True
                i += 1
        refid = opts.get("refid") or f"{driver[:3]}{n}"
        entry = {"driver": driver, "param": param, "refid": refid,
                 "lock": opts.get("lock"), "noselect": bool(opts.get("noselect")),
                 "prefer": bool(opts.get("prefer")), "poll": opts.get("poll")}
        is_pps = driver == "PPS" or (driver in ("SOCK", "SHM") and "PPS" in refid.upper())
        if is_pps and pps is None:
            pps = entry
        elif not is_pps and driver in ("SHM", "SOCK") and nmea is None:
            nmea = entry
    if words_list:
        return {"pps": pps, "nmea": nmea, "source": "chrony.conf"}
    return {"pps": None, "nmea": None, "source": "unavailable"}


_VERSION = None


def version():
    """chronyd version string, cached (it doesn't change while running)."""
    global _VERSION
    if _VERSION is None:
        out = _run(["chronyd", "--version"])
        _VERSION = out.strip().split("\n")[0] if out and not out.startswith("error") else ""
    return _VERSION or None


def tracking():
    """`chronyc -n tracking` as {field: value}; {} when chronyc is unavailable."""
    ok, out = run_chronyc("tracking")
    return parse_tracking(out) if ok else {}


def sources():
    """`chronyc -n sources` rows (legacy keys plus parsed numeric fields)."""
    ok, out = run_chronyc("sources")
    return parse_sources(out) if ok else []


def sourcestats():
    ok, out = run_chronyc("sourcestats")
    return out if ok else ""


def clients():
    rows, started = [], False
    ok, out = run_chronyc("clients")
    for line in (out if ok else "").splitlines():
        if line.startswith("==="):
            started = True
            continue
        if not started or not line.strip():
            continue
        f = line.split()
        if len(f) >= 6 and f[1].isdigit():
            rows.append({"host": f[0], "ntp_packets": int(f[1]),
                         "dropped": f[2], "last": f[5]})
    return rows


def _parse_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _seconds(text):
    """'0.000000157 seconds slow of NTP time' -> signed float seconds."""
    if not text:
        return None
    m = re.match(r"([\d.eE+-]+)\s+seconds\s+(fast|slow)?", text)
    if not m:
        return None
    v = float(m.group(1))
    return -v if m.group(2) == "slow" else v


def sync_state(trk, srcs, gnss=None, pps=None, refclocks=None):
    """Top-level synchronization banner as (headline, detail).

    Replaced in feat/pps-chain: the banner always names what disciplines the
    clock and never reports GPS/PPS Stratum 1 unless chrony has the PPS
    refclock selected. Logic lives in timing_chain.timing_status().
    """
    from . import timing_chain
    st = timing_chain.timing_status(trk, srcs, gnss=gnss, pps=pps,
                                    refclocks=refclocks if refclocks is not None else refclock_config())
    return (st["headline"], st["banner"] + (" — " + st["detail"] if st["detail"] else ""))


def quality(trk):
    """The timing-quality panel, machine values in seconds."""
    sys_t = _seconds(trk.get("System time"))
    return {
        "system_time_s": sys_t,
        "last_offset_s": _parse_float((trk.get("Last offset", "").split() or [None])[0]),
        "rms_offset_s": _parse_float((trk.get("RMS offset", "").split() or [None])[0]),
        "root_delay_s": _parse_float((trk.get("Root delay", "").split() or [None])[0]),
        "root_dispersion_s": _parse_float((trk.get("Root dispersion", "").split() or [None])[0]),
        "frequency": trk.get("Frequency"),
        "residual_freq": trk.get("Residual freq"),
        "skew": trk.get("Skew"),
        "update_interval": trk.get("Update interval"),
        "leap": trk.get("Leap status"),
        "stratum": trk.get("Stratum"),
        "reference": trk.get("Reference ID"),
        "ref_time": trk.get("Ref time (UTC)"),
    }


def _default_tracking_log():
    for p in ("/run/chrony-log/tracking.log", "/var/log/chrony/tracking.log"):
        if os.path.exists(p):
            return p
    return "/var/log/chrony/tracking.log"


TRACKING_LOG = os.environ.get("GTP_TRACKING_LOG") or _default_tracking_log()


def history(max_points=600):
    """Parse chrony's tracking.log into [{t, offset_s, err_s}, ...],
    downsampled to at most max_points. Requires `log tracking` in
    chrony.conf. Column positions per chrony 4.x tracking.log format:
    Date Time IP St Freq Skew Offset LeapCombined RootDelay RootDisp MaxError..."""
    rows = []
    try:
        with open(TRACKING_LOG) as f:
            for line in f:
                t = line.split()
                if len(t) < 7 or not t[0][:2].isdigit():
                    continue
                try:
                    when = datetime.strptime(t[0] + " " + t[1], "%Y-%m-%d %H:%M:%S")
                    when = when.replace(tzinfo=timezone.utc)
                    offset = float(t[6])
                except (ValueError, IndexError):
                    continue
                err = None
                for idx in (10, 9, 8):
                    if len(t) > idx:
                        v = _parse_float(t[idx])
                        if v is not None and v >= 0:
                            err = v
                            break
                rows.append({"t": when.timestamp(), "offset_s": offset, "err_s": err})
    except OSError:
        return {"available": False, "points": [],
                "note": "chrony tracking log not found — add 'log tracking' to chrony.conf"}
    if len(rows) > max_points:
        step = len(rows) / max_points
        rows = [rows[int(i * step)] for i in range(max_points)]
    return {"available": True, "points": rows, "note": None}
