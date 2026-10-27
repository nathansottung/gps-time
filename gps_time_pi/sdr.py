"""The optional SDR stack as the web service sees it, read only (/api/sdr, Administration).

Everything here is read from the running system; nothing is started, stopped or written:
- the units scripts/sdr-stack.sh installs (systemctl show, which needs no privilege), with
  their CPU time and memory from the cgroup files under /sys/fs/cgroup;
- the RTL-SDR dongles on USB (sysfs): serial, speed, the role the installer gave the serial,
  and whether the DVB-T driver holds the device;
- the decoders' aircraft.json files: age and how many aircraft, never a position.

A value that can't be read is None (UNKNOWN), never a guess. Each SDR module also gets its
readiness checks for Administration: what it needs that the station can observe.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from .labels import q

UNITS = {
    "gps-time-rtl-tcp.service": "rtl_tcp (PPS markers)",
    "gps-time-readsb.service": "readsb (1090 MHz)",
    "gps-time-dump978.service": "dump978-fa (978 MHz)",
    "gps-time-skyaware978.service": "skyaware978 (978 MHz)",
    "readsb.service": "readsb, the package's own unit",
    "gps-time-modules.service": "module supervisor",
}
SDR_UNITS = tuple(UNITS)[:4]
SHOW = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState", "NRestarts",
        "ActiveEnterTimestampMonotonic", "ControlGroup")
CGROUP = Path(os.environ.get("GTP_CGROUP_ROOT", "/sys/fs/cgroup"))
USB = Path(os.environ.get("GTP_USB_DEVICES", "/sys/bus/usb/devices"))
ENVFILE = Path(os.environ.get("GTP_SDR_ENV", "/etc/default/gps-time-sdr"))
# Realtek RTL2832U dongles (the generic and the original IDs).
RTL_IDS = {("0bda", "2838"), ("0bda", "2832")}
ROLES = {"GTP_SDR_PPS_SERIAL": "PPS markers", "GTP_SDR_1090_SERIAL": "1090 MHz", "GTP_SDR_978_SERIAL": "978 MHz"}
FEEDS = {"1090": Path(os.environ.get("GTP_FEED_1090", "/run/readsb/aircraft.json")),
         "978": Path(os.environ.get("GTP_FEED_978", "/run/skyaware978/aircraft.json"))}
FEED_FRESH_S = 60.0
MAX_FEED_BYTES = 4 * 1024 * 1024


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def show_units(names, run=subprocess.run):
    """{unit: {property: value}} from one `systemctl show`; {} when systemctl can't be run."""
    try:
        r = run(["systemctl", "show", "--no-pager", "-p", ",".join(SHOW), *names],
                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return {}
    if r.returncode != 0:
        return {}
    out, cur = {}, {}
    for line in (r.stdout + "\n").splitlines():
        if not line.strip():
            if cur.get("Id"):
                out[cur["Id"]] = cur
            cur = {}
            continue
        k, _, v = line.partition("=")
        cur[k] = v
    return out


def _cgroup_stats(cgroup):
    """(cpu_usage_usec, memory_bytes) from the unit's cgroup v2 files; None for each one unread."""
    if not cgroup:
        return None, None
    base = CGROUP / cgroup.lstrip("/")
    usage = None
    stat = _read(base / "cpu.stat")
    for line in (stat or "").splitlines():
        k, _, v = line.partition(" ")
        if k == "usage_usec":
            usage = _int(v)
    return usage, _int(_read(base / "memory.current"))


def units(run=subprocess.run, monotonic_us=None):
    """One row per known unit that is installed (LoadState loaded); None when systemctl can't be read."""
    now_us = monotonic_us if monotonic_us is not None else time.monotonic() * 1e6
    props = show_units(list(UNITS), run)
    if not props:
        return None
    rows = []
    for name, what in UNITS.items():
        p = props.get(name)
        if p is None:
            continue
        if p.get("LoadState") != "loaded":
            continue
        active = p.get("ActiveState")
        usage, mem = _cgroup_stats(p.get("ControlGroup")) if active == "active" else (None, None)
        since = _int(p.get("ActiveEnterTimestampMonotonic"))
        avg = None
        if usage is not None and since and now_us > since:
            avg = round(100.0 * usage / (now_us - since), 1)
        rows.append({
            "unit": name, "what": what,
            "active": q(active, None, "observed", "systemctl show ActiveState"),
            "sub": p.get("SubState"),
            "enabled": p.get("UnitFileState"),
            "restarts": q(_int(p.get("NRestarts")), "count", "observed"),
            "cpu_s": q(None if usage is None else round(usage / 1e6, 1), "s", "observed",
                       "CPU time since the unit started (cgroup cpu.stat)"),
            "cpu_avg_pct": q(avg, "% of one core", "calculated", "CPU time / time since the unit started"),
            "memory_mib": q(None if mem is None else round(mem / 1048576, 1), "MiB", "observed"),
        })
    return rows


def roles():
    """{serial: role} from the installer's /etc/default/gps-time-sdr."""
    out = {}
    for line in (_read(ENVFILE) or "").splitlines():
        k, _, v = line.partition("=")
        if k in ROLES and v.strip():
            out[v.strip()] = ROLES[k]
    return out


def dongles():
    """RTL-SDRs on USB, from sysfs."""
    by_serial = roles()
    rows = []
    try:
        entries = sorted(USB.iterdir())
    except OSError:
        return None
    for d in entries:
        if ":" in d.name:
            continue
        ident = (_read(d / "idVendor"), _read(d / "idProduct"))
        if ident not in RTL_IDS:
            continue
        serial = _read(d / "serial")
        driver = None
        try:
            driver = os.path.basename(os.readlink(d / f"{d.name}:1.0" / "driver"))
        except OSError:
            pass
        rows.append({
            "port": d.name, "serial": serial, "product": _read(d / "product"),
            "role": by_serial.get(serial) if serial else None,
            "speed_mbps": q(_int(_read(d / "speed")), "Mb/s", "observed", "sysfs speed"),
            "dvb_driver": q(driver == "dvb_usb_rtl28xxu", None, "observed",
                            "the DVB-T driver holds the device; the SDR software can't open it"),
        })
    return rows


def feed(band, now=None):
    """A decoder's aircraft.json: age and aircraft count (positions are never read out)."""
    now = time.time() if now is None else now
    path = FEEDS[band]
    try:
        st = path.stat()
    except OSError:
        return {"band": band, "path": path.as_posix(), "present": False, "age_s": q(None, "s", "observed"),
                "aircraft": q(None, "count", "observed"), "fresh": False}
    count = None
    if st.st_size <= MAX_FEED_BYTES:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            count = len(doc.get("aircraft") or []) if isinstance(doc, dict) else None
        except (OSError, ValueError):
            count = None
    age = round(max(0.0, now - st.st_mtime), 1)
    return {"band": band, "path": path.as_posix(), "present": True,
            "age_s": q(age, "s", "observed", "time since the decoder last wrote the file"),
            "aircraft": q(count, "count", "observed"), "fresh": age <= FEED_FRESH_S}


def status(run=subprocess.run, now=None, monotonic_us=None):
    """The whole /api/sdr answer."""
    rows = units(run, monotonic_us)
    return {
        "installed": None if rows is None else any(r["unit"] in SDR_UNITS for r in rows),
        "units": rows, "dongles": dongles(), "feeds": [feed("1090", now), feed("978", now)],
        "note": "Read only: the station starts, stops and configures none of this (docs/deploy/sdr-stack.md).",
    }


def _unit(st, name):
    return next((r for r in st["units"] or [] if r["unit"] == name), None)


def readiness(st, cfg):
    """{module: [{"check", "ok": True|False|None, "detail"}]} for the SDR modules."""
    mc = (cfg.get("module_config") or {}) if isinstance(cfg, dict) else {}
    out = {}

    rtl = _unit(st, "gps-time-rtl-tcp.service")
    rtl_ok = None if st["units"] is None else bool(rtl and rtl["active"]["value"] == "active")
    pps_cfg = mc.get("sdr-pps-marker") if isinstance(mc.get("sdr-pps-marker"), dict) else {}
    live = bool(pps_cfg.get("rtl_tcp")) and pps_cfg.get("fs_nominal") is not None
    out["sdr-pps-marker"] = [
        {"check": "rtl_tcp running", "ok": rtl_ok,
         "detail": (rtl["active"]["value"] if rtl else "gps-time-rtl-tcp.service is not installed (GTP_SDR=1)")},
        {"check": "live capture configured", "ok": live,
         "detail": "fs_nominal and an rtl_tcp plan are set" if live else
                   "needs fs_nominal and an rtl_tcp plan in the module's settings (its README)"},
        {"check": "PPS injected at the dongle", "ok": None,
         "detail": "not observable from here: the module's marker count shows it"},
    ]
    fresh = [f for f in st["feeds"] if f["fresh"]]
    adsb = []
    for f in st["feeds"]:
        adsb.append({"check": f"{f['band']} MHz feed", "ok": f["fresh"] if f["present"] else False,
                     "detail": (f"{f['path']} not found" if not f["present"] else
                                f"written {f['age_s']['value']} s ago" + ("" if f["fresh"] else " (stale)"))})
    adsb.append({"check": "at least one feed", "ok": bool(fresh), "detail": f"{len(fresh)} of 2 fresh"})
    out["reference-adsb"] = adsb
    return out
