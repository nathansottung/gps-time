"""Independent references: the station's clock compared with NTP servers that
are not steering it.

chrony already measures every server it polls. A server that chrony is not
using to discipline the clock at the moment (configured `noselect`, or simply
not selected or combined) is an independent check on it. This module reads
those measurements, keeps a short RAM history per server, and says whether the
station agrees with them.

Rules:
  - The measurements come from other people's servers over the network, so
    they are labeled `external`.
  - A server chrony has selected or combined is steering the clock and is not
    independent; it is listed, but not counted.
  - The station's own address is never a reference.
  - The outcome is "agrees" or "disagrees" with a count. A disagreement says
    two clocks differ. It never says which one is wrong, or why.
  - No network is not a failure: the answer is "no external references
    reachable".
Nothing here writes chrony's configuration or contacts a server itself.
"""

import os
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone

from . import chrony

THRESHOLD_S = float(os.environ.get("GTP_REF_DISAGREE_S", "0.05"))
HISTORY_INTERVAL_S = 60.0
HISTORY_POINTS = 1440          # 24 h at one point a minute
MAX_SOURCES = 16
NTPDATA_INTERVAL_S = 15.0
MIN_FOR_MAJORITY = 2

SIGN_NOTE = ("offset_s is chrony's figure for the last measurement: positive means the station's clock "
             "is ahead of that server.")


def role(row):
    """'self' | 'steering' | 'independent' for a network source row; None for a refclock."""
    if row.get("mode") == "#":
        return None
    if row.get("is_self"):
        return "self"
    return "steering" if row.get("state") in ("*", "+") else "independent"


def usable(row):
    """A reachable source with a recent measurement."""
    if not row.get("reach_int") or row.get("offset_s") is None:
        return False
    last = row.get("lastrx_s")
    return last is not None and last <= max(4 * 2 ** row.get("poll", 6), 120)


def assess_one(offset_s, error_bound_s, threshold_s):
    """'agrees' | 'disagrees' | 'inconclusive' for one usable reference.
    Inconclusive: the offset is over the threshold but inside the error bound
    chrony gives for that server, so the measurement can't decide."""
    if abs(offset_s) <= threshold_s:
        return "agrees"
    if error_bound_s is not None and abs(offset_s) <= error_bound_s:
        return "inconclusive"
    return "disagrees"


def verdict(refs, sources_ok, threshold_s):
    """Overall outcome from the independent references. Pure."""
    def out(code, headline, detail, **counts):
        return {"code": code, "headline": headline, "detail": detail, "provenance": "calculated",
                "threshold_s": threshold_s, **counts}

    if not sources_ok:
        return out("UNKNOWN", "INDEPENDENT REFERENCES UNKNOWN", "chrony's source list could not be read.")
    if not refs:
        return out("NONE_CONFIGURED", "NO INDEPENDENT REFERENCES",
                   "chrony is not polling any server that is not steering the clock, so there is nothing to compare with.")
    good = [r for r in refs if r["usable"]]
    counts = {"configured": len(refs), "usable": len(good),
              "agreeing": sum(1 for r in good if r["assessment"] == "agrees"),
              "disagreeing": sum(1 for r in good if r["assessment"] == "disagrees"),
              "inconclusive": sum(1 for r in good if r["assessment"] == "inconclusive")}
    limit = f"{threshold_s * 1000:g} ms"
    if not good:
        return out("NONE_REACHABLE", "NO EXTERNAL REFERENCES REACHABLE",
                   f"None of the {len(refs)} independent server(s) has answered recently. "
                   "The station works without them; there is no comparison to report.", **counts)
    if len(good) < MIN_FOR_MAJORITY:
        r = good[0]
        return out("ONE_REFERENCE", "ONE INDEPENDENT REFERENCE",
                   f"Only {r['name']} is answering; its measurement {r['assessment']} with the station "
                   f"(limit {limit}). A majority needs at least {MIN_FOR_MAJORITY} references.", **counts)
    if counts["disagreeing"] * 2 > len(good):
        return out("DISAGREE", "STATION DISAGREES WITH MOST INDEPENDENT REFERENCES",
                   f"The station's clock differs from {counts['disagreeing']} of {len(good)} independent "
                   f"references by more than {limit}. This is a disagreement between clocks; it does not say "
                   "which clock is wrong or why.", **counts)
    return out("AGREE", "STATION AGREES WITH INDEPENDENT REFERENCES",
               f"{counts['agreeing']} of {len(good)} independent references are within {limit} of the station"
               + (f"; {counts['disagreeing']} differ by more" if counts["disagreeing"] else "")
               + (f"; {counts['inconclusive']} can't decide (offset inside the server's own error bound)"
                  if counts["inconclusive"] else "") + ".", **counts)


class Tracker:
    """RAM-only history of chrony's measurements of each independent server."""

    def __init__(self, clock=time.time, ntpdata_reader=None, threshold_s=None):
        self.clock = clock
        self.ntpdata_reader = ntpdata_reader or chrony.ntpdata
        self.threshold_s = THRESHOLD_S if threshold_s is None else threshold_s
        self._lock = threading.Lock()
        self._history = OrderedDict()       # name -> deque of points
        self._recorded = {}                 # name -> time of the last recorded point
        self._ntpdata, self._ntpdata_at = None, None
        self._rows, self._ok, self._at = [], False, None

    def update(self, rows, sources_ok=True):
        """Called with every fresh `chronyc -n sources` result."""
        now = self.clock()
        if self._ntpdata_at is None or now - self._ntpdata_at >= NTPDATA_INTERVAL_S:
            try:
                self._ntpdata = self.ntpdata_reader()
            except Exception:  # noqa: BLE001 — a helper problem must not stop the timing chain
                self._ntpdata = None
            self._ntpdata_at = now
        with self._lock:
            self._rows, self._ok, self._at = list(rows or []), bool(sources_ok), now
            if not sources_ok:
                return
            for row in self._rows:
                if role(row) != "independent" or not usable(row):
                    continue
                name = row["name"]
                # one point per new measurement, at most once a minute
                since = now - self._recorded.get(name, float("-inf"))
                if since < HISTORY_INTERVAL_S or row["lastrx_s"] >= since:
                    continue
                if name not in self._history:
                    if len(self._history) >= MAX_SOURCES:
                        old, _ = self._history.popitem(last=False)
                        self._recorded.pop(old, None)
                    self._history[name] = deque(maxlen=HISTORY_POINTS)
                self._history[name].append({
                    "t": round(now - row["lastrx_s"], 1), "offset_s": row["offset_s"],
                    "error_bound_s": row["error_bound_s"], "delay_s": self._delay(name)})
                self._recorded[name] = now

    def _delay(self, name):
        d = (self._ntpdata or {}).get(name.lower())
        return d.get("peer_delay_s") if d else None

    def report(self, history_for=None):
        """The /api/references payload. Each server's history is included only
        for `history_for` (a server name), or for the first independent server
        with history when it is None: all of them at once was about 1 MB."""
        with self._lock:
            rows, ok, at = list(self._rows), self._ok, self._at
            history = {k: list(v) for k, v in self._history.items()}
        refs, excluded = [], []
        if history_for is None:
            history_for = next((r["name"] for r in rows if role(r) == "independent" and history.get(r["name"])), None)
        for row in rows:
            kind = role(row)
            if kind is None:
                continue
            if kind == "self":
                excluded.append({"name": row["name"], "why": "this station's own address"})
                continue
            if kind == "steering":
                excluded.append({"name": row["name"],
                                 "why": f"chrony has it {row['state_label']}: it is steering the clock, so it is not independent"})
                continue
            good = usable(row)
            nd = (self._ntpdata or {}).get(row["name"].lower()) or {}
            refs.append({
                "name": row["name"], "state": row["state"], "state_label": row["state_label"],
                "stratum": row["stratum"], "poll_s": 2 ** row["poll"], "reach": row["reach"],
                "reachable": bool(row["reach_int"]), "usable": good, "lastrx_s": row["lastrx_s"],
                "offset_s": row["offset_s"] if good else None,
                "error_bound_s": row["error_bound_s"] if good else None,
                "delay_s": nd.get("peer_delay_s") if good else None,
                "root_delay_s": nd.get("root_delay_s") if good else None,
                "assessment": assess_one(row["offset_s"], row["error_bound_s"], self.threshold_s) if good else "not usable",
                "provenance": "external",
                "history": history.get(row["name"], []) if row["name"] == history_for else [],
                "history_points": len(history.get(row["name"], [])),
            })
        return {
            "available": ok,
            "provenance": "external",
            "as_of_utc": datetime.fromtimestamp(at, timezone.utc).isoformat(timespec="seconds") if at else None,
            "verdict": verdict(refs, ok, self.threshold_s),
            "references": refs,
            "excluded": excluded,
            "delay_available": self._ntpdata is not None,
            "delay_note": None if self._ntpdata is not None else
                          "Network delay per server is UNKNOWN: it comes from the chrony helper service's "
                          "published `chronyc -n ntpdata`, which is not available.",
            "sign": SIGN_NOTE,
            "history": {"interval_s": HISTORY_INTERVAL_S, "max_points": HISTORY_POINTS,
                        "storage": "RAM only; lost when the service restarts"},
        }
