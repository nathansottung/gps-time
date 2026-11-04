"""Where this Pi's clock gets its time, and how good chrony says it is (GET /api/time-quality).

For labelling timestamps made here (clips, observation files): on the station the clock follows its
own GNSS/PPS reference clock; on an SDR node (docs/deploy/sdr-node.md) it follows the station over
NTP, so a node's timestamps are labelled ntp (owner, 2026-11-04).

  source     refclock (a local reference clock: the station's GNSS/PPS), ntp (a network server;
             on a node, the station), or unknown (chronyc can't be read, or not synchronised)
  max_error  chronyc's bound |System time| + Root dispersion + ½ Root delay (chrony.max_error_bound):
             `calculated`, and only as good as the reference itself (review GPS-007)

Read only: chronyc -n tracking, and the installer's /etc/default files.
"""
import ipaddress
import os
from pathlib import Path

from . import chrony
from .labels import q

NODE_ENV = Path(os.environ.get("GTP_NODE_ENV", "/etc/default/gps-time-node"))
PEER_ENV = Path(os.environ.get("GTP_SDR_NODE_ENV", "/etc/default/gps-time-sdr-node"))


def _env(path, key):
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key and v.strip():
                return v.strip()
    except OSError:
        pass
    return None


def role():
    """('sdr-node', station address) on a node; ('station', the node it reads or None) otherwise."""
    station = _env(NODE_ENV, "GTP_NODE_STATION")
    if station:
        return "sdr-node", station
    return "station", _env(PEER_ENV, "GTP_SDR_NODE")


def _is_ip(text):
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def current(run=chrony.run_chronyc):
    """The /api/time-quality answer."""
    r, peer = role()
    ok, text = run("tracking")
    out = {"role": r, "station": peer if r == "sdr-node" else None, "sdr_node": peer if r == "station" else None}
    if not ok:
        return {**out, "source": "unknown", "reference": None, "stratum": None,
                "max_error_s": q(None, "s", "calculated", "chronyc tracking can't be read"),
                "label": "UNKNOWN: chronyc can't be read"}
    trk = chrony.parse_tracking(text)
    qual = chrony.quality(trk)
    name = trk.get("reference_name")
    try:
        stratum = int(trk.get("Stratum"))
    except (TypeError, ValueError):
        stratum = None
    leap = (trk.get("Leap status") or "").lower()
    if not name or stratum in (None, 0) or "not synchronised" in leap:
        source = "unknown"
    elif _is_ip(name):
        source = "ntp"
    else:
        source = "refclock"
    bound = qual["max_error_bound_s"]
    label = {"refclock": f"refclock {name}", "ntp": f"ntp from {name}"}.get(source, "UNKNOWN: not synchronised")
    if bound is not None and source != "unknown":
        label += f", within ±{_fmt(bound)} (chrony's bound)"
    return {**out, "source": source, "reference": name, "stratum": stratum,
            "max_error_s": q(bound, "s", "calculated", "chrony: |System time| + Root dispersion + ½ Root delay"),
            "label": label}


def _fmt(s):
    for unit, k in (("s", 1), ("ms", 1e-3), ("µs", 1e-6), ("ns", 1e-9)):
        if abs(s) >= k:
            return f"{s / k:.3g} {unit}"
    return f"{s * 1e9:.3g} ns"
