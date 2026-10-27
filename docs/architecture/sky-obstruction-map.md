# Learned sky-obstruction map

Addendum §10–11 (`specs/ADDENDUM-SKY-SOLAR-SATELLITE.md`). Code: `gps_time_pi/skymap.py`, the station's capability record `gps_time_pi/capability.py`. API: `GET /api/sky-obstruction`, `GET /api/capability` (`api/endpoints.md`). UI: GNSS & Site → Sky Obstruction (`web/src/components/skymap.tsx`, `web/src/lib/skymap.ts`); Administration → Capability record.

The station learns which directions its antenna normally hears well, from its own satellites over days, so that a satellite lost in a direction that is normally blocked is not treated as an anomaly.

## What is recorded

The GNSS collector (`gps.py`) passes every fresh SKY report to the map (`gps.add_sky_listener`); HTTP traffic never feeds it. Once a minute, each satellite gpsd lists with an azimuth and elevation is counted in its cell. The grid has 36 × 18 = 648 cells, each 10° of azimuth × 5° of elevation. Each cell keeps five counters:

| Counter | Meaning |
|---|---|
| listed | satellite-minutes in the cell |
| tracked | of those, with C/N₀ > 0 |
| used | of those, used in the fix |
| Σ C/N₀ | sum of C/N₀ of the tracked ones (observed, dB-Hz) |
| Σ C/N₀² | sum of squares, for the spread |

The map also keeps the UTC day numbers that had data, for "learned over N days". All constellations share one grid.

## Storage on the SD card

The map follows the project rule that nothing is written at 1 Hz:

- **In RAM:** the grid itself.
- **Writes:** `sky-obstruction.json`, next to `config.json`, written atomically (temp file, fsync, rename) once an hour and on a clean stop. Nothing is written when the grid has not changed.
- **Capped by design:**
  - the grid has a fixed size;
  - when a cell reaches 20 000 samples, all five of its counters are halved, so old behaviour fades and the numbers stay bounded;
  - at most 400 day numbers are kept.

  The file is about 25 KB when every cell has data.
- **No position and no time of day:** the file holds neither. A file that can't be read, has the wrong format or is over 256 KiB is set aside, never mixed in.

To start again after moving the antenna, stop the service and delete the file. An action for this is not in this version.

## What is inferred (labeled `inferred`)

An antenna hears low satellites worse in every direction, so each cell is compared with the **other cells at the same elevation**. That reference is the median C/N₀ of the classified cells within ±5° of elevation, and at least 4 cells are needed for it. A cell needs at least 20 satellite-minutes to be classified.

| Class | When |
|---|---|
| blocked | 8 dB or more below its band, or tracked less than 50 % of the time (*) |
| attenuated | 4 dB or more below its band, or tracked less than 80 % of the time (*) |
| clear | otherwise |
| unknown | too few samples, or no reference |

(*) The tracked share is used only when the receiver lists satellites it isn't tracking, that is, satellites with C/N₀ 0 (u-blox does). Otherwise it can't be observed, and only C/N₀ is used.

The map is **relative to this station's own sky**. A sky that is equally poor in every direction looks uniform, never "blocked". A cell with no data is "not enough data", never blocked: the station has no orbit model here, so it can't tell an orbital gap from an obstruction.

**Sectors (8 × 45°).** Each column of cells gets a horizon: from 0° upwards, the top of the highest blocked cell below the first clear one. A sector shows one of four states:

- **obstructed:** the median horizon of its columns is at least 10°. It reads "Expected obstruction below ~N°".
- **attenuated:** otherwise, if at least two cells below 60° are weak. It reads "Intermittent attenuation a–b°".
- **clear:** otherwise. It reads "Mostly clear".
- **unknown:** nothing in the sector is classified. It reads "Not enough data".

The map is **learned** after data on 2 days; before that it says "learning".

## Satellite losses (§11)

Each fresh report is compared with the one before, if it is no more than 30 s older. A satellite tracked before and missing (or at C/N₀ 0) now is a loss at its last direction:

| Class | Meaning |
|---|---|
| EXPECTED | the learned map has that cell blocked or attenuated: an expected environmental loss |
| NOT EXPLAINED | the map has it clear; the map does not explain the loss |
| SET | below 5°: the satellite set |
| UNKNOWN | the map has too little data there |

A **sky-wide C/N₀ drop** is flagged when all of these hold in one report:

- at least 4 satellites above 30° are lost or drop by 10 dB or more;
- they lie in at least three quadrants;
- they are at least half of those tracked above 30°.

The note says that the learned map does not explain it and that the evidence does not establish a cause.

Losses and drops are kept in RAM: the last 200 of each, with counts since the service started. They are not written to the card. The map never names a cause (jamming, spoofing, interference, antenna failure): it says only whether a loss fits what this antenna normally sees.

## Privacy

Satellite azimuths and elevations over time constrain the station's position, and the shape of the grid gives its rough latitude (the orbits' gap toward the pole). What each mode allows:

- **Hidden:** nothing is collected, served or exported:
  - `/api/sky-obstruction` answers `available: false`;
  - the capability record and the diagnostics export leave the summary out.

  The file already on the card is kept as it is.
- **Rounded and exact:** the map is shown. Satellite directions are already shown in these modes (`config.privacy_sats`).

## The sky-quality summary (opt-in)

`POST /api/setting {"sky_quality_share": true}` (admin token; off by default) adds a coarse summary to two places:

- the capability record (`GET /api/capability`, `sky_quality`);
- the diagnostics export (`GET /api/diagnostics`, the "sky quality" lines).

The summary holds:

- the state;
- the number of days;
- the share of classified cells that are clear;
- the eight sectors with their state and horizon.

It never holds the grid, any time, or losses. In hidden mode it is left out even when opted in.

## The capability record

`GET /api/capability` is the small record a coordinator join will carry (`specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md` §1, `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md` "Capability records"). It holds:

- **Station ID:** the station key's fingerprint, read from `station-key.pub`.
- **Software version.**
- **Timing:** the state and source from the timing status.
- **GNSS:** the receiver's driver and firmware.
- **SDR:** the SDR roles, never serials.
- **Location:** only at rounded precision, and only in rounded mode. In exact mode none is given ("exact positions are never published"); in hidden mode none.
- **Sky quality:** the opt-in sky-quality summary above.

The station does not send this record anywhere yet. The coordinator tier (ADR-0008) is a skeleton.

## Limits

- The map is an RF horizon, not a physical survey: multipath and the antenna pattern also shape it.
- Constellations are pooled. A sector seen mostly by one constellation carries that constellation's C/N₀ level.
- Nothing has run on a Pi yet: the classes and thresholds come from synthetic tests and the demo.
