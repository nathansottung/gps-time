"""Synthetic marker-timed captures for the check (fixtures/scenarios.json). Deterministic by seed.

A capture is what sdr-pps-marker would write: complex baseband samples at the SDR's real rate,
a first capture without time (before the PPS marker), then one timed from the marker's UTC
second at the marker-measured rate, and a pps_marker annotation over the marker's spike.

Each tower's waveform (waveform.Prn) leaves its antenna at T0 + emit_s + the scenario's common
emission offset, and arrives after its predicted delay plus any `extra_delay_s` the scenario
injects (to show a disagreement). The truth is known here, so the tests can check the analysis
recovers it. Not real signals, not a measurement.
"""

import cmath
import json
import math
import random
from pathlib import Path

from gps_time_pi import obsformat

from .waveform import from_spec

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_scenarios():
    return json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))


def load_predictions():
    return [json.loads(line) for line in (FIXTURES / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line]


def predicted_delays(predictions):
    return {o["values"]["transmitter"]["value"]: o["values"]["delay_s"]["value"] for o in predictions}


def make(scenario, predictions):
    """(meta, data bytes, emissions, truth) for one scenario."""
    sc = scenario
    rnd = random.Random(sc["seed"])
    fs = sc["fs_nominal"]
    rate = fs * (1 + sc["clock_ppm"] * 1e-6)            # the SDR's real rate, as the markers measure it
    pre = sc["pre_marker_samples"]
    n = pre + math.ceil(sc["duration_s"] * rate)
    t0_ns = obsformat.parse_ns(sc["t0_utc"])
    delays = predicted_delays(predictions)
    noise = sc["noise_rms"] / math.sqrt(2)
    x = [complex(rnd.gauss(0, noise), rnd.gauss(0, noise)) for _ in range(n)]
    emissions, truth = [], {}
    for tw in sc["towers"]:
        wave = from_spec(tw["waveform"])
        emit_s = tw["emit_s"]
        true_arrival_s = emit_s + sc["emission_offset_s"] + delays[tw["transmitter"]] + tw.get("extra_delay_s", 0.0)
        amp, ph = tw.get("amplitude", 1.0), cmath.exp(1j * rnd.uniform(0, 2 * math.pi))
        first = pre + math.floor(true_arrival_s * rate) - 4
        last = pre + math.ceil((true_arrival_s + wave.duration_s) * rate) + 4
        for i in range(max(0, first), min(n, last)):
            x[i] += amp * ph * wave.value((i - pre) / rate - true_arrival_s)
        emissions.append({"transmitter": tw["transmitter"], "waveform": tw["waveform"],
                          "emission_utc_ns": t0_ns + round(emit_s * 1e9)})
        truth[tw["transmitter"]] = {"arrival_ns": t0_ns + round(true_arrival_s * 1e9),
                                    "extra_delay_s": tw.get("extra_delay_s", 0.0)}
    for i in range(pre - 2, pre + 3):                    # the PPS marker's spike, blanked by the analysis
        x[i] += complex(40.0, 0.0)
    caps = [{"core:sample_start": 0, "core:frequency": sc["frequency_hz"], "gpstime:time_valid": False},
            {"core:sample_start": pre, "core:frequency": sc["frequency_hz"], "core:datetime": sc["t0_utc"],
             "gpstime:sample_rate": rate}]
    notes = [{"core:sample_start": pre - 6, "core:sample_count": 13, "core:label": "pps_marker",
              "core:comment": "PPS marker energy: blank before analysis", "gpstime:utc_second": t0_ns // 1_000_000_000}]
    meta = obsformat.build_meta(
        datatype="cf32_le", sample_rate=fs, captures=caps, annotations=notes,
        recorder="gps-time analysis-tower-delay-check synth", description=f"SYNTHETIC capture: {sc['name']}",
        gpstime={"station_id": "synthetic", "sensor": "rf", "quantity": "complex baseband voltage",
                 "unit": "relative", "channels": [{"name": "IQ"}], "time_source": "pps_marker",
                 "time_offset_bound_s": sc["time_offset_bound_s"],
                 "sample_time_uncertainty_s": sc["sample_time_uncertainty_s"],
                 "frequency_reference": {"state": "calibrated", "error_ppm": sc["clock_ppm"], "source": "pps_marker"},
                 "calibration": {"marker_delay_s": 0.0, "sample_scale": 1.0, "note": "synthetic"},
                 "position": {"privacy": "hidden", "lat": None, "lon": None},
                 "provenance": "observed", "request_id": None, "licence": "CC-BY-4.0"})
    return meta, obsformat.encode(x, "cf32_le"), emissions, truth
