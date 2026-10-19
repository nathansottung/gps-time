"""Temperature logged alongside chrony's frequency estimate: the data a trained
oscillator profile will be fitted on (roadmap/ROADMAP-OSCILLATOR-AND-MISC.md §1).

What is recorded, once a minute:
  - chrony's `Frequency` (how fast the uncorrected system clock runs, in ppm;
    + = fast), its `Skew` and `Residual freq` (observed, chrony's estimates);
  - the SoC temperature from /sys/class/thermal (observed). It is the
    processor's sensor, not the crystal's: they track each other only roughly;
  - whether chrony had the PPS refclock selected. Frequency estimates made under
    another source are kept but marked, and never used for the fit.

Storage (project rule: nothing written at 1 Hz):
  - one-minute samples are folded into 10-minute bins in RAM;
  - finished bins are appended to a CSV next to config.json once an hour, and
    on a clean stop (about one short line per bin);
  - the file has a size cap; past it, the oldest quarter is dropped in one
    atomic rewrite;
  - the file starts with a hash of the board's serial number (never the serial
    itself). A file from another board is set aside, not mixed in.

Nothing here fits a profile or predicts holdover. It reports a straight-line
frequency-versus-temperature slope over the logged bins, labeled
`calculated`, with the conditions it needs.
"""

import hashlib
import math
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone

from .labels import q

SAMPLE_INTERVAL_S = 60.0
BIN_S = 600
FLUSH_INTERVAL_S = 3600.0
RAM_BINS = 7 * 144                    # 7 days of 10-minute bins
MAX_BYTES = int(os.environ.get("GTP_OSCILLATOR_LOG_MAX_BYTES", str(4 * 1024 * 1024)))
FIT_MIN_BINS = 36                     # 6 hours of PPS-selected bins
FIT_MIN_TEMP_SPAN_C = 2.0
FORMAT = "gps-time oscillator log v1"
COLUMNS = ("bin_start_utc", "samples", "pps_samples", "temp_mean_c", "temp_min_c", "temp_max_c",
           "freq_mean_ppm", "freq_min_ppm", "freq_max_ppm", "skew_mean_ppm", "residual_mean_ppm")

THERMAL = os.environ.get("GTP_THERMAL", "/sys/class/thermal/thermal_zone0/temp")
SERIAL = os.environ.get("GTP_BOARD_SERIAL", "/sys/firmware/devicetree/base/serial-number")
MODEL = os.environ.get("GTP_BOARD_MODEL", "/proc/device-tree/model")

SENSOR_NOTE = ("SoC temperature sensor (/sys/class/thermal), not the crystal: the two follow each other "
               "only roughly, and with a lag.")


def default_path():
    configured = os.environ.get("GTP_OSCILLATOR_LOG")
    if configured:
        return configured
    cfg = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return os.path.join(os.path.dirname(os.path.abspath(cfg)), "oscillator-log.csv")


def _read(path, binary=False):
    try:
        with open(path, "rb") as f:
            data = f.read()
        return data if binary else data.decode("ascii", errors="replace").replace("\0", "").strip()
    except OSError:
        return None


def read_temp_c(path=None):
    text = _read(path or THERMAL)
    try:
        return round(int(text) / 1000.0, 2)
    except (TypeError, ValueError):
        return None


def board_identity(serial_path=None, model_path=None):
    """{'serial_sha256': 16 hex chars or None, 'model': str or None}. The raw serial never leaves here."""
    raw = _read(serial_path or SERIAL, binary=True)
    digest = hashlib.sha256(raw.rstrip(b"\0\n")).hexdigest()[:16] if raw else None
    return {"serial_sha256": digest, "model": _read(model_path or MODEL)}


_PPM = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*ppm(?:\s+(fast|slow))?")


def parse_ppm(text):
    """'10.345 ppm fast' -> 10.345, '2.1 ppm slow' -> -2.1, '-0.000 ppm' -> -0.0; None if unparseable."""
    m = _PPM.match(text or "")
    if not m:
        return None
    v = float(m.group(1))
    return -v if m.group(2) == "slow" else v


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def linear_fit(bins):
    """Least-squares slope (ppm per degree C) and intercept of frequency against
    temperature over PPS-selected bins, with the conditions it needs. Pure."""
    pts = [(b["temp_mean_c"], b["freq_mean_ppm"]) for b in bins
           if b["pps_samples"] == b["samples"] and b["temp_mean_c"] is not None and b["freq_mean_ppm"] is not None]
    out = {"bins_used": len(pts), "slope_ppm_per_c": None, "intercept_ppm": None, "r": None,
           "temp_span_c": None, "reason": None, "provenance": "calculated"}
    if len(pts) < FIT_MIN_BINS:
        out["reason"] = (f"needs {FIT_MIN_BINS} bins (6 h) with PPS selected throughout; "
                         f"{len(pts)} so far")
        return out
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    span = max(xs) - min(xs)
    out["temp_span_c"] = round(span, 2)
    if span < FIT_MIN_TEMP_SPAN_C:
        out["reason"] = f"the temperature has varied by only {span:.1f} °C; a slope needs at least {FIT_MIN_TEMP_SPAN_C:g} °C"
        return out
    n = len(pts)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    slope = sxy / sxx
    out.update(slope_ppm_per_c=round(slope, 5), intercept_ppm=round(my - slope * mx, 4),
               r=round(sxy / math.sqrt(sxx * syy), 3) if syy > 0 else None)
    return out


class Log:
    """Samples in, 10-minute bins out; RAM first, the CSV hourly."""

    def __init__(self, path=None, clock=time.time, temp_reader=read_temp_c, identity=None, max_bytes=None):
        self.path = path or default_path()
        self.clock = clock
        self.temp_reader = temp_reader
        self.identity = identity if identity is not None else board_identity()
        self.max_bytes = MAX_BYTES if max_bytes is None else max_bytes
        self._lock = threading.Lock()
        self._bins = deque(maxlen=RAM_BINS)
        self._pending = []                  # finished bins not yet on disk
        self._acc = None
        self._last_sample = None
        self._last_flush = clock()
        self.problems = []
        self.set_aside = None
        self._load()

    # -- file ----------------------------------------------------------------

    def _header(self):
        i = self.identity
        return (f"# {FORMAT}; board_sha256={i.get('serial_sha256') or 'unknown'}; "
                f"model={(i.get('model') or 'unknown').replace(';', ',')}\n" + ",".join(COLUMNS) + "\n")

    def _load(self):
        """Read the existing log into RAM; set a file from another board aside."""
        try:
            with open(self.path, encoding="ascii", errors="replace") as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            return
        except OSError as e:
            self.problems.append(f"{self.path}: {e.strerror or e}")
            return
        head = lines[0] if lines else ""
        m = re.search(r"board_sha256=([0-9a-f]+|unknown)", head)
        mine = self.identity.get("serial_sha256")
        if not head.startswith("# " + FORMAT) or (m and mine and m.group(1) not in (mine, "unknown")):
            aside = self.path + f".set-aside-{int(self.clock())}"
            try:
                os.replace(self.path, aside)
                self.set_aside = aside
                self.problems.append("the existing log belongs to another board or format; it was set aside as "
                                     + os.path.basename(aside))
            except OSError as e:
                self.problems.append(f"could not set the old log aside: {e.strerror or e}")
            return
        for line in lines[2:]:
            b = self._parse_row(line)
            if b:
                self._bins.append(b)

    @staticmethod
    def _parse_row(line):
        f = line.split(",")
        if len(f) != len(COLUMNS):
            return None
        try:
            t = datetime.fromisoformat(f[0]).timestamp()
            num = [None if x == "" else float(x) for x in f[3:]]
            return {"t": t, "samples": int(f[1]), "pps_samples": int(f[2]),
                    **dict(zip(COLUMNS[3:], num))}
        except ValueError:
            return None

    @staticmethod
    def _row(b):
        def fmt(v, d):
            return "" if v is None else f"{v:.{d}f}"
        return ",".join([_iso(b["t"]), str(b["samples"]), str(b["pps_samples"]),
                         fmt(b["temp_mean_c"], 2), fmt(b["temp_min_c"], 2), fmt(b["temp_max_c"], 2),
                         fmt(b["freq_mean_ppm"], 4), fmt(b["freq_min_ppm"], 4), fmt(b["freq_max_ppm"], 4),
                         fmt(b["skew_mean_ppm"], 4), fmt(b["residual_mean_ppm"], 4)]) + "\n"

    def flush(self):
        """Append the finished bins to the CSV (one write, fsync). Called hourly and on a clean stop."""
        with self._lock:
            pending, self._pending = self._pending, []
            self._last_flush = self.clock()
        if not pending:
            return 0
        try:
            new = not os.path.exists(self.path)
            os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
            with open(self.path, "a", encoding="ascii", newline="\n") as f:
                if new:
                    f.write(self._header())
                f.write("".join(self._row(b) for b in pending))
                f.flush()
                os.fsync(f.fileno())
            if os.path.getsize(self.path) > self.max_bytes:
                self._trim()
        except OSError as e:
            with self._lock:
                self._pending = pending + self._pending     # keep them for the next try
            self.problems.append(f"write failed: {e.strerror or e}")
            return 0
        return len(pending)

    def _trim(self):
        """Over the cap: keep the newest three quarters of the rows, in one atomic rewrite."""
        with open(self.path, encoding="ascii", errors="replace") as f:
            lines = f.read().splitlines(keepends=True)
        head, rows = lines[:2], lines[2:]
        keep = rows[len(rows) // 4:]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="ascii", newline="\n") as f:
            f.write("".join(head + keep))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    # -- samples -------------------------------------------------------------

    def _close_bin(self):
        a = self._acc
        if not a or not a["n"]:
            return
        def mean(k):
            vals = a[k]
            return sum(vals) / len(vals) if vals else None
        b = {"t": a["start"], "samples": a["n"], "pps_samples": a["pps"],
             "temp_mean_c": mean("temp"), "temp_min_c": min(a["temp"]) if a["temp"] else None,
             "temp_max_c": max(a["temp"]) if a["temp"] else None,
             "freq_mean_ppm": mean("freq"), "freq_min_ppm": min(a["freq"]) if a["freq"] else None,
             "freq_max_ppm": max(a["freq"]) if a["freq"] else None,
             "skew_mean_ppm": mean("skew"), "residual_mean_ppm": mean("resid")}
        self._bins.append(b)
        self._pending.append(b)

    def add(self, tracking, pps_selected):
        """Called on every chain evaluation with chrony's parsed tracking; samples once a minute."""
        now = self.clock()
        flush_due = False
        with self._lock:
            if self._last_sample is not None and now - self._last_sample < SAMPLE_INTERVAL_S:
                return
            freq = parse_ppm((tracking or {}).get("Frequency"))
            if freq is None:
                return                                  # chrony unreadable: nothing to log
            self._last_sample = now
            start = now - now % BIN_S
            if self._acc and self._acc["start"] != start:
                self._close_bin()
                self._acc = None
            if self._acc is None:
                self._acc = {"start": start, "n": 0, "pps": 0, "temp": [], "freq": [], "skew": [], "resid": []}
            a = self._acc
            a["n"] += 1
            a["pps"] += 1 if pps_selected else 0
            a["freq"].append(freq)
            for key, field in (("skew", "Skew"), ("resid", "Residual freq")):
                v = parse_ppm((tracking or {}).get(field))
                if v is not None:
                    a[key].append(v)
            temp = self.temp_reader()
            if temp is not None:
                a["temp"].append(temp)
            flush_due = now - self._last_flush >= FLUSH_INTERVAL_S
        if flush_due:
            self.flush()

    # -- report --------------------------------------------------------------

    def report(self, limit_bins=RAM_BINS):
        with self._lock:
            bins = list(self._bins)[-limit_bins:]
            pending = len(self._pending)
        latest = bins[-1] if bins else None
        size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        return {
            "available": bool(bins),
            "reason": None if bins else "No 10-minute bin has been completed yet (one needs chrony's frequency for at least one minute).",
            "provenance": "observed",
            "sensor": SENSOR_NOTE,
            "frequency_note": "chrony's Frequency: how fast the uncorrected system clock runs; + = fast. Bins with "
                              "PPS not selected throughout are kept but not used for the fit.",
            "bin_s": BIN_S, "sample_interval_s": SAMPLE_INTERVAL_S,
            "bins": [{**b, "t": _iso(b["t"])} for b in bins],
            "latest": None if not latest else {
                "temp_c": q(latest["temp_mean_c"], "°C", "observed", SENSOR_NOTE),
                "freq_ppm": q(latest["freq_mean_ppm"], "ppm", "observed", "chrony's frequency estimate"),
                "bin_start_utc": _iso(latest["t"])},
            "fit": linear_fit(bins),
            "fit_note": ("A straight line through frequency against temperature over the logged bins. It is not "
                         "the oscillator profile and not a holdover prediction."),
            "storage": {"path": self.path, "bytes": size, "max_bytes": self.max_bytes,
                        "pending_bins": pending, "flush_interval_s": FLUSH_INTERVAL_S,
                        "note": "10-minute bins appended once an hour and on a clean stop; oldest quarter dropped past the cap"},
            "board": {"serial_sha256": self.identity.get("serial_sha256"), "model": self.identity.get("model")},
            "problems": list(self.problems),
        }
