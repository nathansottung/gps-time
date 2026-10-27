"""Measured against predicted tower delays (Analysis interface). Pure apart from reading captures.

Inputs (the window):
  - captures: marker-timed captures (capture.Capture) at site a; a tower is looked for in the
    capture whose passband holds most of its band (a 2.4 MS/s SDR sees one ATSC channel, or a
    few FM stations, per tuning);
  - predictions: reference-broadcast-towers' observations for site a (transmitter, frequency_hz,
    delay_s, uncertainty_s), as dicts;
  - emissions: per tower, the waveform ({"kind": "atsc_field_sync"} or {"kind": "fm_reference",
    "offset_s", "duration_s"}) and, in the single-site modes, "emission_utc_ns": the nominal UTC
    instant the field sync's first symbol left the antenna;
  - TDOA modes only: captures_b and predictions_b, for site b.

Finding a waveform: complex cross-correlation (numpy) with the template made for that
capture's rate and tuning, the peak refined by band-limited (windowed-sinc) interpolation of the
complex correlation, and
a detection threshold: the peak's power over the median power away from the peak's main lobe
must be at least min_snr. Not detected: verdict UNKNOWN, nothing else claimed. The 1-sigma of
an arrival: the correlator's (Cramér-Rao, 1 / (RMS bandwidth × √SNR), floored at 0.02 sample),
the capture's sample-time uncertainty, and the prediction's (95 % bound / 1.96).

Four modes:
  - "absolute" (ATSC; emission times known, e.g. a time-locked test signal): each residual
    (measured − predicted delay) on its own; the capture's clock bound (as 95 %) is added.
  - "common_offset" (ATSC): the towers' emission times are known up to one shared offset; it
    is estimated (a weighted median with three or more towers, the weighted mean with two) and
    removed, then each tower is tested on what is left, and the set by chi-square.
  - "tdoa": two sites receive the same broadcasts; the emission time cancels. Per tower:
    measured (arrival at b − arrival at a) against predicted (delay to b − delay to a). ATSC:
    the field sync is found in both captures. FM: a segment of a's capture, isolated to
    ±100 kHz around the station, is the template found in b's capture ("FM correlation"). Both
    clocks are trusted to their bounds.
  - "tdoa_common_offset": as tdoa, with b's clock offset against a's (and any difference of the
    receivers' filter delays) estimated across the towers and removed: the reference-transmitter
    method of SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.

Real broadcasts: a licence record doesn't say when a field sync leaves the antenna, and ATSC
stations aren't required to align fields to UTC, so the single-site modes need emission times
from elsewhere; TDOA needs none. The prediction bounds of one tower at two sites are added as if
independent (they share the tower's position error): conservative.

Verdicts are `inferred` and say only agree / disagree / unknown (|z| ≤ z_max agrees): a
disagreement names no cause (multipath, a wrong record, a non-line-of-sight path, a timing
fault all look alike here).
"""

import math

import numpy as np

from gps_time_pi.modkit import Analysis, Result

from .waveform import AtscFieldSync, FmReference, from_spec, mainlobe_samples, rms_bandwidth

NAME = "analysis-tower-delay-check"
METHOD = ("complex cross-correlation with a known waveform (ATSC field sync) or a reference capture (FM), "
          "parabolic peak; arrival from the PPS-marker timing; compared with reference-broadcast-towers' prediction")
MODES = ("absolute", "common_offset", "tdoa", "tdoa_common_offset")
DEFAULTS = {"mode": "common_offset", "search_s": 20e-6, "floor_s": 200e-6, "min_snr": 25.0, "z_max": 3.0}
INTERP_FLOOR_SAMPLES = 0.02
HALF_BW = {"atsc_field_sync": 3e6, "fm_reference": 100e3}
MIN_COVER = {"atsc_field_sync": 1e6, "fm_reference": 150e3}


def _lv(value, unit, prov, note=None):
    d = {"value": value, "unit": unit, "provenance": prov}
    if note:
        d["note"] = note
    return d


def correlate(samples, template, lo, hi):
    """|correlation|² for template starts lo..hi-1, and the complex values (template conjugated)."""
    m = len(template)
    seg = samples[lo:hi + m - 1]
    c = np.correlate(seg, template, "valid")
    return np.abs(c) ** 2, c


def find_peak(power):
    """(index of the peak, fractional refinement in −0.5..0.5) by a parabola through three points."""
    power = np.asarray(power, dtype=float)
    k = int(np.argmax(power))
    if 0 < k < len(power) - 1:
        a, b, c = np.sqrt(power[k - 1:k + 2])
        den = a - 2 * b + c
        frac = 0.5 * (a - c) / den if den != 0 else 0.0
        return k, float(max(-0.5, min(0.5, frac)))
    return k, 0.0


def refine_peak(c, k, half_taps=16, step=0.002):
    """Sub-sample position of |c|'s peak near integer index k: the complex correlation is
    band-limited, so it is interpolated with a windowed sinc on a fine grid (−1..1 sample).
    A parabola through three points is biased by up to ~0.1 sample at these bandwidths."""
    c = np.asarray(c, dtype=complex)
    d = np.arange(-1.0, 1.0 + step / 2, step)
    p = k + d
    base = np.floor(p).astype(np.int64)
    v = np.zeros(len(p), dtype=complex)
    for j in range(-half_taps + 1, half_taps + 1):
        idx = base + j
        x = p - idx
        w = np.sinc(x) * (0.5 + 0.5 * np.cos(np.pi * x / half_taps))
        ok = (idx >= 0) & (idx < len(c))
        v[ok] += w[ok] * c[idx[ok]]
    i = int(np.argmax(np.abs(v)))
    return float(d[i])


def measure(cap, tmpl, lead_s, centre=None, search_s=20e-6, floor_s=200e-6, min_snr=25.0, coherence=False):
    """Find the template in a capture: around the fractional index `centre` (±search_s), or over
    the whole timed part when centre is None. A dict: detected, index, arrival_ns (the instant
    lead_s after the template's start), snr, sigma_corr_s; or detected False and a reason.

    coherence: take the correlator's SNR from the normalised correlation at the peak (rho):
    SNR = m·rho²/(1 − rho²), for a template that is itself a noisy capture (FM). Its program
    content correlates with itself away from the peak, so the peak-over-floor ratio (still used
    to decide detection) would understate the SNR the timing actually has."""
    rate, m = cap.rate, len(tmpl)
    if m < 8:
        return {"detected": False, "reason": "the template is too short at this capture's rate"}
    first, last = cap.timed_start, cap.timed_end - m          # template starts that stay in the timed part
    if centre is None:
        plo, phi = first, last + 1
        lo, hi = plo, phi
    else:
        c0 = math.floor(centre)
        s, f = math.ceil(search_s * rate), math.ceil(max(floor_s, search_s) * rate)
        plo, phi = max(first, c0 - s), min(last + 1, c0 + s + 1)
        lo, hi = max(first, c0 - f), min(last + 1, c0 + f + 1)
    if phi - plo < 3:
        return {"detected": False, "reason": "the search window runs off the timed part of the capture"}
    power, cplx = correlate(cap.samples, tmpl, lo, hi)
    k, _ = find_peak(power[plo - lo:phi - lo])
    k += plo - lo
    frac = refine_peak(cplx, k)
    guard = max(2, 3 * mainlobe_samples(tmpl))
    idx = np.arange(len(power))
    rest = power[np.abs(idx - k) > guard]
    floor = float(np.median(rest)) if len(rest) else 0.0
    snr = float(power[k] / floor) if floor > 0 else math.inf
    if snr < min_snr:
        return {"detected": False, "reason": f"no peak above the threshold (SNR {snr:.1f} < {min_snr:g})", "snr": snr}
    index = lo + k + frac
    t = cap.time_ns(index + lead_s * rate)
    if t is None:
        return {"detected": False, "reason": "the peak falls on samples without a time", "snr": snr}
    snr_t = snr
    if coherence:
        start = lo + k
        seg = cap.samples[start:start + m]
        den = math.sqrt(float(np.sum(np.abs(seg) ** 2)) * float(np.sum(np.abs(tmpl) ** 2)))
        rho2 = min(0.999999, float(power[k]) / den ** 2) if den > 0 else 0.0
        snr_t = m * rho2 / (1 - rho2)
    beta = rms_bandwidth(tmpl)
    sig = max(INTERP_FLOOR_SAMPLES, 1.0 / (beta * math.sqrt(snr_t))) if beta > 0 and snr_t > 0 else 1.0
    return {"detected": True, "index": index, "arrival_ns": t, "snr": snr, "sigma_corr_s": sig / rate}


def pick_capture(caps, freq_hz, kind, t_ns=None):
    """The capture holding most of the signal's band (and the instant t_ns, if given), or None."""
    best, cover = None, 0.0
    for c in caps:
        if t_ns is not None and c.index_of(t_ns) is None:
            continue
        v = c.covers(freq_hz, HALF_BW[kind])
        if v > cover:
            best, cover = c, v
    return best if cover >= MIN_COVER[kind] else None


def common_offset(rows):
    """(offset, 1-sigma) shared by the towers' residuals. Three or more: the weighted median, so one
    tower that disagrees can't drag the others with it. Two: the weighted mean (a median of two is
    undefined); a disagreement then can't be pinned on either tower."""
    w = [1 / r["sigma_s"] ** 2 for r in rows]
    sigma = math.sqrt(1 / sum(w))
    if len(rows) == 2:
        return sum(wi * r["residual_s"] for wi, r in zip(w, rows)) / sum(w), sigma
    pairs = sorted(zip((r["residual_s"] for r in rows), w))
    half, acc = sum(w) / 2, 0.0
    for x, wi in pairs:
        acc += wi
        if acc >= half:
            return x, 1.2533 * sigma          # a median's efficiency against the mean
    return pairs[-1][0], 1.2533 * sigma


def _preds(observations):
    out = {}
    for o in observations or []:
        v = o.get("values", o)
        tx = (v.get("transmitter") or {}).get("value")
        if tx and (v.get("delay_s") or {}).get("value") is not None:
            out[tx] = v
    return out


def _u(p):
    return (p["uncertainty_s"]["value"] or 0.0) / 1.96


class TowerDelayCheck(Analysis):
    def __init__(self, config=None):
        self.config = {**DEFAULTS, **(config or {})}

    def handle(self, observation):
        raise NotImplementedError("this analysis runs over a window (captures, predictions, emissions)")

    def _measure(self, cap, wave, centre=None):
        tmpl, lead = wave.template(cap)
        return measure(cap, tmpl, lead, centre, float(self.config["search_s"]), float(self.config["floor_s"]),
                       float(self.config["min_snr"]), coherence=wave.kind == "fm_reference")

    def _single(self, e, p, caps, mode):
        kind = e["waveform"].get("kind")
        if kind != "atsc_field_sync":
            return {"m": {"detected": False, "reason": "FM correlation needs a reference capture: TDOA modes only"}}
        if e.get("emission_utc_ns") is None:
            return {"m": {"detected": False, "reason": "no nominal emission time (single-site modes need one)"}}
        freq, d = p["frequency_hz"]["value"], p["delay_s"]["value"]
        nominal = int(e["emission_utc_ns"]) + round(d * 1e9)
        cap = pick_capture(caps, freq, kind, nominal)
        if cap is None:
            return {"m": {"detected": False, "reason": "no capture holds this channel at the nominal arrival"}}
        wave = from_spec(e["waveform"], freq)
        tmpl, lead = wave.template(cap)
        centre = cap.index_of(nominal - round(lead * 1e9))[0]
        m = self._measure(cap, wave, centre)
        row = {"m": m, "caps": [cap]}
        if m["detected"]:
            row["measured_s"] = (m["arrival_ns"] - int(e["emission_utc_ns"])) / 1e9
            row["residual_s"] = row["measured_s"] - d
            clock = (cap.offset_bound_s or 0.0) / 1.96 if mode == "absolute" else 0.0
            row["sigma_s"] = math.sqrt(m["sigma_corr_s"] ** 2 + (cap.sample_uncertainty_s or 0.0) ** 2
                                       + _u(p) ** 2 + clock ** 2)
        return row

    def _tdoa(self, e, pa, pb, caps_a, caps_b, mode):
        spec = e["waveform"]
        kind = spec.get("kind")
        if kind not in HALF_BW:
            return {"m": {"detected": False, "reason": f"unknown waveform {kind!r}"}}
        freq = pa["frequency_hz"]["value"]
        da, db = pa["delay_s"]["value"], pb["delay_s"]["value"]
        cap_a = pick_capture(caps_a, freq, kind)
        cap_b = pick_capture(caps_b, freq, kind)
        if cap_a is None or cap_b is None:
            return {"m": {"detected": False, "reason": f"no capture at site {'a' if cap_a is None else 'b'} holds this signal"}}
        if kind == "atsc_field_sync":
            wave = AtscFieldSync(freq)
            ma = self._measure(cap_a, wave)                        # the strongest field sync in a's capture
            if not ma["detected"]:
                return {"m": {**ma, "reason": "site a: " + ma["reason"]}, "caps": [cap_a, cap_b]}
            arr_a, sig_a, snr_a = ma["arrival_ns"], ma["sigma_corr_s"], ma["snr"]
        else:
            start = cap_a.timed_start + round(float(spec.get("offset_s", 5e-4)) * cap_a.rate)
            count = round(float(spec.get("duration_s", 2e-3)) * cap_a.rate)
            if start + count > cap_a.timed_end:
                return {"m": {"detected": False, "reason": "site a: the reference segment runs off the capture"}}
            wave = FmReference(freq, cap_a, start, count)
            arr_a, sig_a, snr_a = cap_a.time_ns(start), 0.0, None
        tmpl, lead = wave.template(cap_b)
        hit = cap_b.index_of(arr_a + round((db - da) * 1e9) - round(lead * 1e9))
        if hit is None:
            return {"m": {"detected": False, "reason": "site b: the expected arrival isn't in a timed capture"},
                    "caps": [cap_a, cap_b]}
        mb = self._measure(cap_b, wave, hit[0])
        row = {"m": mb, "caps": [cap_a, cap_b], "arrival_a_ns": arr_a, "snr_a": snr_a}
        if mb["detected"]:
            row["measured_s"] = (mb["arrival_ns"] - arr_a) / 1e9
            row["predicted_tdoa_s"] = db - da
            row["residual_s"] = row["measured_s"] - (db - da)
            mb["sigma_corr_s"] = math.sqrt(mb["sigma_corr_s"] ** 2 + sig_a ** 2)
            clock = (math.hypot(cap_a.offset_bound_s or 0.0, cap_b.offset_bound_s or 0.0) / 1.96
                     if mode == "tdoa" else 0.0)
            row["sigma_s"] = math.sqrt(mb["sigma_corr_s"] ** 2 + (cap_a.sample_uncertainty_s or 0.0) ** 2
                                       + (cap_b.sample_uncertainty_s or 0.0) ** 2 + _u(pa) ** 2 + _u(pb) ** 2
                                       + clock ** 2)
        return row

    def run(self, window):
        """window: {"captures", "predictions", "emissions"} (+ "captures_b", "predictions_b" for the
        TDOA modes; "capture" is accepted for one capture). Returns [Result per emission..., summary]."""
        mode = self.config["mode"]
        if mode not in MODES:
            raise ValueError(f"mode {mode!r}: one of {', '.join(MODES)}")
        tdoa = mode.startswith("tdoa")
        caps_a = list(window.get("captures") or [window["capture"]])
        caps_b = list(window.get("captures_b") or [])
        preds_a, preds_b = _preds(window.get("predictions")), _preds(window.get("predictions_b"))
        rows = []
        for e in window["emissions"]:
            tx = e["transmitter"]
            pa, pb = preds_a.get(tx), preds_b.get(tx)
            if pa is None or (tdoa and pb is None):
                row = {"m": {"detected": False, "reason": f"no prediction for this transmitter{' at site b' if pa else ''}"}}
            elif tdoa:
                row = self._tdoa(e, pa, pb, caps_a, caps_b, mode)
            else:
                row = self._single(e, pa, caps_a, mode)
            row.update(tx=tx, kind=(e.get("waveform") or {}).get("kind"), pred=pa, pred_b=pb,
                       emission_ns=e.get("emission_utc_ns"))
            rows.append(row)

        det = [r for r in rows if "residual_s" in r]
        offset = offset_sigma = chi2 = None
        shared = mode in ("common_offset", "tdoa_common_offset")
        if shared and len(det) >= 2:
            offset, offset_sigma = common_offset(det)
        z_max = float(self.config["z_max"])
        for r in rows:
            r.setdefault("verdict", "unknown")
            r.setdefault("z", None)
            if "residual_s" not in r or (shared and offset is None):
                continue
            r["left_s"] = r["residual_s"] - (offset if shared else 0.0)
            r["z"] = r["left_s"] / r["sigma_s"]
            r["verdict"] = "agree" if abs(r["z"]) <= z_max else "disagree"
        if det and (not shared or offset is not None):
            chi2 = sum(r["z"] ** 2 for r in det)
        dof = (len(det) - 1 if shared else len(det)) if det else 0
        return self._results(window, caps_a + caps_b, rows, det, mode, offset, offset_sigma, chi2, dof)

    def _results(self, window, caps, rows, det, mode, offset, offset_sigma, chi2, dof):
        t_ns = int(window.get("time_ns") or 0)
        tdoa = mode.startswith("tdoa")
        shared = mode in ("common_offset", "tdoa_common_offset")
        inputs = [str(x) for x in (window.get("capture_ids") or []) if x] + [r["tx"] for r in rows]
        out = []
        never = "agree or disagree only; a disagreement names no cause (multipath, a wrong record, an indirect path and a timing fault look alike here)"
        for r in rows:
            m = r["m"]
            vals = {"transmitter": _lv(r["tx"], None, "external", "from reference-broadcast-towers"),
                    "waveform": _lv(r["kind"], None, "calculated",
                                    "ATSC A/53 field sync" if r["kind"] == "atsc_field_sync" else
                                    "FM correlation against site a's capture" if r["kind"] == "fm_reference" else None),
                    "detected": _lv(m["detected"], None, "calculated", m.get("reason")),
                    "verdict": _lv(r["verdict"], None, "inferred", never)}
            unc = {}
            if r["pred"] is not None:
                vals["predicted_delay_s"] = _lv(r["pred"]["delay_s"]["value"], "s", "calculated",
                                                "reference-broadcast-towers" + (", site a" if tdoa else ""))
                unc["predicted_delay_s"] = _lv(r["pred"]["uncertainty_s"]["value"], "s", "calculated", "95 % bound, from the reference")
            if m.get("snr") is not None:
                vals["snr"] = _lv(round(m["snr"], 1), None, "calculated",
                                  "correlation peak power over its median floor" + (", site b" if tdoa else ""))
            if r.get("snr_a") is not None:
                vals["snr_a"] = _lv(round(r["snr_a"], 1), None, "calculated", "site a's field sync")
            if m["detected"]:
                if tdoa:
                    vals["arrival_a_utc_ns"] = _lv(r["arrival_a_ns"], "ns", "calculated", "site a's marker timing")
                    vals["arrival_b_utc_ns"] = _lv(m["arrival_ns"], "ns", "calculated", "site b's marker timing")
                    vals["predicted_tdoa_s"] = _lv(r["predicted_tdoa_s"], "s", "calculated", "delay to b − delay to a")
                    vals["measured_tdoa_s"] = _lv(r["measured_s"], "s", "calculated", "arrival at b − arrival at a")
                    unc["measured_tdoa_s"] = _lv(m["sigma_corr_s"], "s", "calculated", "1-sigma, correlators only")
                else:
                    vals["arrival_utc_ns"] = _lv(m["arrival_ns"], "ns", "calculated", "from the capture's marker timing")
                    vals["measured_delay_s"] = _lv(r["measured_s"], "s", "calculated", "arrival − nominal emission")
                    unc["measured_delay_s"] = _lv(m["sigma_corr_s"], "s", "calculated", "1-sigma, correlator only")
                vals["residual_s"] = _lv(r["residual_s"], "s", "calculated", "measured − predicted")
                unc["residual_s"] = _lv(r["sigma_s"], "s", "calculated", "1-sigma, combined")
                if r.get("z") is not None:
                    vals["residual_after_offset_s" if shared else "residual_tested_s"] = _lv(r["left_s"], "s", "calculated")
                    vals["z"] = _lv(round(r["z"], 3), None, "calculated")
            out.append(Result(time_ns=t_ns, analysis=NAME, values=vals, method=METHOD, inputs=inputs, uncertainty=unc))

        if not det:
            overall, why = "unknown", "no tower detected"
        elif shared and offset is None:
            overall, why = "unknown", "one tower detected: an unknown common offset leaves nothing to compare"
        else:
            bad = sum(1 for r in det if r["verdict"] == "disagree")
            overall, why = ("consistent", None) if bad == 0 else ("inconsistent", f"{bad} of {len(det)} towers disagree")
        notes = {"absolute": "absolute: emission times known",
                 "common_offset": "common_offset: one unknown emission and clock offset shared by the towers, estimated and removed",
                 "tdoa": "tdoa: arrival differences between two sites; emission cancels; both clocks trusted to their bounds",
                 "tdoa_common_offset": "tdoa_common_offset: arrival differences between two sites, with site b's clock offset "
                                       "against a estimated across the towers and removed"}
        bounds = [c.offset_bound_s for c in caps if c.offset_bound_s is not None]
        summ = {
            "mode": _lv(mode, None, "calculated", notes[mode]),
            "towers": _lv(len(rows), None, "calculated"),
            "detected": _lv(len(det), None, "calculated"),
            "overall": _lv(overall, None, "inferred", why or never),
            "chi2": _lv(None if chi2 is None else round(chi2, 3), None, "calculated"),
            "dof": _lv(dof, None, "calculated"),
            "captures": _lv(len(caps), None, "calculated"),
            "blanked_marker_samples": _lv(sum(c.blanked for c in caps), None, "calculated", "PPS marker windows set to zero first"),
            "time_offset_bound_s": _lv(max(bounds) if bounds else None, "s", "observed",
                                       "the largest clock bound of the captures when made"),
        }
        unc = {}
        if shared:
            summ["common_offset_s"] = _lv(offset, "s", "calculated",
                                          "emission timing and station clock together; not separable from one station"
                                          if mode == "common_offset" else
                                          "site b's clock against site a's, with any difference of the receivers' delays")
            unc["common_offset_s"] = _lv(offset_sigma, "s", "calculated", "1-sigma")
        tested = [r["left_s"] for r in det if r.get("left_s") is not None]
        summ["residual_rms_s"] = _lv(math.sqrt(sum(x * x for x in tested) / len(tested)) if tested else None, "s",
                                     "calculated", "after the common offset" if shared else None)
        out.append(Result(time_ns=t_ns, analysis=NAME, values=summ, method=METHOD, inputs=inputs, uncertainty=unc))
        return out
