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

In SigMF, `c` means complex and `r` means real: use `ci16_le` (or `cf32_le`, `cu8`) for IQ, and the `r` types for real samples.

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
| `gpstime:public_key` | The signing station's Ed25519 public key (base64), or null |
| `gpstime:signature` | `ed25519:<base64>` over the metadata, or null (the validator warns "unsigned") |

RF observations need `core:frequency` on every capture.

## Signing

Each station has an Ed25519 key pair, made once at install (`gps_time_pi/station_key.py`):
- **Private key:** `/opt/gps-time-pi/station-key`, 0600, owned by `gps-time`. The module user can't read it.
- **Public key:** `station-key.pub`.
- **Station ID:** `ed25519:<SHA-256 of the public key>`.

```python
from gps_time_pi import station_key
of.write(base, meta, data, signer=station_key.load())     # sets station_id, public_key, signature
of.validate(base, trusted=["ed25519:..."])                # verifies; warns if the station isn't trusted
```

```bash
python -m gps_time_pi.station_key show                     # this station's ID and public key
python -m gps_time_pi.station_key sign <base>              # sign an existing file (as gps-time)
python -m gps_time_pi.station_key verify <base> --trust ed25519:...
```

- **What is signed:** the canonical JSON of the metadata (sorted keys, no spaces) with the signature set to null. The metadata includes `gpstime:checksum`, so the signature covers the samples too.
- **What the validator reports:**
  - errors: any change after signing, a public key that doesn't match the station ID, or changed samples;
  - warnings: unsigned files, a valid signature from a station not in the trusted list, and signatures it can't check (no `cryptography` package).

## Converting to WAV and miniSEED

Converters, not replacements: the observation file stays the record. Code: [`gps_time_pi/convert.py`](../../gps_time_pi/convert.py).

```bash
python -m gps_time_pi.convert wav <base> <out_base> [--sign]
python -m gps_time_pi.convert miniseed <base> <out.mseed> --net XX --sta GTP01 --loc 00 --cha HDF
```

**WAV** (audio, IQ):
- 16-bit PCM: mono for real samples, stereo I/Q for complex.
- A sidecar `<out_base>.sigmf-meta` points at the WAV (`core:dataset`, `core:header_bytes` 44) and keeps the original captures, so every sample keeps its UTC time exactly. It records `gpstime:derived_from` (source checksum, station, signature, method) and the scale in `gpstime:calibration`.
- The original signature doesn't carry over; `--sign` signs the sidecar with this station's key.
- WAV can only hold an integer sample rate; the sidecar keeps the exact one.

**miniSEED 2** (seismic, infrasound, other real samples):
- 512-byte big-endian records: INT32 from `ri16_le`, FLOAT32 from `rf32_le`. Complex data is refused, and so is a non-integer nominal rate.
- Each record's start time comes from the observation's own timing, to 1 µs (BTIME plus blockette 1001). Blockette 100 carries the measured rate.
- Samples without a time are left out, as a gap.
- The I/O flag "clock locked" is set for `pps` and `pps_marker` time sources. Timing quality is not set (0).
- `<out>.gpstime.json` keeps what miniSEED has no field for: station ID, source checksum and signature, uncertainties, provenance.
- Checked against ObsPy 1.5.1: codes, start times, rates, encodings, samples and gaps read back as written (`tests/test_convert.py`, skipped where ObsPy isn't installed).

## Not yet

- Rolling buffers and capture requests (Part 2 of the spec).

## Example: sdr-pps-marker

`sdr_pps_marker.observation.to_observation(samples, model, ...)` writes a capture timed by PPS markers:
- `gpstime:time_source = pps_marker`.
- One capture per interval between markers, each with its UTC time and measured sample rate, so the file's sample times match the time model to the nanosecond.
- No time before the first marker, after the last, or across dropped samples.
- The SDR clock's measured error is in `frequency_reference`.
- Each marker window is annotated `pps_marker`, so analyses can blank it.
