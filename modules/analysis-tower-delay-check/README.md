# analysis-tower-delay-check (research)

**Maturity:** research, 0.2.0 (#137, #139). Type: analysis. Spec: `docs/specs/SPEC-EXTENSIBILITY.md` → "Reference modules to build first", item 3; the calibration check in `docs/specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md` §3; the FM trial in `docs/specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md` §5. **Synthetic data only so far:** no real capture has been checked.

Given captures timed by PPS markers and the predictions of `reference-broadcast-towers`, this module asks one question per tower: did its signal arrive when the geometry says it should? With one site, that needs to know when the signal left the antenna. With two sites, the departure cancels and only the difference in arrival is compared.

Needs **numpy**, already a station dependency.

## The waveforms

| Kind | What is correlated | Where it comes from |
|---|---|---|
| `atsc_field_sync` | The ATSC 1.0 (8-VSB) Data Field Sync segment | ATSC A/53 Part 2:2011 §5.3 |
| `fm_reference` | A 2 ms segment of site a's capture, isolated to ±100 kHz around the FM station | "FM correlation": the program is the signal |

**ATSC field sync.** The known symbols are:
- the 4 segment-sync symbols;
- PN511;
- the first and third PN63;
- the 24 VSB-mode symbols for trellis-coded 8-VSB.

That makes 665 symbols, 68 µs. Details:
- **Left out:** the middle PN63, because it is inverted on every other field, and the reserved and precode symbols, which are unknown.
- **Checks:** the code holds the standard's printed PN511 and PN63, and a test regenerates both from their polynomials (X⁹+X⁷+X⁶+X⁴+X³+X+1, preload 010000000; X⁶+X+1, preload 100111).
- **Signal model:** symbols at Sr = 4.5/286 × 684 MHz, the 1.25 pilot, and the upper sideband with a root-raised cosine edge (α = 0.1152). Centred on the channel, that is a_k·(−j)^k shaped by a low-pass root-raised cosine of Nyquist frequency Sr/4. A test checks that the pilot lands 2.69 MHz below the centre and that the band stays inside 6 MHz.
- **Repetition:** the field sync repeats every 24.2 ms.
- **Not covered:** ATSC 3.0 stations, flagged `atsc3` in the tower cache, don't carry a field sync.

**FM correlation.** An FM broadcast has no known sequence, so the template is site a's own capture of the station:
- shifted to 0 Hz and band-limited to ±100 kHz, which removes neighbouring stations;
- then resampled and shifted to site b's tuning.

It can only be used between two sites (the TDOA modes).

**Template per capture.** Each template is made for the capture's sample rate and tuning:
- **Tuning:** an RTL-SDR's tuner runs from the same crystal as its sample clock, so the tuner is off by the same parts per million as the marker-measured sample rate. The template follows that (`lo_follows_clock`, on by default).
- **Passband:** the SDR's filter is modelled as flat to 80 % of Nyquist, with a raised-cosine edge.
- **Filter delay:** a real SDR's filter delay is the same for every signal at one tuning and rate. It goes into the common offset, or cancels between matched receivers.

## How it works

For each tower, the module:
1. **Picks the capture** whose passband holds most of the signal's band. A 2.4 MS/s SDR sees one ATSC channel, or a few FM stations, per tuning.
2. **Finds the waveform:** complex cross-correlation (numpy) within ±`search_s` (20 µs) of the expected arrival, or over the whole capture for site a's ATSC field sync in the TDOA modes. The peak is refined by windowed-sinc interpolation of the complex correlation. A parabola through three points was biased by up to 50 ns (0.12 sample) at these bandwidths, independent of SNR.
3. **Decides detected or not:** the peak's power must be at least `min_snr` (25) times the median power within ±`floor_s` (200 µs), away from the main lobe. If not, the verdict is `unknown` and nothing is claimed.
4. **Times the arrival:** from the capture's marker timing, in integer nanoseconds.
5. **States the 1-sigma**, combining:
   - **the correlator:** 1 / (RMS bandwidth × √SNR), at least 0.02 sample. For FM, the SNR comes from the coherence at the peak, m·ρ²/(1 − ρ²), because program audio correlates with itself away from the peak and would understate it.
   - **the capture's sample-time uncertainty;**
   - **the prediction:** its 95 % bound / 1.96.

| Mode (`mode`) | Sites | Tested |
|---|---|---|
| `absolute` | one | arrival − emission − predicted delay, per tower; emission times must be known (a time-locked test signal); the clock bound is added |
| `common_offset` (default) | one | the same, after removing one unknown offset shared by the towers (weighted median with three or more, weighted mean with two); χ² for the set |
| `tdoa` | two | (arrival at b − arrival at a) − (predicted delay to b − to a); the emission cancels; both clocks trusted to their bounds |
| `tdoa_common_offset` | two | the same, after removing site b's clock offset against a (and any difference of receiver delays), estimated across the towers: the reference-transmitter method of the FM trial spec |

**Emission timing:**
- **Single-site modes:** a licence record doesn't say when a field sync leaves the antenna, and ATSC stations aren't required to align their fields to UTC. So the single-site modes need emission times from elsewhere.
- **TDOA modes:** these need none. **They are the realistic use.**
- **Prediction bounds in TDOA:** the bounds for one tower at two sites are added as if independent, although they share the tower's position error. That is conservative.

**Verdicts** are `inferred`: `agree` (|z| ≤ `z_max`, 3), `disagree` or `unknown`. A disagreement **names no cause**: multipath, a wrong licence record, an indirect path and a timing fault all look alike here.

## Output

One `result/1` per tower:
- `transmitter`, `waveform`, `detected`, `verdict`, `snr`;
- the predicted delay, residual, z, and the residual after the offset (or the residual as tested);
- single site: `arrival_utc_ns` and `measured_delay_s`;
- TDOA: `arrival_a_utc_ns`, `arrival_b_utc_ns`, `predicted_tdoa_s` and `measured_tdoa_s`, plus `snr_a` for ATSC;
- the uncertainties.

Then a summary:
- `mode`, `towers`, `detected`, `overall`, `chi2`, `dof`;
- `captures` and `blanked_marker_samples`;
- `time_offset_bound_s`: the largest clock bound of the captures;
- `common_offset_s` and its sigma, in the offset modes;
- `residual_rms_s`.

## Run it

The module host runs only `source` entries, so an analysis runs from its command line. Run it from this folder, with the repository on `PYTHONPATH` and numpy installed:

```sh
python -m tower_delay_check demo                       # every synthetic scenario
python -m tower_delay_check synth --scenario fm-tdoa-agree --out /tmp/fm
python -m tower_delay_check check --window /tmp/fm/window.json
```

`window.json` lists the captures of each site (observation-file bases), each site's predictions (JSON lines from `reference-broadcast-towers`), the emissions and the mode.

## Results on synthetic data

The scenarios are in `fixtures/scenarios.json`. Each capture is 2.4 MS/s with the sample clock off by −9 to +12 ppm, and the tuner off by the same fraction. One sample is 417 ns.
- **ATSC:** an 8-VSB stream with random data, at 0 dB SNR per sample.
- **FM:** a synthetic broadcast with noise for program audio, stereo and a pilot, at 3–10 dB.
- **Sites:** site a is the US Naval Observatory example point and site b the Washington Monument.

| Scenario | Result |
|---|---|
| `atsc-absolute-agree` (three channels; one tuned 0.5 MHz off centre, one partly outside the channel) | all agree; arrival errors −12 to +15 ns against a stated 1-sigma of 25–32 ns |
| `atsc-common-offset-one-disagrees` | the unknown 2.5 µs offset is recovered within 9 ns; the tower made 4 µs late disagrees (z ≈ 64) |
| `atsc-one-tower-too-weak` | the buried tower is `unknown` (SNR 8 < 25); the other two agree |
| `fm-tdoa-agree` (three stations, two sites) | all agree; TDOA errors −17 to +17 ns against 34–70 ns |
| `mixed-tdoa-common-offset-one-disagrees` (two FM, two ATSC) | site b's hidden 1.7 µs clock offset is recovered within 7 ns; the FM tower made 3 µs late at b disagrees (z ≈ 33) |

**Coverage over 40 seeds:**
- ATSC: every arrival error was inside 1.96 × the stated sigma (median 0.43 sigma). The sigma is on the cautious side, because the data symbols around the field sync count as noise.
- FM: 95 % of the TDOA errors were inside 1.96 sigma (median 0.70 sigma).
- The tests require at least 90 % for ATSC and 85 % for FM, over 24 seeds.

**These are simulated figures, not measurements.** Real broadcasts, the SDR's real filter, multipath and real program content will differ.

## Files

| File | What |
|---|---|
| `tower_delay_check/check.py` | the analysis (`TowerDelayCheck.run`), the correlator, the peak refinement, the capture choice, the common offset |
| `tower_delay_check/waveform.py` | the A/53 sequences and 8-VSB model, the FM reference template, resampling and band-limiting, the synthetic emissions |
| `tower_delay_check/capture.py` | a marker-timed observation file: samples, UTC per sample (integer ns), tuning, marker blanking |
| `tower_delay_check/synth.py` | synthetic captures for one or two sites, with the truth |
| `fixtures/scenarios.json`, `fixtures/predictions.jsonl`, `fixtures/predictions-b.jsonl` | the scenarios, and predictions for the two example sites from `reference-broadcast-towers`' synthetic cache (a test recomputes them) |

Tests: `tests/test_tower_delay_check.py`, run with the station's (`tests/test_modules.py`). They skip where numpy isn't installed; CI runs them in the station's venv and fails if they skip.

## Next

- **Real captures:** from `sdr-pps-marker`'s live capture (RTL-SDR through `rtl_tcp`, #140), once the PPS injection is built.
- **A bench check:** two receivers on one antenna (the TDOA should be zero), then two sites. This follows SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.
- **The pilot:** for coarse carrier tracking, if real captures need it.

Maintainer: project maintainers. Licence: MIT.
