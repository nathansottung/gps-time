"""The optional SDR stack as the web service sees it, read only (/api/sdr, Administration).

Everything here is read from the running system; nothing is started, stopped or written:
- the units scripts/sdr-stack.sh installs (systemctl show, which needs no privilege), with
  their CPU time and memory from the cgroup files under /sys/fs/cgroup;
- the RTL-SDR dongles on USB (sysfs): serial, speed, the role the installer gave the serial,
  and whether the DVB-T driver holds the device;
- the decoders' aircraft.json files: age, how many aircraft and messages per second, never a position;
- which dongle (by serial) each decoder uses, and which one the web SDR is pinned to (aircraft()).

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
WEB_ENVFILE = Path(os.environ.get("GTP_WEBSDR_ENV", "/etc/default/gps-time-websdr"))
MODEL = Path(os.environ.get("GTP_BOARD_MODEL", "/proc/device-tree/model"))
# The owner's limit (2026-11-04): at most 3 RTL-SDRs by serial on a Pi 4 (scripts/dongle-roles.sh).
LIMITED_MODELS = ("Raspberry Pi 4", "Raspberry Pi 400", "Raspberry Pi Compute Module 4")
MAX_PI4 = 3
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


def _env_values(path):
    out = {}
    for line in (_read(path) or "").splitlines():
        k, _, v = line.partition("=")
        v = v.strip().strip('"')
        if v and v != "none":
            out[k.strip()] = v
    return out


def assignments():
    """The dongle mapping, by serial, from the installers' files (None for a role with no dongle):
    {"1090", "978", "pps", "websdr"} and "websdr_band": the role whose dongle the web SDR takes
    ("1090", "978", or None for a dongle with no other role). Only that role's decoder pauses."""
    env = _env_values(ENVFILE)
    web = _env_values(WEB_ENVFILE).get("GTP_WEBSDR_SERIAL")
    out = {"1090": env.get("GTP_SDR_1090_SERIAL"), "978": env.get("GTP_SDR_978_SERIAL"),
           "pps": env.get("GTP_SDR_PPS_SERIAL"), "websdr": web}
    out["websdr_band"] = next((b for b in ("1090", "978") if web and out[b] == web), None)
    return out


def websdr_band():
    return assignments()["websdr_band"]


def websdr_running():
    """True while gps-time-websdr.service's cgroup exists; None when cgroups can't be read."""
    if not (CGROUP / "system.slice").is_dir():
        return None
    return (CGROUP / "system.slice" / "gps-time-websdr.service").is_dir()


def roles():
    """{serial: role} from the installers' /etc/default/gps-time-sdr and gps-time-websdr. The web SDR
    may share the 1090 MHz dongle: then that serial's role names both."""
    out = {}
    for k, v in _env_values(ENVFILE).items():
        if k in ROLES:
            out[v] = ROLES[k]
    web = _env_values(WEB_ENVFILE).get("GTP_WEBSDR_SERIAL")
    if web:
        out[web] = f"{out[web]} + web SDR" if web in out else "web SDR"
    return out


def limit(dongle_rows=None):
    """The owner's dongle limit for this board, against the roles given and the dongles plugged in."""
    model = (_read(MODEL) or "").replace("\x00", "").strip() or None
    cap = MAX_PI4 if model and model.startswith(LIMITED_MODELS) else None
    assigned = len(roles())
    plugged = None if dongle_rows is None else len(dongle_rows)
    over = cap is not None and (assigned > cap or (plugged or 0) > cap)
    return {"model": q(model, None, "observed", "device tree"), "max": cap,
            "assigned": q(assigned, "count", "calculated", "distinct serials given a role"),
            "plugged": q(plugged, "count", "observed", "RTL-SDRs on USB"),
            "over": over,
            "rule": ("at most 3 RTL-SDRs by serial on a Pi 4 (owner, 2026-11-04): one USB 2.0 bus, shared "
                     "power and CPU with the timing core") if cap else
                    ("no limit for this board" if model else "the board model can't be read: no limit applied")}


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


# The last (now, messages) each decoder wrote, for a rate between two reads (RAM only).
_LAST_COUNT = {}


def _stats_rate(path):
    """readsb's stats.json beside aircraft.json: messages over its last full minute, per second."""
    try:
        if path.stat().st_size > MAX_FEED_BYTES:
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
        m = doc["last1min"]
        span = float(m["end"]) - float(m["start"])
        n = float(m["messages"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return round(n / span, 1) if span > 0 and n >= 0 else None


def _counter_rate(band, doc):
    """From aircraft.json's own counters ("now", "messages"): the change since the previous read."""
    if not isinstance(doc, dict):
        return None
    try:
        t, n = float(doc["now"]), float(doc["messages"])
    except (KeyError, TypeError, ValueError):
        return None
    prev = _LAST_COUNT.get(band)
    _LAST_COUNT[band] = (t, n)
    if not prev or t <= prev[0] or n < prev[1]:
        return None                       # first read, the same file again, or the decoder restarted
    return round((n - prev[1]) / (t - prev[0]), 1)


def feed(band, now=None):
    """A decoder's aircraft.json: age, aircraft count and message rate (positions are never read out)."""
    now = time.time() if now is None else now
    path = FEEDS[band]
    try:
        st = path.stat()
    except OSError:
        return {"band": band, "path": path.as_posix(), "present": False, "age_s": q(None, "s", "observed"),
                "aircraft": q(None, "count", "observed"), "messages_per_s": q(None, "msg/s", "calculated"),
                "fresh": False}
    count, doc = None, None
    if st.st_size <= MAX_FEED_BYTES:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            count = len(doc.get("aircraft") or []) if isinstance(doc, dict) else None
        except (OSError, ValueError):
            count = None
    age = round(max(0.0, now - st.st_mtime), 1)
    rate, basis = _stats_rate(path.with_name("stats.json")), "readsb's stats.json: messages in its last minute / 60 s"
    counted = _counter_rate(band, doc)
    if rate is None:
        rate, basis = counted, "the decoder's message counter in aircraft.json, between two reads"
    fresh = age <= FEED_FRESH_S
    return {"band": band, "path": path.as_posix(), "present": True,
            "age_s": q(age, "s", "observed", "time since the decoder last wrote the file"),
            "aircraft": q(count, "count", "observed"),
            "messages_per_s": q(rate if fresh else None, "msg/s", "calculated", basis),
            "fresh": fresh}


def aircraft(rows, feeds, websdr_on=None):
    """The aircraft decoders for Radio & SDR: each one's units and state, the dongle serial it uses,
    whether that dongle is plugged in, whether the web SDR has paused it, its map, and its feed."""
    from . import tar1090              # the map pages' folders; tar1090 imports nothing of ours
    a = assignments()
    plugged = None
    try:
        plugged = {(_read(d / "serial") or "") for d in USB.iterdir()
                   if ":" not in d.name and (_read(d / "idVendor"), _read(d / "idProduct")) in RTL_IDS}
    except OSError:
        pass
    by_unit = {r["unit"]: r for r in rows or []}
    feed_of = {f["band"]: f for f in feeds}

    def unit_state(name):
        if rows is None:
            return None                                  # systemctl couldn't be read: UNKNOWN
        r = by_unit.get(name)
        return r["active"]["value"] if r else "not installed"

    out = []
    for band, decoder, units_, site, url in (
            ("1090", "readsb", ["gps-time-readsb.service"], "tar1090", tar1090.PREFIX),
            ("978", "dump978-fa + skyaware978", ["gps-time-dump978.service", "gps-time-skyaware978.service"],
             "skyaware978", tar1090.SKY_PREFIX)):
        serial = a[band]
        paused = None if websdr_on is None else bool(websdr_on and a["websdr_band"] == band)
        out.append({
            "band": band, "decoder": decoder,
            "units": [{"unit": u, "state": unit_state(u)} for u in units_],
            "serial": serial,
            "serial_plugged": q(None if plugged is None or not serial else serial in plugged, None, "observed",
                                "an RTL-SDR with this serial on USB (sysfs)"),
            "paused_by_websdr": paused,
            "map": {"name": site, "url": url, "installed": tar1090.installed(site)},
            "feed": feed_of.get(band),
        })
    return {"decoders": out, "websdr_serial": a["websdr"], "websdr_band": a["websdr_band"],
            "websdr_running": websdr_on}


def status(run=subprocess.run, now=None, monotonic_us=None):
    """The whole /api/sdr answer."""
    rows = units(run, monotonic_us)
    usb = dongles()
    feeds = [feed("1090", now), feed("978", now)]
    return {
        "installed": None if rows is None else any(r["unit"] in SDR_UNITS for r in rows),
        "units": rows, "dongles": usb, "limit": limit(usb), "feeds": feeds,
        "aircraft": aircraft(rows, feeds, websdr_running()),
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
