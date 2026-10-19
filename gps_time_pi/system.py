"""Pi system diagnostics — everything you'd otherwise SSH in to check.

Honesty note on power: a Pi 4 has no power-measurement hardware and cannot
report its own wattage. We report core voltage and the firmware's
under-voltage/throttling flags (current and latched-since-boot), which is
the actionable power-supply diagnostic. On a Pi 5, the PMIC ADC provides
real voltage/current, and we compute watts from it when available.
"""

import os
import re
import subprocess
import threading
import time

from . import chrony


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _vcgencmd(*args):
    out = _run(["vcgencmd", *args])
    return out if out and "error" not in out.lower() else None


THROTTLE_BITS = [
    (0, "Under-voltage now"), (1, "Frequency capped now"),
    (2, "Throttled now"), (3, "Soft temp limit now"),
    (16, "Under-voltage occurred since boot"), (17, "Frequency capped since boot"),
    (18, "Throttled since boot"), (19, "Soft temp limit since boot"),
]


def _throttled():
    out = _vcgencmd("get_throttled")
    if not out:
        return None
    try:
        val = int(out.split("=")[1], 16)
    except (IndexError, ValueError):
        return None
    return {"raw": out.split("=")[1],
            "flags": [{"label": lbl, "active": bool(val >> bit & 1),
                       "now": bit < 16} for bit, lbl in THROTTLE_BITS],
            "any_now": bool(val & 0xF), "any_ever": bool(val & 0xF0000)}


def _pmic_power():
    """Pi 5 only: PMIC ADC gives real rails. Returns watts on the 5V input
    if the readings parse; None elsewhere (Pi 4 cannot measure power)."""
    out = _run(["vcgencmd", "pmic_read_adc"])
    if not out or "error" in out.lower():
        return None
    volts = dict(re.findall(r"(\w+)_V volt\(\d+\)=([\d.]+)V", out))
    amps = dict(re.findall(r"(\w+)_A current\(\d+\)=([\d.]+)A", out))
    v, a = volts.get("EXT5V"), amps.get("EXT5V")
    if v and a:
        return {"volts": float(v), "amps": float(a),
                "watts": round(float(v) * float(a), 2)}
    return None


def _meminfo():
    try:
        m = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            m[k] = int(v.strip().split()[0])  # kB
        return {"total_mb": round(m["MemTotal"] / 1024),
                "available_mb": round(m["MemAvailable"] / 1024),
                "used_pct": round(100 * (1 - m["MemAvailable"] / m["MemTotal"]))}
    except Exception:  # noqa: BLE001
        return None


def diagnostics():
    d = {}
    try:
        d["model"] = open("/proc/device-tree/model").read().strip("\x00").strip()
    except OSError:
        d["model"] = None
    u = os.uname()
    d["kernel"] = f"{u.sysname} {u.release}"
    try:
        d["uptime_s"] = float(open("/proc/uptime").read().split()[0])
    except OSError:
        d["uptime_s"] = None
    try:
        d["load"] = list(os.getloadavg())
    except OSError:
        d["load"] = None
    d["mem"] = _meminfo()
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        d["disk"] = {"total_gb": round(total / 1e9, 1), "free_gb": round(free / 1e9, 1),
                     "used_pct": round(100 * (1 - free / total))}
    except OSError:
        d["disk"] = None
    try:
        cur = int(open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read())
        d["cpu_mhz"] = round(cur / 1000)
    except OSError:
        d["cpu_mhz"] = None
    volts = _vcgencmd("measure_volts", "core")
    d["core_volts"] = volts.split("=")[1] if volts and "=" in volts else None
    d["throttled"] = _throttled()
    d["power"] = _pmic_power()
    d["power_note"] = ("Measured at PMIC" if d["power"] else
                       "This Pi cannot measure its own wattage; voltage and "
                       "throttle flags below are the power-supply diagnostics.")

    # RAM-log status
    log = chrony.tracking_log_path()
    d["ramlog"] = {"path": log, "in_ram": log.startswith("/run/"),
                   "size_kb": None, "flushed_age_s": None, "sd_copy": None, "sd_size_kb": None}
    try:
        d["ramlog"]["size_kb"] = round(sum(os.path.getsize(p) for p in chrony._tracking_files(log)) / 1024, 1)
    except OSError:
        pass
    for copy in chrony.SD_COPIES:          # the rc.9 append-only copy, else the older full copy
        try:
            d["ramlog"]["flushed_age_s"] = round(time.time() - os.path.getmtime(copy))
            d["ramlog"]["sd_copy"] = copy
            d["ramlog"]["sd_size_kb"] = round(os.path.getsize(copy) / 1024, 1)
            break
        except OSError:
            continue
    return d


# Management actions. The web service runs unprivileged (User=gps-time); each
# command is a fixed argv authorized by the polkit rule system/50-gps-time-pi.rules,
# which allows exactly these units/verbs and reboot. No shell, no arguments
# from the request. The caller (server.py) has already checked the admin token.
ACTIONS = {
    "restart_chrony": ["systemctl", "restart", "chrony.service"],
    "restart_gpsd": ["systemctl", "restart", "gpsd.service"],
    # The root oneshot unit does the copy; the service user may only start it.
    "flush_logs": ["systemctl", "start", "gps-time-pi-logflush.service"],
}
DELAYED = {   # detach so the HTTP response gets out before the process/host goes down
    "restart_web": (1.0, ["systemctl", "restart", "gps-time-pi.service"], "restarting in 1 s"),
    "reboot": (2.0, ["systemctl", "reboot"], "rebooting in 2 s"),
}
ADMIN_ACTIONS = frozenset(ACTIONS) | frozenset(DELAYED)


def _spawn(argv):
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def admin(action):
    if action in ACTIONS:
        try:
            r = subprocess.run(ACTIONS[action], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as e:
            return {"ok": False, "action": action, "detail": str(e)[:300]}
        return {"ok": r.returncode == 0, "action": action,
                "detail": (r.stderr or r.stdout).strip()[:300]}
    if action in DELAYED:
        delay, argv, detail = DELAYED[action]
        t = threading.Timer(delay, _spawn, args=(argv,))
        t.daemon = True
        t.start()
        return {"ok": True, "action": action, "detail": detail}
    return {"ok": False, "action": action, "detail": "unknown action"}
