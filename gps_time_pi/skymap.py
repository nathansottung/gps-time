"""The learned sky-obstruction map (addendum §10–11): what the station's antenna
normally hears, by direction, learned from its own satellites over days.

What is recorded (from the GNSS collector's fresh SKY reports; never from HTTP traffic):
  - once a minute, every satellite gpsd lists with an azimuth and elevation is
    counted in its sky cell (10° of azimuth × 5° of elevation): listed, tracked
    (C/N₀ > 0), used in the fix, and the sum and sum of squares of its C/N₀
    (observed, from the receiver);
  - the UTC days that had data (for "learned over N days").
A satellite-minute is one sample. Constellations are pooled in one grid.

Storage (project rule: nothing written at 1 Hz):
  - the grid is in RAM; it is written once an hour and on a clean stop as one
    small JSON file next to config.json (`sky-obstruction.json`), atomically;
  - the file is capped by design: a fixed grid of 648 cells, and when a cell
    reaches CELL_CAP samples all its counters are halved, so old behaviour fades
    and the numbers never grow without bound; at most MAX_DAYS day numbers are kept;
  - it holds no position and no time of day.

What is inferred from it (labeled `inferred`; never a cause):
  - each cell against the cells at the same elevation in other directions: an
    antenna hears low satellites worse everywhere, so a direction is "blocked"
    only when it is clearly worse than the rest of its elevation band, or when
    the receiver lists satellites there that it rarely tracks. A sky that is
    uniformly poor looks uniform: the map is relative to this station's own sky;
  - per 45° sector: "obstructed below ~N°", "intermittent attenuation a–b°",
    "mostly clear", or "not enough data" (UNKNOWN), never a guess;
  - satellite losses (§11): a satellite tracked in one sky report and not in the
    next, at its last direction, is EXPECTED (the learned map has that cell
    blocked or attenuated), NOT EXPLAINED (the map has it clear), SET (below 5°),
    or UNKNOWN (the map has too little data there);
  - a SKY-WIDE C/N₀ DROP: in one report, at least SKYWIDE_MIN satellites above
    30°, in at least three quadrants and at least half of those tracked there,
    lost or down by SKYWIDE_DB. The learned map does not explain it; the evidence
    does not establish a cause.

Privacy: satellite azimuths and elevations over time constrain the station's
position, and the grid's shape gives its rough latitude. In hidden mode nothing
is collected, served or exported (the file on the SD card is kept as it is).
"""

import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

from . import config

FORMAT = "gps-time-sky-obstruction/1"
FILE_NAME = "sky-obstruction.json"
AZ_STEP = 10
EL_STEP = 5
N_AZ = 360 // AZ_STEP
N_EL = 90 // EL_STEP
SAMPLE_INTERVAL_S = 60.0
FLUSH_INTERVAL_S = 3600.0
CELL_CAP = 20000              # samples per cell before its counters are halved (≈ 2 weeks of a busy cell)
MAX_DAYS = 400
MAX_FILE_BYTES = 256 * 1024   # a larger file is not ours: set aside, not read
MIN_CELL = 20                 # satellite-minutes before a cell is classified
MIN_BAND = 4                  # classified cells in an elevation band for its median
LEARNED_DAYS = 2
BLOCKED_DB, ATTEN_DB = 8.0, 4.0
BLOCKED_TRACK, ATTEN_TRACK = 0.5, 0.8
LOSS_GAP_S = 30.0             # reports further apart than this are not compared
SET_EL = 5
SKYWIDE_EL, SKYWIDE_MIN, SKYWIDE_DB = 30, 4, 10.0
RECENT = 200
SECTORS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

NOTE = ("Learned from this station's own satellites: each direction is compared with the rest of its "
        "elevation band. It is an RF horizon, not a physical survey of the sky, and it never says what "
        "blocks a signal.")
HIDDEN_REASON = ("Location privacy is hidden: satellite directions over time would reveal the station's "
                 "position, so the sky-obstruction map is neither collected nor shown.")


def default_path():
    configured = os.environ.get("GTP_SKY_OBSTRUCTION")
    if configured:
        return configured
    cfg = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return os.path.join(os.path.dirname(os.path.abspath(cfg)), FILE_NAME)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def cell_of(az, el):
    """(azimuth index, elevation index) or None for a direction gpsd didn't give."""
    if not (_num(az) and _num(el)) or el < 0 or el > 90:
        return None
    return int(az % 360 // AZ_STEP), min(N_EL - 1, int(el // EL_STEP))


def _utc(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


class SkyMap:
    """Samples in from the collector; a classified grid, sectors and losses out."""

    def __init__(self, path=None, clock=time.time, monotonic=time.monotonic, mode=None):
        self.path = path or default_path()
        self.clock = clock
        self.monotonic = monotonic
        self._mode = mode or (lambda: config.load().get("location_display", "exact"))
        self._lock = threading.Lock()
        self.cells = {}                 # (ai, ei) -> [listed, tracked, used, sum_cn0, sum_cn0²]
        self.days = []                  # UTC day numbers with data, sorted
        self.samples = 0
        self.untracked_seen = False     # the receiver lists satellites it isn't tracking (C/N₀ 0)
        self.problems = []
        self.last_write = None
        self.dirty = False
        self._last_sample = None
        self._last_flush = monotonic()
        self._prev = None               # (monotonic, {key: (az, el, cn0)}) of the last report
        self.losses = deque(maxlen=RECENT)
        self.loss_counts = {"EXPECTED": 0, "NOT EXPLAINED": 0, "UNKNOWN": 0, "SET": 0}
        self.skywide = deque(maxlen=RECENT)
        self._class = None              # classification cache, rebuilt after each sample
        self._load()

    # -- file -------------------------------------------------------------------------

    def _load(self):
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return
        try:
            if size > MAX_FILE_BYTES:
                raise ValueError(f"over {MAX_FILE_BYTES} bytes")
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
            if not isinstance(doc, dict) or doc.get("format") != FORMAT \
                    or doc.get("az_step") != AZ_STEP or doc.get("el_step") != EL_STEP:
                raise ValueError("not a sky-obstruction file of this format")
            cells = {}
            for key, v in (doc.get("cells") or {}).items():
                ai, ei = (int(x) for x in key.split(","))
                if not (0 <= ai < N_AZ and 0 <= ei < N_EL) or not isinstance(v, list) or len(v) != 5 \
                        or not all(_num(x) and x >= 0 for x in v):
                    raise ValueError(f"bad cell {key}")
                cells[(ai, ei)] = [float(x) for x in v]
            days = sorted({int(d) for d in doc.get("days") or [] if isinstance(d, int)})[-MAX_DAYS:]
        except (OSError, ValueError, TypeError) as e:
            aside = self.path + f".set-aside-{int(self.clock())}"
            try:
                os.replace(self.path, aside)
                self.problems.append(f"{os.path.basename(self.path)} could not be read ({e}); "
                                     f"set aside as {os.path.basename(aside)}")
            except OSError as e2:
                self.problems.append(f"could not set the unreadable map aside: {e2.strerror or e2}")
            return
        self.cells, self.days = cells, days
        self.samples = int(doc.get("samples") or 0)
        self.untracked_seen = bool(doc.get("untracked_seen"))
        self.last_write = doc.get("written_utc")

    def document(self):
        with self._lock:
            return {"format": FORMAT, "az_step": AZ_STEP, "el_step": EL_STEP,
                    "note": "listed, tracked, used, sum C/N0, sum C/N0^2 per cell; no position, no time of day",
                    "written_utc": _utc(self.clock()), "samples": self.samples,
                    "untracked_seen": self.untracked_seen, "days": list(self.days),
                    "cells": {f"{a},{e}": [round(x, 1) for x in v] for (a, e), v in sorted(self.cells.items())}}

    def flush(self):
        """Write the grid (atomic, fsync). Hourly and on a clean stop; nothing if unchanged."""
        if not self.dirty:
            return False
        doc = self.document()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
            config._atomic_write(self.path, json.dumps(doc, separators=(",", ":")))
        except OSError as e:
            self.problems.append(f"write failed: {e.strerror or e}")
            return False
        with self._lock:
            self.dirty = False
            self.last_write = doc["written_utc"]
            self._last_flush = self.monotonic()
        return True

    # -- samples ----------------------------------------------------------------------

    def observe(self, sats):
        """One fresh SKY report (gps.snapshot()-shaped satellites). Off in hidden mode."""
        if self._mode() == "hidden":
            self._prev = None
            return
        now_m = self.monotonic()
        self._losses(sats, now_m)
        flush_due = False
        with self._lock:
            if self._last_sample is None or now_m - self._last_sample >= SAMPLE_INTERVAL_S:
                self._last_sample = now_m
                self._add(sats)
            flush_due = self.dirty and now_m - self._last_flush >= FLUSH_INTERVAL_S
        if flush_due:
            self.flush()

    def _add(self, sats):
        added = False
        for s in sats:
            c = cell_of(s.get("az"), s.get("el"))
            if c is None:
                continue
            cn0 = s.get("snr")
            v = self.cells.setdefault(c, [0.0] * 5)
            v[0] += 1
            if _num(cn0) and cn0 > 0:
                v[1] += 1
                v[3] += cn0
                v[4] += cn0 * cn0
            else:
                self.untracked_seen = True
            if s.get("used"):
                v[2] += 1
            if v[0] >= CELL_CAP:
                self.cells[c] = [x / 2 for x in v]
            added = True
        if added:
            self.samples += 1
            day = int(self.clock() // 86400)
            if not self.days or self.days[-1] != day:
                self.days = (self.days + [day])[-MAX_DAYS:]
            self.dirty = True
            self._class = None

    # -- §11: losses --------------------------------------------------------------------

    def _losses(self, sats, now_m):
        cur = {}
        for s in sats:
            if _num(s.get("az")) and _num(s.get("el")):
                cur[(s.get("gnss"), s.get("id"))] = (s["az"], s["el"], s.get("snr") if _num(s.get("snr")) else 0)
        prev, self._prev = self._prev, (now_m, cur)
        if prev is None or now_m - prev[0] > LOSS_GAP_S:
            return
        when = _utc(self.clock())
        classes = self.classified()
        high_prev, high_down = [], []
        for key, (az, el, cn0) in prev[1].items():
            if cn0 <= 0:
                continue
            now = cur.get(key)
            lost = now is None or now[2] <= 0
            if el >= SKYWIDE_EL:
                high_prev.append(key)
                if lost or cn0 - now[2] >= SKYWIDE_DB:
                    high_down.append((key, az))
            if not lost:
                continue
            kind, note = self._loss_class(classes, az, el)
            with self._lock:
                self.loss_counts[kind] += 1
                self.losses.append({"utc": when, "gnss": key[0], "sat": key[1], "az": az, "el": el,
                                    "cn0_before": cn0, "class": kind, "note": note,
                                    "provenance": "inferred"})
        quadrants = {int(az % 360 // 90) for _, az in high_down}
        if len(high_down) >= SKYWIDE_MIN and len(quadrants) >= 3 and len(high_down) * 2 >= len(high_prev):
            with self._lock:
                self.skywide.append({"utc": when, "satellites": len(high_down), "of": len(high_prev),
                                     "quadrants": len(quadrants), "provenance": "inferred",
                                     "note": ("Satellites above 30° in several directions lost or dropped "
                                              f"{SKYWIDE_DB:.0f} dB together. The learned obstruction map does "
                                              "not explain this; the evidence does not establish a cause.")})

    @staticmethod
    def _loss_class(classes, az, el):
        if el < SET_EL:
            return "SET", f"below {SET_EL}°: the satellite set"
        c = classes.get(cell_of(az, el))
        if c is None or c["class"] == "unknown":
            return "UNKNOWN", "the learned map has too little data in this direction"
        if c["class"] in ("blocked", "attenuated"):
            return "EXPECTED", f"expected environmental loss: this direction is normally {c['class']} here"
        return "NOT EXPLAINED", "this direction is normally clear here; the map does not explain the loss"

    # -- inference ----------------------------------------------------------------------

    def classified(self):
        """{(ai, ei): cell report}, every cell with data; cached until the next sample."""
        with self._lock:
            if self._class is not None:
                return self._class
            cells = {k: list(v) for k, v in self.cells.items()}
            untracked = self.untracked_seen
        stats = {}
        for k, (n, t, u, s, s2) in cells.items():
            mean = s / t if t else None
            sd = math.sqrt(max(0.0, s2 / t - mean * mean)) if t > 1 else None
            stats[k] = {"n": n, "tracked": t / n if n else None, "used": u / n if n else None,
                        "mean": mean, "sd": sd}
        rows = {}
        for (a, e), st in stats.items():
            if st["n"] >= MIN_CELL and st["mean"] is not None:
                rows.setdefault(e, []).append(st["mean"])
        out = {}
        for (a, e), st in stats.items():
            band = [m for r in (e - 1, e, e + 1) for m in rows.get(r, [])]
            ref = _median(band) if len(band) >= MIN_BAND else None
            delta = st["mean"] - ref if ref is not None and st["mean"] is not None else None
            trk = st["tracked"] if untracked else None
            if st["n"] < MIN_CELL or (delta is None and trk is None):
                cls = "unknown"
            elif (trk is not None and trk < BLOCKED_TRACK) or (delta is not None and delta <= -BLOCKED_DB):
                cls = "blocked"
            elif (trk is not None and trk < ATTEN_TRACK) or (delta is not None and delta <= -ATTEN_DB):
                cls = "attenuated"
            else:
                cls = "clear"
            out[(a, e)] = {"az0": a * AZ_STEP, "el0": e * EL_STEP, "samples": int(round(st["n"])),
                           "tracked_pct": None if st["tracked"] is None else round(100 * st["tracked"]),
                           "used_pct": None if st["used"] is None else round(100 * st["used"]),
                           "cn0_mean": None if st["mean"] is None else round(st["mean"], 1),
                           "cn0_sd": None if st["sd"] is None else round(st["sd"], 1),
                           "band_median": None if ref is None else round(ref, 1),
                           "delta_db": None if delta is None else round(delta, 1),
                           "class": cls}
        with self._lock:
            self._class = out
        return out

    @staticmethod
    def _column_horizon(classes, ai):
        """Top of the highest blocked cell below the first clear one, from the horizon up;
        0 when the lowest classified cell is clear; None when nothing is classified."""
        top, seen = 0, False
        for ei in range(N_EL):
            c = classes.get((ai, ei))
            cls = c["class"] if c else "unknown"
            if cls == "clear":
                return top
            if cls == "blocked":
                top, seen = (ei + 1) * EL_STEP, True
            elif cls == "attenuated":
                seen = True
        return top if seen else None

    def sectors(self, classes=None):
        classes = self.classified() if classes is None else classes
        out = []
        for i, name in enumerate(SECTORS):
            centre = i * 45
            cols = [a for a in range(N_AZ) if ((a * AZ_STEP + AZ_STEP / 2 - centre + 180) % 360) - 180 < 22.5
                    and ((a * AZ_STEP + AZ_STEP / 2 - centre + 180) % 360) - 180 >= -22.5]
            mine = [classes[(a, e)] for a in cols for e in range(N_EL) if (a, e) in classes]
            known = [c for c in mine if c["class"] != "unknown"]
            horizons = [h for h in (self._column_horizon(classes, a) for a in cols) if h is not None]
            below = _median(horizons) if horizons else None
            weak = [c for c in known if c["class"] in ("blocked", "attenuated") and c["el0"] < 60]
            if not known:
                state, text = "unknown", "Not enough data"
            elif below is not None and below >= 10:
                state, text = "obstructed", f"Expected obstruction below ~{below:.0f}°"
            elif len(weak) >= 2:
                lo, hi = min(c["el0"] for c in weak), max(c["el0"] for c in weak) + EL_STEP
                state, text = "attenuated", f"Intermittent attenuation {lo}–{hi}°"
            else:
                state, text = "clear", "Mostly clear"
            means = [c["cn0_mean"] for c in known if c["cn0_mean"] is not None]
            out.append({"sector": name, "az_centre": centre, "state": state, "text": text,
                        "below_deg": below if state == "obstructed" else None,
                        "cells_classified": len(known), "cells": len(mine),
                        "cn0_median": None if not means else round(_median(means), 1),
                        "provenance": "inferred"})
        return out

    def summary(self, classes=None):
        classes = self.classified() if classes is None else classes
        known = [c for c in classes.values() if c["class"] != "unknown"]
        with self._lock:
            days, samples, untracked = len(self.days), self.samples, self.untracked_seen
        return {"days": days, "satellite_minutes": int(sum(c["samples"] for c in classes.values())),
                "reports_sampled": samples, "cells_total": N_AZ * N_EL, "cells_with_data": len(classes),
                "cells_classified": len(known),
                "clear_pct": None if not known else round(100 * sum(c["class"] == "clear" for c in known) / len(known)),
                "state": "learned" if days >= LEARNED_DAYS and known else "learning",
                "untracked_reported": untracked}

    def report(self, recent=20):
        classes = self.classified()
        with self._lock:
            losses = list(self.losses)[-recent:][::-1]
            counts = dict(self.loss_counts)
            skywide = list(self.skywide)[-recent:][::-1]
            n_sky = len(self.skywide)
            file = {"name": os.path.basename(self.path), "last_write_utc": self.last_write,
                    "unsaved": self.dirty, "problems": list(self.problems)}
        return {"available": True, "format": FORMAT, "az_step": AZ_STEP, "el_step": EL_STEP,
                "summary": self.summary(classes), "sectors": self.sectors(classes),
                "cells": [classes[k] for k in sorted(classes)],
                "losses": {"counts": counts, "recent": losses, "since": "service start"},
                "sky_wide": {"count": n_sky, "recent": skywide},
                "thresholds": {"min_cell_samples": MIN_CELL, "blocked_db": BLOCKED_DB, "attenuated_db": ATTEN_DB,
                               "blocked_tracked": BLOCKED_TRACK, "attenuated_tracked": ATTEN_TRACK,
                               "learned_days": LEARNED_DAYS},
                "file": file, "note": NOTE, "provenance": "inferred"}

    def sky_quality(self):
        """The coarse summary for the capability record and the export: sectors only, no grid, no times."""
        classes = self.classified()
        s = self.summary(classes)
        return {"state": s["state"], "days": s["days"], "clear_pct": s["clear_pct"],
                "cells_classified": s["cells_classified"],
                "sectors": [{k: x[k] for k in ("sector", "state", "below_deg")} for x in self.sectors(classes)],
                "provenance": "inferred",
                "note": "From the learned sky-obstruction map: an RF horizon relative to this station's own sky."}


SERVICE = None
_SERVICE_LOCK = threading.Lock()


def service():
    """The station's map (created on first use; flushed at a clean stop)."""
    global SERVICE
    with _SERVICE_LOCK:
        if SERVICE is None:
            SERVICE = SkyMap()
            import atexit
            atexit.register(SERVICE.flush)
        return SERVICE


def payload(m, mode):
    """GET /api/sky-obstruction under the privacy mode."""
    if mode == "hidden":
        return {"available": False, "reason": HIDDEN_REASON, "location_display": mode}
    return {**m.report(), "location_display": mode}


def sky_quality_block(m, cfg):
    """The opt-in sky-quality summary, or (None, why not)."""
    if cfg.get("location_display") == "hidden":
        return None, "location privacy is hidden"
    if not cfg.get("sky_quality_share"):
        return None, "off (opt-in: POST /api/setting {\"sky_quality_share\": true})"
    return m.sky_quality(), None


def diagnostic_lines(m, cfg):
    q, why = sky_quality_block(m, cfg)
    if q is None:
        return [f"sky quality: not included ({why})"]
    lines = [f"sky quality ({q['provenance']}): {q['state']}, {q['days']} days, "
             f"clear {q['clear_pct'] if q['clear_pct'] is not None else 'UNKNOWN'} % of classified cells"]
    lines += [f"  {x['sector']:<2} {x['state']}" + (f" below ~{x['below_deg']:.0f}°" if x["below_deg"] else "")
              for x in q["sectors"]]
    return lines
