# sdr-pps-marker (research)

Finds the station's PPS pulse inside an SDR's own sample stream and uses it to give every sample a UTC time. Research steps 1 and 2 of [`SPEC-SDR-PPS-MARKER.md`](../../docs/specs/SPEC-SDR-PPS-MARKER.md):
- **Step 1:** the detector and time model, on synthetic data.
- **Step 2's software (0.2.0, #140):** live capture from an RTL-SDR through `rtl_tcp`, with timed windows written as observation files. It is tested against a fake `rtl_tcp` only.

**No hardware has been built or measured.**

- **Type:** source (spec: [`SPEC-EXTENSIBILITY.md`](../../docs/specs/SPEC-EXTENSIBILITY.md)). Maturity: research.
- **Status:** the first module the loader (`gps_time_pi.modkit`) loads. Its source (`sdr_pps_marker/source.py`) has three modes:
  - demo: replays the fixture scenarios;
  - live: captures with an `rtl_tcp` section in its config (below);
  - otherwise it emits nothing.

  Off by default; the Pi bundle doesn't ship `modules/`. Demo: `python -m gps_time_pi.modkit demo sdr-pps-marker`.
- **Dependencies:**
  - the step-1 core (generator, detector, time model, writer): Python standard library, plus `gps_time_pi.labels`;
  - the fast detector, live capture and fake server: numpy, a station dependency.

## What it does

| Part | File | What |
|---|---|---|
| Generator | `sdr_pps_marker/synth.py` | Complex IQ with noise, an optional slow carrier, a band-limited spike per PPS edge (rising, and falling one pulse width later), a fast or slow and drifting sample clock, dropped sample blocks, missed markers. Deterministic by seed. |
| Detector | `sdr_pps_marker/detector.py` | Finds spikes with a high-pass test (a carrier can't hide them), sets the threshold for one false alarm per hour of samples, removes the local carrier, matched-filters, and interpolates the peak to a fraction of a sample. Drops falling edges: a spike one pulse width after another, or a lone spike one pulse width after the second-phase of confirmed rising edges. |
| Source | `sdr_pps_marker/source.py` | The loader's entry point: demo mode emits one Observation per fixture scenario with the time model's labeled health values. |
| Observation files | `sdr_pps_marker/observation.py` | `to_observation(samples, model, ...)`: a SigMF + `gpstime:` file with `time_source = pps_marker`. One capture per marker interval (UTC time and measured rate), no time where the model has none, the SDR clock's measured error, marker windows annotated. Format: `docs/modules/observation-format.md`. |
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
- **The pure-Python detector is slow** at real rates (2.4 MS/s). `fast.py` is the numpy path, and a test checks it returns the same markers. On a desktop it finds the markers in 10 s of 2.4 MS/s samples in about 1 s. **On a Pi it isn't measured yet.**

## Run the tests

From the repository root (no hardware or network needed; the live-capture tests need numpy and are skipped without it):

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

## Live capture (research step 2 software)

```
RTL-SDR (with the injected PPS) ──USB──► rtl_tcp (gps-time-rtl-tcp.service, 127.0.0.1:1234)
                                              │ cu8 samples, retune commands
                                              ▼
                        sdr-pps-marker in gps-time-modules.service (sandboxed, localhost only)
                          dwell → markers → time model → timed windows → RAM storage (observation files)
```

**Why rtl_tcp.** A module may not start processes or load native libraries: that is the sandbox's permission guard. So it can't run `rtl_sdr`, and it can't use librtlsdr through ctypes, as pyrtlsdr does.
- **What runs it:** `rtl_tcp` (osmocom's own server) runs as its own service, owns the USB device, and serves samples on the loopback address.
- **What the module does:** it connects and speaks the documented protocol (`rtltcp.py`): a 12-byte header, 5-byte commands for frequency, sample rate and gain, then unsigned 8-bit I/Q.

**One dwell per plan entry** (`capture.py`). For each entry, the module:
1. **Connects, tunes and settles:** opens a new connection, so rtl_tcp starts with an empty buffer. It tunes, then drops `settle_s` (0.3 s) of samples.
2. **Records:** reads `dwell_s` (10 s) of raw samples into RAM: 48 MB at 2.4 MS/s.
3. **Times the samples:** finds the markers with the numpy detector and builds the time model.
   - **UTC second:** each marker's UTC second comes from the host clock at the first byte.
   - **Safety check:** if that clock puts the markers more than 0.25 s from whole seconds, the second is ambiguous, so **nothing is written**.
4. **Writes windows:** each window (`at_s`, `duration_s`; default 30 ms, enough for one ATSC field) goes out as an observation file.
   - **Format:** `cu8`, the dongle's own samples, with `gpstime:calibration` giving the offset and scale.
   - **Timing:** `time_source` is `pps_marker`; the window has one capture per marker interval, and no time where the model has none.
   - **Position:** the privacy-filtered position.
5. **Keeps the newest files only:** files go to the module's RAM storage (16 MiB), never the SD card, and only the newest `keep_files` (40) are kept.

**After each dwell** the module emits an observation with:
- the time model's health (markers, clock error, sample-time uncertainty, dropped-sample events);
- `host_clock_offset_s`;
- how many windows were written or skipped, and why.

**What it never does:**
- write anything without markers (state `UNKNOWN`, with the reason);
- give time to samples the model can't time.

`tower_delay_check` reads these files (it centres the cu8 samples).

**Config** (`module_config` → `sdr-pps-marker`):

```json
{"station_id": "my-station",
 "rtl_tcp": {"host": "127.0.0.1", "port": 1234, "sample_rate_hz": 2400000, "gain_tenth_db": 296,
             "cycle_s": 600, "keep_files": 40,
             "plan": [{"center_hz": 521000000, "dwell_s": 10, "windows": [{"at_s": 4.0, "duration_s": 0.03}], "label": "RF 22"},
                      {"center_hz": 88800000, "dwell_s": 10, "windows": [{"at_s": 4.0, "duration_s": 0.005}], "label": "FM"}]}}
```

- **`gain_tenth_db`:** `null` means automatic gain.
- **Window placement:** put windows between markers, at least a second into the dwell, so markers fall on both sides.
- **`marker_delay_s`:** the calibrated injection-path delay. It is 0 until the bench says otherwise.

**On a station** (not done yet; nothing here is deployed):
1. **The injection build:** see the spec, "Physical build". Without the PPS at the SDR's input there are no markers, and the module writes nothing.
2. **rtl_tcp:** `sudo GTP_SDR=1 GTP_SDR_PPS_SERIAL=<the dongle's serial> bash install.sh` (`docs/deploy/sdr-stack.md`). It installs `rtl-sdr` and `gps-time-rtl-tcp.service`, which listens on 127.0.0.1 only and has its own sandbox: USB devices and the loopback address.
3. **The localhost drop-in for the module service** comes with step 2 (`gps-time-modules.service.d/gps-time-sdr.conf`: `IPAddressAllow=localhost`). The service keeps `IPAddressDeny=any`, so loopback is all it can reach. The manifest's `network = true` is for this only.
4. **Enable the module** and set its config (above).
5. **Watch the timing chain** while it runs. The capture adds USB and CPU load. It doesn't touch gpsd, chrony or the PPS line, but its effect on the station's timing hasn't been measured.

**Without hardware:**
- `python -m sdr_pps_marker.fakesdr --port 1234`, run from this folder, serves a synthetic stream with markers at real time. Point the config at it.
- The tests use the same fake: `tests/test_live_capture.py`, with a USB drop, a clock off by 23 ppm, no markers, a host clock off by 0.45 s, and file retention.

**Estimates, not measurements:**
- The time model's figures on the fake stream: about 0.03 samples RMS of marker error, about 23 ns of stated sample-time uncertainty at 2.4 MS/s.
- Real spikes, the real tuner and USB, and real broadcast signals around the spike come with bench step 2.

## Next (research steps 2–5)

Bench with one SDR (the capture software is ready), then two SDRs through a splitter, then a scope check against the PPS line, then publishing the schematic, BOM and measured results. See the spec.

Maintainer: project maintainers. Licence: MIT.
