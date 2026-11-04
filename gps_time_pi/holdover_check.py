"""Holdover validation: predicted against measured clock error at each PPS outage (GPS-008).

When an outage opens, the holdover projections of that moment are kept as the prediction
(`modeled`). The measurement is the kernel PPS timestamp of the first good pulse after recovery
(`observed`): its distance from the whole second is how far the system clock had drifted from
GNSS time while PPS was away. "Good" means the pulses are back (HEALTHY or DEGRADED) and GNSS is
healthy again, after the outage had seen either of them fail, so the pulse is the receiver's
locked pulse and chrony hasn't started steering to it yet. An outage where the pulses and GNSS
never failed (chrony stopped using PPS on its own) is measured at the first pulse after chrony
selects PPS again; chrony may already be correcting by then, so it isn't scored.

Each entry compares the measured error with each model's predicted error at the same time
since the outage began. The scorecard is the running record of those entries; holdover()
reports it with the projections and, from SCORE_MIN eligible outages on, adds a `scored`
projection: the profile's (or the trained) rate scaled by the worst measured/predicted ratio.

Not scored, and flagged instead:
  - chrony selected a network NTP source during the outage: the clock was steered, so the error
    at recovery isn't holdover error (`network_ntp`, with the sources);
  - no prediction: the outage began at boot or before the service started, or the projections
    weren't available then;
  - measured only after chrony re-selected PPS (see above);
  - |error| near 0.5 s or more: the whole second can't be told apart.

Storage: `holdover-scorecard.json` next to the events checkpoint, written once when an outage
closes (atomic, fsync), capped at MAX_ENTRIES. The prediction is kept in the open event, which
the events checkpoint already saves, so it survives a service restart. No position.
"""

import json
import os
import statistics
import tempfile
import time

from . import pps
from .labels import q

MAX_ENTRIES = 200
SCORE_MIN = 3               # eligible outages before the `scored` projection is offered
AMBIGUOUS_NS = 400_000_000  # |phase| at or past 0.4 s: the whole second may be wrong
SCHEMA = "gps-time.holdover-scorecard/1"
GOOD_PULSES = ("HEALTHY", "DEGRADED")


def default_path(events_path):
    return os.path.join(os.path.dirname(os.path.abspath(events_path)), "holdover-scorecard.json")


def error_at(rate_ppm, aging_ppm_day, tau_s):
    """Modeled |error| (s) after tau_s: rate·τ + aging·τ²/2, as oscprofile.holdover projects it."""
    if rate_ppm is None or tau_s is None:
        return None
    rate, accel = abs(rate_ppm) * 1e-6, abs(aging_ppm_day or 0.0) * 1e-6 / 86400.0
    return rate * tau_s + 0.5 * accel * tau_s * tau_s


def _iso(t):
    return None if t is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def basis_from(holdover):
    """The prediction to keep at an outage's start: each available projection's rate and aging."""
    if not holdover:
        return None
    models = [{"name": p["name"], "rate_ppm": p["rate_ppm"], "aging_ppm_per_day": p.get("aging_ppm_per_day") or 0.0}
              for p in holdover.get("projections", []) if p.get("available") and p.get("rate_ppm") is not None
              and p["name"] != "scored"]
    if not models:
        return None
    return {"sample_utc": holdover.get("sample_utc"), "models": models}


class Scorecard:
    def __init__(self, path=None, clock=time.time, max_entries=MAX_ENTRIES):
        self.path = path
        self.clock = clock
        self.max_entries = max_entries
        self.entries = []
        self.problems = []
        self._last_ts = None        # the newest pulse already seen (one sample per pulse)
        self._closing = None        # an outage that closed before a recovery pulse was measured
        self._load()

    def _problem(self, text):
        self.problems = (self.problems + [text])[-20:]

    # -- persistence ---------------------------------------------------------

    def _load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
            self.entries = list(doc.get("entries", []))[-self.max_entries:]
        except (OSError, ValueError) as e:
            self._problem(f"scorecard file unreadable, set aside: {e}")
            try:
                os.replace(self.path, f"{self.path}.corrupt-{int(self.clock())}")
            except OSError:
                pass

    def _write(self):
        if not self.path:
            return
        doc = {"schema": SCHEMA, "written_utc": _iso(self.clock()), "entries": self.entries[-self.max_entries:]}
        d = os.path.dirname(os.path.abspath(self.path))
        try:
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".scorecard-", dir=d)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(doc, f, indent=1)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        except OSError as e:
            self._problem(f"could not write the scorecard: {e.strerror or e}")

    # -- observation, once per chain evaluation ------------------------------

    def observe(self, chain, open_event, pulse_ts_ns, holdover_now=None):
        """chain: this evaluation; open_event: the tracker's open outage (or None), changed in
        place to keep the prediction and the measurement; pulse_ts_ns: the newest kernel PPS
        timestamp (int ns) or None; holdover_now: a callable giving the projections now.
        True when this call attached the prediction to a newly opened outage (checkpoint it)."""
        new_pulse = pulse_ts_ns is not None and pulse_ts_ns != self._last_ts
        if pulse_ts_ns is not None:
            self._last_ts = pulse_ts_ns
        if self._closing is not None:
            # The outage closed before a recovery pulse: take the first pulse after selection.
            if new_pulse:
                ev, self._closing = self._closing, None
                hc = ev["holdover_check"]
                hc["measured"] = {"ts_ns": pulse_ts_ns, "at": "reselected"}
                self._finish(ev)
            return False
        if open_event is None:
            return False
        hc = open_event.get("holdover_check")
        started = hc is None
        if started:
            hc = open_event["holdover_check"] = self._start(open_event, holdover_now)
        sel = (chain.get("chrony") or {}).get("selected") or {}
        if sel.get("kind") == "network" and not sel.get("is_self") and sel.get("name") \
                and sel["name"] not in hc["network_ntp_sources"]:
            hc["network_ntp_sources"].append(sel["name"])
        pulses_ok = (chain.get("pps") or {}).get("pulse_health") in GOOD_PULSES
        gnss_ok = (chain.get("gnss") or {}).get("healthy") is True
        if not (pulses_ok and gnss_ok):
            hc["seen_bad"] = True
        elif hc["seen_bad"] and hc.get("measured") is None and new_pulse:
            hc["measured"] = {"ts_ns": pulse_ts_ns, "at": "recovery"}
        return started

    def _start(self, ev, holdover_now):
        hc = {"basis": None, "no_basis_reason": None, "network_ntp_sources": [], "seen_bad": False, "measured": None}
        if ev.get("start_bound") == "boot":
            hc["no_basis_reason"] = "the outage began at boot: no trained clock to predict from"
        elif ev.get("start_bound") == "service_start":
            hc["no_basis_reason"] = "the outage began before the service started: no prediction from its start"
        else:
            try:
                hc["basis"] = basis_from(holdover_now() if holdover_now else None)
            except Exception as e:  # noqa: BLE001 — a missing projection must not stop the timing chain
                self._problem(f"no holdover projection at an outage's start: {e}")
            if hc["basis"] is None:
                hc["no_basis_reason"] = "no holdover projection was available when the outage began"
        hc["start_epoch"] = ev.get("start_epoch")
        return hc

    def closed(self, ev):
        """The tracker closed this outage (chrony selected PPS again)."""
        hc = ev.get("holdover_check")
        if hc is None:
            return
        if hc.get("measured") is None:
            self._closing = ev                # measured at the next pulse
            return
        self._finish(ev)

    # -- scoring -------------------------------------------------------------

    def _finish(self, ev):
        hc = ev["holdover_check"]
        m = hc["measured"]
        sec, phase = pps.phase_ns(pps.require_ns(m["ts_ns"]))
        t_meas = sec
        start = hc.get("start_epoch") if hc.get("start_epoch") is not None else ev.get("start_epoch")
        tau = None if start is None else max(0.0, t_meas - start)
        err_s = abs(phase) / 1e9
        flags, reasons = [], []
        if hc["network_ntp_sources"]:
            flags.append("network_ntp")
            reasons.append("chrony selected network NTP during the outage, so the clock was steered")
        if hc["basis"] is None:
            flags.append("no_prediction")
            reasons.append(hc.get("no_basis_reason") or "no prediction")
        if m["at"] == "reselected":
            flags.append("after_reselection")
            reasons.append("measured only after chrony selected PPS again; it may already have been correcting")
        if abs(phase) >= AMBIGUOUS_NS:
            flags.append("ambiguous_second")
            reasons.append("the error is near half a second or more: the whole second can't be told")
        if ev.get("restarts"):
            flags.append("service_restarted")       # noted; chrony kept running, so still scored
        preds = []
        for mdl in (hc["basis"] or {}).get("models", []):
            p = error_at(mdl["rate_ppm"], mdl["aging_ppm_per_day"], tau)
            ratio = (err_s / p) if p else None
            preds.append({"name": mdl["name"], "rate_ppm": mdl["rate_ppm"],
                          "predicted_error_s": q(p, "s", "modeled"),
                          "ratio": q(None if ratio is None else round(ratio, 4), None, "calculated",
                                     "measured / predicted; above 1, the model was too optimistic"),
                          "held": None if p is None else err_s <= p})
        blocking = [f for f in flags if f != "service_restarted"]
        entry = {"event_id": ev.get("id"), "start_utc": ev.get("start_utc"), "end_utc": ev.get("end_utc"),
                 "measured_utc": _iso(t_meas), "measured_at": m["at"],
                 "time_since_start_s": q(None if tau is None else round(tau, 1), "s", "calculated"),
                 "measured_error_s": q(phase / 1e9, "s", "observed",
                                       "kernel PPS timestamp's distance from the whole second; + = system clock ahead"),
                 "prediction_sample_utc": (hc["basis"] or {}).get("sample_utc"),
                 "predictions": preds, "network_ntp": bool(hc["network_ntp_sources"]),
                 "network_ntp_sources": list(hc["network_ntp_sources"]),
                 "flags": flags, "eligible": not blocking, "not_scored_because": reasons or None}
        if isinstance(ev.get("recovery"), dict):
            ev["recovery"]["holdover_check"] = {"measured_error_s": entry["measured_error_s"],
                                                "eligible": entry["eligible"], "flags": flags}
        self.entries.append(entry)
        self.entries = self.entries[-self.max_entries:]
        self._write()

    def summary(self, recent=20):
        """Per model: how often the bound held over the eligible outages, and the ratios."""
        ok = [e for e in self.entries if e.get("eligible")]
        models = {}
        for e in ok:
            for p in e["predictions"]:
                r = p["ratio"]["value"]
                if r is None:
                    continue
                m = models.setdefault(p["name"], {"name": p["name"], "n": 0, "held": 0, "ratios": []})
                m["n"] += 1
                m["held"] += 1 if p["held"] else 0
                m["ratios"].append(r)
        per = []
        for m in models.values():
            rs = m.pop("ratios")
            per.append({**m, "provenance": "calculated", "median_ratio": round(statistics.median(rs), 4),
                        "worst_ratio": round(max(rs), 4)})
        return {"provenance": "calculated", "entries": len(self.entries), "eligible": len(ok),
                "network_ntp": sum(1 for e in self.entries if e.get("network_ntp")),
                "score_min": SCORE_MIN, "models": per,
                "recent": list(reversed(self.entries[-recent:])),
                "note": ("Each outage's predicted error (modeled, from the projections when it began) against "
                         "the error measured at the first good PPS pulse after recovery (observed). Outages where "
                         "chrony used network NTP, or with no prediction, are listed but not scored."),
                "problems": list(self.problems)}
