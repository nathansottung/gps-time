"""Linux kernel PPS observation.

Reads /sys/class/pps/pps0/assert ("<sec>.<nsec>#<sequence>") on each poll and
keeps a bounded RAM ring buffer of observed events. Nothing here is written to
disk.

Measurement layer: every timestamp is the Linux kernel's CLOCK_REALTIME stamp
of the PPS interrupt. Interval statistics therefore describe what Linux
observed (including interrupt latency and the system clock being disciplined),
NOT the receiver's or the electrical signal's jitter.
"""

import os
import re
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timezone

from .labels import q

DEVICE = os.environ.get("GTP_PPS_DEVICE", "/dev/pps0")
SYSFS = os.environ.get("GTP_PPS_SYSFS", "/sys/class/pps/pps0")
BOOT_CONFIGS = [p for p in os.environ.get(
    "GTP_BOOT_CONFIG", "/boot/firmware/config.txt:/boot/config.txt").split(":") if p]

DEGRADED_AFTER_S = float(os.environ.get("GTP_PPS_DEGRADED_S", "1.5"))
LOST_AFTER_S = float(os.environ.get("GTP_PPS_LOST_S", "3.0"))
RING_SIZE = 600   # ~10 minutes of 1 Hz events

LAYER_NOTE = ("Linux kernel PPS timestamps (CLOCK_REALTIME); not receiver or "
              "electrical PPS jitter")

_ASSERT = re.compile(r"^\s*(\d+)\.(\d{1,9})#(\d+)\s*$")


def read_assert(sysfs_dir):
    """Return ('ok', ts, seq) | ('missing', None, None) | ('unreadable', None, None)."""
    path = os.path.join(sysfs_dir, "assert")
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        return "missing", None, None
    except OSError:
        return "unreadable", None, None
    m = _ASSERT.match(text)
    if not m:
        return "unreadable", None, None
    sec, frac, seq = m.groups()
    return "ok", int(sec) + int(frac.ljust(9, "0")) / 1e9, int(seq)


def _read_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def boot_pps_config(paths=None):
    """Configured pps-gpio overlay from config.txt (read-only): gpio and edge."""
    for p in paths or BOOT_CONFIGS:
        text = _read_text(p)
        if text is None:
            continue
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if line.startswith("dtoverlay=pps-gpio"):
                params = dict(kv.split("=", 1) if "=" in kv else (kv, "1")
                              for kv in line.split("=", 1)[1].split(",")[1:])
                gpio = int(params.get("gpiopin", 18))   # overlay default is GPIO 18
                edge = "falling" if params.get("assert_falling_edge") in ("1", "true", "on") else "rising"
                return {"gpio": gpio, "assert_edge": edge, "source": p}
        return {"gpio": None, "assert_edge": None, "source": p,
                "note": "no pps-gpio overlay found in this file"}
    return None


class PPSMonitor:
    """RAM-only view of kernel PPS events. poll() is cheap (one sysfs read)."""

    def __init__(self, device=None, sysfs=None, ring=RING_SIZE,
                 clock=time.time, degraded_s=None, lost_s=None,
                 reader=None, device_state=None):
        """reader / device_state are injection hooks for demo mode: reader() ->
        (status, ts, seq) like read_assert; device_state() -> (present|None, note)."""
        self.device = device or DEVICE
        self.sysfs = sysfs or SYSFS
        self.clock = clock
        self._reader = reader or (lambda: read_assert(self.sysfs))
        self._device_state_fn = device_state
        self.degraded_s = DEGRADED_AFTER_S if degraded_s is None else degraded_s
        self.lost_s = LOST_AFTER_S if lost_s is None else lost_s
        self._lock = threading.Lock()
        self._events = deque(maxlen=ring)      # (seq, ts)
        self._intervals = deque(maxlen=ring)   # seconds between consecutive (seq+1) events
        self._last = None                      # (seq, ts)
        self._read_status = None
        self.missed_total = 0
        self.consecutive = 0
        self.resets = 0

    def poll(self):
        status, ts, seq = self._reader()
        with self._lock:
            self._read_status = status
            if status != "ok" or seq == 0 or ts == 0:
                return
            if self._last is None:
                self._last = (seq, ts)
                self._events.append((seq, ts))
                self.consecutive = 1
                return
            lseq, lts = self._last
            if seq == lseq:
                return
            if seq < lseq:                     # counter reset (driver reload / reboot)
                self.resets += 1
                self._events.clear()
                self._intervals.clear()
                self._last = (seq, ts)
                self._events.append((seq, ts))
                self.consecutive = 1
                return
            dseq, dt = seq - lseq, ts - lts
            missed = max(0, int(round(dt)) - dseq) if dt > 0 else 0
            if dseq == 1 and dt > 0:
                self._intervals.append(dt)
            self.missed_total += missed
            self.consecutive = 1 if missed else self.consecutive + dseq
            self._last = (seq, ts)
            self._events.append((seq, ts))

    def last_event(self):
        """(sequence, kernel timestamp) of the newest observed event, or None."""
        with self._lock:
            return self._last

    def _device_state(self):
        if self._device_state_fn:
            return self._device_state_fn()
        sysfs_root = os.path.dirname(self.sysfs.rstrip("/"))
        dev = os.path.exists(self.device)
        cls = os.path.isdir(self.sysfs)
        if not os.path.isdir(sysfs_root) and not dev:
            return None, "Linux PPS subsystem not observable on this host"
        return (dev or cls), None

    def snapshot(self):
        now = self.clock()
        with self._lock:
            last, read_status = self._last, self._read_status
            events, intervals = list(self._events), list(self._intervals)
            missed, consecutive, resets = self.missed_total, self.consecutive, self.resets
        present, note = self._device_state()

        if present is None:
            health = "UNKNOWN"
        elif not present:
            health = "MISSING"
        elif read_status in (None, "unreadable"):
            health = "UNKNOWN"
            note = "PPS sysfs attributes could not be read" if read_status else "not polled yet"
        elif last is None:
            health = "NO_EVENTS"
        else:
            age = now - last[1]
            health = ("HEALTHY" if age < self.degraded_s else
                      "DEGRADED" if age < self.lost_s else "LOST")

        out = {
            "device": q(self.device, None, "observed"),
            "device_present": q(present, None, "observed") if present is not None
                              else q(None, None, "observed", "not observable"),
            "metadata": {
                "name": _read_text(os.path.join(self.sysfs, "name")),
                "path": _read_text(os.path.join(self.sysfs, "path")),
            },
            "pulse_health": health,
            "pulse_health_provenance": "calculated",
            "thresholds_s": {"degraded_after": self.degraded_s, "lost_after": self.lost_s},
            "measurement_layer": LAYER_NOTE,
            "note": note,
            "last_event_utc": None, "last_sequence": None, "age_s": None,
            "last_interval_s": None, "rate_hz": None,
            "consecutive_pulses": q(consecutive if last else 0, "count", "calculated"),
            "missed_pulses": q(missed, "count", "calculated",
                               "time gap between observed events exceeding the sequence count"),
            "sequence_resets": resets,
            "interval_stats": None,
        }
        if last is not None:
            age = now - last[1]
            out["last_event_utc"] = q(datetime.fromtimestamp(last[1], timezone.utc)
                                      .isoformat(timespec="microseconds"), None, "observed")
            out["last_sequence"] = q(last[0], None, "observed")
            out["age_s"] = q(round(age, 6), "s", "calculated",
                             "system clock now minus kernel timestamp" + ("; negative: clock stepped back" if age < 0 else ""))
        if intervals:
            out["last_interval_s"] = q(intervals[-1], "s", "calculated", LAYER_NOTE)
            stats = {"count": len(intervals), "mean": statistics.fmean(intervals),
                     "min": min(intervals), "max": max(intervals),
                     "stdev": statistics.stdev(intervals) if len(intervals) > 1 else None}
            out["interval_stats"] = q(stats, "s", "calculated", LAYER_NOTE)
        if len(events) >= 2:
            (s0, t0), (s1, t1) = events[0], events[-1]
            if t1 > t0:
                out["rate_hz"] = q((s1 - s0) / (t1 - t0), "Hz", "calculated",
                                   f"over the last {len(events)} observed events")
        return out

