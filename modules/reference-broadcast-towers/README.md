# reference-broadcast-towers

**Maturity:** experimental, 0.1.0 (#136). Types: reference and source. Spec: `docs/specs/SPEC-EXTENSIBILITY.md` → "Reference modules to build first", item 2; `docs/specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md` §2.

Broadcast transmitters stand still, and their positions are public. With the station's surveyed site, the time a broadcast signal takes to reach the station follows from geometry. This module turns licence records for **FM**, **ATSC digital TV** and **NOAA Weather Radio** into references: a list of transmitters with positions, and a predicted delay to the station with a bound. `analysis-tower-delay-check` compares those predictions with arrival times measured from a capture.

## The cache: offline, built by the operator

The module never fetches anything: it has no network permission. It reads one JSON file, the **tower cache**, that the operator builds from exported records:

```sh
cd modules/reference-broadcast-towers
python -m reference_broadcast_towers.build_cache \
  --fm fm.csv --tv tv.csv --noaa nwr.csv \
  --near 38.9,-77.1 --radius-km 150 --retrieved 2026-10-26 \
  --out /var/lib/gps-time/towers-cache.json
```

- **FM and ATSC:** export the FCC FM Query and TV Query results for the area as CSV with a header row.
- **NOAA:** the NOAA Weather Radio transmitter list, as CSV.
- **Columns are matched by header name, never by position.** Case, spaces and punctuation are ignored, and common names are accepted (`Call Sign`, `Facility ID`, `RF Channel`, `LATD`/`LATM`/`LATS`/`N/S`, `RCAMSL`, `HAAT`, `ERP`; full list in `cache.py`). A column the export doesn't have is simply absent. The FCC's own text layout wasn't checked against an official key for this release, so no position-based parser is included. Rename the headers if your export's names differ.
- **Each row needs:**
  - a call sign;
  - a position, either decimal or degrees/minutes/seconds with a hemisphere letter;
  - FM: the frequency, 88.1 to 107.9 MHz;
  - ATSC: the **RF** channel, 2 to 36 (not the virtual channel);
  - NOAA: one of the seven channels, 162.400 to 162.550 MHz.
- **Optional:** facility ID, datum, radiation centre above sea level (`rc_amsl_m`), HAAT, ERP, status, record date.
- **Kept with each transmitter:** where it came from (file name, SHA-256, retrieval date) and the record's own date. Licence records can be wrong or out of date (the trust spec's rule).
- **Rejected rows are counted by reason:** no call sign, no position, bad position, bad frequency or channel, duplicate, outside the area.
- **Privacy:** `--near` is rounded to 0.1° before use, and only that rounded point is stored. The cache never holds the station's position.

## What it does with each transmitter

- **Left out (counted):** a status other than licensed (`LIC`; a construction permit is left out), a service switched off (`services`), or farther than `max_range_km` (150 km).
- **Delay** (`calculated`): the straight-line range from the site to the antenna (WGS84 ECEF), at c × (1 + 300 × 10⁻⁶) for the air near the ground.
- **Bound** (`calculated`): an approximate 95 % bound, root-sum-square of:
  - the transmitter's position: 30 m for NAD83/WGS84 records given to 1″; 100 m for NAD27 or no datum (the NAD27 shift isn't applied);
  - its height: 5 m with `rc_amsl_m` and the site's height above sea level known (both in the same frame); 60 m with only the site's ellipsoidal height; 300 m without `rc_amsl_m`;
  - the air: ±60 × 10⁻⁶ of the range;
  - in rounded privacy mode, the site's rounding (about ±7 km, which dominates).
- **Line of sight** (`inferred`): within the radio horizon for a 4/3 Earth, from the tower's HAAT and an assumed 10 m receiving antenna. It is unknown without a HAAT. Beyond the horizon the signal arrives by diffraction or scatter, and the straight-line delay is a lower bound.
- **Not modelled,** as the note says:
  - multipath;
  - over-the-horizon paths;
  - **the transmitter's own emission timing.** A licence record doesn't say when a broadcast leaves the antenna, so a single tower's absolute delay can't be checked. An analysis compares arrival-time **differences** between towers, or calibrates the offset out.

## Privacy

- The site comes only from `ctx.site()`, already filtered by the station's privacy mode.
- **Hidden:** nothing is predicted. The module emits only counts, with `site_available` false.
- **Rounded:** the module predicts from the rounded site and adds its rounding to the bound.
- The module never outputs the site. Transmitter positions are public records.

## What it emits

Every `interval_s` (an hour; the cache is read again only when its file changes):

- **A summary:**
  - per service, the transmitters in the cache and those accepted;
  - rejections by reason;
  - the cache's build time and age, and `cache_stale` once it is older than `max_cache_age_days` (365);
  - whether a site was available;
  - any problem reading the cache.
- **One observation per accepted transmitter,** best-bounded first, at most `max_per_service` (10) per service:
  - `external`: `transmitter` (service:facility:kHz), `frequency_hz`, `bandwidth_hz`, `lat`, `lon`, `alt_m`;
  - `calculated`: `delay_s`, `uncertainty_s`, `range_m`, `elevation_deg`;
  - `inferred`: `line_of_sight`.

Without a cache it emits the summary with the problem and nothing else. An enabled module never invents transmitters.

## Enable it on a station

1. Build the cache (above) and copy it to `/var/lib/gps-time/towers-cache.json`, readable by every user.
2. Copy this folder to `/opt/gps-time-pi/modules/reference-broadcast-towers/` (`sudo chmod -R a+rX`).
3. Administration → Experimental modules: turn the switch on, then this module. Paths and limits go in `module_config` in the station config.
4. `gps-time-modules.service` must be enabled (`docs/modules/README.md`). No drop-in is needed: the module needs no device and no network.

## Fixtures and tests

- `fixtures/fm-synthetic.csv`, `tv-synthetic.csv` (degrees/minutes/seconds columns, FCC-style headers) and `noaa-synthetic.csv` are **synthetic**. Their call signs (`SYN…`) and positions are invented around the US Naval Observatory example site, with one row for each rejection reason.
- `fixtures/towers-cache.json` is built from them (marked `SYNTHETIC` in its comment). A test checks that it rebuilds identically.
- `python -m gps_time_pi.modkit demo reference-broadcast-towers` emits the summary and 10 references.
- Tests: `tests/test_reference_broadcast_towers.py`, run with the station's (`tests/test_modules.py`).
