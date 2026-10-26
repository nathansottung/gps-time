"""Second pulse: a GPIO output edge at each second of the system clock (validation).

    python -m gps_time_pi.secpulse --line 23 [--chip /dev/gpiochip0] [--width-ms 100]
                                   [--count N] [--log /dev/shm/secpulse.csv] [--rt]

Why. The station's figures compare the system clock with the PPS edges as
Linux timestamped them. This puts the system clock (CLOCK_REALTIME, as chrony
disciplines it) back on a wire, so a scope or a time-interval counter can
compare it with the receiver's PPS electrically, from outside the Pi. The
comparison tool is tools/pps_compare.py; the guide is
docs/validation/second-pulse.md.

What the edge is. At each whole second of the system clock the line goes high
and, --width-ms later, low again. The rising edge is late by the software
latency L of the write: the time from the second boundary until the GPIO
register changes. L is not observed. What is observed, per pulse, is the
system clock just before the write and just after it returns
("before_ns", "after_ns", both relative to the boundary), so the edge lies in
that window if the clock is read correctly. With x = t(edge) - t(PPS) from the
instrument and e = system clock minus PPS time:  x = L - e.

What it never does. It doesn't touch chrony, gpsd or the PPS input. It refuses
the PPS input line named in config.txt (pps-gpio overlay). It never writes to
the SD card unless --log names a file there; nothing is written at 1 Hz by
default (a RAM ring of the last hour, and a summary line per minute on stdout).
A second whose wake-up came more than MAX_LATE_S late gets no pulse (counted
as skipped), so a pulse is never put in the wrong place.

Linux only (GPIO character device, uAPI v2). Needs read/write access to the
chip (the gpio group on Raspberry Pi OS). --rt (SCHED_FIFO) needs CAP_SYS_NICE.
"""

import argparse
import ctypes
import math
import os
import statistics
import sys
import time
from collections import deque

from . import pps

LEAD_US = 500           # wake this long before the boundary, then spin on the clock
MAX_LATE_S = 0.2        # later than this after the boundary: no pulse this second
RING = 3600             # RAM ring of the last hour of pulses
SUMMARY_S = 60

# ── GPIO character device, uAPI v2 (linux/gpio.h) ────────────────────────────

GPIO_V2_LINES_MAX = 64
GPIO_V2_LINE_NUM_ATTRS_MAX = 10
GPIO_V2_LINE_FLAG_OUTPUT = 1 << 3


def _iowr(nr, size):
    return (3 << 30) | (size << 16) | (0xB4 << 8) | nr


class _Attr(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("padding", ctypes.c_uint32), ("value", ctypes.c_uint64)]


class _ConfigAttr(ctypes.Structure):
    _fields_ = [("attr", _Attr), ("mask", ctypes.c_uint64)]


class _LineConfig(ctypes.Structure):
    _fields_ = [("flags", ctypes.c_uint64), ("num_attrs", ctypes.c_uint32), ("padding", ctypes.c_uint32 * 5),
                ("attrs", _ConfigAttr * GPIO_V2_LINE_NUM_ATTRS_MAX)]


class _LineRequest(ctypes.Structure):
    _fields_ = [("offsets", ctypes.c_uint32 * GPIO_V2_LINES_MAX), ("consumer", ctypes.c_char * 32),
                ("config", _LineConfig), ("num_lines", ctypes.c_uint32), ("event_buffer_size", ctypes.c_uint32),
                ("padding", ctypes.c_uint32 * 5), ("fd", ctypes.c_int32)]


class _LineValues(ctypes.Structure):
    _fields_ = [("bits", ctypes.c_uint64), ("mask", ctypes.c_uint64)]


GPIO_V2_GET_LINE_IOCTL = _iowr(0x07, ctypes.sizeof(_LineRequest))
GPIO_V2_LINE_SET_VALUES_IOCTL = _iowr(0x0F, ctypes.sizeof(_LineValues))


class GpioLine:
    """One output line, requested from the chip and released on close()."""

    def __init__(self, chip, line, consumer=b"gps-time-secpulse"):
        import fcntl   # POSIX only; imported here so the module loads anywhere
        self._fcntl = fcntl
        req = _LineRequest()
        req.offsets[0] = line
        req.num_lines = 1
        req.consumer = consumer
        req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT
        chip_fd = os.open(chip, os.O_RDWR | os.O_CLOEXEC)
        try:
            fcntl.ioctl(chip_fd, GPIO_V2_GET_LINE_IOCTL, req)
        finally:
            os.close(chip_fd)
        self.fd = req.fd
        self._v = _LineValues(0, 1)
        self.set(0)

    def set(self, value):
        self._v.bits = 1 if value else 0
        self._fcntl.ioctl(self.fd, GPIO_V2_LINE_SET_VALUES_IOCTL, self._v)

    def close(self):
        if self.fd is not None:
            try:
                self.set(0)
            finally:
                os.close(self.fd)
                self.fd = None


# ── clock ────────────────────────────────────────────────────────────────────

def now_ns():
    return time.clock_gettime_ns(time.CLOCK_REALTIME)


class _Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def _abs_sleeper():
    """sleep_until(t_ns) on CLOCK_REALTIME with TIMER_ABSTIME where libc has it, so a
    clock step or slew during the sleep doesn't move the wake-up; else time.sleep."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.clock_nanosleep
    except (OSError, AttributeError):
        fn = None

    def sleep_until(t_ns):
        if fn is not None:
            ts = _Timespec(t_ns // 1_000_000_000, t_ns % 1_000_000_000)
            while fn(0, 1, ctypes.byref(ts), None) == 4:      # CLOCK_REALTIME, TIMER_ABSTIME; EINTR
                pass
            return
        d = (t_ns - now_ns()) / 1e9
        if d > 0:
            time.sleep(d)

    return sleep_until


# ── the pulse loop (clock, sleep and line are injectable for tests) ──────────

class Pulser:
    def __init__(self, line, width_ms=100, lead_us=LEAD_US, clock=now_ns, sleep_until=None, out=None):
        if not 1 <= width_ms <= 900:
            raise ValueError("width must be 1..900 ms")
        self.line, self.width_ns, self.lead_ns = line, int(width_ms * 1e6), int(lead_us * 1e3)
        self.clock = clock
        self.sleep_until = sleep_until or _abs_sleeper()
        self.out = out
        self.ring = deque(maxlen=RING)       # (second, before_ns, after_ns)
        self.skipped = 0

    def one(self):
        """Wait for the next second, pulse, return the record (or None if skipped)."""
        t = self.clock()
        boundary = (t // 1_000_000_000 + 1) * 1_000_000_000
        self.sleep_until(boundary - self.lead_ns)
        while self.clock() < boundary:          # spin the last part: wake-up jitter is larger
            pass
        before = self.clock()
        if before - boundary > MAX_LATE_S * 1e9:
            self.skipped += 1
            return None
        self.line.set(1)
        after = self.clock()
        rec = (boundary // 1_000_000_000, before - boundary, after - boundary)
        self.ring.append(rec)
        if self.out is not None:
            self.out.write(f"{rec[0]},{rec[1]},{rec[2]}\n")
        self.sleep_until(boundary + self.width_ns)
        self.line.set(0)
        return rec

    def summary(self, last=SUMMARY_S):
        recs = list(self.ring)[-last:]
        if not recs:
            return {"pulses": 0, "skipped": self.skipped}
        after = sorted(r[2] for r in recs)
        return {"pulses": len(recs), "skipped": self.skipped,
                "write_done_after_ns": {"median": statistics.median(after),
                                        "p99": after[min(len(after) - 1, math.ceil(0.99 * len(after)) - 1)],
                                        "max": after[-1]},
                "write_window_ns_median": statistics.median(r[2] - r[1] for r in recs)}


def refuse_pps_line(line, boot=None):
    """An error message if `line` is the PPS input from config.txt, else None."""
    cfg = pps.boot_pps_config() if boot is None else boot
    if cfg and cfg.get("gpio") is not None and int(cfg["gpio"]) == int(line):
        return (f"GPIO {line} is the PPS input (pps-gpio overlay in {cfg.get('source')}); "
                "the second pulse must use another line")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_pi.secpulse", description=__doc__.split("\n\n")[0])
    ap.add_argument("--chip", default="/dev/gpiochip0")
    ap.add_argument("--line", type=int, required=True, help="GPIO line offset (BCM number on a Raspberry Pi)")
    ap.add_argument("--width-ms", type=float, default=100.0)
    ap.add_argument("--lead-us", type=float, default=LEAD_US, help="wake this early, then spin to the boundary")
    ap.add_argument("--count", type=int, default=0, help="stop after N pulses (0: until stopped)")
    ap.add_argument("--log", help="CSV of second,before_ns,after_ns per pulse. Put it on tmpfs (/dev/shm), "
                                  "not the SD card, for long runs")
    ap.add_argument("--rt", action="store_true", help="SCHED_FIFO priority 50 (needs CAP_SYS_NICE)")
    a = ap.parse_args(argv)

    err = refuse_pps_line(a.line)
    if err:
        print(err, file=sys.stderr)
        return 2
    if a.rt:
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(50))
    line = GpioLine(a.chip, a.line)
    out = open(a.log, "w", encoding="ascii", buffering=1 << 16) if a.log else None
    if out:
        out.write("second,before_ns,after_ns\n")
    p = Pulser(line, a.width_ms, a.lead_us, out=out)
    print(f"second pulse on {a.chip} line {a.line}: rising edge at each system-clock second, "
          f"{a.width_ms:g} ms wide. Ctrl-C to stop.", flush=True)
    n, last = 0, time.monotonic()
    try:
        while not a.count or n < a.count:
            if p.one():
                n += 1
            if time.monotonic() - last >= SUMMARY_S:
                last = time.monotonic()
                print(p.summary(), flush=True)
                if out:
                    out.flush()
    except KeyboardInterrupt:
        pass
    finally:
        line.close()
        if out:
            out.close()
        print(p.summary(len(p.ring)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
