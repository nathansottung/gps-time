# Observation files

One file format for any timed measurement: SigMF (a binary data file plus a JSON metadata file) with a `gpstime:` extension. Spec: [`../specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md`](../specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md), Part 1. Code: [`gps_time_pi/obsformat.py`](../../gps_time_pi/obsformat.py) (standard library only). Schema of the global object: [`schemas/sigmf-gpstime.v1.json`](../../schemas/sigmf-gpstime.v1.json).

## Files

```
<station>_<sensor>_<start-utc>.sigmf-data   samples
<station>_<sensor>_<start-utc>.sigmf-meta   global, captures, annotations (JSON)
```

`obsformat.filename(station_id, sensor, start_ns)` makes the name.

## Write, read, check

```python
from gps_time_pi import obsformat as of

meta = of.build_meta(datatype="cf32_le", sample_rate=2.4e6, recorder="my-module 0.1.0",
                     captures=[{"core:sample_start": 0, "core:frequency": 100.1e6,
                                "core:datetime": of.format_ns(t0_ns)}],
                     gpstime={...})                       # the gpstime:* fields below, without the prefix
of.write(base, meta, of.encode(samples, "cf32_le"))      # data, then metadata with its SHA-256; each atomic
meta, data = of.read(base)
errors, warnings = of.validate(base)
of.sample_time(meta, index)                              # (UTC ns, sample uncertainty s) or None
```

From the shell:

```bash
python -m gps_time_pi.obsformat validate <base>    # exit 1 if invalid
python -m gps_time_pi.obsformat info <base>
```

## The rule

**The time of every sample that claims one must be computable.** A sample's time comes from its capture:
- the capture's `core:datetime` (ISO 8601 UTC, up to 9 fraction digits, `Z`);
- its `core:sample_start`;
- its sample rate: the capture's `gpstime:sample_rate` when present, else `core:sample_rate`.

The uncertainty comes from `gpstime:sample_time_uncertainty_s`; add the station's `gpstime:time_offset_bound_s` for the total.

Samples that have no time are in a capture with `"gpstime:time_valid": false` and no `core:datetime`. Examples: samples before a time reference is found, or across dropped samples. The validator checks that consecutive timed captures agree with their sample rates.

## Datatypes

| Datatype | Samples | Use |
|---|---|---|
| `cf32_le` | complex float32 | IQ |
| `ci16_le` | complex int16 (raw counts) | IQ, compact |
| `cu8` | complex uint8 (raw counts 0–255) | RTL-SDR native IQ |
| `rf32_le` | real float32 | audio, infrasound, seismic |
| `ri16_le` | real int16 (raw counts) | audio, compact |

In SigMF, `c` means complex and `r` means real. Use `ci16_le` for IQ, not `ri16_le` (the spec's example names `ri16_le` for RF IQ).

## gpstime: fields (all required)

| Field | Meaning |
|---|---|
| `gpstime:schema` | `"1"` |
| `gpstime:station_id` | The station (its key fingerprint once station keys exist) |
| `gpstime:sensor` | `rf`, `audio`, `infrasound`, `seismic`, `magnetic`, `optical`, `particle`, `weather`, `other` |
| `gpstime:quantity`, `gpstime:unit` | What a sample measures |
| `gpstime:channels` | `[{"name": ...}, ...]` |
| `gpstime:time_source` | `pps`, `ntp`, `mlat_calibrated`, `free_running`, `pps_marker` |
| `gpstime:time_offset_bound_s` | The station's clock error bound (null when unknown: warning) |
| `gpstime:sample_time_uncertainty_s` | Extra uncertainty from the sensor path (null when unknown: warning) |
| `gpstime:frequency_reference` | `{"state": "free" \| "calibrated" \| "gpsdo", "error_ppm", "source"}` |
| `gpstime:calibration` | Sensor response, gain, delays, or null |
| `gpstime:position` | `{"privacy": "exact" \| "rounded" \| "hidden", "lat", "lon"[, "alt_m", "uncertainty_m"]}`. Hidden carries no position; rounded carries at most 1 decimal and the altitude to 10 m (the station's privacy rule) |
| `gpstime:provenance` | `observed` for raw samples |
| `gpstime:request_id` | The capture request it answers, or null |
| `gpstime:licence` | Default `CC-BY-4.0` |
| `gpstime:checksum` | `sha256:<hex>` of the data file (set by `write`) |
| `gpstime:signature` | Null until station keys exist: the validator warns "unsigned" |

RF observations need `core:frequency` on every capture.

## Not yet

- Signatures: they need station keys, which come with the coordinator spec.
- Converters to miniSEED and WAV.
- Rolling buffers and capture requests (Part 2 of the spec).

## Example: sdr-pps-marker

`sdr_pps_marker.observation.to_observation(samples, model, ...)` writes a capture timed by PPS markers:
- `gpstime:time_source = pps_marker`.
- One capture per interval between markers, each with its UTC time and measured sample rate, so the file's sample times match the time model to the nanosecond.
- No time before the first marker, after the last, or across dropped samples.
- The SDR clock's measured error is in `frequency_reference`.
- Each marker window is annotated `pps_marker`, so analyses can blank it.
