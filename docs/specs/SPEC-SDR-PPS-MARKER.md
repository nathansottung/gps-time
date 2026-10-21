# SPEC — PPS Time Markers in SDR Sample Streams (Research)

## Status

RESEARCH, planned. Extends SPEC-RF-NODE-AND-TDOA.md and SPEC-OBSERVATION-FORMAT-AND-TASKING.md. Receive-only: nothing is transmitted over the air. Every figure here is an estimate until measured.

## Problem

An RTL-SDR's samples have no reliable timestamps. The station's clock can be accurate to well under a microsecond, but USB buffering adds about 1–10 ms of uncertainty to when each sample was actually taken, and the dongle can silently drop samples. Radio travels 300 m per µs, so 1 ms of error is 300 km.

Broadcast signals don't carry their emit time (like a shout from a mountain with no start time), so they can't fix this on their own.

## Idea

Feed the GNSS receiver's PPS pulse, buffered and heavily attenuated, into the SDR input alongside the antenna signal. The pulse's sharp edge has energy across a wide band, so it appears in the SDR's samples as a short spike wherever the SDR is tuned. That spike marks a known UTC second inside the sample stream itself, before any USB delay.

## What it gives

- **Absolute sample timing:** each sample's UTC time from the surrounding markers.
- **SDR clock calibration every second:** the sample count between markers gives the dongle's true sample rate, so its crystal error (ppm) and drift are measured continuously.
- **Dropped-sample detection:** an interval with the wrong count is flagged and excluded.
- **One time base across nodes,** so arrival times from different nodes can be compared directly.

---

## Physical build

### Option 1 — tap the receiver's PPS (preferred)

No change to the GPS HAT. The HAT already drives the PPS onto GPIO 18.

```
GNSS HAT ──PPS──► GPIO 18 (pin 12) ──jumper──► buffer ──► SMA ──► attenuators ──► combiner ──► RTL-SDR
                                                   ▲                                   ▲
                                         3.3 V (pin 1), GND (pin 6)              antenna cable
```

1. **Stacking header** (or a 40-pin extender) under or over the HAT, so pins 1, 6 and 12 are reachable.
2. **Jumper wires** from pin 12 (GPIO 18, PPS), pin 6 (ground) and pin 1 (3.3 V) to a small board.
3. **Buffer:** a single-gate logic buffer (e.g. 74LVC1G17 or similar) so the injection path can't load or disturb the PPS line chrony uses. A series resistor at its output matches the 50 Ω line.
4. **SMA connector** on the board.
5. **Fixed SMA attenuators**, screw-together: start with 20 + 20 + 10 dB (50 dB total) and adjust.
6. **Resistive combiner, splitter used in reverse, or directional coupler** inline on the antenna cable, joining the marker path and the antenna into the SDR.
7. **RTL-SDR** as usual.

Rough parts cost: under $25, mostly off-the-shelf SMA parts plus one small solder job.

Rules:
- Never connect the 3.3 V pulse directly to the SDR input.
- Keep the marker as weak as detection allows, so it doesn't add interference across the band.
- Record cable lengths and the injection point; that path's delay is a fixed calibration value.

### Option 2 — Pi-generated pulse (fallback)

Software watches PPS and toggles a spare GPIO, which feeds the same buffer/attenuator chain. No tap on the PPS line, but kernel and scheduling latency add several µs of jitter (about 1 km of range). Good for dropped-sample detection and sample-rate calibration; weak for ranging.

### Frequency coverage

The edge's energy falls off at higher frequencies. Expect easy detection in the FM and TV bands (~100–600 MHz) and a weaker marker at 1090 MHz (ADS-B), which may need less attenuation or a faster-edge source (e.g. a comb generator). Characterize on the bench.

### Kit possibility

If the bench results hold, a small "marker injector" board (buffer, SMA out, pin header input, optional built-in attenuator) could be published as open hardware with a schematic and BOM, and possibly offered pre-assembled. Not before the design is measured and documented.

---

## Timing error budget (estimates, to be measured)

| Source | Estimate | Notes |
|---|---|---|
| Receiver PPS accuracy | ~20–30 ns (MAX-M8Q class); ~5 ns (ZED-F9T) | datasheet-class figures, to confirm |
| Buffer and wiring delay | a few ns, stable | calibrate once |
| Cable and attenuator delay | ~5 ns per metre, stable | calibrate once |
| Marker position in samples | 417 ns per sample at 2.4 MS/s; ~10–50 ns after interpolation | depends on marker signal-to-noise |
| SDR internal delay (filters, tuner) | fixed per frequency and gain setting | calibrate per band |
| Sample-clock drift between markers | ~ns after a linear fit | measured every second |

Rough total per node: **~50–100 ns**, i.e. roughly 15–30 m of range per node. This is a hypothesis for the research to test, not a claim.

Antenna and cable delay before the injection point are not covered by the marker and must be calibrated separately.

---

## Research plan

1. **Synthetic first.** Detector, sub-sample interpolation and time model on generated data with pulses, drops and drift. Runs in CI with no hardware.
2. **Bench, one SDR.** Visibility of the marker across bands and attenuation levels; detection rate; measured sample-rate error over hours and temperature.
3. **Bench, two SDRs.** Same signal through a splitter, both with markers: measured arrival-time difference should be zero within the stated uncertainty. This gives the first real timing figure.
4. **Scope check.** Compare against an oscilloscope or time-interval counter on the PPS line.
5. **Publish** the schematic, BOM, measured results, and the observation format's `time_source: pps_marker` with measured uncertainty.

## Path to aircraft tracking and MLAT

1. **One node, ADS-B:** decode aircraft with marker-timestamped samples; compare each message's arrival time with the time predicted from the aircraft's reported position. With one node the emit time is unknown, so this checks consistency, not absolute delay.
2. **Two nodes, ADS-B TDOA:** the unknown emit time cancels. Compare measured arrival-time differences with those predicted from reported positions. The residuals measure the system's real accuracy.
3. **Three or more nodes, MLAT:** locate aircraft that send Mode S without position (no ADS-B), and cross-check ADS-B positions.
4. **Other signals:** apply the same timing to FM/ATSC towers, the FM two-tower trial, and fox hunts.
5. **Coordinator integration:** solver as a module; results with error ellipses; optional feed to existing MLAT networks.

## Software outputs

- Detector and time model as a `source` module (see SPEC-EXTENSIBILITY).
- Observation format: `gpstime:time_source = pps_marker`, measured `sample_time_uncertainty_s`, the SDR's measured clock error, and annotations marking blanked marker windows.
- Dashboard health: markers per minute, sample-rate error, dropped-sample events, timing uncertainty.
