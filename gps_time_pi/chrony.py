"""chrony interface: parsers for chronyc output, the synchronization state
machine, and the tracking-log reader that powers the History page."""

import os
import re
import subprocess
from datetime import datetime, timezone


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


_VERSION = None


def version():
    """chronyd version string, cached (it doesn't change while running)."""
    global _VERSION
    if _VERSION is None:
        out = _run(["chronyd", "--version"])
        _VERSION = out.strip().split("\n")[0] if out and not out.startswith("error") else ""
    return _VERSION or None


def tracking():
    out = {}
    for line in _run(["chronyc", "tracking"]).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


_SRC = re.compile(r"^(.)(.) (\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(.*)$")

STATE_LABEL = {"*": "selected", "+": "combined", "-": "available",
               "?": "not selectable", "x": "false ticker", "~": "too variable"}


def sources():
    rows, started = [], False
    for line in _run(["chronyc", "sources"]).splitlines():
        if line.startswith("==="):
            started = True
            continue
        if not started:
            continue
        m = _SRC.match(line)
        if m:
            mode, state, name, stratum, poll, reach, lastrx, sample = m.groups()
            rows.append({"mode": mode, "state": state,
                         "state_label": STATE_LABEL.get(state, state),
                         "name": name, "stratum": int(stratum), "poll": int(poll),
                         "reach": reach, "lastrx": lastrx, "sample": sample.strip()})
    return rows


def sourcestats():
    return _run(["chronyc", "sourcestats"])


def clients():
    rows, started = [], False
    for line in _run(["chronyc", "clients"]).splitlines():
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


def sync_state(trk, srcs, gps_fix_mode):
    """Derive the explicit overall state the plan doc requires.

    Returns (STATE, detail) where STATE is one of SYNCHRONIZED, HOLDOVER,
    DEGRADED, ACQUIRING, UNSYNCHRONIZED, NO GPS FIX.
    """
    leap = trk.get("Leap status", "")
    stratum = trk.get("Stratum", "")
    ref = trk.get("Reference ID", "")
    gps = next((s for s in srcs if s["name"] == "GPS"), None)

    if "Not synchronised" in leap:
        return ("UNSYNCHRONIZED",
                "Do not use this server as an authoritative time source.")
    on_gps = "GPS" in ref or "PPS" in ref
    gps_alive = gps is not None and gps["reach"] not in ("0", "")
    if on_gps and stratum == "1":
        if gps_alive:
            return ("SYNCHRONIZED", "GPS/PPS · Stratum 1")
        age = gps["lastrx"] if gps else "?"
        return ("HOLDOVER",
                f"GPS PPS not received for {age} s — clock maintained by "
                "learned oscillator correction.")
    if gps is not None and not gps_alive and gps_fix_mode is not None and gps_fix_mode < 2:
        return ("NO GPS FIX",
                f"Receiver has no position fix — serving stratum {stratum} "
                "from fallback internet sources.")
    if stratum and stratum != "1":
        return ("DEGRADED",
                f"Running on internet fallback sources at stratum {stratum}.")
    return ("ACQUIRING", "Collecting reference samples.")


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
