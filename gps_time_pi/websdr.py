"""The optional web SDR (OpenWebRX+, GTP_WEBSDR=1) as the web service sees it, and its usage log.

Read only toward the web SDR: whether its unit is installed and running, its port and dongle
(from /etc/default/gps-time-websdr), and its CPU. Starting and stopping go through the admin
actions websdr_start / websdr_stop (system.py, polkit), never through this module.

The usage log (owner 2026-11-04: CPU, temperature and PPS jitter while it is in use):
  - every SAMPLE_S seconds: the whole system's CPU (/proc/stat), the web SDR units' CPU
    (their cgroups), the SoC temperature; every kernel PPS event from the timing chain's poller
    gives one phase sample (where the system clock read at the PPS edge);
  - one bin per minute, kept in RAM: CPU mean and max, temperature mean and max, and the PPS
    jitter (standard deviation of the minute's phase samples, largest |phase|, pulses seen);
  - the last BASELINE_MIN minutes are always kept, so each session has a before to compare with;
  - while the unit runs, a session collects its bins (RAM, capped at SESSION_MAX_MIN);
  - when it stops, one summary line goes to websdr-sessions.jsonl beside config.json: one write
    per session, never per second or per minute, capped at MAX_SESSIONS lines.

The PPS figures are the system clock against kernel PPS timestamps, the same layer as
/api/stability (interrupt latency and chrony's loop included). They show what changed while the
web SDR ran; they don't say why, and a difference isn't a cause. The timestamps arrive as integer
nanoseconds (pps.read_assert), so the figures resolve to 1 ns.
"""
import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import sdr
from .pps import phase_ns, require_ns
from .labels import q

UNIT = "gps-time-websdr.service"
GATE_UNIT = "gps-time-websdr-gate.service"
UNITS = (UNIT, GATE_UNIT)
ENVFILE = Path(os.environ.get("GTP_WEBSDR_ENV", "/etc/default/gps-time-websdr"))
PROC_STAT = Path(os.environ.get("GTP_PROC_STAT", "/proc/stat"))
THERMAL = Path(os.environ.get("GTP_THERMAL", "/sys/class/thermal/thermal_zone0/temp"))
SAMPLE_S = 10.0
BASELINE_MIN = 10
SESSION_MAX_MIN = 720
MAX_SESSIONS = 100
LAYER_NOTE = ("PPS jitter: the standard deviation, over each minute, of where the system clock read at the "
              "kernel PPS edges (the /api/stability layer: interrupt latency and chrony's loop included). "
              "It shows what changed while the web SDR ran, not why.")


def _iso(t):
    return None if t is None else datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def default_path():
    cfg = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return os.environ.get("GTP_WEBSDR_LOG") or os.path.join(os.path.dirname(os.path.abspath(cfg)), "websdr-sessions.jsonl")


def settings():
    """{port, serial, max_hours, auth, remember_days, hf} from the installer's
    /etc/default/gps-time-websdr; None where unset (an older install without the login settings
    has the login off, as the gate does)."""
    out = {"port": None, "serial": None, "max_hours": None, "auth": None, "remember_days": None, "hf": None}
    try:
        text = ENVFILE.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        k, _, v = line.partition("=")
        v = v.strip()
        if k == "GTP_WEBSDR_PORT" and v.isdigit():
            out["port"] = int(v)
        elif k == "GTP_WEBSDR_SERIAL" and v:
            out["serial"] = v
        elif k == "GTP_WEBSDR_MAX_HOURS" and v.replace(".", "", 1).isdigit():
            out["max_hours"] = float(v)
        elif k == "GTP_WEBSDR_AUTH":
            out["auth"] = v.lower() in ("1", "on", "yes", "true")
        elif k == "GTP_WEBSDR_REMEMBER_DAYS" and v.isdigit():
            out["remember_days"] = int(v)
        elif k == "GTP_WEBSDR_HF" and v in ("off", "direct", "native"):
            out["hf"] = v
    if out["port"] is not None and out["auth"] is None:
        out["auth"] = False
    return out


# ── readers (None when unreadable: UNKNOWN, never a guess) ─────────────────

def read_cpu_times():
    """(busy, total) jiffies of all CPUs from /proc/stat."""
    try:
        first = PROC_STAT.read_text(encoding="utf-8").splitlines()[0].split()
    except (OSError, IndexError):
        return None
    if first[0] != "cpu":
        return None
    try:
        v = [int(x) for x in first[1:]]
    except ValueError:
        return None
    idle = v[3] + (v[4] if len(v) > 4 else 0)
    total = sum(v[:8])
    return total - idle, total


def read_temp():
    try:
        return round(int(THERMAL.read_text(encoding="utf-8").strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def unit_cgroup(name):
    return sdr.CGROUP / "system.slice" / name


PAUSES = {"1090": "readsb (1090 MHz)", "978": "dump978-fa and skyaware978 (978 MHz)"}


def unit_active(name=UNIT):
    """True while the unit's cgroup exists (systemd removes it when the unit stops); None if
    cgroups can't be read at all."""
    if not (sdr.CGROUP / "system.slice").is_dir():
        return None
    return unit_cgroup(name).is_dir()


def unit_cpu_usec(name):
    usage, _mem = sdr._cgroup_stats(f"/system.slice/{name}")
    return usage


# ── minute bins ────────────────────────────────────────────────────────────

class _Acc:
    def __init__(self, minute):
        self.minute = minute
        self.cpu, self.unit_cpu, self.temp = [], [], []
        self.n, self.s, self.ss, self.maxabs = 0, 0.0, 0.0, 0.0
        self.active = False

    def bin(self):
        mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else None   # noqa: E731
        sd = None
        if self.n >= 2:
            m = self.s / self.n
            sd = math.sqrt(max(0.0, (self.ss - self.n * m * m) / (self.n - 1)))
        return {"t": self.minute * 60, "active": self.active,
                "cpu_pct": mean(self.cpu), "cpu_max_pct": max(self.cpu) if self.cpu else None,
                "websdr_cpu_pct": mean(self.unit_cpu),
                "temp_c": mean(self.temp), "temp_max_c": max(self.temp) if self.temp else None,
                "pps_pulses": self.n,
                "pps_jitter_ns": None if sd is None else round(sd * 1e9, 1),
                "pps_max_abs_ns": round(self.maxabs * 1e9, 1) if self.n else None}


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def summarize(bins):
    """Figures over a list of minute bins (pure)."""
    def vals(k):
        return [b[k] for b in bins if b.get(k) is not None]
    cpu, temp, jit = vals("cpu_pct"), vals("temp_c"), vals("pps_jitter_ns")
    pulses = sum(b.get("pps_pulses") or 0 for b in bins)
    return {
        "minutes": len(bins),
        "cpu_mean_pct": round(sum(cpu) / len(cpu), 1) if cpu else None,
        "cpu_max_pct": max(vals("cpu_max_pct"), default=None),
        "websdr_cpu_mean_pct": (round(sum(vals("websdr_cpu_pct")) / len(vals("websdr_cpu_pct")), 1)
                                if vals("websdr_cpu_pct") else None),
        "temp_mean_c": round(sum(temp) / len(temp), 1) if temp else None,
        "temp_max_c": max(vals("temp_max_c"), default=None),
        "pps_jitter_median_ns": None if not jit else round(_median(jit), 1),
        "pps_jitter_max_ns": max(jit, default=None),
        "pps_max_abs_ns": max(vals("pps_max_abs_ns"), default=None),
        "pps_pulses": pulses,
        "pps_expected": 60 * len(bins),
    }


def labelled(s):
    """A summary with a provenance label on each figure (for the API)."""
    if s is None:
        return None
    return {
        "minutes": s["minutes"],
        "cpu_mean_pct": q(s["cpu_mean_pct"], "% of all cores", "calculated", "mean of /proc/stat samples"),
        "cpu_max_pct": q(s["cpu_max_pct"], "% of all cores", "observed", "largest 10 s sample"),
        "websdr_cpu_mean_pct": q(s["websdr_cpu_mean_pct"], "% of one core", "calculated",
                                 "the web SDR and its gate, from their cgroups"),
        "temp_mean_c": q(s["temp_mean_c"], "°C", "calculated"),
        "temp_max_c": q(s["temp_max_c"], "°C", "observed"),
        "pps_jitter_median_ns": q(s["pps_jitter_median_ns"], "ns", "calculated", "median of the minutes' standard deviations"),
        "pps_jitter_max_ns": q(s["pps_jitter_max_ns"], "ns", "calculated", "the worst minute's standard deviation"),
        "pps_max_abs_ns": q(s["pps_max_abs_ns"], "ns", "observed", "largest |phase| of one pulse"),
        "pps_pulses": q(s["pps_pulses"], "count", "observed", f"of {s['pps_expected']} seconds"),
    }


class UsageLog:
    """RAM minute bins, sessions while the web SDR runs, one summary line per session on disk."""

    def __init__(self, path=None, clock=time.time, active=unit_active, cpu=read_cpu_times, temp=read_temp,
                 unit_cpu=unit_cpu_usec, monotonic=time.monotonic):
        self.path = path or default_path()
        self.clock, self.monotonic = clock, monotonic
        self._active, self._cpu, self._temp, self._unit_cpu = active, cpu, temp, unit_cpu
        self._lock = threading.Lock()
        self._acc = None
        self._baseline = deque(maxlen=BASELINE_MIN)
        self._session = None
        self._last_cpu = None
        self._sampled = False
        self._last_pps = None
        self._last_unit = None
        self._recent = None              # summaries, loaded from the file on first use
        self.write_error = None
        self._thread = None

    # inputs
    def add_pps(self, ts_ns):
        """One kernel PPS timestamp (integer ns); the phase is its distance from the nearest second."""
        second, ph_ns = phase_ns(require_ns(ts_ns))
        phase = ph_ns / 1e9
        with self._lock:
            if second == self._last_pps:
                return                     # the poller reads the newest event each second: once each
            self._last_pps = second
            acc = self._minute(int(self.clock() // 60))
            acc.n += 1
            acc.s += phase
            acc.ss += phase * phase
            acc.maxabs = max(acc.maxabs, abs(phase))

    def _minute(self, minute):
        """The accumulator for this minute; a finished minute is closed first (lock held)."""
        if self._acc is not None and self._acc.minute != minute:
            self._close_minute()
        if self._acc is None:
            self._acc = _Acc(minute)
        return self._acc

    def _close_minute(self):
        b = self._acc.bin()
        self._acc = None
        if self._session is not None and b["active"]:
            if len(self._session["bins"]) < SESSION_MAX_MIN:
                self._session["bins"].append(b)
            else:
                self._session["truncated"] = True
        else:
            self._baseline.append(b)

    def sample(self):
        """One 10 s sample; starts or ends a session when the unit's state changed."""
        now = self.clock()
        active = self._active()
        cpu = self._cpu()
        mono = self.monotonic()
        unit_us = None
        if active:
            parts = [self._unit_cpu(u) for u in UNITS]
            unit_us = sum(p for p in parts if p is not None) if any(p is not None for p in parts) else None
        ended = None
        with self._lock:
            if active and self._session is None:
                # A session found running when the web service starts began earlier: marked partial.
                partial = not self._sampled
                self._session = {"start": now, "partial": partial, "truncated": False,
                                 "before": list(self._baseline), "bins": []}
                self._last_unit = None
            acc = self._minute(int(now // 60))
            if active:
                acc.active = True
            if cpu and self._last_cpu and cpu[1] > self._last_cpu[1]:
                acc.cpu.append(round(100.0 * (cpu[0] - self._last_cpu[0]) / (cpu[1] - self._last_cpu[1]), 1))
            if active and unit_us is not None and self._last_unit is not None and unit_us >= self._last_unit[0]:
                dt = mono - self._last_unit[1]
                if dt > 0:
                    acc.unit_cpu.append(round(100.0 * (unit_us - self._last_unit[0]) / 1e6 / dt, 1))
            t = self._temp()
            if t is not None:
                acc.temp.append(t)
            self._last_cpu = cpu
            self._sampled = True
            self._last_unit = (unit_us, mono) if unit_us is not None else None
            if active is False and self._session is not None:
                if self._acc is not None and self._acc.active:
                    self._close_minute()
                ended = self._end(now)
        if ended is not None:
            self._write(ended)

    def _end(self, now):
        s, self._session = self._session, None
        return {"format": "gps-time.websdr-session/1", "start_utc": _iso(s["start"]), "end_utc": _iso(now),
                "duration_s": round(now - s["start"]), "partial": s["partial"], "truncated": s["truncated"],
                "before": summarize(s["before"]), "during": summarize(s["bins"])}

    # storage: one line per session
    def _load(self):
        if self._recent is not None:
            return
        self._recent = deque(maxlen=MAX_SESSIONS)
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        doc = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(doc, dict) and doc.get("format") == "gps-time.websdr-session/1":
                        self._recent.append(doc)
        except OSError:
            pass

    def _write(self, summary):
        with self._lock:
            self._load()
            self._recent.append(summary)
            lines = [json.dumps(s, separators=(",", ":")) for s in self._recent]
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            self.write_error = None
        except OSError as e:
            self.write_error = str(e)

    # the API
    def view(self):
        with self._lock:
            self._load()
            live = None
            if self._session is not None:
                bins = list(self._session["bins"])
                if self._acc is not None and self._acc.active:
                    bins.append(self._acc.bin())
                live = {"start_utc": _iso(self._session["start"]), "partial": self._session["partial"],
                        "truncated": self._session["truncated"], "bins": bins,
                        "before": labelled(summarize(self._session["before"])),
                        "during": labelled(summarize(bins))}
            baseline = labelled(summarize(list(self._baseline))) if self._baseline else None
            recent = [{**s, "before": labelled(s.get("before")), "during": labelled(s.get("during"))}
                      for s in list(self._recent)[-10:]][::-1]
        return {"session": live, "baseline": baseline, "recent": recent,
                "file": {"name": os.path.basename(self.path), "error": self.write_error},
                "note": LAYER_NOTE}

    # the thread
    def start(self):
        if self._thread is not None:
            return
        def loop():
            while True:
                try:
                    self.sample()
                except Exception:  # noqa: BLE001 - observability never takes the server down
                    pass
                time.sleep(SAMPLE_S - (time.time() % SAMPLE_S))
        self._thread = threading.Thread(target=loop, name="websdr-usage", daemon=True)
        self._thread.start()


_SERVICE = None
_SERVICE_LOCK = threading.Lock()


def service():
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = UsageLog()
        return _SERVICE


def installed(run=None):
    """True/False from systemctl (LoadState of the web SDR unit); None when systemctl can't be read."""
    props = sdr.show_units([UNIT], run) if run else sdr.show_units([UNIT])
    if not props:
        return None, None
    p = props.get(UNIT) or {}
    return p.get("LoadState") == "loaded", p


def status(usage=None, run=None):
    """The /api/websdr answer."""
    inst, p = installed(run)
    st = settings()
    active = (p or {}).get("ActiveState")
    from . import timequality
    role, peer = timequality.role()
    return {
        "node_host": peer if role == "station" and not inst else None,   # the web SDR is on the SDR node
        "installed": inst,
        "active": q(active, None, "observed", "systemctl show ActiveState") if inst else q(None, None, "observed"),
        "port": st["port"], "serial": st["serial"], "max_hours": st["max_hours"],
        # The installer's settings (configured, not observed): the gate's login and the HF profiles.
        "auth": {"enabled": st["auth"], "remember_days": st["remember_days"]},
        "hf": st["hf"],
        "usage": (usage or service()).view(),
        # The one service on the web SDR's dongle, stopped while it runs (None: a dongle with no other role).
        "pauses": PAUSES.get(sdr.websdr_band()),
        "note": ("OpenWebRX+ behind the station's LAN gate (login optional). While it runs, the service on its "
                 "dongle is stopped and comes back when the web SDR stops (docs/deploy/websdr.md)."),
    }
