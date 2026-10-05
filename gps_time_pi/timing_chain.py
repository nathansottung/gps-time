"""GNSS → PPS → chrony timing-chain model (docs/architecture/timing-chain.md).

Each stage of the chain is observed and reported independently, so "GNSS is
fine" can never be mistaken for "PPS is disciplining the clock". Classifications
are evidence-based and never name a cause (jamming, spoofing, antenna failure)
the observations cannot establish.

Pure functions (gnss_summary, chrony_view, timing_status, classify, build_chain)
take plain data so tests can drive them with fixtures. PPSStateMachine and
EventTracker hold the little state that needs history. TimingChainService runs
the 1 Hz collector loop on the station.
"""

import json
import os
import statistics
import tempfile
import threading
import time
from datetime import datetime, timezone

from . import chrony, stability
from .labels import q
from .pps import PPSMonitor

OUTAGE_DEBOUNCE_S = float(os.environ.get("GTP_PPS_OUTAGE_DEBOUNCE_S", "30"))
ACQUIRE_WINDOW_S = float(os.environ.get("GTP_PPS_ACQUIRE_WINDOW_S", "1800"))   # 30 min after boot
NMEA_STALE_MIN_S = float(os.environ.get("GTP_NMEA_STALE_MIN_S", "30"))
CHRONY_INTERVAL_S = 5.0
CHECKPOINT_REFRESH_S = 900.0   # while an outage is open, refresh evidence at most every 15 min
RECENT_EVENTS_MAX = 50

FORBIDDEN_CAUSES = ("JAMMING", "SPOOF", "INTERFERENCE", "ANTENNA")


def _iso(epoch):
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def _val(x):
    return x["value"] if isinstance(x, dict) and "value" in x else x


# ── GNSS ────────────────────────────────────────────────────────────────────

def gnss_summary(snap):
    """Receiver comms / satellite reception / nav-time solution from gps.snapshot().
    Contains counts and signal levels only — never coordinates."""
    snap = snap or {}
    age = snap.get("data_age_s")
    if age is None:
        comms = "UNKNOWN"
    elif snap.get("stale"):
        comms = "FAILED"
    else:
        comms = "OK"

    sats = snap.get("sats") or []
    sky_fresh = not snap.get("sky_stale", True) and snap.get("sky_age_s") is not None
    used = [s for s in sats if s.get("used")]
    cn0 = [s.get("snr") for s in sats if isinstance(s.get("snr"), (int, float)) and s.get("snr") > 0]
    used_cn0 = [s.get("snr") for s in used if isinstance(s.get("snr"), (int, float)) and s.get("snr") > 0]
    if not sky_fresh:
        reception = "UNKNOWN"
    elif len(used) >= 4:
        reception = "OK"
    elif used or cn0:
        reception = "DEGRADED"
    else:
        reception = "FAILED"

    fix = snap.get("fix")
    if comms != "OK":
        solution = "UNKNOWN"
    elif fix == "3D":
        solution = "OK"
    elif fix == "2D":
        solution = "DEGRADED"
    else:
        solution = "FAILED"

    healthy = comms == "OK" and reception == "OK" and solution == "OK"
    unhealthy = comms == "OK" and (reception == "FAILED" or solution == "FAILED")
    return {
        "receiver_comms": comms, "satellite_reception": reception, "nav_time_solution": solution,
        "healthy": True if healthy else (False if unhealthy or comms == "FAILED" else None),
        "data_age_s": q(age, "s", "calculated"),
        "fix": q(fix, None, "observed"),
        "satellites_visible": q(len(sats) if sky_fresh else None, "count", "observed"),
        "satellites_used": q(len(used) if sky_fresh else None, "count", "observed"),
        "best_cn0": q(max(cn0) if (cn0 and sky_fresh) else None, "dB-Hz", "observed"),
        "median_cn0_used": q(statistics.median(used_cn0) if (used_cn0 and sky_fresh) else None,
                             "dB-Hz", "calculated"),
        "tdop": q(snap.get("tdop") if sky_fresh else None, None, "observed"),
    }


# ── chrony ──────────────────────────────────────────────────────────────────

def _pick_refclocks(rows, refcfg):
    """Return (pps_name, nmea_name, assumed). Config identifies refclocks; names
    are only assumed when chrony.conf is unreadable."""
    pps_cfg, nmea_cfg = (refcfg or {}).get("pps"), (refcfg or {}).get("nmea")
    if (refcfg or {}).get("source") == "chrony.conf":
        return (pps_cfg or {}).get("refid"), (nmea_cfg or {}).get("refid"), False
    local = [r["name"] for r in rows if r["mode"] == "#"]
    pps = next((n for n in local if n.upper().startswith("PPS")), None) or ("GPS" if "GPS" in local else None)
    nmea = next((n for n in local if n != pps and n.upper() in ("NMEA", "SHM0", "SOCK0", "GPSD")), None)
    return pps, nmea, True


def chrony_view(inputs, refcfg):
    """Interpret chronyc -n tracking/sources/sourcestats output (inputs dict of
    {name}_ok/{name}_text). Never adds a rejection reason chrony doesn't show."""
    trk = chrony.parse_tracking(inputs.get("tracking_text")) if inputs.get("tracking_ok") else {}
    rows = chrony.parse_sources(inputs.get("sources_text")) if inputs.get("sources_ok") else []
    stats = chrony.parse_sourcestats(inputs.get("sourcestats_text")) if inputs.get("sourcestats_ok") else {}
    sources_ok = bool(inputs.get("sources_ok"))
    pps_name, nmea_name, assumed = _pick_refclocks(rows, refcfg)
    pps_cfg = (refcfg or {}).get("pps")
    by_name = {r["name"]: r for r in rows}
    selected = next((r for r in rows if r["state"] == "*"), None)

    def source_detail(name):
        r = by_name.get(name)
        if not r:
            return None
        st = stats.get(name, {})
        return {
            "name": name, "mode": r["mode_label"],
            "state_symbol": q(r["state"], None, "observed"),
            "state_meaning": r["state_meaning"],
            "reach": q(r["reach"], "octal", "observed"),
            "reach_successes_of_8": q(r["reach_bits"], "count", "calculated"),
            "last_rx_s": q(r["lastrx_s"], "s", "observed"),
            "poll_log2_s": r["poll"],
            "offset_s": q(r["offset_s"], "s", "observed", "chrony's adjusted offset of the last sample"),
            "error_bound_s": q(r["error_bound_s"], "s", "observed"),
            "frequency_ppm": q(st.get("frequency_ppm"), "ppm", "calculated"),
            "skew_ppm": q(st.get("skew_ppm"), "ppm", "calculated"),
            "std_dev_s": q(st.get("std_dev_s"), "s", "calculated"),
        }

    if not sources_ok:
        pps_status, nmea_status = "UNKNOWN", "UNKNOWN"
    else:
        if pps_name is None:
            pps_status = "NOT_CONFIGURED"
        elif pps_name not in by_name:
            pps_status = "NOT_VISIBLE"
        else:
            r = by_name[pps_name]
            pps_status = ("SELECTED" if r["state"] == "*" else
                          "ACCEPTED" if r["state"] in "+-" else
                          "VISIBLE_NO_SAMPLES" if r["reach_int"] == 0 else "REJECTED")
        if nmea_name is None:
            nmea_status = "NOT_CONFIGURED"
        elif nmea_name not in by_name:
            nmea_status = "NOT_VISIBLE"
        else:
            r = by_name[nmea_name]
            limit = max(3 * 2 ** max(r["poll"], 0), NMEA_STALE_MIN_S)
            stale = r["reach_int"] == 0 or r["lastrx_s"] is None or r["lastrx_s"] > limit
            nmea_status = "STALE" if stale else "OK"

    return {
        "available": {"tracking": bool(trk), "sources": sources_ok, "sourcestats": bool(inputs.get("sourcestats_ok"))},
        "refclocks": {"pps": pps_name, "nmea": nmea_name,
                      "identified_from": "assumed default names" if assumed else "chrony.conf",
                      "pps_lock": (pps_cfg or {}).get("lock")},
        "pps_status": pps_status, "nmea_status": nmea_status,
        "pps": source_detail(pps_name) if pps_name else None,
        "nmea": source_detail(nmea_name) if nmea_name else None,
        "selected": None if not selected else {
            "name": selected["name"], "kind": "refclock" if selected["mode"] == "#" else "network",
            "stratum": selected["stratum"],
            "is_pps": selected["name"] == pps_name, "is_nmea": selected["name"] == nmea_name,
            "is_self": bool(selected.get("is_self"))},
        # chrony sources that are this station's own address (never an external reference)
        "self_sources": [r["name"] for r in rows if r.get("is_self")],
        "any_selected": selected is not None if sources_ok else None,
        "nmea_calibration": nmea_calibration((refcfg or {}).get("nmea") if not assumed else None,
                                             stats.get(nmea_name) if nmea_name else None,
                                             bool(selected) and selected["name"] == pps_name),
        "tracking": {
            "leap": trk.get("Leap status"), "stratum": trk.get("Stratum"),
            "reference": trk.get("reference_name"),
            "system_time_s": q(chrony._seconds(trk.get("System time")), "s", "observed",
                               "chrony's remaining correction, not an independent error measurement"),
            "root_delay_s": q(chrony._parse_float((trk.get("Root delay", "").split() or [None])[0]), "s", "observed"),
            "root_dispersion_s": q(chrony._parse_float((trk.get("Root dispersion", "").split() or [None])[0]), "s", "observed"),
            "frequency": trk.get("Frequency"),
        } if trk else None,
    }


def _nmea_cal_line(cal):
    if not cal:
        return "not reported"
    conf = _val(cal.get("configured_offset_s")) if cal.get("configured_offset_s") else None
    if not cal.get("available"):
        return f"configured {conf if conf is not None else 'UNKNOWN'} s; not measurable now ({cal.get('reason')})"
    return (f"configured {conf} s; residual {_val(cal['residual_s']):+.3f} s over {_val(cal['samples'])} samples; "
            f"suggested {_val(cal['suggested_offset_s'])} s" + ("" if cal.get("change_worthwhile") else " (no change needed)"))


NMEA_CAL_MIN_SAMPLES = 16
NMEA_CAL_MIN_CHANGE_S = 0.005


def nmea_calibration(nmea_cfg, nmea_stats, pps_selected):
    """A measured recommendation for the NMEA refclock's `offset` in chrony.conf.
    Nothing here changes chrony; the operator edits the file.

    Serial time messages arrive a roughly constant delay after the second they
    describe; chrony's `offset` option compensates for it. While PPS disciplines
    the clock, the system clock is right to far better than a millisecond, so
    chrony's own statistics for the NMEA source measure what is left over:

      residual  = `chronyc sourcestats` Offset for the NMEA source. In chrony's
                  reports a positive offset means the local clock is ahead of
                  the source, i.e. the NMEA time is still late.
      suggested = configured offset + residual

    The sign rule is chrony's documented convention; it has not been confirmed
    on this project's hardware, so the result says how to verify the change.
    """
    def unavailable(reason, **kw):
        return {"available": False, "reason": reason, **kw}

    if not nmea_cfg:
        return unavailable("no NMEA/serial refclock in chrony.conf")
    configured = nmea_cfg.get("offset_s")
    conf_q = q(configured, "s", "observed", "the offset option on the NMEA refclock line in chrony.conf")
    if configured is None:
        return unavailable("the NMEA refclock's offset in chrony.conf could not be read", configured_offset_s=conf_q)
    if not pps_selected:
        return unavailable("PPS must be the selected source: only then is the system clock a good enough "
                           "reference to measure the NMEA delay against", configured_offset_s=conf_q)
    st = nmea_stats or {}
    residual, sd, n = st.get("offset_s"), st.get("std_dev_s"), st.get("samples")
    if residual is None or sd is None or n is None:
        return unavailable("chrony has no statistics for the NMEA source", configured_offset_s=conf_q)
    if n < NMEA_CAL_MIN_SAMPLES:
        return unavailable(f"too few NMEA samples so far ({n}; {NMEA_CAL_MIN_SAMPLES} needed)",
                           configured_offset_s=conf_q, samples=q(n, "count", "observed"))
    suggested = round(configured + residual, 3)
    worthwhile = abs(residual) >= max(3 * sd, NMEA_CAL_MIN_CHANGE_S)
    return {
        "available": True, "reason": None,
        "configured_offset_s": conf_q,
        "residual_s": q(residual, "s", "observed",
                        "chronyc sourcestats Offset for the NMEA source while PPS is selected; "
                        "positive = the NMEA time is late relative to the PPS-disciplined clock"),
        "std_dev_s": q(sd, "s", "observed"),
        "samples": q(n, "count", "observed"),
        "span_s": q(st.get("span_s"), "s", "observed"),
        "suggested_offset_s": q(suggested, "s", "calculated", "configured offset + residual, to the millisecond"),
        "change_worthwhile": worthwhile,
        "advice": (f"Change `offset {configured:g}` to `offset {suggested:g}` on the NMEA refclock line in "
                   "chrony.conf and restart chrony. Then check this again after a few minutes: the residual "
                   "should be near zero. If it has roughly doubled instead, the sign is the other way round on "
                   f"this system: use `offset {round(configured - residual, 3):g}`."
                   if worthwhile else
                   "The residual is within the noise or under 5 ms: no change is needed."),
    }


# ── banner ──────────────────────────────────────────────────────────────────

def timing_status(trk, srcs, gnss=None, pps=None, refclocks=None):
    """Stateless top-level banner from parsed `chronyc -n tracking` (dict) and
    `chronyc -n sources` rows. Always names the disciplining source and never
    reports GPS/PPS Stratum 1 unless chrony has the PPS refclock selected ('*').
    srcs None or [] means the source list is unavailable."""
    rows = srcs or []
    pps_name, nmea_name, _ = _pick_refclocks(rows, refclocks)
    pps_configured = pps_name is not None
    sel = next((r for r in rows if r.get("state") == "*"), None)
    g = gnss if (gnss and "receiver_comms" in gnss) else gnss_summary(gnss)
    leap = (trk or {}).get("Leap status")
    stratum = (trk or {}).get("Stratum")
    gnss_note = ("GNSS healthy" if g["healthy"] else
                 "GNSS unhealthy" if g["healthy"] is False else "GNSS state unknown")

    def out(code, headline, banner, detail, source=None):
        return {"code": code, "headline": headline, "banner": banner, "detail": detail,
                "source": source, "gnss_healthy": g["healthy"], "provenance": "calculated"}

    if not trk:
        return out("UNKNOWN", "UNKNOWN", "TIMING SOURCE UNKNOWN",
                   "chrony status unavailable; cannot determine what disciplines the clock.")
    if leap and "Not synchronised" in leap:
        return out("UNSYNCHRONIZED", "UNSYNCHRONIZED", "UNSYNCHRONIZED · NO REFERENCE",
                   "Do not use this server as an authoritative time source.")
    if not rows:
        return out("SOURCE_UNKNOWN", "SOURCE UNKNOWN", "SYNCHRONIZED · SOURCE UNKNOWN",
                   "chrony reports synchronized, but its source list is unavailable.")
    if sel is None:
        return out("HOLDOVER", "HOLDOVER", "HOLDOVER · NO EXTERNAL REFERENCE",
                   f"No source selected; clock coasting on chrony's last frequency estimate. {gnss_note}.")
    kind = "refclock" if sel.get("mode") == "#" else "network"
    src = {"name": sel["name"], "kind": kind, "stratum": stratum}
    if sel.get("is_self"):
        # chrony is polling this station's own address and has selected it: the
        # clock follows itself. Whatever stratum that "source" reports, there is
        # no external reference.
        return out("HOLDOVER", "HOLDOVER", "HOLDOVER · NO EXTERNAL REFERENCE · CHRONY SELECTED THIS STATION ITSELF",
                   f"chrony's selected source {sel['name']} is this station's own address, so the clock is "
                   f"following itself. Remove that server from chrony (it usually comes from DHCP; "
                   f"re-running install.sh disables DHCP-provided servers). {gnss_note}.",
                   {**src, "is_self": True})
    if sel["name"] == pps_name:
        return out("GPS_PPS", "SYNCHRONIZED", f"SYNCHRONIZED · GPS/PPS · STRATUM {stratum}",
                   f"PPS refclock {sel['name']} selected by chrony.", src)
    if sel["name"] == nmea_name:
        if pps_configured:
            return out("DEGRADED", "DEGRADED", "DEGRADED · GNSS SERIAL TIME (NMEA) · PPS NOT SELECTED",
                       f"Clock disciplined by NMEA refclock {sel['name']} (millisecond-class).", src)
        return out("GNSS_NMEA", "SYNCHRONIZED", f"SYNCHRONIZED · GNSS SERIAL TIME (NMEA) · STRATUM {stratum}",
                   "No PPS refclock configured; serial GNSS time is millisecond-class.", src)
    if kind == "refclock":
        return out("REFCLOCK", "SYNCHRONIZED", f"SYNCHRONIZED · REFERENCE CLOCK {sel['name']} · STRATUM {stratum}",
                   "", src)
    if g["healthy"]:
        return out("DEGRADED", "DEGRADED", "DEGRADED · GNSS HEALTHY · PPS NOT SELECTED",
                   f"Network failover: clock disciplined by {sel['name']} (stratum {stratum}).", src)
    return out("NETWORK_FAILOVER", "NETWORK FAILOVER", "SYNCHRONIZED · NETWORK FAILOVER · GPS/PPS UNAVAILABLE",
               f"Clock disciplined by {sel['name']} (stratum {stratum}). {gnss_note}.", src)


def acquiring_status(base, boot_view):
    """Boot-phase overlay: until PPS is first selected after boot, report
    ACQUIRING instead of a degraded/failover state. GPS_PPS and UNSYNCHRONIZED
    are never masked (the latter carries a client-safety warning)."""
    if not boot_view or boot_view.get("phase") != "ACQUIRING" or base["code"] in ("GPS_PPS", "UNSYNCHRONIZED"):
        return base
    since = _val(boot_view.get("since_boot_s"))
    mins = boot_view["acquire_window_s"] / 60
    detail = (f"Booted {round(since / 60) if since is not None else '?'} min ago; PPS not yet selected. "
              f"An outage is recorded if PPS is not selected within {mins:g} min of boot. "
              f"Now: {base['banner']}" + (f" — {base['detail']}" if base["detail"] else ""))
    return {"code": "ACQUIRING", "headline": "ACQUIRING", "banner": "ACQUIRING · PPS NOT YET SELECTED SINCE BOOT",
            "detail": detail, "source": base["source"], "gnss_healthy": base["gnss_healthy"],
            "provenance": "calculated", "underlying": base}


# ── PPS state machine ───────────────────────────────────────────────────────

PPS_STATES = ("UNKNOWN", "DEVICE_MISSING", "DEVICE_PRESENT_NO_EVENTS", "EVENTS_PRESENT",
              "CHRONY_VISIBLE", "CHRONY_REJECTED", "CHRONY_ACCEPTED", "SELECTED", "LOST", "RECOVERING")


class PPSStateMachine:
    """Combines kernel pulse health with chrony's view of the PPS refclock.
    LOST needs history (pulses seen before); RECOVERING lasts from the return
    of pulses after LOST until chrony selects PPS again."""

    def __init__(self):
        self.state = "UNKNOWN"
        self.recovering = False

    def update(self, pulse_health, chrony_pps_status):
        if pulse_health == "UNKNOWN":
            # kernel side not observable; chrony's own selection is still evidence
            s = "SELECTED" if chrony_pps_status == "SELECTED" else "UNKNOWN"
            if s == "SELECTED":
                self.recovering = False
        elif pulse_health == "MISSING":
            s = "DEVICE_MISSING"
        elif pulse_health == "NO_EVENTS":
            s = "DEVICE_PRESENT_NO_EVENTS"
        elif pulse_health == "LOST":
            s = "LOST"
            self.recovering = True
        elif chrony_pps_status == "SELECTED":
            s = "SELECTED"
            self.recovering = False
        elif self.recovering:
            s = "RECOVERING"
        else:
            s = {"ACCEPTED": "CHRONY_ACCEPTED", "REJECTED": "CHRONY_REJECTED",
                 "VISIBLE_NO_SAMPLES": "CHRONY_VISIBLE"}.get(chrony_pps_status, "EVENTS_PRESENT")
        self.state = s
        return s


# ── classification ──────────────────────────────────────────────────────────

def classify(pulse_health, gnss, chrony_v):
    """Evidence-based classification of a PPS problem. Returns dict with
    classification, confidence, boundary and notes. Never names a cause."""
    present = pulse_health in ("HEALTHY", "DEGRADED")
    absent = pulse_health in ("LOST", "NO_EVENTS")
    lock = (chrony_v.get("refclocks") or {}).get("pps_lock")
    nmea_name = (chrony_v.get("refclocks") or {}).get("nmea")
    if pulse_health == "MISSING":
        return {"classification": "PPS DEVICE MISSING", "confidence": "high",
                "boundary": "kernel PPS device (/dev/pps*) not present",
                "notes": ["No PPS device exists; check the pps-gpio overlay and boot configuration."]}
    if absent and gnss["healthy"] is True:
        return {"classification": "PPS PATH ANOMALY", "confidence": "moderate",
                "boundary": "receiver PPS output / GPIO / kernel PPS interface",
                "notes": ["GNSS reception and navigation remained healthy while kernel PPS events stopped.",
                          "Evidence does not establish which component in that path failed."]}
    if absent and gnss["healthy"] is False and gnss["receiver_comms"] == "OK":
        return {"classification": "GNSS RECEPTION ANOMALY", "confidence": "low",
                "boundary": "GNSS reception / receiver solution",
                "notes": ["Satellite reception or the navigation solution failed together with PPS.",
                          "Evidence does not establish a cause."]}
    if absent:
        return {"classification": "PPS AND GNSS TELEMETRY UNAVAILABLE", "confidence": "low",
                "boundary": "unknown", "notes": ["Neither kernel PPS events nor fresh GNSS telemetry are available."]}
    if present and chrony_v.get("pps_status") == "UNKNOWN":
        return {"classification": "UNKNOWN", "confidence": None, "boundary": "unknown",
                "notes": ["Kernel PPS events are present, but chrony's source list is unavailable, "
                          "so whether chrony uses PPS cannot be determined."]}
    if present and chrony_v.get("pps_status") != "SELECTED":
        notes = []
        pps = chrony_v.get("pps") or {}
        if pps.get("state_symbol"):
            notes.append(f"chrony shows the PPS refclock with state '{_val(pps['state_symbol'])}': {pps.get('state_meaning')}.")
        evidence = {}
        if lock and lock == nmea_name and chrony_v.get("nmea_status") == "STALE":
            evidence["lock_reference_stale"] = True
            notes.append(f"The PPS refclock is configured with 'lock {lock}', and refclock {lock} "
                         "currently has no recent samples.")
        return {"classification": "PPS NOT USED BY CHRONY", "confidence": "moderate",
                "boundary": "chrony source selection", "notes": notes, "evidence": evidence}
    return {"classification": "UNKNOWN", "confidence": "low", "boundary": "unknown", "notes": []}


# ── chain assembly ──────────────────────────────────────────────────────────

def _stage(sid, label, status, summary, **evidence):
    return {"id": sid, "label": label, "status": status, "summary": summary, "evidence": evidence}


def build_chain(pps_snap, pps_state, gnss, chrony_v, status, events=None, now=None, boot=None):
    now = time.time() if now is None else now
    ph = pps_snap["pulse_health"]
    cv = chrony_v
    pps_d = cv.get("pps") or {}
    nmea_d = cv.get("nmea") or {}
    open_ev = (events or {}).get("open")
    stage_status = {"OK": "OK", "DEGRADED": "DEGRADED", "FAILED": "FAILED", "UNKNOWN": "UNKNOWN"}
    pulse_stage = {"HEALTHY": "OK", "DEGRADED": "DEGRADED", "LOST": "FAILED", "NO_EVENTS": "FAILED",
                   "MISSING": "NOT_APPLICABLE", "UNKNOWN": "UNKNOWN"}[ph]
    pps_cs = cv["pps_status"]
    stages = [
        _stage("receiver_comms", "GNSS receiver communication", stage_status[gnss["receiver_comms"]],
               "gpsd reports from the receiver", data_age_s=gnss["data_age_s"]),
        _stage("satellite_reception", "Satellite reception", stage_status[gnss["satellite_reception"]],
               "satellites tracked and used", used=gnss["satellites_used"], visible=gnss["satellites_visible"],
               best_cn0=gnss["best_cn0"], median_cn0_used=gnss["median_cn0_used"], tdop=gnss["tdop"]),
        _stage("nav_time_solution", "Navigation / time solution", stage_status[gnss["nav_time_solution"]],
               "receiver fix type", fix=gnss["fix"]),
        _stage("receiver_pps_output", "Receiver PPS output", "NOT_OBSERVABLE",
               "not directly observable by software; a HAT LED is not measured"),
        _stage("pps_device", "Linux PPS device",
               "UNKNOWN" if ph == "UNKNOWN" else ("FAILED" if ph == "MISSING" else "OK"),
               pps_snap.get("note") or "kernel PPS device", device=pps_snap["device"],
               present=pps_snap["device_present"], metadata=pps_snap["metadata"],
               boot_config=pps_snap.get("boot_config")),
        _stage("kernel_events", "Kernel PPS events", pulse_stage, f"pulse health {ph}",
               last_event_utc=pps_snap["last_event_utc"], age_s=pps_snap["age_s"],
               rate_hz=pps_snap["rate_hz"], consecutive=pps_snap["consecutive_pulses"],
               missed=pps_snap["missed_pulses"], interval_stats=pps_snap["interval_stats"],
               measurement_layer=pps_snap["measurement_layer"]),
        _stage("nmea_refclock", "chrony NMEA/serial refclock",
               {"OK": "OK", "STALE": "FAILED", "NOT_VISIBLE": "FAILED", "NOT_CONFIGURED": "NOT_APPLICABLE",
                "UNKNOWN": "UNKNOWN"}[cv["nmea_status"]],
               f"refclock {cv['refclocks']['nmea'] or '—'}: {cv['nmea_status']}", source=nmea_d or None),
        _stage("chrony_pps_visible", "chrony PPS source visible",
               "UNKNOWN" if pps_cs == "UNKNOWN" else ("NOT_APPLICABLE" if pps_cs == "NOT_CONFIGURED" else
                                                      "FAILED" if pps_cs == "NOT_VISIBLE" else "OK"),
               f"refclock {cv['refclocks']['pps'] or '—'}", source=pps_d or None),
        _stage("chrony_pps_accepted", "chrony PPS accepted",
               "UNKNOWN" if pps_cs == "UNKNOWN" else ("OK" if pps_cs in ("ACCEPTED", "SELECTED") else
                                                      "NOT_APPLICABLE" if pps_cs == "NOT_CONFIGURED" else "FAILED"),
               pps_d.get("state_meaning") or pps_cs),
        _stage("chrony_pps_selected", "chrony PPS selected",
               "UNKNOWN" if pps_cs == "UNKNOWN" else ("OK" if pps_cs == "SELECTED" else
                                                      "NOT_APPLICABLE" if pps_cs == "NOT_CONFIGURED" else "FAILED"),
               "PPS is the source disciplining the clock" if pps_cs == "SELECTED" else "PPS not selected"),
        _stage("system_sync", "System clock synchronization",
               {"GPS_PPS": "OK", "GNSS_NMEA": "OK", "REFCLOCK": "OK", "UNKNOWN": "UNKNOWN",
                "SOURCE_UNKNOWN": "UNKNOWN", "UNSYNCHRONIZED": "FAILED",
                "ACQUIRING": "INFO"}.get(status["code"], "DEGRADED"),
               status["banner"], tracking=cv.get("tracking")),
        _stage("fallback_source", "Fallback source",
               "FAILED" if (cv.get("selected") or {}).get("is_self") else
               "INFO" if (status["source"] and not (cv.get("selected") or {}).get("is_pps")) else "NOT_APPLICABLE",
               (f"{cv['selected']['name']} is this station's own address, not an external source"
                if (cv.get("selected") or {}).get("is_self") else
                f"{status['source']['name']} ({status['source']['kind']})" if status["source"]
                and not (cv.get("selected") or {}).get("is_pps") else "not in use")
               + (f"; chrony also lists this station's own address as a source: {', '.join(cv['self_sources'])}"
                  if cv.get("self_sources") and not (cv.get("selected") or {}).get("is_self") else ""),
               source=status["source"], self_sources=cv.get("self_sources") or []),
        _stage("failover_duration", "PPS unavailable/unused for", "INFO" if open_ev else "NOT_APPLICABLE",
               "open PPS outage event" if open_ev else "no open PPS outage",
               duration_s=q(round(now - open_ev["start_epoch"]) if open_ev else None, "s", "calculated"),
               since_utc=open_ev["start_utc"] if open_ev else None),
    ]
    return {
        "schema": "gps-time.timing-chain/1",
        "generated_utc": _iso(now),
        "status": status,
        "pps_state": q(pps_state, None, "calculated"),
        "pps": pps_snap,
        "gnss": gnss,
        "chrony": cv,
        "classification": classify(ph, gnss, cv) if pps_state != "SELECTED" else None,
        "stages": stages,
        "events": events or {"open": None, "recent": []},
        "boot": boot,
    }


# ── events ──────────────────────────────────────────────────────────────────

def read_boot(uptime_path="/proc/uptime", boot_id_path="/proc/sys/kernel/random/boot_id", clock=time.time):
    """(boot_epoch, boot_id) of the running Linux boot, or (None, None) if unavailable."""
    try:
        with open(uptime_path) as f:
            uptime = float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None, None
    try:
        with open(boot_id_path) as f:
            boot_id = f.read().strip() or None
    except OSError:
        boot_id = None
    return clock() - uptime, boot_id


class EventTracker:
    """One PPS_OUTAGE event per outage, closed when chrony selects PPS again.

    Boot rule: until PPS is first selected after a boot, the station is
    ACQUIRING, not in an outage. If PPS is not selected within ACQUIRE_WINDOW_S
    of boot, one outage opens, backdated to boot time. The rule applies only
    when observation started inside that window (otherwise nothing is known
    about the time before the service started). After PPS has been selected in
    this boot, a loss opens an outage once PPS has been unselected for
    OUTAGE_DEBOUNCE_S.

    A small checkpoint file lets an open outage, and the fact that PPS was
    selected in the current boot, survive service restarts. It is written only
    on open/close/classification change, on the first PPS selection of a boot,
    and at most every CHECKPOINT_REFRESH_S while open (no 1 Hz writes)."""

    def __init__(self, path=None, clock=time.time, debounce_s=None, boot=None, acquire_window_s=None):
        self.path = path
        self.clock = clock
        self.debounce_s = OUTAGE_DEBOUNCE_S if debounce_s is None else debounce_s
        self.acquire_window_s = ACQUIRE_WINDOW_S if acquire_window_s is None else acquire_window_s
        self.started = clock()
        self.boot_epoch, self.boot_id = boot if boot else (None, None)
        self.boot_rule = self.boot_epoch is not None and \
            (self.started - self.boot_epoch) < self.acquire_window_s
        self.selected_this_boot = False
        self.open = None
        self.recent = []
        self._bad_since = None
        self._last_checkpoint = None
        self._resumed = False
        self._load()

    def phase(self, now=None):
        """'ACQUIRING' until PPS is first selected after boot (within the window), else 'RUN'."""
        now = self.clock() if now is None else now
        if self.boot_rule and not self.selected_this_boot and self.open is None \
                and now - self.boot_epoch < self.acquire_window_s:
            return "ACQUIRING"
        return "RUN"

    def boot_view(self, now=None):
        now = self.clock() if now is None else now
        return {"phase": self.phase(now),
                "boot_utc": _iso(self.boot_epoch), "boot_id_known": self.boot_id is not None,
                "since_boot_s": q(round(now - self.boot_epoch) if self.boot_epoch else None, "s", "calculated"),
                "acquire_window_s": self.acquire_window_s,
                "acquire_deadline_utc": _iso(self.boot_epoch + self.acquire_window_s) if self.boot_epoch else None,
                "boot_rule_applies": self.boot_rule,
                "pps_selected_this_boot": self.selected_this_boot}

    # persistence
    def _load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            os.replace(self.path, f"{self.path}.corrupt-{int(self.clock())}")
            return
        self.recent = data.get("recent", [])[-RECENT_EVENTS_MAX:]
        self.open = data.get("open")
        boot = data.get("boot") or {}
        if self.boot_id and boot.get("id") == self.boot_id and boot.get("pps_selected"):
            self.selected_this_boot = True
        if self.open:
            self._resumed = True
            self.open.setdefault("restarts", []).append(
                {"last_checkpoint_utc": self.open.get("last_checkpoint_utc"), "resumed_utc": _iso(self.clock())})

    def _checkpoint(self):
        if not self.path:
            return
        now = self.clock()
        if self.open:
            self.open["last_checkpoint_utc"] = _iso(now)
            self.open["last_checkpoint_epoch"] = now
        data = {"schema": "gps-time.events-checkpoint/1", "written_utc": _iso(now),
                "boot": {"id": self.boot_id, "pps_selected": self.selected_this_boot},
                "open": self.open, "recent": self.recent[-RECENT_EVENTS_MAX:]}
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".events-", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # evaluation
    def update(self, chain):
        now = self.clock()
        pps_state = _val(chain["pps_state"])
        if chain["chrony"]["pps_status"] == "UNKNOWN" and pps_state in ("UNKNOWN", "EVENTS_PRESENT"):
            return   # cannot tell whether PPS is in use: neither open nor close an outage
        if pps_state == "SELECTED":
            first_this_boot = not self.selected_this_boot
            self.selected_this_boot = True
            self._bad_since = None
            if self.open:
                self._close(now, chain)          # checkpoint includes the boot flag
            elif first_this_boot and self.boot_id:
                self._checkpoint()               # one write per boot
            self._resumed = False
            return
        if self.open:
            self._accumulate(now, chain)
            return
        if self.boot_rule and not self.selected_this_boot:
            if now - self.boot_epoch < self.acquire_window_s:
                return                           # ACQUIRING, not an outage
            self._open(self.boot_epoch, now, chain, start_bound="boot")
            return
        if self._bad_since is None:
            self._bad_since = now
        if now - self._bad_since >= self.debounce_s:
            self._open(self._bad_since, now, chain)

    def _evidence_snapshot(self, chain):
        g, cv = chain["gnss"], chain["chrony"]
        return {"pps_state": _val(chain["pps_state"]), "pulse_health": chain["pps"]["pulse_health"],
                "gnss_healthy": g["healthy"], "satellites_used": _val(g["satellites_used"]),
                "best_cn0": _val(g["best_cn0"]), "chrony_pps_status": cv["pps_status"],
                "nmea_status": cv["nmea_status"], "selected_source": (cv.get("selected") or {}).get("name"),
                "status_code": chain["status"]["code"]}

    def _open(self, start, now, chain, start_bound=None):
        c = chain.get("classification") or {}
        ev = {"schema": "gps-time.event/1", "id": f"pps-outage-{int(start)}", "type": "PPS_OUTAGE",
              "start_epoch": start, "start_utc": _iso(start), "end_utc": None, "duration_s": None,
              "open": True, "severity": "critical" if chain["pps"]["pulse_health"] in ("LOST", "NO_EVENTS", "MISSING") else "warning",
              "classification": c.get("classification", "UNKNOWN"),
              "initial_classification": c.get("classification", "UNKNOWN"),
              "confidence": c.get("confidence"), "boundary": c.get("boundary"),
              "classification_provenance": "inferred",
              "evidence": {"at_start": self._evidence_snapshot(chain), "latest": None,
                           "satellites_used_range": None, "fallback_sources": [],
                           "max_abs_system_time_s": None, "gnss_unhealthy_seen": False},
              "recovery": None, "notes": list(c.get("notes", []))}
        if start_bound == "boot":
            ev["start_bound"] = "boot"
            ev["notes"].insert(0, f"PPS was not selected within {self.acquire_window_s / 60:g} min "
                                  "of boot; the outage is backdated to boot time.")
        elif start <= self.started + 1:
            ev["start_bound"] = "service_start"
            ev["notes"].insert(0, "PPS was already not selected when the service started; "
                                  "the true start is at or before this time.")
        self.open = ev
        self._accumulate(now, chain, force_checkpoint=True)

    def _accumulate(self, now, chain, force_checkpoint=False):
        ev = self.open
        e = ev["evidence"]
        snap = self._evidence_snapshot(chain)
        e["latest"] = snap
        used = snap["satellites_used"]
        if used is not None:
            lo, hi = (e["satellites_used_range"] or [used, used])
            e["satellites_used_range"] = [min(lo, used), max(hi, used)]
        sel = snap["selected_source"]
        sel_is_pps = (chain["chrony"].get("selected") or {}).get("is_pps")
        sel_is_self = (chain["chrony"].get("selected") or {}).get("is_self")
        if sel and not sel_is_pps and not sel_is_self and sel not in e["fallback_sources"]:
            e["fallback_sources"].append(sel)     # the station's own address is not a fallback
        st = _val(((chain["chrony"].get("tracking") or {}).get("system_time_s")))
        if st is not None:
            e["max_abs_system_time_s"] = max(abs(st), e["max_abs_system_time_s"] or 0.0)
        if chain["gnss"]["healthy"] is False:
            e["gnss_unhealthy_seen"] = True
        ph = chain["pps"]["pulse_health"]
        if ph in ("HEALTHY", "DEGRADED") and ev.get("pulses_returned_epoch") is None and \
                ev["evidence"]["at_start"]["pulse_health"] not in ("HEALTHY", "DEGRADED"):
            ev["pulses_returned_epoch"] = now
        pulses_ok_since_start = ev["evidence"]["at_start"]["pulse_health"] in ("HEALTHY", "DEGRADED")
        if chain["chrony"]["pps_status"] in ("ACCEPTED", "SELECTED") and ev.get("accepted_epoch") is None                 and ph in ("HEALTHY", "DEGRADED") and (pulses_ok_since_start or ev.get("pulses_returned_epoch")):
            ev["accepted_epoch"] = now
        c = chain.get("classification") or {}
        changed = c.get("classification") and c["classification"] != ev["classification"]
        if changed:
            ev["classification"], ev["confidence"], ev["boundary"] = c["classification"], c.get("confidence"), c.get("boundary")
            ev["notes"] = list(c.get("notes", []))
        ev["duration_s"] = round(now - ev["start_epoch"])
        if force_checkpoint or changed or self._last_checkpoint is None or \
                now - self._last_checkpoint >= CHECKPOINT_REFRESH_S:
            self._checkpoint()
            self._last_checkpoint = now

    def _close(self, now, chain):
        ev = self.open
        self._accumulate(now, chain)
        ev["open"] = False
        ev["end_utc"] = _iso(now)
        ev["duration_s"] = round(now - ev["start_epoch"])
        returned = ev.get("pulses_returned_epoch")
        rec = {"recovered_utc": _iso(now),
               "duration_s": q(ev["duration_s"], "s", "calculated"),
               "time_to_accept_s": q(round(ev["accepted_epoch"] - returned, 1)
                                     if (returned and ev.get("accepted_epoch")) else None, "s", "calculated"),
               "time_to_select_s": q(round(now - returned, 1) if returned else None, "s", "calculated"),
               "fallback_sources": ev["evidence"]["fallback_sources"],
               "max_abs_system_time_s": q(ev["evidence"]["max_abs_system_time_s"], "s", "observed",
                                          "largest chrony remaining-correction seen; chrony estimate, "
                                          "not an independent error measurement")}
        if self._resumed:
            last = (ev.get("restarts") or [{}])[-1].get("last_checkpoint_utc")
            rec["end_bounds_utc"] = [last, _iso(now)]
            rec["note"] = ("Recovery observed after a service restart; PPS was re-selected at some "
                           "time between the last checkpoint and this observation.")
        ev["recovery"] = rec
        self.recent.append(ev)
        self.recent = self.recent[-RECENT_EVENTS_MAX:]
        self.open = None
        self._checkpoint()

    def view(self):
        return {"open": self.open, "recent": list(reversed(self.recent[-10:]))}


# ── service ─────────────────────────────────────────────────────────────────

def read_chrony_inputs():
    out = {}
    for name in ("tracking", "sources", "sourcestats"):
        ok, text = chrony.run_chronyc(name)
        out[f"{name}_ok"], out[f"{name}_text"] = ok, text
    return out


def default_events_path():
    configured = os.environ.get("GTP_EVENTS_PATH")
    if configured:
        return configured
    cfg = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return os.path.join(os.path.dirname(os.path.abspath(cfg)), "timing-events.json")


class TimingChainService:
    """1 Hz PPS poll + 5 s chrony poll + chain evaluation, independent of HTTP."""

    def __init__(self, monitor=None, tracker=None, chrony_reader=read_chrony_inputs,
                 gnss_reader=None, refclock_reader=chrony.refclock_config,
                 boot_config_reader=None, clock=time.time):
        from . import gps, pps
        self.monitor = monitor or PPSMonitor()
        self.tracker = tracker if tracker is not None else EventTracker(default_events_path(), boot=read_boot())
        self.chrony_reader = chrony_reader
        self.gnss_reader = gnss_reader or gps.snapshot
        self.refclock_reader = refclock_reader
        self.boot_config_reader = boot_config_reader or pps.boot_pps_config
        self.clock = clock
        self.sm = PPSStateMachine()
        self.stability = stability.Recorder(clock=clock)   # RAM-only phase history for /api/stability
        self._chrony_inputs, self._chrony_at = None, None
        self._refcfg = None
        self._boot = None
        self._latest = None
        self._lock = threading.Lock()
        self._thread, self._stop = None, None

    def tick(self, refresh_chrony=None):
        now = self.clock()
        self.monitor.poll()
        if refresh_chrony or self._chrony_inputs is None or \
                (refresh_chrony is None and now - (self._chrony_at or 0) >= CHRONY_INTERVAL_S):
            self._chrony_inputs, self._chrony_at = self.chrony_reader(), now
            self._refcfg = self.refclock_reader()
            if self._boot is None:
                self._boot = self.boot_config_reader()
        pps_snap = self.monitor.snapshot()
        pps_snap["boot_config"] = self._boot
        gnss = gnss_summary(self.gnss_reader())
        cv = chrony_view(self._chrony_inputs, self._refcfg)
        pps_state = self.sm.update(pps_snap["pulse_health"], cv["pps_status"])
        ci = self._chrony_inputs
        trk = chrony.parse_tracking(ci.get("tracking_text")) if ci.get("tracking_ok") else {}
        rows = chrony.parse_sources(ci.get("sources_text")) if ci.get("sources_ok") else []
        status = timing_status(trk, rows, gnss=gnss, refclocks=self._refcfg)
        chain = build_chain(pps_snap, pps_state, gnss, cv, status, now=now)
        self.tracker.update(chain)
        boot = self.tracker.boot_view(now)
        status = acquiring_status(status, boot)
        chain = build_chain(pps_snap, pps_state, gnss, cv, status, events=self.tracker.view(), now=now, boot=boot)
        chain["raw"] = {k: self._chrony_inputs.get(f"{k}_text") if self._chrony_inputs.get(f"{k}_ok") else None
                        for k in ("tracking", "sources", "sourcestats")}
        last = self.monitor.last_event()
        if last is not None:
            # One phase sample per kernel PPS event; the recorder ignores a repeat.
            self.stability.add(last[1], status.get("code") == "GPS_PPS")
        with self._lock:
            self._latest = chain
        return chain

    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def apply_boot_phase(self, status):
        """Apply the boot-phase overlay to a banner computed elsewhere (/api)."""
        return acquiring_status(status, self.tracker.boot_view())

    def latest(self):
        with self._lock:
            chain = self._latest
        return chain if chain is not None else self.tick()

    def _loop(self, stop, interval):
        while not stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — observability must never take the server down
                pass
            stop.wait(next_tick_delay(self.clock(), interval))

    def start(self, interval=1.0):
        if self._thread and self._thread.is_alive():
            return self._thread
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, args=(self._stop, interval),
                                        name="timing-chain", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self, timeout=5.0):
        if self._stop:
            self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        self._thread = self._stop = None


TICK_PHASE_S = 0.25


def next_tick_delay(now, interval=1.0, phase=TICK_PHASE_S):
    """Seconds until the next poll, on a fixed grid `phase` after each whole
    interval of the clock. Sleeping a fixed interval after each tick would make
    the period interval + the tick's own duration, so the poll would drift
    across the PPS edge and skip a pulse every so often. With the clock on PPS
    the pulse lands on the second, and a poll 0.25 s later sees each one once."""
    return interval - ((now - phase) % interval)


SERVICE = None


def service():
    global SERVICE
    if SERVICE is None:
        SERVICE = TimingChainService()
    return SERVICE


# ── diagnostic snapshot ─────────────────────────────────────────────────────

def _fmt(x, unit=""):
    v = _val(x)
    if v is None:
        return "UNKNOWN"
    if isinstance(v, float):
        return f"{v:.6g}{(' ' + unit) if unit else ''}"
    return f"{v}{(' ' + unit) if unit else ''}"


def _dur(s):
    if s is None:
        return "—"
    s = int(s)
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m, sec = divmod(r, 60)
    return (f"{d}d " if d else "") + f"{h:02d}h {m:02d}m {sec:02d}s"


def diagnostic_snapshot(chain, location):
    """Plain-text, copyable snapshot. `location` must already have the privacy
    mode applied (config.displayed_location); nothing else here carries position."""
    g, cv, p = chain["gnss"], chain["chrony"], chain["pps"]
    sel = cv.get("selected") or {}
    open_ev = chain["events"].get("open")
    lines = [
        "GPS TIME PI DIAGNOSTIC SNAPSHOT",
        f"Generated: {chain['generated_utc']}",
        "",
        f"STATUS: {chain['status']['banner']}",
        f"  {chain['status']['detail']}",
        f"PPS state: {_val(chain['pps_state'])}",
        "",
        "GNSS:",
        f"  Receiver communication: {g['receiver_comms']}",
        f"  Satellite reception: {g['satellite_reception']}",
        f"  Navigation/time solution: {g['nav_time_solution']}",
        f"  Fix: {_fmt(g['fix'])}",
        f"  Satellites visible: {_fmt(g['satellites_visible'])}",
        f"  Satellites used: {_fmt(g['satellites_used'])}",
        f"  TDOP: {_fmt(g['tdop'])}",
        f"  Best C/N0: {_fmt(g['best_cn0'], 'dB-Hz')}",
        "",
        "PPS (Linux kernel observation):",
        f"  Device: {_fmt(p['device'])}",
        f"  Device present: {_fmt(p['device_present'])}",
        f"  Pulse health: {p['pulse_health']}",
        f"  Last event: {_fmt(p['last_event_utc'])}",
        f"  Age: {_fmt(p['age_s'], 's')}",
        f"  Rate: {_fmt(p['rate_hz'], 'Hz')}",
        f"  Missed pulses: {_fmt(p['missed_pulses'])}",
        f"  Configured GPIO: {(p.get('boot_config') or {}).get('gpio', 'UNKNOWN')}",
        "",
        "CHRONY:",
        f"  PPS refclock: {cv['refclocks']['pps'] or 'none'} ({cv['refclocks']['identified_from']})",
        f"  PPS source status: {cv['pps_status']}",
        f"  NMEA refclock: {cv['refclocks']['nmea'] or 'none'} — {cv['nmea_status']}",
        f"  PPS lock reference: {cv['refclocks']['pps_lock'] or 'none'}",
        "  NMEA offset: " + _nmea_cal_line(cv.get("nmea_calibration")),
        f"  Selected source: {sel.get('name', 'none')}",
        f"  System stratum: {(cv.get('tracking') or {}).get('stratum', 'UNKNOWN')}",
        "",
        "SYSTEM:",
        f"  Timing mode: {chain['status']['code']}",
        f"  PPS unavailable/unused for: {_dur(open_ev['duration_s']) if open_ev else '—'}",
        "",
        "LOCATION:",
        ("  Hidden (privacy mode)" if location.get("mode") == "hidden" or location.get("lat") is None else
         f"  {location['lat']}, {location['lon']} ({location.get('mode')})"),
        "",
        "RECENT EVENTS:",
    ]
    evs = ([open_ev] if open_ev else []) + chain["events"].get("recent", [])
    if not evs:
        lines.append("  none")
    for ev in evs:
        lines.append(f"  {ev['type']} {ev['start_utc']} → {ev['end_utc'] or 'OPEN'} "
                     f"({_dur(ev['duration_s'])}) {ev['classification']} [confidence {ev.get('confidence')}]")
    raw = chain.get("raw") or {}
    for name in ("tracking", "sources", "sourcestats"):
        lines += ["", f"RAW chronyc -n {name} (observed):", raw.get(name) or "  unavailable"]
    return "\n".join(lines) + "\n"
