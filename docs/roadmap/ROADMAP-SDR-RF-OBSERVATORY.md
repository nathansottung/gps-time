# ROADMAP — SDR and RF Observatory

## Status

SCOPING. Not scheduled. Pi timing work and the first Pi deploy come first.

## Goal

Use the station's precise time and frequency to make SDR observations that are timestamped and frequency-calibrated, so results from one station can be trusted and later compared across stations.

Follows the project rules: offline-first, provenance on every value, no claimed causes the evidence can't support, and the Pi tier stays light.

## Hardware tiers

| Tier | Example hardware | Timing quality | Notes |
|---|---|---|---|
| Basic | RTL-SDR v4 | Sample clock free-running; timestamps from host clock | Good for ADS-B, WWV listening, meteor counts |
| Disciplined | SDR with external 10 MHz input (Airspy with clock mod, SDRplay RSPdx, HackRF + clock) | Frequency locked to a GPS reference | Needs a GPSDO or a disciplined 10 MHz source |
| Lab | USRP B2xx/N2xx with GPSDO | Sample-accurate time and frequency | Best results; costs the most |

The current Pi HAT gives PPS but no 10 MHz output. A disciplined tier needs a separate GPSDO, or a receiver with a programmable timepulse set to 10 MHz, with care about its jitter.

## Software

- **GNU Radio** for processing flowgraphs, run as services with fixed configs.
- **SoapySDR** as the device layer so flowgraphs don't care which SDR is attached.
- A small station-side agent that tags each recording or detection with UTC, the station's timing state at that moment (from the timing chain), and the frequency reference state.
- Results become events in the existing event model.

## Candidate observations

1. **WWV/WWVH time comparison.** Measure the tick arrival time against PPS. Expect ms-level results, dominated by ionospheric path delay; label as observed with path delay modeled.
2. **Frequency calibration.** Measure the SDR's own ppm error against a known carrier (WWV 10 MHz, or the GPS reference). Store per device.
3. **Meteor scatter.** Count echoes from a distant FM or radar transmitter. Timestamp each echo; compare counts with known meteor showers.
4. **Lightning sferics (VLF).** Timestamp impulses. Single-station gives rates only; direction or location needs multiple stations (coordinator tier).
5. **ADS-B.** Already on the roadmap; timestamps feed future multilateration.
6. **Hydrogen line (1420 MHz).** Needs a dish or horn; good outreach project.
7. **Spectrum watch around GNSS bands.** Passive noise-floor logging near L1 to give context to GNSS integrity events. Never call a raised noise floor jamming.

## Related precise-timing measurements (not SDR)

- **Grid frequency.** A 9 V AC wall adapter through an optocoupler into a GPIO pin; timestamp zero crossings against PPS for mHz-level mains frequency. Never connect mains directly. Optional multi-station comparison later.
- **Oscilloscope checks.** Use PPS as a trigger and timebase reference for checking a scope, and log the result.

## Resource tiers

- **Pi:** event tagging, light detectors (ADS-B decode, tick timing, grid frequency).
- **Coordinator or a stronger host:** heavy GNU Radio flowgraphs, waterfall storage, multi-station correlation, meteor and sferic analysis.

## UI

- RF Observatory page shows each receiver, its frequency reference state, calibration, and recent events.
- Every value carries a provenance tag. Uncalibrated receivers are labeled as such.

## Open questions

- Which SDR to buy first.
- Whether to add a GPSDO with 10 MHz out, or rely on PPS-only timestamping at first.
- Which observations to build first. Suggested order: frequency calibration, WWV comparison, grid frequency, meteor scatter.
