"""Outage evidence kept on the SD card, under a size cap (rc.9 item 2; OBS §13).

The rc.8 soak run had real PPS/GNSS outages on 2026-10-17 that left nothing in
the system journal. The only evidence was the station's event list and chrony's
tracking log in RAM, which a reboot would have lost. This module writes, for
each outage event, one file that survives a reboot:

  - the event as the timing chain recorded it;
  - a timeline of the station's view every 10 s (status, PPS state and pulse
    counters, chrony's view, GNSS summary) from a RAM ring of the last 2 hours;
  - chrony's tracking-log lines from 5 minutes before the start to 5 minutes
    after the end;
  - chrony's sources and tracking output at the time of writing.

When: 5 minutes after an outage opens (so a reboot during a long outage still
leaves its start), and again 5 minutes after it closes (replacing the first).
Nothing is written at 1 Hz; a quiet station writes nothing at all.

Cap: the evidence directory is kept under GTP_EVIDENCE_MAX_BYTES (20 MiB) and
200 files; the oldest files go first. One file is cut to 2 MiB of tracking
lines at most.

Privacy: no position is stored. The GNSS summary has satellite counts and C/N0
only, as the event list does.
"""

import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone

from . import chrony

WINDOW_S = 300.0
TIMELINE_STEP_S = 10.0
TIMELINE_POINTS = 720                 # 2 h at 10 s
MAX_BYTES = int(os.environ.get("GTP_EVIDENCE_MAX_BYTES", str(20 * 1024 * 1024)))
MAX_FILES = 200
MAX_TRACKING_BYTES = 2 * 1024 * 1024
SCHEMA = "gps-time.evidence/1"
ID_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def default_dir():
    configured = os.environ.get("GTP_EVIDENCE_DIR")
    if configured:
        return configured
    cfg = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return os.path.join(os.path.dirname(os.path.abspath(cfg)), "evidence")


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def _val(x):
    return x.get("value") if isinstance(x, dict) else x


def snapshot(chain, now):
    """The station's view at one moment, small and without position."""
    g, cv, p = chain.get("gnss") or {}, chain.get("chrony") or {}, chain.get("pps") or {}
    trk = cv.get("tracking") or {}
    return {"t": round(now, 1), "status": (chain.get("status") or {}).get("code"),
            "pps_state": _val(chain.get("pps_state")), "pulse_health": p.get("pulse_health"),
            "pps_age_s": _val(p.get("age_s")), "missed_pulses": _val(p.get("missed_pulses")),
            "unread_pulses": _val(p.get("unread_pulses")),
            "chrony_pps_status": cv.get("pps_status"), "nmea_status": cv.get("nmea_status"),
            "selected_source": (cv.get("selected") or {}).get("name"),
            "system_time_s": _val(trk.get("system_time_s")),
            "gnss_healthy": g.get("healthy"), "satellites_used": _val(g.get("satellites_used")),
            "satellites_visible": _val(g.get("satellites_visible")), "best_cn0": _val(g.get("best_cn0"))}


def tracking_lines(start, end, files=None, limit=MAX_TRACKING_BYTES):
    """chrony tracking-log lines with a timestamp in [start, end], oldest first,
    from the RAM log and the part rotated away. At most `limit` bytes: if there
    are more, the first and last halves are kept and the cut is marked."""
    files = files if files is not None else chrony._tracking_files(chrony.tracking_log_path())
    out = []
    for name in files:
        try:
            with open(name, encoding="ascii", errors="replace") as f:
                for line in f:
                    if len(line) < 20 or not line[:2].isdigit():
                        continue
                    try:
                        t = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
                    except ValueError:
                        continue
                    if start <= t <= end:
                        out.append(line.rstrip("\n"))
        except OSError:
            continue
    size = sum(len(l) + 1 for l in out)
    if size <= limit:
        return out, False
    head, tail, budget = [], [], limit // 2
    used = 0
    for l in out:
        if used + len(l) + 1 > budget:
            break
        head.append(l)
        used += len(l) + 1
    used = 0
    for l in reversed(out):
        if used + len(l) + 1 > budget:
            break
        tail.append(l)
        used += len(l) + 1
    return head + ["... (lines omitted: over the size limit for one evidence file) ..."] + list(reversed(tail)), True


class Store:
    def __init__(self, directory=None, clock=time.time, max_bytes=None, max_files=MAX_FILES,
                 tracking_files=None, chrony_now=None):
        self.dir = directory or default_dir()
        self.clock = clock
        self.max_bytes = MAX_BYTES if max_bytes is None else max_bytes
        self.max_files = max_files
        self.tracking_files = tracking_files
        self.chrony_now = chrony_now
        self._lock = threading.Lock()
        self._timeline = deque(maxlen=TIMELINE_POINTS)
        self._last_point = None
        self.problems = []
        self.removed = 0
        self._written = self._scan()      # event id -> "open" | "closed"

    def _scan(self):
        out = {}
        try:
            for name in os.listdir(self.dir):
                if name.endswith(".json"):
                    try:
                        with open(os.path.join(self.dir, name), encoding="utf-8") as f:
                            d = json.load(f)
                        out[d.get("event_id")] = d.get("phase")
                    except (OSError, ValueError):
                        continue
        except FileNotFoundError:
            pass
        except OSError as e:
            self.problems.append(f"{self.dir}: {e.strerror or e}")
        return out

    def observe(self, chain, events=None):
        """Called after each chain evaluation: keep the timeline, write what is due."""
        now = self.clock()
        if self._last_point is None or now - self._last_point >= TIMELINE_STEP_S:
            with self._lock:
                self._timeline.append(snapshot(chain, now))
            self._last_point = now
        ev = events if events is not None else (chain.get("events") or {})
        due = []
        o = ev.get("open")
        if o and o.get("id") not in self._written and now - o.get("start_epoch", now) >= WINDOW_S:
            due.append((o, "open"))
        for e in ev.get("recent") or []:
            end = self._end_epoch(e)
            if end is not None and self._written.get(e.get("id")) != "closed" and now - end >= WINDOW_S \
                    and now - end < 6 * 3600:          # not for old events found after a restart
                due.append((e, "closed"))
        for e, phase in due:
            self.write(e, phase)

    @staticmethod
    def _end_epoch(e):
        if not e.get("end_utc"):
            return None
        try:
            return datetime.fromisoformat(e["end_utc"]).timestamp()
        except ValueError:
            return None

    def write(self, event, phase):
        eid = event.get("id") or ""
        if not ID_RE.match(eid):
            return None
        now = self.clock()
        start = event.get("start_epoch") or now
        end = self._end_epoch(event) if phase == "closed" else now
        lo, hi = start - WINDOW_S, (end or now) + WINDOW_S
        with self._lock:
            timeline = [p for p in self._timeline if lo <= p["t"] <= hi]
        lines, cut = tracking_lines(lo, hi, self.tracking_files)
        notes = []
        if timeline and timeline[0]["t"] > lo + TIMELINE_STEP_S:
            notes.append("The timeline starts later than the window: the station keeps 2 hours in memory, "
                         "or the service started during the window.")
        if cut:
            notes.append("Tracking-log lines were cut to the size limit for one file.")
        doc = {"schema": SCHEMA, "event_id": eid, "phase": phase, "written_utc": _iso(now),
               "window_utc": [_iso(lo), _iso(hi)], "window_s_before_after": WINDOW_S,
               "event": event, "timeline_step_s": TIMELINE_STEP_S, "timeline": timeline,
               "chrony_tracking_lines": lines,
               "chrony_now": self.chrony_now() if self.chrony_now else None,
               "notes": notes,
               "privacy": "No position is stored: satellite counts and C/N0 only."}
        path = os.path.join(self.dir, eid + ".json")
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as e:
            self.problems.append(f"write failed for {eid}: {e.strerror or e}")
            return None
        self._written[eid] = phase
        self._enforce_cap(keep=path)
        return path

    def _files(self):
        try:
            names = [n for n in os.listdir(self.dir) if n.endswith(".json")]
        except OSError:
            return []
        out = []
        for n in names:
            p = os.path.join(self.dir, n)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append((st.st_mtime, st.st_size, p))
        return sorted(out)

    def _enforce_cap(self, keep):
        files = self._files()
        total = sum(s for _, s, _ in files)
        while files and (total > self.max_bytes or len(files) > self.max_files):
            mtime, size, p = files.pop(0)
            if p == keep:
                continue
            try:
                os.remove(p)
                total -= size
                self.removed += 1
            except OSError:
                break

    def index(self):
        """The files on the SD card, newest first, without their contents."""
        out = []
        for mtime, size, p in reversed(self._files()):
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, ValueError):
                continue
            e = d.get("event") or {}
            out.append({"id": d.get("event_id"), "phase": d.get("phase"), "written_utc": d.get("written_utc"),
                        "start_utc": e.get("start_utc"), "end_utc": e.get("end_utc"),
                        "duration_s": e.get("duration_s"), "classification": e.get("classification"),
                        "bytes": size, "tracking_lines": len(d.get("chrony_tracking_lines") or []),
                        "timeline_points": len(d.get("timeline") or [])})
        total = sum(i["bytes"] for i in out)
        return {"available": True, "dir": self.dir, "files": out, "total_bytes": total,
                "max_bytes": self.max_bytes, "max_files": self.max_files, "removed_for_space": self.removed,
                "problems": list(self.problems),
                "note": ("Written 5 minutes after an outage opens and again 5 minutes after it closes; "
                         "the oldest files are removed when the cap is reached.")}

    def read(self, eid):
        if not ID_RE.match(eid or ""):
            return None
        try:
            with open(os.path.join(self.dir, eid + ".json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None
