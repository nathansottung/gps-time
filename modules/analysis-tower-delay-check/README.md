# analysis-tower-delay-check (research)

**Maturity:** research, 0.1.0 (#137). Type: analysis. Spec: `docs/specs/SPEC-EXTENSIBILITY.md` → "Reference modules to build first", item 3; the calibration check in `docs/specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md` §3. **Synthetic data only so far:** no real capture has been checked.

Given a capture timed by the PPS marker (`sdr-pps-marker`) and the predictions of `reference-broadcast-towers`, this module asks one question per tower: did its signal arrive when the geometry says it should?

## How it works

Inputs:
- **A marker-timed capture:** an observation file (SigMF + `gpstime:`) with `gpstime:time_source` `pps_marker`. Each sample's UTC time comes from the file's captures; samples without one are never used. The marker windows (`pps_marker` annotations) are zeroed first, as the marker writer asks.
- **Predictions:** the observations `reference-broadcast-towers` emits (`transmitter`, `delay_s`, `uncertainty_s`), as JSON lines.
- **Emissions:** for each tower, the waveform to look for and its nominal emission time (UTC ns). The only waveform so far is `prn`, a seeded pseudo-random chip code with Gaussian pulses. It stands in for the known parts of a real broadcast (an ATSC field sync segment, a pilot). Real broadcast waveforms aren't implemented yet.

For each tower:
1. **Find it:** complex cross-correlation with the waveform's template, ±`search_s` (20 µs) around the nominal arrival (emission + predicted delay), then a parabola through the three highest points.
2. **Detected or not:** the peak's power must be at least `min_snr` (25) times the correlation's median elsewhere. If it isn't, the verdict is `unknown` and nothing else is claimed.
3. **Measured delay:** arrival (from the capture's marker timing, integer nanoseconds) − emission. **Residual:** measured − predicted.
4. **1-sigma:** the correlator's (1 / (RMS bandwidth × √SNR), at least 0.02 sample), the capture's sample-time uncertainty, and the prediction's (95 % bound / 1.96).

Two modes (`mode`):

| Mode | When | What is tested |
|---|---|---|
| `absolute` | the emission times are known exactly (a time-locked test signal; synthetic data) | each residual on its own, with the station's clock bound (`gpstime:time_offset_bound_s`, as 95 %) added to its sigma |
| `common_offset` (default) | the towers share one unknown emission and clock offset, the usual case: a licence record doesn't say when a broadcast leaves the antenna | the offset is estimated and removed (weighted median with three or more towers, so one bad tower can't drag the rest; weighted mean with two, when a disagreement can't be pinned on either). Each tower is tested on what is left, and the set by χ². One detected tower: nothing can be said |

**Verdicts** are `inferred`: `agree` (|z| ≤ `z_max`, 3), `disagree` or `unknown`. A disagreement **names no cause**: multipath, a wrong licence record, an indirect path and a timing fault all look alike here. The summary's `overall` is `consistent`, `inconsistent` (with how many towers disagree) or `unknown`.

## Output

One `result/1` per tower:
- `transmitter`, `detected`, `verdict`, `snr`;
- `predicted_delay_s`, `arrival_utc_ns`, `measured_delay_s`, `residual_s`, `z`;
- the residual after the common offset, or the residual as tested;
- uncertainties for the prediction, the correlator and the combined residual.

Then a summary with:
- `mode`, `towers`, `detected`, `overall`, `chi2`, `dof`;
- `common_offset_s` and its sigma: emission timing and station clock together, which one station can't separate;
- `residual_rms_s`, `blanked_marker_samples`, `time_offset_bound_s`.

## Run it

The station's module host runs only `source` entries, so an analysis runs from its command line (from this folder, with the repository on `PYTHONPATH`):

```sh
python -m tower_delay_check demo                       # every synthetic scenario
python -m tower_delay_check synth --scenario common-offset-one-disagrees --out /tmp/cap
python -m tower_delay_check check --capture /tmp/cap --predictions fixtures/predictions.jsonl \
    --emissions /tmp/cap.emissions.json
```

## Results on synthetic data

The scenarios are in `fixtures/scenarios.json`. Each is 2.4 MS/s with a sample clock off by −15 to +15 ppm (the marker-measured rate is in the capture), and 3 ms of noise with each tower's 425 µs code at about −6 dB per sample. One sample is 417 ns.

| Scenario | Result |
|---|---|
| `absolute-agree` | all three agree; arrival errors 6–70 ns against a stated 1-sigma of 89–118 ns |
| `common-offset-one-disagrees` | the unknown 2.5 µs offset is recovered within 60 ns; the tower made 4 µs late disagrees (z ≈ 35); the other two agree |
| `one-tower-too-weak` | the buried tower is `unknown` (SNR 8 < 25), the other two agree, and the offset is recovered |

Over 24 seeds (72 arrivals), every arrival error stayed inside 1.96 × the stated correlator sigma. The median error was 0.39 sigma and the largest 1.74 sigma; a test requires at least 90 % coverage. The SNR is measured against the code's own sidelobes as well as noise, so the stated sigma is on the cautious side. **These are simulated figures, not measurements.** Real broadcasts, the SDR's filters and multipath will differ.

## Files

| File | What |
|---|---|
| `tower_delay_check/check.py` | the analysis (`TowerDelayCheck.run`), the correlator, the peak, the common offset |
| `tower_delay_check/capture.py` | a marker-timed observation file: samples, UTC per sample (integer ns), marker blanking |
| `tower_delay_check/waveform.py` | the `prn` waveform: continuous (for synthesis) and sampled (the template) |
| `tower_delay_check/synth.py` | synthetic captures from the scenarios, with the truth |
| `fixtures/scenarios.json`, `fixtures/predictions.jsonl` | synthetic scenarios, and three predictions from the `reference-broadcast-towers` demo (synthetic towers) |

Tests: `tests/test_tower_delay_check.py`, run with the station's (`tests/test_modules.py`).

## Next

- A real waveform: the ATSC field sync segment or the pilot.
- An SDR source writing marker-timed captures (`sdr-pps-marker` research step 2).
- Then a bench check against towers whose emission timing is known, or between two stations (SPEC-RF-TASKING-AND-FM-TDOA-TRIAL).

Maintainer: project maintainers. Licence: MIT.
