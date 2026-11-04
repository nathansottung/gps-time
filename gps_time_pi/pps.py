"""Linux kernel PPS observation.

Reads /sys/class/pps/pps0/assert ("<sec>.<nsec>#<sequence>") on each poll and
keeps a bounded RAM ring buffer of observed events. Nothing here is written to
disk.

Measurement layer: every timestamp is the Linux kernel's CLOCK_REALTIME stamp
of the PPS interrupt. Interval statistics therefore describe what Linux
observed (including interrupt latency and the system clock being disciplined),
NOT the receiver's or the electrical signal's jitter.

Timestamps are integer nanoseconds since the Unix epoch, from the kernel's own
"<sec>.<nsec>" text to every phase and interval. A float of today's epoch in
seconds resolves only about 0.24 us, so seconds-as-float are made only from
differences (an interval, a phase within its second), never from a whole
timestamp, except for display (last_event_utc) and the coarse age.
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
LATE_POLL_S = 1.5  # a gap between two polls longer than this is a late poll

LAYER_NOTE = ("Linux kernel PPS timestamps (CLOCK_REALTIME); not receiver or "
              "electrical PPS jitter")

_ASSERT = re.compile(r"^\s*(\d+)\.(\d{1,9})#(\d+)\s*$")
NS = 1_000_000_000


def phase_ns(ts_ns):
    """(second, phase in ns) of an integer-ns timestamp: the nearest whole second and the
    signed distance from it, -0.5 s < phase <= 0.5 s. Exact integer arithmetic."""
    second, rem = divmod(ts_ns, NS)
    if rem > NS // 2:
        second, rem = second + 1, rem - NS
    return second, rem


def require_ns(ts):
    """Kernel PPS timestamps travel as int nanoseconds; a float here would lose them."""
    if isinstance(ts, bool) or not isinstance(ts, int):
        raise TypeError(f"PPS timestamp must be integer nanoseconds, not {type(ts).__name__}")
    return ts


def read_assert(sysfs_dir):
    """Return ('ok', ts_ns, seq) | ('missing', None, None) | ('unreadable', None, None).
    ts_ns is the kernel's timestamp as integer nanoseconds (no float on the way)."""
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
    return "ok", int(sec) * NS + int(frac.ljust(9, "0")), int(seq)


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
        (status, ts_ns, seq) like read_assert (integer ns); device_state() -> (present|None, note)."""
        self.device = device or DEVICE
        self.sysfs = sysfs or SYSFS
        self.clock = clock
        self._reader = reader or (lambda: read_assert(self.sysfs))
        self._device_state_fn = device_state
        self.degraded_s = DEGRADED_AFTER_S if degraded_s is None else degraded_s
        self.lost_s = LOST_AFTER_S if lost_s is None else lost_s
        self._lock = threading.Lock()
        self._events = deque(maxlen=ring)      # (seq, ts_ns)
        self._intervals = deque(maxlen=ring)   # ns between consecutive (seq+1) events (int)
        self._last = None                      # (seq, ts_ns)
        self._read_status = None
        self.missed_total = 0     # pulses the kernel never counted (from its sequence number)
        self.unread_total = 0     # pulses the kernel counted that no poll read individually
        self.consecutive = 0
        self.resets = 0
        self.polls = 0
        self.late_polls = 0
        self.max_poll_gap_s = None
        self._last_poll_at = None

    def poll(self):
        polled_at = self.clock()
        status, ts, seq = self._reader()
        with self._lock:
            if self._last_poll_at is not None:
                gap = polled_at - self._last_poll_at
                self.max_poll_gap_s = gap if self.max_poll_gap_s is None else max(self.max_poll_gap_s, gap)
                if gap > LATE_POLL_S:
                    self.late_polls += 1
            self._last_poll_at = polled_at
            self.polls += 1
            self._read_status = status
            if status != "ok" or seq == 0 or ts == 0:
                return
            require_ns(ts)
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
            # Missed pulses are counted from the kernel's own sequence number:
            # the pulses that the elapsed kernel time calls for, minus the ones
            # the kernel counted. A pulse the kernel counted but no poll read on
            # its own (dseq > 1) was not lost; it is counted as unread.
            dseq, dt = seq - lseq, ts - lts            # dt: integer ns
            missed = max(0, (dt + NS // 2) // NS - dseq) if dt > 0 else 0
            if dseq == 1 and dt > 0:
                self._intervals.append(dt)
            self.missed_total += missed
            self.unread_total += dseq - 1
            self.consecutive = 1 if missed else self.consecutive + dseq
            self._last = (seq, ts)
            self._events.append((seq, ts))

    def last_event(self):
        """(sequence, kernel timestamp in integer ns) of the newest observed event, or None."""
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
            unread, polls, late, max_gap = self.unread_total, self.polls, self.late_polls, self.max_poll_gap_s
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
            age = now - last[1] / NS
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
                               "pulses the kernel never counted: elapsed kernel time between observed events "
                               "minus the kernel's sequence count"),
            "unread_pulses": q(unread, "count", "calculated",
                               "pulses the kernel counted that the station didn't read individually (two or more "
                               "arrived between polls); not lost"),
            "poller": {"polls": polls, "late_polls": late,
                       "max_poll_gap_s": None if max_gap is None else round(max_gap, 3),
                       "late_after_s": LATE_POLL_S,
                       "note": "the station's own reads of the kernel PPS; a late poll delays observation, not the clock"},
            "sequence_resets": resets,
            "interval_stats": None,
        }
        if last is not None:
            age = now - last[1] / NS
            sec, nsec = divmod(last[1], NS)
            out["last_event_utc"] = q(datetime.fromtimestamp(sec, timezone.utc)
                                      .replace(microsecond=nsec // 1000).isoformat(timespec="microseconds"),
                                      None, "observed")
            out["last_sequence"] = q(last[0], None, "observed")
            out["age_s"] = q(round(age, 6), "s", "calculated",
                             "system clock now minus kernel timestamp" + ("; negative: clock stepped back" if age < 0 else ""))
        if intervals:
            # Integer ns throughout; seconds only at the end (a 1 s interval as a float keeps sub-ns).
            out["last_interval_s"] = q(intervals[-1] / NS, "s", "calculated", LAYER_NOTE)
            stats = {"count": len(intervals), "mean": sum(intervals) / len(intervals) / NS,
                     "min": min(intervals) / NS, "max": max(intervals) / NS,
                     "stdev": statistics.stdev(intervals) / NS if len(intervals) > 1 else None}
            out["interval_stats"] = q(stats, "s", "calculated", LAYER_NOTE)
        if len(events) >= 2:
            (s0, t0), (s1, t1) = events[0], events[-1]
            if t1 > t0:
                out["rate_hz"] = q((s1 - s0) * NS / (t1 - t0), "Hz", "calculated",
                                   f"over the last {len(events)} observed events")
        return out

