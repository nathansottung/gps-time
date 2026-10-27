"""Synthetic marker-timed captures for the check (fixtures/scenarios.json). Deterministic by seed.

A capture is what an SDR source with PPS markers would write: complex baseband samples at the
SDR's real rate, a first part without time (before the PPS marker), then a part timed from the
marker's UTC second at the marker-measured rate, and a pps_marker annotation over the marker's
spike. The SDR's tuner is off by the same fraction as its sample clock (one crystal).

The towers are real waveforms (waveform.py):
  - ATSC: an 8-VSB stream (random 8-level data, segment syncs, field syncs as A/53 defines them,
    the pilot), shaped and band-limited to the capture's passband;
  - FM: a synthetic broadcast (band-limited noise as program audio, stereo, pilot) at 75 kHz.
Each tower's stream is seeded by the tower, so two sites receive the same broadcast.

Timing truth: a tower's field sync (ATSC), or its stream origin (FM), leaves the antenna at
T0 + emit_s + the scenario's hidden emission_offset_s, and arrives at a site after the predicted
delay for that site, plus any extra_delay_s the scenario injects there (to show a
disagreement). Site b's clock may be off by a hidden clock_offset_b_s: its capture times are
labelled late by that much. Not real signals, not a measurement.
"""

import json
import math
from pathlib import Path

import numpy as np

from gps_time_pi import obsformat

from . import waveform as wv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HALF_BW = {"atsc_field_sync": 3e6, "fm_reference": 100e3}


def load_scenarios():
    return json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))


def load_predictions(name="predictions.jsonl"):
    return [json.loads(line) for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines() if line]


def by_transmitter(predictions):
    return {o["values"]["transmitter"]["value"]: o["values"] for o in predictions}


def _tower_seed(seed, tx):
    return (seed * 1_000_003 + sum((i + 1) * ord(c) for i, c in enumerate(tx))) % (2 ** 32)


def _true_times(cap, n, pre, rate, t0_ns, clock_offset_s):
    """True UTC (s, relative to T0) of each sample: labels minus the site's clock offset."""
    return (np.arange(n) - pre) / rate - clock_offset_s


def _render_atsc(tw, sc, cap, rel_t, arrival_rel_s):
    rng = np.random.default_rng(_tower_seed(sc["seed"], tw["transmitter"]))
    lead = 3e-3                                             # stream starts this long before the field sync
    span = lead + max(0.0, rel_t[-1] - arrival_rel_s) + 1e-3
    n_sym = int(math.ceil(span * wv.SR))
    f_at = int(round(lead * wv.SR))
    levels = wv.atsc_stream(rng, n_sym, f_at, bool(tw.get("middle_inverted", False)))
    x, r2 = wv.vsb_baseband(levels, pilot=True)
    x = wv.shift_and_limit(x, r2, tw["channel_hz"] - cap["tune_hz"], cap["rate"])
    # stream time u = 0 at its first symbol; the field sync's first symbol is at f_at / SR
    u = rel_t - arrival_rel_s + f_at / wv.SR
    return wv.resample(x, r2, u)


def _render_fm(tw, sc, cap, rel_t, arrival_rel_s, margin_s):
    rng = np.random.default_rng(_tower_seed(sc["seed"], tw["transmitter"]))
    x, re = wv.fm_emission(rng, sc["duration_s"] + 2 * margin_s + 2e-3)
    u = rel_t - arrival_rel_s + margin_s                    # emission origin at stream time margin_s
    y = wv.resample(x, re, u)
    return y * np.exp(2j * math.pi * (tw["channel_hz"] - cap["tune_hz"]) * (rel_t - rel_t[0]))


def make(scenario, predictions=None, predictions_b=None):
    """(window for TowerDelayCheck.run with Capture objects built from the files, files, truth).
    files: [(site, id, meta, data bytes)]; truth: per transmitter, what the check should find."""
    from .capture import Capture
    sc = scenario
    preds = {"a": by_transmitter(predictions or load_predictions(sc.get("predictions", "predictions.jsonl")))}
    if "b" in {c["site"] for c in sc["captures"]}:
        preds["b"] = by_transmitter(predictions_b or load_predictions(sc.get("predictions_b", "predictions-b.jsonl")))
    rng = np.random.default_rng(sc["seed"])
    t0_ns = obsformat.parse_ns(sc["t0_utc"])
    pre = sc["pre_marker_samples"]
    offsets = {"a": 0.0, "b": float(sc.get("clock_offset_b_s", 0.0))}
    hidden = float(sc.get("emission_offset_s", 0.0))
    margin = 2e-3
    towers = []
    for tw in sc["towers"]:
        kind = tw["waveform"]["kind"]
        ch = preds["a"][tw["transmitter"]]["frequency_hz"]["value"]
        towers.append({**tw, "kind": kind, "channel_hz": ch})
    files, truth = [], {}
    for c in sc["captures"]:
        site = c["site"]
        rate = c["fs_nominal"] * (1 + c["clock_ppm"] * 1e-6)
        cap = {"tune_hz": c["center_hz"] * (1 + c["clock_ppm"] * 1e-6), "rate": rate}
        n = pre + int(math.ceil(sc["duration_s"] * rate))
        rel_t = _true_times(cap, n, pre, rate, t0_ns, offsets[site])
        sig = np.zeros(n, dtype=complex)
        for tw in towers:
            lo, hi = cap["tune_hz"] - 0.4 * rate, cap["tune_hz"] + 0.4 * rate
            if min(hi, tw["channel_hz"] + HALF_BW[tw["kind"]]) - max(lo, tw["channel_hz"] - HALF_BW[tw["kind"]]) <= 0:
                continue
            d = preds[site][tw["transmitter"]]["delay_s"]["value"]
            extra = float((tw.get("extra_delay_s") or {}).get(site, 0.0))
            emit_rel = tw["emit_s"] + hidden
            arrival_rel = emit_rel + d + extra
            if tw["kind"] == "atsc_field_sync":
                y = _render_atsc(tw, sc, cap, rel_t, arrival_rel)
            else:
                y = _render_fm(tw, sc, cap, rel_t, arrival_rel, margin)
            p = np.mean(np.abs(y[pre:]) ** 2)
            amp = math.sqrt(10 ** (tw.get("snr_db", 0.0) / 10) * sc["noise_rms"] ** 2 / p) if p > 0 else 0.0
            sig += amp * np.exp(2j * math.pi * rng.uniform()) * y
            t = truth.setdefault(tw["transmitter"], {"kind": tw["kind"], "extra_delay_s": tw.get("extra_delay_s") or {}})
            t[f"arrival_{site}_ns"] = t0_ns + round((arrival_rel + offsets[site]) * 1e9)   # as site's clock labels it
            t[f"delay_{site}_s"] = d
        noise = sc["noise_rms"] / math.sqrt(2)
        x = sig + noise * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
        x[pre - 2:pre + 3] += 40.0                                 # the PPS marker's spike, blanked by the analysis
        caps = [{"core:sample_start": 0, "core:frequency": c["center_hz"], "gpstime:time_valid": False},
                {"core:sample_start": pre, "core:frequency": c["center_hz"], "core:datetime": sc["t0_utc"],
                 "gpstime:sample_rate": rate}]
        notes = [{"core:sample_start": pre - 6, "core:sample_count": 13, "core:label": "pps_marker",
                  "core:comment": "PPS marker energy: blank before analysis", "gpstime:utc_second": t0_ns // 1_000_000_000}]
        meta = obsformat.build_meta(
            datatype="cf32_le", sample_rate=c["fs_nominal"], captures=caps, annotations=notes,
            recorder="gps-time analysis-tower-delay-check synth",
            description=f"SYNTHETIC capture: {sc['name']}, site {site}, {c['center_hz'] / 1e6:.3f} MHz",
            gpstime={"station_id": f"synthetic-{site}", "sensor": "rf", "quantity": "complex baseband voltage",
                     "unit": "relative", "channels": [{"name": "IQ"}], "time_source": "pps_marker",
                     "time_offset_bound_s": sc["time_offset_bound_s"],
                     "sample_time_uncertainty_s": sc["sample_time_uncertainty_s"],
                     "frequency_reference": {"state": "calibrated", "error_ppm": c["clock_ppm"], "source": "pps_marker"},
                     "calibration": {"marker_delay_s": 0.0, "sample_scale": 1.0, "note": "synthetic"},
                     "position": {"privacy": "hidden", "lat": None, "lon": None},
                     "provenance": "observed", "request_id": None, "licence": "CC-BY-4.0"})
        files.append((site, c["id"], meta, obsformat.encode(list(x), "cf32_le")))
    emissions = []
    for tw in towers:
        e = {"transmitter": tw["transmitter"], "waveform": tw["waveform"]}
        if sc["mode"] in ("absolute", "common_offset"):
            e["emission_utc_ns"] = t0_ns + round(tw["emit_s"] * 1e9)          # nominal: without the hidden offset
        emissions.append(e)
    window = {"captures": [Capture(m, d) for s, _i, m, d in files if s == "a"],
              "captures_b": [Capture(m, d) for s, _i, m, d in files if s == "b"],
              "predictions": [{"values": v} for v in preds["a"].values()],
              "predictions_b": [{"values": v} for v in preds.get("b", {}).values()],
              "emissions": emissions}
    return window, files, truth
