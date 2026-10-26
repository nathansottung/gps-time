"""Measured against predicted delays (Analysis interface). Pure apart from reading the capture.

Inputs:
  - a marker-timed capture (capture.Capture);
  - predictions: observations from reference-broadcast-towers (values transmitter, delay_s,
    uncertainty_s), as dicts;
  - emissions: what is known about each tower's signal: {"transmitter", "waveform" (see
    waveform.py), "emission_utc_ns"}: the nominal UTC time the waveform left the antenna.

For each emission:
  1. Search ±search_s around the nominal arrival (emission + predicted delay) by complex
     cross-correlation with the waveform's template; refine the peak by a parabola through the
     three highest points of |correlation|.
  2. Detected if the peak's power is at least min_snr times the median power of the correlation
     away from the peak. Not detected: verdict UNKNOWN, nothing else claimed.
  3. Arrival (UTC) from the capture's time of the fractional index; measured delay = arrival −
     emission; residual = measured − predicted.
  4. Its 1-sigma: the correlator's (Cramér-Rao: 1 / (RMS bandwidth × √SNR), floored at 0.02
     sample for the interpolation's bias), the capture's sample-time uncertainty, and the
     prediction's (its 95 % bound / 1.96).

Two modes:
  - "absolute": the emission times are known exactly (a time-locked test signal, or synthetic
    data). Each residual is tested on its own; the station's clock bound
    (gpstime:time_offset_bound_s, taken as 95 %) is added to its sigma.
  - "common_offset": the towers share one unknown emission and clock offset (the usual case: a
    licence record doesn't say when a broadcast leaves the antenna). The offset is estimated
    (common_offset: a weighted median with three or more towers, the weighted mean with two) and
    removed; each tower is tested on what is left, and the set by chi-square. Needs two detected
    towers; with one, nothing can be said. With two, a disagreement can't be pinned on either.

Verdicts are `inferred` and say only agree / disagree / unknown (|z| ≤ z_max agrees): a
disagreement names no cause (multipath, a wrong record, a non-line-of-sight path, a timing
fault all look alike here).
"""

import math

from gps_time_pi.modkit import Analysis, Result

from .waveform import from_spec, rms_bandwidth

NAME = "analysis-tower-delay-check"
METHOD = ("complex cross-correlation with the known waveform, parabolic peak; delay = arrival (marker-timed) − "
          "emission; compared with reference-broadcast-towers' prediction")
DEFAULTS = {"mode": "common_offset", "search_s": 20e-6, "min_snr": 25.0, "z_max": 3.0}
INTERP_FLOOR_SAMPLES = 0.02


def _lv(value, unit, prov, note=None):
    d = {"value": value, "unit": unit, "provenance": prov}
    if note:
        d["note"] = note
    return d


def correlate(samples, template, lo, hi):
    """|correlation|² for template starts at lo..hi-1 (integers), and the complex values."""
    m = len(template)
    out = []
    for k in range(lo, hi):
        acc = 0j
        seg = samples[k:k + m]
        for a, b in zip(seg, template):
            acc += a * b
        out.append(acc)
    return [abs(c) ** 2 for c in out], out


def find_peak(power):
    """(index of the peak, fractional refinement in −0.5..0.5) by a parabola through three points."""
    k = max(range(len(power)), key=power.__getitem__)
    if 0 < k < len(power) - 1:
        a, b, c = (math.sqrt(power[k - 1]), math.sqrt(power[k]), math.sqrt(power[k + 1]))
        den = a - 2 * b + c
        frac = 0.5 * (a - c) / den if den != 0 else 0.0
        return k, max(-0.5, min(0.5, frac))
    return k, 0.0


def measure(cap, wave, nominal_arrival_ns, search_s, min_snr):
    """One waveform in the capture: dict with detected, index, arrival_ns, snr, sigma_s, or a reason."""
    hit = cap.index_of(nominal_arrival_ns)
    if hit is None:
        return {"detected": False, "reason": "the nominal arrival isn't in a timed part of the capture"}
    centre, rate = hit
    tmpl = wave.template(rate)
    half = math.ceil(search_s * rate)
    lo, hi = max(0, math.floor(centre) - half), min(cap.n - len(tmpl), math.floor(centre) + half + 1)
    if hi - lo < 3:
        return {"detected": False, "reason": "the search window runs off the capture"}
    power, _ = correlate(cap.samples, tmpl, lo, hi)
    k, frac = find_peak(power)
    guard = max(2, math.ceil(rate / wave.chip_rate_hz) * 2)
    rest = sorted(p for i, p in enumerate(power) if abs(i - k) > guard)
    floor = rest[len(rest) // 2] if rest else 0.0
    snr = power[k] / floor if floor > 0 else math.inf
    if snr < min_snr:
        return {"detected": False, "reason": f"no peak above the threshold (SNR {snr:.1f} < {min_snr:g})", "snr": snr}
    index = lo + k + frac
    t = cap.time_ns(index)
    if t is None:
        return {"detected": False, "reason": "the peak falls on samples without a time", "snr": snr}
    beta = rms_bandwidth(tmpl)
    sig_samples = max(INTERP_FLOOR_SAMPLES, 1.0 / (beta * math.sqrt(snr))) if beta > 0 else 1.0
    return {"detected": True, "index": index, "arrival_ns": t, "snr": snr, "sigma_corr_s": sig_samples / rate,
            "rate": rate}


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


class TowerDelayCheck(Analysis):
    def __init__(self, config=None):
        self.config = {**DEFAULTS, **(config or {})}

    def handle(self, observation):
        raise NotImplementedError("this analysis runs over a window (capture, predictions, emissions)")

    def run(self, window):
        """window: {"capture": Capture, "predictions": [observation dicts], "emissions": [...],
        "capture_id": str}. Returns [Result per emission..., summary Result]."""
        cap = window["capture"]
        preds = {}
        for o in window["predictions"]:
            v = o.get("values", o)
            tx = (v.get("transmitter") or {}).get("value")
            if tx and (v.get("delay_s") or {}).get("value") is not None:
                preds[tx] = v
        mode = self.config["mode"]
        if mode not in ("absolute", "common_offset"):
            raise ValueError(f"mode {mode!r}: absolute or common_offset")
        su = cap.sample_uncertainty_s or 0.0
        clock = (cap.offset_bound_s or 0.0) / 1.96 if mode == "absolute" else 0.0
        rows = []
        for e in window["emissions"]:
            tx = e["transmitter"]
            p = preds.get(tx)
            row = {"tx": tx, "emission_ns": e["emission_utc_ns"], "pred": p}
            if p is None:
                row["m"] = {"detected": False, "reason": "no prediction for this transmitter"}
            else:
                d, u = p["delay_s"]["value"], p["uncertainty_s"]["value"] or 0.0
                row["m"] = measure(cap, from_spec(e["waveform"]), int(e["emission_utc_ns"]) + round(d * 1e9),
                                   float(self.config["search_s"]), float(self.config["min_snr"]))
                if row["m"]["detected"]:
                    row["measured_s"] = (row["m"]["arrival_ns"] - int(e["emission_utc_ns"])) / 1e9
                    row["residual_s"] = row["measured_s"] - d
                    row["sigma_s"] = math.sqrt(row["m"]["sigma_corr_s"] ** 2 + su ** 2 + (u / 1.96) ** 2 + clock ** 2)
            rows.append(row)

        det = [r for r in rows if "residual_s" in r]
        offset = offset_sigma = chi2 = None
        if mode == "common_offset" and len(det) >= 2:
            offset, offset_sigma = common_offset(det)
        z_max = float(self.config["z_max"])
        for r in rows:
            if "residual_s" not in r:
                r["verdict"], r["z"] = "unknown", None
                continue
            if mode == "common_offset":
                if offset is None:
                    r["verdict"], r["z"] = "unknown", None
                    continue
                r["left_s"] = r["residual_s"] - offset
                r["z"] = r["left_s"] / r["sigma_s"]
            else:
                r["left_s"] = r["residual_s"]
                r["z"] = r["residual_s"] / r["sigma_s"]
            r["verdict"] = "agree" if abs(r["z"]) <= z_max else "disagree"
        if det and (mode == "absolute" or offset is not None):
            chi2 = sum(r["z"] ** 2 for r in det)
        dof = (len(det) - 1 if mode == "common_offset" else len(det)) if det else 0
        return self._results(window, cap, rows, det, mode, offset, offset_sigma, chi2, dof)

    def _results(self, window, cap, rows, det, mode, offset, offset_sigma, chi2, dof):
        t_ns = int(window.get("time_ns") or 0)
        inputs = [x for x in (window.get("capture_id"),) if x] + [r["tx"] for r in rows]
        out = []
        never = "agree or disagree only; a disagreement names no cause (multipath, a wrong record, an indirect path and a timing fault look alike here)"
        for r in rows:
            m = r["m"]
            vals = {"transmitter": _lv(r["tx"], None, "external", "from reference-broadcast-towers"),
                    "detected": _lv(m["detected"], None, "calculated", m.get("reason")),
                    "verdict": _lv(r["verdict"], None, "inferred", never)}
            unc = {}
            if r["pred"] is not None:
                vals["predicted_delay_s"] = _lv(r["pred"]["delay_s"]["value"], "s", "calculated", "reference-broadcast-towers")
                unc["predicted_delay_s"] = _lv(r["pred"]["uncertainty_s"]["value"], "s", "calculated", "95 % bound, from the reference")
            if "snr" in m:
                vals["snr"] = _lv(round(m["snr"], 1), None, "calculated", "correlation peak power over its median floor")
            if m["detected"]:
                vals["arrival_utc_ns"] = _lv(m["arrival_ns"], "ns", "calculated", "from the capture's marker timing")
                vals["measured_delay_s"] = _lv(r["measured_s"], "s", "calculated", "arrival − nominal emission")
                vals["residual_s"] = _lv(r["residual_s"], "s", "calculated", "measured − predicted")
                unc["measured_delay_s"] = _lv(m["sigma_corr_s"], "s", "calculated", "1-sigma, correlator only")
                unc["residual_s"] = _lv(r["sigma_s"], "s", "calculated", "1-sigma, combined")
                if r.get("z") is not None:
                    vals["residual_after_offset_s" if mode == "common_offset" else "residual_tested_s"] = _lv(
                        r["left_s"], "s", "calculated")
                    vals["z"] = _lv(round(r["z"], 3), None, "calculated")
            out.append(Result(time_ns=t_ns, analysis=NAME, values=vals, method=METHOD, inputs=inputs, uncertainty=unc))

        if not det:
            overall, why = "unknown", "no tower detected"
        elif mode == "common_offset" and offset is None:
            overall, why = "unknown", "one tower detected: an unknown common offset leaves nothing to compare"
        else:
            bad = sum(1 for r in det if r["verdict"] == "disagree")
            overall, why = ("consistent", None) if bad == 0 else ("inconsistent", f"{bad} of {len(det)} towers disagree")
        summ = {
            "mode": _lv(mode, None, "calculated",
                        "absolute: emission times known" if mode == "absolute"
                        else "common_offset: one unknown emission and clock offset shared by the towers, estimated and removed"),
            "towers": _lv(len(rows), None, "calculated"),
            "detected": _lv(len(det), None, "calculated"),
            "overall": _lv(overall, None, "inferred", why or never),
            "chi2": _lv(None if chi2 is None else round(chi2, 3), None, "calculated"),
            "dof": _lv(dof, None, "calculated"),
            "blanked_marker_samples": _lv(cap.blanked, None, "calculated", "PPS marker windows set to zero first"),
            "time_offset_bound_s": _lv(cap.offset_bound_s, "s", "observed", "the station's clock bound when captured"),
        }
        unc = {}
        if mode == "common_offset":
            summ["common_offset_s"] = _lv(offset, "s", "calculated",
                                          "emission timing and station clock together; not separable from one station")
            unc["common_offset_s"] = _lv(offset_sigma, "s", "calculated", "1-sigma")
        tested = [r["left_s"] for r in det if r.get("left_s") is not None]
        summ["residual_rms_s"] = _lv(math.sqrt(sum(x * x for x in tested) / len(tested)) if tested else None, "s",
                                     "calculated", "after the common offset" if mode == "common_offset" else None)
        out.append(Result(time_ns=t_ns, analysis=NAME, values=summ, method=METHOD, inputs=inputs, uncertainty=unc))
        return out

