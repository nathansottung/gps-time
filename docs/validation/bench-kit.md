# Bench kit

**Status:** list, 2026-10-26 (#127). Models are examples, not endorsements. Check current specifications on the maker's datasheet before buying. No prices, because they change.

What it takes to validate a station's timing from outside the Pi: [`second-pulse.md`](second-pulse.md) (system clock against PPS), and a second station ([`../deploy/second-station.md`](../deploy/second-station.md)). The station parts themselves are in [`../hardware/HARDWARE-REFERENCE-NODE.md`](../hardware/HARDWARE-REFERENCE-NODE.md).

## Level 1: system clock against PPS (second pulse)

Enough to run `secpulse` and `pps_compare`.

| Item | Need | Examples | Notes |
|---|---|---|---|
| **Time-interval counter** *or* scope | one of them | see the two rows below | a counter is simpler for long runs; a scope shows the edges |
| Time-interval counter | single-shot time-interval resolution of 1 ns or better, two inputs, CSV/USB/LAN logging | used HP/Agilent 53131A or 53132A; Keysight 53220A/53230A; Pendulum CNT-90/91 | check that it logs one reading per second for hours. Older counters may need GPIB; plan the logging |
| Oscilloscope | 2 channels, ≥ 100 MHz, ≥ 1 GSa/s, delay measurement with logging or export | Rigol DS1000Z family; Siglent SDS1000X-E family | export of a measurement per trigger varies by model; test a short run first |
| Probes | 2 × 10× passive, or short coax to 1 MΩ inputs | the scope's own probes | measure each channel's delay, or use equal lengths |
| BNC tee and short coax | tap the receiver's PPS without moving it | BNC T, RG-58 patch leads | keep the tap high impedance (1 MΩ input) |
| Header-to-BNC lead | the Pi's GPIO pin and a ground pin to BNC | Dupont-to-BNC lead, or a small adapter board | short; a 3.3 V output into 1 MΩ |
| Line driver (only for 50 Ω inputs) | buffer the Pi's 3.3 V output | a 74LVC1G125-class buffer with a series resistor, or a PPS distribution amplifier | a bare Pi pin into 50 Ω is a heavy load with a slow edge |

## Level 2: an independent reference

To say anything about PPS against UTC. Choose at least one.

| Item | What it adds | Examples | Notes |
|---|---|---|---|
| Second GNSS receiver with its own PPS | another receiver on the same sky; a receiver-specific error shows as a difference | ZED-F9T timing board; a second MAX-M8Q board | both receivers still use GNSS; a shared error (antenna, site, constellation) doesn't show |
| GNSS-disciplined oscillator (GPSDO) with 1 PPS and 10 MHz outputs | a reference that holds through short GNSS outages, and a 10 MHz timebase for the counter | Leo Bodnar GPS reference clocks; Trimble Thunderbolt-class units (used) | disciplined by GNSS too; its holdover is what makes it independent during an outage |
| 10 MHz reference into the counter | the counter's timebase stops being the weak link on long runs | the GPSDO's 10 MHz output | only if the counter has an external reference input |

## For a second station sharing an antenna (setup A)

| Item | Need | Notes |
|---|---|---|
| GNSS splitter, 2-way, active | one port passes DC to the antenna, the other has a DC block with a load | two receivers powering one antenna can damage one; check which port passes DC |
| Matched short GNSS cables | equal lengths from splitter to each receiver | or measure each and record the difference |

## Recording

- **Cable delays:** measure them (a scope with a tee and an open end, or the counter) or use equal lengths. Note the coax type: about 5 ns per metre for solid-PE coax.
- **What was connected:** channel A, channel B, trigger levels and slopes, the instrument's timebase (internal or 10 MHz), the date. `pps_compare` prints what it assumed; keep that with the result.
- **Keep instrument files outside the repository.** They are real station data. Only summaries go into the docs, as for the soak runs.
