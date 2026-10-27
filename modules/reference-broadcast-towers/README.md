# reference-broadcast-towers

**Maturity:** experimental, 0.2.0 (#136, #138). Types: reference and source. Spec: `docs/specs/SPEC-EXTENSIBILITY.md` → "Reference modules to build first", item 2; `docs/specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md` §2.

Broadcast transmitters stand still, and their positions are public. With the station's surveyed site, the time a broadcast signal takes to reach the station follows from geometry. This module turns licence records for **FM**, **ATSC digital TV** and **NOAA Weather Radio** into references: a list of transmitters with positions, and a predicted delay to the station with a bound. `analysis-tower-delay-check` compares those predictions with arrival times measured from a capture.

## The cache: offline, built by the operator

The module never fetches anything: it has no network permission. It reads one JSON file, the **tower cache**, that the operator builds in two steps, on any computer:

```sh
cd modules/reference-broadcast-towers
python -m reference_broadcast_towers.fetch --dir ~/towers-downloads
python -m reference_broadcast_towers.build_cache --downloads ~/towers-downloads \
  --near 38.9,-77.1 --radius-km 150 --out ~/towers-cache.json
```

**1. Download (`fetch.py`)** the three national lists. They are whole-country lists, so **no location goes into any request**; the area is chosen offline in step 2.

| List | Source | Size (Oct 2026) |
|---|---|---|
| FM | FCC FM Query, text output (`fmq?serv=FM&list=4`) | ~13,000 records, 6 MB |
| TV | FCC TV Query, text output (`tvq?chan=0&cha2=36&list=4`) | ~11,500 records, 6 MB |
| NOAA Weather Radio | `ccl-data.js`, the data file behind weather.gov/nwr/station_listing | ~1,000 transmitters, 0.75 MB |

- Each file is written atomically, then `fetch-manifest.json` records its URL, retrieval time (UTC), size and SHA-256.
- A failed download, or a reply too short to be the list (an error page), keeps the previous file and its manifest entry.

**2. Build (`build_cache.py`).**
- **Area:** keeps the transmitters within `--radius-km` of `--near`, which is rounded to 0.1° before use. Only that rounded point is stored, so the cache never holds the station's position.
- **Checksums:** checks each download against its manifest SHA-256 and refuses a file that changed since it was downloaded.
- **Provenance:** each transmitter keeps its file, retrieval date and record date. Licence records can be wrong or out of date (the trust spec's rule).
- **Output:** writes the cache atomically.

Copy the result to the station; see "Enable it on a station". **Keep a real cache out of git**: `.gitignore` ignores `towers-cache*.json`, `towers-downloads/` and `fetch-manifest.json` everywhere except the synthetic fixture.

### Formats (told apart by content)

- **FCC text output** (pipe-delimited, no header row):
  - **Field positions:** read by position, from the FCC's own key ("Text output option for AM, FM, and TV Queries", fcc.gov/media/radio/am-fm-tv-textlist-key, updated 2024-02-02). `cache.py` holds the key's field names in order: 38 for FM, 39 for TV. Each position we read is looked up by its name, and a test checks them.
  - **Trailing field:** real lines carry one more trailing identifier than the key lists; it is ignored.
  - **Datum:** the query result pages state "Coordinates are NAD83".
  - **FM services:** full-power FM only. Translators (FX) and low-power FM (FL) are left out, counted as `service_not_used`.
  - **TV services kept:** full-power digital (DTV), Class A digital (DCA), low-power digital (LPD) and digital replacement translators (DRT).
  - **TV services left out:** distributed transmission (DTS: several synchronized transmitters on one channel, so no single delay) and analog LPT records.
  - **Channels and flags:** the RF channel (not the virtual one, which is kept as `virtual_channel`) gives the frequency. ATSC 3.0 stations are flagged `atsc3`; they carry no ATSC 1.0 field sync.
- **NOAA `ccl-data.js`** (`var cclData = [...]`):
  - **Fields used:** call sign, position (4 decimals), frequency (one of the seven NWR channels) and status. `NORMAL` counts as in service; anything else is left out by the module.
  - **Missing:** no antenna height and no datum, so the bounds use the wide defaults.
- **CSV with a header row** (any other export, and the older synthetic fixtures):
  - **Columns:** found by header name, never by position. Case, spaces and punctuation are ignored, and common names are accepted (`Call Sign`, `Facility ID`, `RF Channel`, `LATD`/`LATM`/`LATS`/`N/S`, `RCAMSL`, `HAAT`, `ERP`; full list in `cache.py`).
  - **Each row needs:** a call sign, a position (decimal, or degrees/minutes/seconds with a hemisphere letter) and the frequency or the RF channel.
  - **Older form:** files given one at a time (`--fm`, `--tv`, `--noaa`) need `--retrieved`.

**Duplicates:** a facility can have a licence and an application or construction permit on one frequency. The licensed record is kept, whichever came first. Rejected rows are counted by reason: no call sign, no position, bad position, bad frequency or channel, service not used, duplicate, outside the area.

### A real build (October 2026)

From the national lists retrieved 2026-10-27, for a 150 km area in the mid-Atlantic, the build kept 334 transmitters:
- 187 FM;
- 136 ATSC: 75 licensed, plus permits and applications that the module leaves out;
- 11 NOAA.

The module then accepted 273 licensed or in-service transmitters. Every FM record had RCAMSL and HAAT; 8 ATSC records and every NOAA record had no height. The station's area and the cache stay out of the repository.

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

- `fixtures/fm-fcc-synthetic.txt`, `tv-fcc-synthetic.txt` and `nwr-synthetic.js` are **synthetic** rows in the real FCC text and NOAA layouts (call signs `SYN…`, licensee `SYNTHETIC LICENSEE`). They cover a translator, DTS and analog records, a permit before its licence, ATSC 3.0, a bad RF channel, a non-NWR frequency and a transmitter out of service.
- `fixtures/fm-synthetic.csv`, `tv-synthetic.csv` (degrees/minutes/seconds columns, FCC-style headers) and `noaa-synthetic.csv` are **synthetic**. Their call signs (`SYN…`) and positions are invented around the US Naval Observatory example site, with one row for each rejection reason.
- `fixtures/towers-cache.json` is built from them (marked `SYNTHETIC` in its comment). A test checks that it rebuilds identically.
- `python -m gps_time_pi.modkit demo reference-broadcast-towers` emits the summary and 10 references.
- Tests: `tests/test_reference_broadcast_towers.py`, run with the station's (`tests/test_modules.py`).
