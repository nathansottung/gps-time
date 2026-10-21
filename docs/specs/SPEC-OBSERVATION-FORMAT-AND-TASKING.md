# SPEC — Universal Observation Format and Cross-Station Capture Requests

## Status

NEXT (format), PLANNED (tasking). Builds on SPEC-EXTENSIBILITY.md, SPEC-COORDINATOR.md and SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md.

## Goal

1. One file format for any timed measurement, whether radio, sound, ground motion, pressure, light or particles, so the same tools can store, share, align and analyze them.
2. One way for a station to ask nearby stations to **capture** the same moment, whatever their sensor, so arrival times can be compared.

"Request" here always means a request to **record**. Stations never transmit on request. Any transmission (e.g. an amateur beacon for a fox hunt) is done by a licensed operator under their own licence, outside this system.

---

## Part 1 — The observation format

### Choice

Build on **SigMF** (Signal Metadata Format): an open standard that pairs a binary data file with a JSON metadata file. It already handles any sampled data type, supports named extensions, and has existing tools. GPS Time adds one extension namespace, `gpstime:`, for timing quality, station and sensor details.

An observation is two files with the same name:

```
<station>_<sensor>_<start-utc>.sigmf-data   samples (binary)
<station>_<sensor>_<start-utc>.sigmf-meta   metadata (JSON)
```

Bundles of several observations, or of one event across stations, are a SigMF Collection (`.sigmf-collection`) or a tar archive of the pairs.

### Required metadata

Standard SigMF fields:

- `core:datatype` (e.g. `ri16_le` for RF IQ, `rf32_le` for real float samples)
- `core:sample_rate` (Hz)
- `core:version`, `core:recorder`, `core:hw`, `core:description`
- `captures[]`: `core:sample_start`, `core:datetime` (UTC, ISO 8601 with nanoseconds), `core:frequency` (RF only)
- `annotations[]`: marked events within the capture (detections, picks)

`gpstime:` extension, required on every observation:

| Field | Meaning |
|---|---|
| `gpstime:schema` | extension version |
| `gpstime:station_id` | public key fingerprint of the station |
| `gpstime:sensor` | `rf`, `audio`, `infrasound`, `seismic`, `magnetic`, `optical`, `particle`, `weather`, other |
| `gpstime:quantity` / `gpstime:unit` | what each sample measures, in SI units (V, Pa, m/s, T, counts…) |
| `gpstime:channels` | channel names and orientation (e.g. seismic Z/N/E) |
| `gpstime:time_source` | `pps`, `ntp`, `mlat_calibrated`, `free_running` |
| `gpstime:time_offset_bound_s` | the station's bound on its clock error at capture time |
| `gpstime:sample_time_uncertainty_s` | extra uncertainty from the sensor path (e.g. USB buffering) |
| `gpstime:frequency_reference` | `free`, `calibrated`, `gpsdo` (with ppm or ×10⁻ⁿ error) |
| `gpstime:calibration` | sensor response or gain, with source and date |
| `gpstime:position` | position at the sharing level the owner chose, with uncertainty and privacy level |
| `gpstime:provenance` | `observed` for raw samples; derived files say how they were made |
| `gpstime:request_id` | the capture request this answers, if any |
| `gpstime:licence` | data licence (default CC BY 4.0) |
| `gpstime:checksum` | SHA-256 of the data file |
| `gpstime:signature` | station's signature over metadata and checksum |

Rule: **the time of every sample must be computable** from `core:datetime`, `core:sample_start` and `core:sample_rate`, together with its uncertainty from the two uncertainty fields.

### Export to domain formats

Converters, not replacements, so data flows into existing networks:

- seismic and infrasound → miniSEED (Raspberry Shake, FDSN tools)
- GNSS → RINEX
- audio → WAV/FLAC with a sidecar `.sigmf-meta`
- RF stays SigMF

### Events and results

Short detections (a lightning sferic, a thunder onset, an aircraft message) are stored as `annotations` in the capture, or as standalone JSON events using the station's event model, with the same `gpstime:` timing fields. Results from analysis carry inputs (observation IDs), method, uncertainty and provenance.

### Size and privacy

- Captures are short by default (seconds). Long recordings are opt-in and size-capped.
- Content of private communications is never captured on purpose and never stored. Broadcast and amateur signals only, except where the owner records their own signals.
- Positions follow the owner's privacy setting; exact positions never leave the station without consent.

---

## Part 2 — Capture requests across stations

### Capability records

Each station publishes (see SPEC-RF-TASKING) its sensors, extended beyond RF:

- sensor types, ranges (frequency, bandwidth, sample rate, passband)
- timing quality (`time_source`, typical offset bound)
- approximate location, at the owner's chosen precision
- what others may request: allowed sensors, bands, maximum duration, rate limits

### A capture request

Signed JSON:

- `request_id`, requester ID
- target: sensor type, and for RF the frequency, bandwidth and sample rate
- `start_utc` (a few seconds ahead) and duration, or a trigger ("save the last 30 s of buffer around time T")
- area of interest (stations within N km of a rounded point), or named stations
- purpose (logged)
- return: full observation, or features only

### Two modes

1. **Scheduled:** "Record 162.550 MHz from 14:03:20.000 for 0.5 s." All stations capture together.
2. **Look-back:** stations keep a short rolling buffer (seconds to minutes) per sensor. A request for a past moment (a lightning flash, a meteor, a quake) is answered from the buffer. This is how events nobody predicted get captured by everyone.

### Flow

1. Requester sends to the coordinator.
2. Coordinator selects stations by capability and area, forwards the request.
3. Each station checks its owner's rules and accepts or declines.
4. Stations capture (or cut from the buffer), write observations in the format above, sign and upload them.
5. Coordinator aligns all observations on UTC using their timing fields and runs the analysis (TDOA, MLAT, lightning or thunder location).
6. The result, with uncertainty and the list of contributing observations, goes back to the requester and contributors.

### Logging

Every request, decision and upload is logged on both station and coordinator: who asked, what, when, accepted or declined, and which files left the station. Owners can see this log in the dashboard.

## Part 3 — Analysis independent of signal type

Analyses work on the shared structure, not the sensor:

- **Arrival-time pick:** find when a feature arrives in a capture, with uncertainty.
- **Cross-correlation:** align two captures of the same signal.
- **Locate:** given arrival times, station positions, uncertainties and a propagation speed (radio, sound with weather correction, seismic velocity), solve for the source.

The propagation model is the only part that changes with sensor type. Each is a module.

## Order of work

1. Format: `gpstime:` extension schema, writer, reader, validator, converters to miniSEED and WAV.
2. Rolling buffers on the station for enabled sensors.
3. Single-owner capture requests (Stage A).
4. Generic pick, correlate and locate analyses.
5. Trusted groups and third parties (Stages B and C).
