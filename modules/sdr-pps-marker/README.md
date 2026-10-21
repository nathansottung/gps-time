# sdr-pps-marker (research)

Finds the station's PPS pulse inside an SDR's own sample stream and uses it to give every sample a UTC time. This is **research step 1** of [`SPEC-SDR-PPS-MARKER.md`](../../docs/specs/SPEC-SDR-PPS-MARKER.md): synthetic data only. No hardware has been built or measured.

- **Type:** source (spec: [`SPEC-EXTENSIBILITY.md`](../../docs/specs/SPEC-EXTENSIBILITY.md)). Maturity: research.
- **Status:** the first module the loader (`gps_time_pi.modkit`) loads. Its source (`sdr_pps_marker/source.py`) replays the fixture scenarios in demo mode and emits nothing otherwise, since there is no SDR input yet (research step 2). Off by default; the Pi bundle doesn't ship `modules/`. Demo: `python -m gps_time_pi.modkit demo sdr-pps-marker`.
- **Dependencies:** Python standard library, plus `gps_time_pi.labels` for provenance labels.

## What it does

| Part | File | What |
|---|---|---|
| Generator | `sdr_pps_marker/synth.py` | Complex IQ with noise, an optional slow carrier, a band-limited spike per PPS edge (rising, and falling one pulse width later), a fast or slow and drifting sample clock, dropped sample blocks, missed markers. Deterministic by seed. |
| Detector | `sdr_pps_marker/detector.py` | Finds spikes with a high-pass test (a carrier can't hide them), sets the threshold for one false alarm per hour of samples, removes the local carrier, matched-filters, and interpolates the peak to a fraction of a sample. Drops falling edges: a spike one pulse width after another, or a lone spike one pulse width after the second-phase of confirmed rising edges. |
| Source | `sdr_pps_marker/source.py` | The loader's entry point: demo mode emits one Observation per fixture scenario with the time model's labeled health values. |
| Time model | `sdr_pps_marker/timemodel.py` | Numbers each marker's UTC second from a coarse host clock (to within 0.5 s). Flags intervals with the wrong sample count (samples dropped or added) or a rate more than 200 ppm off nominal. Interpolates sample → UTC between markers, as an integer second plus a fraction. Measures the sample rate, its error in ppm and its drift. |

Rules it keeps:
- **No time where it can't know.** Samples before the first marker, after the last, inside a flagged interval, or before the scatter estimate has 3 degrees of freedom get `None`.
- **No cause.** A short interval is reported as `samples_missing`, a long one as `samples_extra`.
- **Labels.** `TimeModel.summary()` labels every value (observed or calculated) and reports state `UNKNOWN` until it has enough markers.
- **Scope of the uncertainty.** It covers the marker fit only: PPS accuracy, the injection path, the SDR's internal delay and the antenna and cable delay come from bench calibration (steps 2–4). `marker_delay_s` takes the calibrated path delay.

## Results on synthetic data

From `fixtures/scenarios.json` at 24 kS/s. Errors are in samples, so they carry over to other rates: at 2.4 MS/s one sample is 417 ns.

| Scenario | Marker SNR | Position error, RMS / max (samples) | Notes |
|---|---|---|---|
| clean | ~41 | 0.019 / 0.035 | |
| noisy | ~8 | 0.10 / 0.19 | |
| carrier (slow tone 2× the spike) | ~8 | 0.041 / 0.069 | |
| fast clock, drifting (+37.5 ppm, 0.02 ppm/s) | ~25 | 0.030 / 0.049 | ppm measured within 0.01 |
| USB drop (1024 samples) | ~25 | 0.022 / 0.043 | drop flagged with the exact count; no time inside it, correct time on both sides |
| missed marker | ~27 | 0.037 / 0.076 | 2 s interval handled |

At 2.4 MS/s that would be about 8–43 ns RMS from the marker fit alone, in line with the spec's 10–50 ns estimate. **These are figures from simulated data, not measurements**: the real spike shape, the SDR's filters, real broadcast signals and real noise will differ, and bench step 2 is where they get measured.

Known limits:
- **The uncertainty is conservative on purpose.** The stated 1-sigma is the 95 % upper confidence bound on the marker scatter (a quadratic fit per block of up to 30 markers, chi-square bound), plus a 0.02-sample floor for interpolation bias. In 200 seeded short runs (7–10 s, random noise, clock error, drift, carrier, drops), the 95 % interval (1.96 sigma) covered the true error in all 180 runs that gave a time; the median error was about a third of the stated sigma. Longer runs state a tighter bound. Runs too short to estimate the scatter (for example a drop splitting 7 markers into two short blocks) give no time.
- **Drops of more than half a second** of samples can't be counted, because the number of seconds is ambiguous.
- **Only a slow tone** stands in for a carrier. Wideband FM or ATSC near the spike is untested until the bench.
- **Pure Python is slow** at real rates (2.4 MS/s). Step 2 will need a faster path, for example numpy or processing only around the expected marker windows.

## Run the tests

From the repository root (no hardware, numpy or network needed):

```bash
python -m unittest tests.test_modules -v
```

They also run with the station's whole test suite (`python -m unittest discover -s tests -t .`), and so in CI.

## Use

```python
from sdr_pps_marker import detect, TimeModel

markers = detect(iq_samples, fs_nominal=2_400_000, pulse_width_s=0.1)
model = TimeModel(markers, 2_400_000, coarse_start_utc=host_time_of_sample_0)
t = model.utc(123_456)          # UtcTime(second, fraction, uncertainty_s) or None
model.events()                  # samples_missing / samples_extra intervals
model.summary()                 # labeled health values for a dashboard
```

## Next (research steps 2–5)

Bench with one SDR, then two SDRs through a splitter, then a scope check against the PPS line, then publishing the schematic, BOM and measured results. See the spec.

Maintainer: project maintainers. Licence: MIT.
