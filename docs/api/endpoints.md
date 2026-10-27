# Endpoint reference

Conventions (errors, caching, units, privacy, demo markers) are in [`README.md`](README.md). TypeScript shapes are in `web/src/api/types.ts`; type names are given for each endpoint. The examples come from the desktop demo (`GTP_DEMO=1`) and are abbreviated.

---

## GET /api

Core status. The web UI polls it every 4–5 s. It never depends on the astronomy layer. Type: `CoreStatus`.

| Field | Meaning |
|---|---|
| `epoch_ms`, `utc` | server time when the response was built |
| `timing_status` | the same status as `/api/timing-chain` → `status`; **live mode only** (absent in demo) |
| `quality` | parsed `chronyc -n tracking`: `system_time_s` (chrony's "System time": the correction still being slewed out, signed, + = fast; not the error against UTC), `last_offset_s`, `rms_offset_s`, `root_delay_s`, `root_dispersion_s`, `max_error_bound_s` (calculated: \|system time\| + root dispersion + ½ root delay, chronyc's bound, valid only if the reference is right; null unless all three are known; since #93, GPS-007), plus chrony's text for `frequency` ("x ppm fast/slow"), `residual_freq`, `skew`, `update_interval`, `leap`, `stratum`, `reference`, `ref_time`. `frequency_ppm` appears only in demo payloads. |
| `sources` | `chronyc -n sources` rows: `mode`, `state`, `state_label`, `name`, `stratum`, `poll` (log₂ s), `reach` (octal), `lastrx`, `sample`, `is_self` (the source is one of this station's own addresses, so not an external reference) |
| `sourcestats` | raw `chronyc sourcestats` text |
| `clients` | NTP client rows: `host`, `ntp_packets`, `dropped`, `last`; `[]` = no clients. **`null`** = UNKNOWN: the list couldn't be read. Source: the output of `chronyc -n clients` published every 15 s by `gps-time-pi-chrony-clients.service` (which also publishes `chronyc -n ntpdata` for `/api/references` and `chronyc -n serverstats` for `/api/ntp-service`) (so up to about 15 s old, and ignored after 60 s); without that file, `chronyc` run directly, which works only as root. |
| `gps` | gpsd snapshot: `fix` (null when TPV is stale), `sats[]` (`id`, `gnss`, `el`, `az`, `snr` (C/N₀ dB-Hz; **gpsd's missing value becomes 0**), `used`; in `hidden` privacy mode `el` and `az` are null), `used`, `visible`, `tdop`, `hdop`, `last_fix`, `last_fix_time`, `stale`, `data_age_s`, `sky_stale`, `sky_age_s`. Counts come from the last SKY report even when `sky_stale` is true. |
| `location` | position **after the privacy mode**: `{mode, lat, lon, alt_msl?, alt_hae?}`. exact → 4 decimals, alt_msl and alt_hae; rounded → 1 decimal, alt_msl to 10 m, no alt_hae; hidden → lat/lon null. |
| `survey` | survey statistics: `n`, `n_fresh`, `n_legacy`, `ingest_rule`, `se_horiz_m`, `se_alt_m` (standard error of the mean), `sd_lat_m`, `sd_lon_m`, `sd_alt_m` (per-fix scatter), `updated` |
| `position_provenance` | `live` (current fix), `stored` (saved site), `none`, or `demo` |
| `sidereal` | local sidereal time `HH:MM:SS`, or null without astronomy or a position. Follows the privacy mode: computed from the rounded site in `rounded`, null in `hidden` (LST − GST is the longitude). |
| `timezone` | Zone for local-time **display** (every timestamp in the API stays UTC): `{tz, source, provenance, basis, note}`. `source` is `override` (the operator's setting), `position` (found offline from the station's position; `provenance: calculated`; `basis` is `exact` or `rounded`), or `null` with `tz: null` (the page uses the browser's zone). In `hidden` privacy mode it is never derived from the position. |
| `astro_available` | whether Skyfield/NumPy loaded |
| `astro_reason` | Why astronomy is unavailable (ephemeris missing, not readable by the service user, truncated; NumPy/Skyfield import failure); `null` when available. It can contain the ephemeris file path. |
| `cpu_temp_c` | `/sys/class/thermal/thermal_zone0/temp`, or null |
| `versions` | `app`, `chrony`, `gpsd`, `receiver` ({driver, firmware, path} or null), `python`. `app` is read from the git tag (`gps_time_pi/version.py`): `gps_time_pi/VERSION` in a deploy bundle, else `git describe` in a checkout (e.g. `1.4.0-rc.1`, `1.4.0-rc.1-3-gabc1234`, `-dirty`), else `unknown`. Demo mode reports the real app version. |
| `demo` | `true` only in demo mode |

## GET /api/timing-chain

Stage-by-stage status of GNSS → PPS → chrony, the PPS state machine, the status banner and outage events. Architecture: `docs/architecture/timing-chain.md`. Type: `TimingChain` (`schema: "gps-time.timing-chain/1"`).

**Query.** `scenario=<name>`, demo mode only; ignored live. Names: `pps_selected` (default), `pps_path_anomaly`, `pps_unused_nmea_stale`, `pps_rejected`, `network_failover`, `holdover`, `recovering`, `device_missing`, `chrony_unknown`, `acquiring`.

**Top-level fields:**
- `status`: `{code, headline, banner, detail, source, gnss_healthy, provenance}`. Codes include `GPS_PPS`, `DEGRADED`, `NETWORK_FAILOVER`, `HOLDOVER`, `UNSYNCHRONIZED`, `ACQUIRING`, `UNKNOWN`.
- `pps_state`: a labeled value, e.g. `SELECTED`, `LOST`.
- `pps`: kernel PPS observation. Includes `device`, `device_present`, `pulse_health`, `last_event_utc`, `age_s`, `rate_hz`, `consecutive_pulses`, `missed_pulses` (pulses the kernel never counted, from its sequence number), `unread_pulses` (counted by the kernel but not read one by one; not lost), `poller` (`polls`, `late_polls`, `max_poll_gap_s`: the station's own reads), `interval_stats` and `boot_config` (GPIO and edge from `config.txt`). The counters run from the service start.
- `gnss`: `receiver_comms`, `satellite_reception`, `nav_time_solution`, `healthy`, plus labeled `fix`, `satellites_visible`, `satellites_used`, `best_cn0`, `median_cn0_used`, `tdop`, `data_age_s`.
- `chrony`:
  - `available.{tracking,sources,sourcestats}`
  - `selected.is_self` and `self_sources[]`: chrony sources that are this station's own address. If chrony selects one, the status is `HOLDOVER · NO EXTERNAL REFERENCE · CHRONY SELECTED THIS STATION ITSELF`, never a network failover.
  - `nmea_calibration`: a measured recommendation for the NMEA refclock's `offset` in `chrony.conf`. `{available, reason}`, and when available `configured_offset_s`, `residual_s` (chronyc sourcestats Offset for NMEA while PPS is selected; observed), `std_dev_s`, `samples`, `span_s`, `suggested_offset_s` (configured + residual; calculated), `change_worthwhile`, `advice`. Available only while PPS is the selected source and chrony has at least 16 NMEA samples. The station never edits `chrony.conf`.
  - `refclocks`: identified from `chrony.conf`, never by name alone
  - `pps_status`, `nmea_status`
  - `pps` and `nmea`: per-refclock labeled reach, offset, error bound, frequency, skew and std dev
  - `selected`, `any_selected`
  - `tracking`
- `classification`: `{classification, confidence, boundary, notes}` or null. It is **inferred**, and it names a boundary in the signal path, never a cause.
- `stages[]`: `{id, label, status, summary, evidence}`. `status` is one of `OK`, `DEGRADED`, `FAILED`, `UNKNOWN`, `NOT_OBSERVABLE`, `NOT_APPLICABLE`, `INFO`. `receiver_pps_output` is always `NOT_OBSERVABLE`.
- `events`: `{open, recent[]}`. Each event follows `schema: "gps-time.event/1"`, `type: "PPS_OUTAGE"`, with:
  - `start_utc`, `end_utc`, `duration_s`, `open`, `severity`
  - `classification`, `confidence`, `boundary`, `classification_provenance: "inferred"`
  - `evidence.at_start` and `evidence.latest`, `recovery`, `notes`
  - `start_bound`: present when the true start is earlier than recorded (`boot`, `service_start`)
- `boot`: `phase` (`ACQUIRING`/`RUN`), `boot_utc`, `since_boot_s`, the acquire window, `pps_selected_this_boot`.
- `raw`: raw `chronyc -n` tracking, sources and sourcestats text.
- `demo`: `{scenario, description, scenarios, note}`, demo only.

Reads only; it never changes chrony, gpsd or PPS configuration. Outage events are checkpointed by the background service (`GTP_EVENTS_PATH`), not by this request.

## GET /api/diagnostics

A plain-text (`text/plain; charset=utf-8`) snapshot for support: status, PPS, GNSS, chrony, location, recent events and raw chronyc output. The location line follows the privacy mode. At the end, the "sky quality" lines: the learned sky-obstruction map's sectors when the owner has opted in (`sky_quality_share`) and the mode is not `hidden`; otherwise one line saying why they are not included. Takes the same `scenario` query as `/api/timing-chain` in demo mode. The new UI shows it under Timing → Timing Chain → "Generate & copy".

## GET /api/history

System-clock offset history from chrony's tracking log (`GTP_TRACKING_LOG`, default `/run/chrony-log/tracking.log` or `/var/log/chrony/tracking.log`), downsampled to at most 600 points. Type: `History`.

```json
{"available": true, "points": [{"t": 1790896336.2, "offset_s": 1.741e-07, "offset_sd_s": 1.789e-07, "remaining_correction_s": 2.5e-07,
  "root_delay_s": 1e-09, "root_dispersion_s": 7.005e-06, "max_error_s": 2.612e-05, "freq_ppm": 10.295, "skew_ppm": 0.009,
  "leap": "N", "n_combined": 1, "stratum": 1, "source": "PPS"}], "note": null, "skipped_lines": 0, "columns": ["date", "time", "..."]}
```

- `t` is Unix seconds.
- `offset_s` is the offset chrony logged (observed by chrony, not an independent measurement).
- Since #93 (review GPS-003) every value is one named column of the chrony 4.x `tracking.log` (`chrony.TRACKING_COLUMNS`): `offset_sd_s` ("Offset sd", chrony's standard deviation of the offset), `remaining_correction_s` ("Rem. corr."), `root_delay_s`, `root_dispersion_s`, `max_error_s` ("Max. error", a bound conditional on the reference), `freq_ppm`, `skew_ppm`, `leap`, `n_combined` ("Co", a source count), `stratum`, `source`. There is no combined `err_s` any more, and nothing is substituted when a column is missing.
- A line that doesn't have the 4.x shape, or follows a banner naming other columns, is skipped and counted in `skipped_lines`, with a `note`. The layout is never guessed.

Since rc.9 the log is parsed at most once a minute (the answer is kept for 60 s). If the log is missing, the response is `{"available": false, "points": [], "note": "chrony tracking log not found — add 'log tracking' to chrony.conf"}`. The span covered depends on the log's rotation, so a "7 d" view may show less.

## GET /api/stability

Frequency-stability statistics of the system clock against kernel PPS timestamps: overlapping Allan deviation, modified Allan deviation and time deviation. Type: `Stability`. Background: `architecture/stability-analysis.md`.

```json
{"available": true, "reason": null, "provenance": "calculated",
 "measurement_layer": "System clock against kernel PPS timestamps: ...",
 "confidence": {"level": 0.683, "applies_to": "adev", "method": "...", "noise_provenance": "inferred"},
 "since_utc": "2026-10-05T01:00:00+00:00", "history_resets": 0, "storage": "RAM only; lost when the service restarts",
 "series": {"seconds": {"tau0_s": 1.0, "samples": 3600, "gaps": 0, "span_s": 3600.0, "capacity_s": 14400.0, "pps_selected_fraction": 1.0},
            "minutes": {"tau0_s": 60.0, "samples": 59, "gaps": 0, "span_s": 3540.0, "capacity_s": 1209600.0, "pps_selected_fraction": 1.0}},
 "points": [{"tau_s": 1.0, "series": "seconds", "adev": 4.4e-07, "adev_terms": 3598, "adev_low": 4.3e-07, "adev_high": 4.5e-07,
             "edf": 1800.0, "noise": "white PM", "noise_assumed": false, "mdev": 4.4e-07, "mdev_terms": 3598, "tdev_s": 2.5e-07}],
 "key_points": [{"tau_s": 1.0, "label": "1 s", "point": {"...": "as in points"}, "reason": null},
                {"tau_s": 86400.0, "label": "1 day", "point": null, "reason": "needs about 3 days of PPS history ..."}],
 "notes": []}
```

- `adev` and `mdev` are dimensionless fractional-frequency deviations; `tdev_s` is in seconds.
- `adev_low`/`adev_high` are the confidence interval for ADEV. They are null when the noise type could not be identified. `noise_assumed: true` means the type from a shorter averaging time was kept.
- `mdev` and `tdev_s` are null where the data covers 3 but not 4 averaging times.
- `key_points` always lists 1 s, 10 s, 100 s, 1000 s and 1 day. `point: null` with a `reason` means UNKNOWN: not enough history yet.
- `pps_selected_fraction` is the share of samples taken while chrony had the PPS refclock selected; null when not known.
- With no PPS events: `available: false`, a `reason`, and empty `points`.
- The answer is recomputed at most every 60 s. The history is in RAM and starts again when the service restarts.
- Nothing here depends on the location, so the privacy mode doesn't change it.

## GET /api/shadow

Earth-shadow geometry over the station's sky: where a satellite at a given height is in sunlight, penumbra or umbra. Type: `Shadow`. Background: `architecture/earth-shadow-and-satellites.md`.

Query: `shell` (height in km, 100 to 50000; default 550) selects the shell for `map` and `query`; `az` and `alt` (degrees) ask about one direction.

```json
{"available": true, "reason": null, "provenance": "modeled", "model": "Conical umbra and penumbra ...", "meaning": "...",
 "as_of_utc": "2026-10-06T01:00:00+00:00", "location_display": "exact",
 "sun": {"altitude_deg": -26.94, "azimuth_deg": 289.5, "depression_deg": 26.94, "distance_au": 0.99963,
         "antisolar": {"azimuth_deg": 109.5, "altitude_deg": 26.94}, "note": "geometric altitude, no refraction; ..."},
 "darkness": {"stage": "night", "astronomical_darkness": true},
 "cone": {"umbra_half_angle_deg": 0.2642, "penumbra_half_angle_deg": 0.2691, "umbra_length_km": 1381900, "axis": "..."},
 "zenith": {"umbra_top_km": 762.8, "penumbra_top_km": 796.7, "ground_state": "UMBRA", "beyond_limit": false,
            "search_limit_km": 50000.0, "note": "..."},
 "shells": [{"altitude_km": 550.0, "zenith": "UMBRA", "sunlit_sky_fraction": 0.226, "sunlit_max_altitude_deg": 45,
             "sunlit_sectors": ["N", "SW", "W", "NW"], "summary": "In Earth's shadow above 45° altitude; ..."}],
 "map": {"shell_km": 550.0, "alt_step_deg": 2, "az_step_deg": 5, "alts_deg": [0, 2, "..."], "azs_deg": [0, 5, "..."],
         "rows": ["SSSSUUUU...", "..."]},
 "query": {"azimuth_deg": 300.0, "altitude_deg": 20.0, "shell_km": 550.0, "state": "SUNLIT", "sunlit_fraction": 1.0,
           "range_km": 1294.3, "note": "..."},
 "messages": ["Most satellites at ~550 km LEO should be in Earth's shadow above 45° altitude; ...", "These are geometric predictions ..."]}
```

- States are `SUNLIT`, `PENUMBRA`, `UMBRA`. In `map.rows` they are the characters `S`, `P`, `U`: one string per altitude in `alts_deg`, one character per azimuth in `azs_deg`.
- `zenith.umbra_top_km` and `penumbra_top_km` are null in daylight (`ground_state: "SUNLIT"`), and when the line of sight is still in shadow at `search_limit_km` (`beyond_limit: true`).
- `shells[]` always has 200, 350, 400, 550, 1000, 1200 and 2000 km, plus the requested shell. `sunlit_sky_fraction` covers the sky above 10°, weighted by solid angle. `sunlit_max_altitude_deg` is null when the shell is in shadow everywhere above 10°.
- `query` is null unless both `az` (0 to 360) and `alt` (0 to 90) are valid. An invalid `shell` falls back to 550.
- `sunlit_fraction` inside the penumbra is a linear estimate.
- Everything is `modeled` and geometric: no atmosphere, no refraction. It says whether a satellite there would be sunlit, not that one is there.
- Needs no ephemeris and no Skyfield.
- Privacy: `hidden` → `{"available": false, "reason": "...", "location_display": "hidden"}`; `rounded` → computed from the rounded site. No position → `available: false`.
- Answers are kept for 20 s.

## GET /api/satellites

Individual satellites from the station's cache of orbital elements. Type: `Satellites`. Background: `architecture/earth-shadow-and-satellites.md`.

Query: `sat` (NORAD catalogue number) selects the satellite for `satellite` and `passes`; `q` (up to 40 characters) searches the cache by name or number.

```json
{"available": true, "reason": null, "provenance": "external", "meaning": "...", "as_of_utc": "...", "location_display": "exact",
 "cache": {"dir": "/opt/gps-time-pi/tle", "satellites": 14,
           "groups": [{"group": "stations", "file": "stations.tle", "count": 14, "rejected": 0,
                       "source": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
                       "fetched_utc": "...", "newest_epoch_utc": "...", "oldest_epoch_utc": "..."}],
           "newest_epoch_utc": "...", "newest_age_days": 1.29, "oldest_age_days": 3.4, "stale_after_days": 14.0,
           "problems": [], "provenance": "external"},
 "featured": [{"norad": 25544, "name": "ISS (ZARYA)", "epoch_utc": "...", "age_days": 1.29, "stale": false, "age_note": null,
               "available": true, "provenance": "modeled", "azimuth_deg": 212.4, "altitude_deg": -31.6, "above_horizon": false,
               "range_km": 7480.2, "height_km": 418, "angular_speed_deg_s": 0.051, "state": "SUNLIT",
               "sunlit_fraction": 1.0, "could_be_seen": false}],
 "satellite": {"...": "as in featured"},
 "passes": [{"rise": {"utc": "...", "azimuth_deg": 318.2, "altitude_deg": 0.0, "range_km": 2368.4, "state": "SUNLIT"},
             "culmination": {"...": "..."}, "set": {"...": "..."}, "in_progress": false, "duration_s": 590,
             "shadow_changes": [{"utc": "...", "kind": "umbra entry", "from": "PENUMBRA", "to": "UMBRA",
                                 "azimuth_deg": 99.8, "altitude_deg": 28.9}],
             "visible": {"start_utc": "...", "end_utc": "...", "duration_s": 276, "max_altitude_deg": 48.3, "max_azimuth_deg": 41.7},
             "sun_altitude_deg": -16.3, "provenance": "predicted"}],
 "matches": [], "window_hours": 24.0}
```

- The elements are `external`; a satellite's present position is `modeled`; passes are `predicted`.
- **Age of the elements:** `epoch_utc` and `age_days` on every satellite, `newest_age_days` on the cache. `stale: true` with an `age_note` beyond 14 days.
- `rise` is null for a pass already under way (`in_progress: true`); `set` is null for one still up at the end of the search.
- `shadow_changes[].kind`: `penumbra entry`, `umbra entry`, `umbra exit`, `shadow exit`.
- `visible` is null when there is no interval that meets all three conditions: at least 10° up, not in the umbra, Sun at least 6° below the horizon. It is geometry only.
- Without `sat`, the first of ISS (25544) and CSS (48274) found in the cache is used. A satellite that isn't cached gives `satellite.available: false` with a reason and no passes.
- `available: false` with a `reason` when the cache is empty (the reason says how to fill it), when the `sgp4` package can't be imported, in `hidden` privacy mode, or without a position. `cache` is still reported where it can be.
- The web service never downloads elements. They come from `python -m gps_time_pi.tle_fetch`, run by the operator.
- Up to 10 passes in the next 24 h. Answers are kept for 20 s.
- Demo mode returns a hand-written sample (`demo.note`); it needs no elements.

## GET /api/evidence

Outage evidence files kept on the SD card. Background: `architecture/timing-chain.md` → "Outage evidence on the SD card".

- Without `id`: the index, newest first: `{"available": true, "dir": "...", "files": [{"id": "pps-outage-1792418236", "phase": "closed", "written_utc": "...", "start_utc": "...", "end_utc": "...", "duration_s": 3363, "classification": "GNSS RECEPTION ANOMALY", "bytes": 48213, "tracking_lines": 141, "timeline_points": 397}], "total_bytes": 48213, "max_bytes": 20971520, "max_files": 200, "removed_for_space": 0, "problems": [], "note": "..."}`.
- With `id=<event id>`: the file: `{"schema": "gps-time.evidence/1", "event_id": ..., "phase": "open" | "closed", "written_utc": ..., "window_utc": [from, to], "event": {...}, "timeline_step_s": 10.0, "timeline": [{"t", "status", "pps_state", "pulse_health", "pps_age_s", "missed_pulses", "unread_pulses", "chrony_pps_status", "nmea_status", "selected_source", "system_time_s", "gnss_healthy", "satellites_used", "satellites_visible", "best_cn0"}], "chrony_tracking_lines": ["..."], "chrony_now": {"tracking", "sources", "sourcestats"}, "notes": [...], "privacy": "..."}`. An unknown or invalid id gives `{"available": false, "reason": ...}`.
- `phase: "open"` was written while the outage was still open.
- No position is stored in any file.

## GET /api/oscillator

SoC temperature logged with chrony's frequency estimate, in 10-minute bins. Type: `Oscillator`. Background: `architecture/oscillator-log.md`.

```json
{"available": true, "reason": null, "provenance": "observed", "sensor": "SoC temperature sensor ... not the crystal ...",
 "frequency_note": "...", "bin_s": 600, "sample_interval_s": 60.0,
 "bins": [{"t": "2026-10-19T15:30:00+00:00", "samples": 10, "pps_samples": 10, "temp_mean_c": 53.4, "temp_min_c": 53.1,
           "temp_max_c": 53.8, "freq_mean_ppm": 10.345, "freq_min_ppm": 10.343, "freq_max_ppm": 10.347,
           "skew_mean_ppm": 0.008, "residual_mean_ppm": -0.0}],
 "latest": {"temp_c": {"value": 53.4, "unit": "°C", "provenance": "observed"}, "freq_ppm": {"value": 10.345, "unit": "ppm", "provenance": "observed"},
            "bin_start_utc": "2026-10-19T15:30:00+00:00"},
 "fit": {"bins_used": 288, "slope_ppm_per_c": -0.031, "intercept_ppm": 12.0, "r": -0.82, "temp_span_c": 6.1, "reason": null, "provenance": "calculated"},
 "fit_note": "... not the oscillator profile and not a holdover prediction.",
 "storage": {"path": "/opt/gps-time-pi/oscillator-log.csv", "bytes": 24727, "max_bytes": 4194304, "pending_bins": 3, "flush_interval_s": 3600.0, "note": "..."},
 "board": {"serial_sha256": "a1b2c3d4e5f60718", "model": "Raspberry Pi 4 Model B Rev 1.2"},
 "problems": []}
```

- `freq_*_ppm`: chrony's `Frequency`, + = fast. A bin with `pps_samples < samples` was not under PPS throughout and is not used for `fit`.
- `fit.slope_ppm_per_c` is null with a `reason` until there are 36 PPS bins and a 2 °C temperature range.
- `bins` holds up to 7 days (RAM); the file holds more.
- `board.serial_sha256` is a hash; the serial number itself is never exposed.
- `available: false` until the first 10-minute bin is finished.
- `profile` (modeled): the oscillator profile fitted over the whole log (`gps_time_pi/oscprofile.py`; `architecture/oscillator-log.md` → "The profile fit"). Shape:

```json
{"status": "fitted", "reason": null, "provenance": "modeled", "model": "linear+aging",
 "terms": [{"name": "a", "value": 10.31, "se": 0.0004, "unit": "ppm"}, {"name": "b", "value": -0.031, "se": 0.0002, "unit": "ppm/°C"},
           {"name": "d", "value": 0.004, "se": 0.0005, "unit": "ppm/day"}],
 "bins_used": 1840, "outliers": 3, "residual_rms_ppm": 0.0021, "r2": 0.97, "temp_ref_c": 52.1,
 "t0_utc": "2026-10-20T00:00:00+00:00", "t0_utc_epoch": 1792454400,
 "covers": {"temp_min_c": 47.2, "temp_max_c": 58.9, "first_utc": "...", "last_utc": "...", "first_utc_epoch": 1792454400, "last_utc_epoch": 1793558400, "days": 12.8},
 "candidates": [{"model": "linear", "bic": -21712.4}, {"model": "linear+aging", "bic": -21790.0}],
 "note": "... not a holdover guarantee."}
```

  `status: "insufficient"` with a `reason` until there are 72 PPS bins (12 h) and 3 °C of range; `terms` is then empty.
- `holdover` (modeled; GPS-008): the time to each error threshold if GPS and PPS went away now, three ways (`architecture/oscillator-log.md` → "Holdover projection"). `times_s` has one entry per `thresholds_s`; `null` means never reached under that model. An unavailable projection has `available: false` and a `reason`.

```json
{"provenance": "modeled", "thresholds_s": [1e-06, 1e-05, 0.0001, 0.001, 0.01, 0.1, 1.0], "sample_utc": "2026-10-26T18:20:00+00:00",
 "projections": [
   {"name": "free_running", "provenance": "modeled", "available": true, "rate_ppm": 10.9, "aging_ppm_per_day": 0.0, "times_s": [0.092, "..."], "basis": "..."},
   {"name": "trained_skew", "provenance": "modeled", "available": true, "rate_ppm": 0.008, "aging_ppm_per_day": 0.0, "times_s": [125.0, "..."], "basis": "..."},
   {"name": "profile", "provenance": "modeled", "available": true, "rate_ppm": 3.57, "aging_ppm_per_day": 0.0, "times_s": [0.28, "..."],
    "components_ppm": {"skew": 0.008, "residual_rms": 0.00085, "temperature": 3.56}, "temp_now_c": 44.4, "temp_assumed_c": [43.7, 56.2],
    "temp_source": "the last 24 h's temperature range", "extrapolated": false, "caveat": null, "basis": "..."}],
 "note": "... not measurements and not guarantees ..."}
```

- `profile_files`: `imported` (this board's file, in use) and `reference` (another board's, or one whose board can't be confirmed: reference only, with `warning` and its refitted `profile`), each `null` when absent. Each has `binding` (`match`, `mismatch` or `unverifiable`), `file`, `bins`, `exported_utc`, `board`, `receiver` and `software_version`.

## GET /api/oscillator/profile

The oscillator profile export, as a download (`Content-Disposition: attachment`). Read only; no token. Type: `OscillatorProfileExport`. No position and no raw serial.

```json
{"format": "gps-time-oscillator-profile/1", "exported_utc": "2026-10-26T18:20:00+00:00",
 "board": {"serial_sha256": "a1b2c3d4e5f60718", "model": "Raspberry Pi 4 Model B Rev 1.2"},
 "receiver": {"driver": "u-blox", "firmware": "..."}, "software_version": "1.5.0",
 "profile": {"status": "fitted", "...": "as in /api/oscillator"},
 "fit_bins": {"columns": ["bin_start_utc_epoch", "temp_mean_c", "freq_mean_ppm"], "rows": [[1792454400, 52.31, 10.3412]], "note": "..."},
 "note": "..."}
```

## POST /api/oscillator/profile

Import an export file (the body is the file). It needs the admin token, like every POST, and accepts up to 2 MB. Answers:

- `{"ok": true, "binding": "match", "bins": 1840, "used": true, "detail": "same board: 1840 bins merged into this board's profile"}`
- `{"ok": true, "binding": "mismatch", "bins": 1840, "used": false, "detail": "a different board: kept for reference only; ..."}`. `unverifiable` is treated the same way.
- `400` with `{"ok": false, "error": "..."}` for a file that isn't an export or has a bad row.
- In demo mode: `"simulated": true`, and nothing is saved.

## GET /api/ntp-service

chrony's NTP server counters (`chronyc -n serverstats`) with rates and a short history. Type: `NtpService`. Code: `gps_time_pi/ntpservice.py`.

```json
{"available": true, "reason": null, "provenance": "observed",
 "state": "SERVING", "state_basis": "over the last hour", "state_provenance": "calculated",
 "as_of_utc": "2026-10-05T02:51:00+00:00",
 "counters": {"ntp_received": 50115, "ntp_dropped": 39, "cmd_received": 412, "cmd_dropped": 0, "client_log_dropped": 0},
 "ntp": {"received": {"value": 50115, "unit": "packets", "provenance": "observed"},
         "dropped": {"value": 39, "unit": "packets", "provenance": "observed"},
         "not_dropped": {"value": 50076, "unit": "packets", "provenance": "calculated"},
         "drop_fraction": {"value": 0.00078, "unit": null, "provenance": "calculated"}},
 "rates": {"last_minute": {"received_per_s": {"value": 0.2}, "dropped_per_s": {"value": 0.0}},
           "last_hour": {"received_per_s": {"value": 0.25}, "dropped_per_s": {"value": 0.0003}}},
 "history": [{"t": 1791168432.0, "received_per_min": 12.0, "dropped_per_min": 0.0}],
 "history_info": {"interval_s": 60.0, "max_points": 1440, "storage": "RAM only; lost when the service restarts"},
 "counter_resets": 0, "note": "Counters are chrony's and restart from zero when chronyd restarts."}
```

- The counters are chrony's own and count from when chronyd started. `counter_resets` counts the restarts the station saw; the history starts again at each one.
- `dropped` is chrony's count of packets dropped under its rate limit (the `ratelimit` directive). No other reason is inferred.
- chrony does not count replies. `not_dropped` (received − dropped) is the nearest figure to requests served and is labeled `calculated`.
- `state`: `SERVING`, `SERVING_WITH_DROPS`, `NO_REQUESTS`, judged over the last hour (or the last minute until there is an hour of history; `state_basis` says which), or `UNKNOWN`.
- A rate is null until the history covers its window.
- When the counters can't be read: `available: false`, `state: "UNKNOWN"`, a `reason`, and null `ntp`/`rates`. Never zeros.
- Source: `chrony-serverstats.txt` published every 15 s by `gps-time-pi-chrony-clients.service`; without that file, `chronyc` run directly, which works only as root.

## GET /api/references

The station compared with NTP servers that are not steering its clock. Type: `References`. Background: `architecture/independent-references.md`.

```json
{"available": true, "provenance": "external", "as_of_utc": "2026-10-05T02:44:00+00:00",
 "verdict": {"code": "AGREE", "headline": "STATION AGREES WITH INDEPENDENT REFERENCES",
             "detail": "3 of 3 independent references are within 50 ms of the station.",
             "provenance": "calculated", "threshold_s": 0.05,
             "configured": 3, "usable": 3, "agreeing": 3, "disagreeing": 0, "inconclusive": 0},
 "references": [{"name": "192.0.2.10", "state": "?", "state_label": "not selectable", "stratum": 1, "poll_s": 256,
                 "reach": "377", "reachable": true, "usable": true, "lastrx_s": 30,
                 "offset_s": 0.0026, "error_bound_s": 0.018, "delay_s": 0.031, "root_delay_s": 0.0004,
                 "assessment": "agrees", "provenance": "external",
                 "history": [{"t": 1791168210.0, "offset_s": 0.0026, "error_bound_s": 0.018, "delay_s": 0.031}]}],
 "excluded": [{"name": "198.51.100.7", "why": "chrony has it combined: it is steering the clock, so it is not independent"}],
 "delay_available": true, "delay_note": null,
 "sign": "offset_s is chrony's figure for the last measurement: positive means the station's clock is ahead of that server.",
 "history": {"interval_s": 60.0, "max_points": 1440, "storage": "RAM only; lost when the service restarts"}}
```

- `verdict.code`: `AGREE`, `DISAGREE`, `ONE_REFERENCE`, `NONE_REACHABLE` ("no external references reachable"), `NONE_CONFIGURED`, `UNKNOWN` (chrony unreadable; then `available` is false). The counts are absent for `NONE_CONFIGURED` and `UNKNOWN`.
- A `DISAGREE` reports a difference between clocks. It does not say which clock is wrong or why, and it does not change `/api/timing-chain`.
- `?history=<server>` chooses whose `history` is included; without it, the first independent server that has any. The others carry `history: []` and `history_points` (how many the station holds). Before rc.9 every server's full history was sent, about 1 MB.
- `references[]` holds only independent servers. Servers chrony has selected or combined, and the station's own address, are in `excluded[]` with the reason.
- For a reference that is not `usable`, `offset_s`, `error_bound_s` and `delay_s` are null and `assessment` is `not usable`.
- `assessment`: `agrees`, `disagrees`, `inconclusive` (over the limit but inside the server's own error bound), `not usable`.
- `delay_s` is chrony's "Peer delay" from the helper's published `chronyc -n ntpdata`. null = UNKNOWN; `delay_note` says why when no server has one.
- `threshold_s` is `GTP_REF_DISAGREE_S` (default 0.05).
- Demo mode takes `?scenario=agree|disagree|unreachable|none` and adds a `demo` block. A live station ignores the query.

## GET /api/timescales

Time scales calculated from the station's UTC clock, the leap-second table they depend on, and UT1 − UTC when a cached IERS file exists. Type: `TimeScales`. Code: `gps_time_pi/timescales.py`.

```json
{"provenance": "calculated", "utc": "2026-10-05T02:23:20+00:00", "unix_s": 1791167000,
 "tai_utc_s": {"value": 37, "unit": "s", "provenance": "calculated", "note": "TAI − UTC from the leap-second table"},
 "gps_utc_s": {"value": 18, "unit": "s", "provenance": "calculated", "note": "GPS − UTC = (TAI − UTC) − 19 s"},
 "tai": {"value": "2026-10-05 02:23:57", "unit": null, "provenance": "calculated"},
 "gps": {"time": {"value": "2026-10-05 02:23:38"}, "week": {"value": 2439}, "week_mod_1024": {"value": 391},
         "seconds_of_week": {"value": 95018, "unit": "s"}},
 "mjd": {"value": 61318.099537, "unit": "d"}, "jd": {"value": 2461318.599537, "unit": "d"},
 "leap_seconds": {"provenance": "external", "source": "file", "source_label": "IERS leap-second list from the operating system",
                  "path": "/usr/share/zoneinfo/leap-seconds.list", "updated_utc": "...", "expires_utc": "2026-12-28T00:00:00+00:00",
                  "days_to_expiry": 83.9, "status": "OK", "warning": null, "warn_days": 60.0,
                  "last": {"utc": "2017-01-01T00:00:00+00:00", "tai_utc_s": 37}, "next": null,
                  "next_note": "None scheduled in the table, which is valid until 2026-12-28.",
                  "chrony_leap_status": {"value": "Normal", "unit": null, "provenance": "observed"}, "problems": []},
 "ut1": {"available": false, "provenance": "external", "path": "/opt/gps-time-pi/iers/finals2000A.daily",
         "ut1_utc_s": null, "kind": null, "file_date_utc": null, "reason": "No cached IERS file on the station. ..."}}
```

- Every scale is `calculated` from the system clock, so it is as good as that clock. `/api/timing-chain` says what disciplines it.
- `tai`, `gps` and the two offsets are null before 1972 (the table's start); `gps` is null before 1980-01-06. Null is UNKNOWN, not zero.
- `mjd` and `jd` are UTC-based. During an inserted leap second they repeat the last second of the day, as Unix time does.
- `gps.week` counts from 1980-01-06 without rollover; `week_mod_1024` is the 10-bit number broadcast on L1 C/A.
- `leap_seconds.status`:
  - `OK`: a file was read and expires more than `warn_days` from now (default 60; `GTP_LEAP_EXPIRY_WARN_DAYS`).
  - `EXPIRES_SOON`, `EXPIRED`: with a `warning` that says what to do (update tzdata).
  - `UNKNOWN`: no file could be read and a built-in list ending 2017-01-01 is used, or the file has no expiry line.
- `leap_seconds.next` is the first table entry after now (`kind`: `insert` or `delete`). When there is none, `next_note` says whether the table is valid enough to rule one out.
- `chrony_leap_status` is chrony's own "Leap status" (observed), from the timing chain's last `chronyc -n tracking`.
- `ut1.available` is true only when the file at `GTP_IERS_FILE` (default `/opt/gps-time-pi/iers/finals2000A.daily`) exists and covers today. `kind` says whether the value is an IERS determination or an IERS prediction. The station never downloads this file.
- The file search path is `GTP_LEAP_SECONDS_FILE` (default `/usr/share/zoneinfo/leap-seconds.list`, from Debian's tzdata).
- Nothing here depends on the location. Local sidereal time stays in `/api` → `sidereal` and follows the privacy mode.

## GET /api/survey

Position-survey convergence for the History page. Type: `Survey`.

- `available`: whether a survey history exists.
- `history[]`: `[epoch_s, n, se_horiz_m, se_alt_m]` tuples, at most 720, thinned evenly.
- `fixes[]`: this session's fixes as `[north_m, east_m]` around the mean. No absolute position.
- `stats`: as in `/api` → `survey`.
- `ingest`: accepted and rejected counts by reason, `last_reason`, `collector_running`.
- `persistence`: `loaded_from`, `corrupt_moved_to`, `last_write_utc`, `last_write_error`, `path`, `previous_checkpoint`.
- `note`: a hint while history is building.

`persistence.path` and `previous_checkpoint` expose absolute file paths on the station.

## GET /api/system

Host diagnostics. Each field is null where the platform cannot report it (non-Pi, no `vcgencmd`). Type: `SystemDiagnostics`.

| Field | Source |
|---|---|
| `model`, `kernel` | `/proc/device-tree/model`; `os.uname()` sysname + release |
| `uptime_s`, `load` | `/proc/uptime`, `os.getloadavg()` |
| `mem` | `/proc/meminfo` → `total_mb`, `available_mb`, `used_pct` |
| `disk` | root filesystem → `total_gb`, `free_gb`, `used_pct` |
| `cpu_mhz` | current CPU frequency from cpufreq (sysfs), MHz |
| `core_volts` | `vcgencmd measure_volts core` as text, e.g. `"0.8563V"` (a string, unit included) |
| `throttled` | `vcgencmd get_throttled` → `{raw, flags[{label, active, now}], any_now, any_ever}`; `now:false` flags are "since boot" bits |
| `power` | Pi 5 PMIC only: `{volts, amps, watts}` on the 5 V input; null elsewhere |
| `power_note` | explains `power` |
| `ramlog` | chrony tracking log location: `path`, `in_ram`, `size_kb`, `flushed_age_s` (last copy to SD) |

## GET /api/almanac

Sun, moon, night and sky map for one date at the observing site. The site is the live fix, or the stored site when there is no live fix. Type: `Almanac | Unavailable`.

**Privacy mode.** Every value here is a function of the position, so the endpoint follows `location_display`:
- `exact`: computed from the site.
- `rounded`: computed only from the rounded site that `/api` → `location` shows (1 decimal ≈ 11 km, MSL altitude to 10 m, no ellipsoidal height).
- `hidden`: `{"available": false, "reason": "Location is hidden by the station's privacy setting. …", "location_display": "hidden"}`, with nothing computed. This applies in demo mode too.

Available responses include `location_display`.

**Query:**
- `date=YYYY-MM-DD`: default today (UTC); supported 1850-01-01 to 2149-12-31.
- `tz=<IANA zone>`: default `UTC`; an unknown zone falls back to `UTC`.
- `at=now|HH:MM`: time for the sky map; default `now`.

**Unavailable:** `{"available": false, "reason": "..."}` when Skyfield/NumPy are not installed, the date is out of range, or there is no position.

**Available** (all times are ISO 8601 with offset, in `tz`):
- `sun`: `{date, tz, events{astro_dawn, naut_dawn, civil_dawn, sunrise, sunset, civil_dusk, naut_dusk, astro_dusk}, noon, daylight_s, bar[], notes[]}`.
- `moon`: `{rise, set, transit, transit_alt, phase, illum (%), age_days, up_s}`.
- `night`: `{defined, sunset, sunrise, span_s, sun_segments, moon_up[], dark[], dark_total_s, midnight, astro_note, tz}`, or `{defined: false, note}`. Fractions are of the elapsed night.
- `/app/` Sun & Moon draws `sun.bar` and `night` and passes `date` from its date navigation.
- `target` (optional): an object query as `/api/object` reads `q`; `sky.target` is its `[alt, az]`, else `null`. Only the requesting client's target is marked.
- `delta_yesterday`: today − yesterday daylight, in s.
- `delta_tomorrow`: tomorrow − today daylight, in s.
- `neighbors.{yesterday,tomorrow}.{sunrise, sunset, noon, daylight_s}` (predicted, like `sun`). The web UI shows the day-to-day shifts from these.
- `sky`: `{stars, lines, bodies, target}`.
- `sky_when`, `position_provenance`, `position_age`.
- `demo: true` in demo mode.

**Unavailable:** `{available: false, reason}`. The reason is the privacy mode, no position, the ephemeris or library problem from `astro_reason`, or `Astronomy calculation failed (<error>)` when a calculation raised (the traceback is in the journal). `/api/object` answers the same way.

Every value is **predicted** (computed from ephemerides for the date).

Since rc.9 the day-level parts of `/api/almanac` (sun for yesterday, today and tomorrow, daylight deltas, moon, night) are computed once per date, zone and site and kept for 6 hours, and the sky snapshot for a minute. Identical requests that arrive during a computation wait for it instead of starting their own. On the Pi a full almanac took about 15 s of CPU.

## GET /api/object

Look up one object for the almanac's object card. `q` accepts a Messier number, star name, planet, or `RA Dec` in J2000 degrees. `date`, `tz` and `at` work as in `/api/almanac`.

**Responses:**
- `{"error": "unparsed"}` if `q` is not understood. This is HTTP 200, and the typed client raises `ApiError`.
- `{"available": false, "reason": "..."}` without astronomy or a position.
- Otherwise:
  - `now_alt`, `now_az`
  - `rise`, `transit`, `transit_alt`, `set`, `circumpolar`, `never_up`
  - `dark_windows[]`, `moonless_windows[]`, `min_alt_deg`, `tz`
  - `name`, `meta`, `emphasis` (`dark` / `moonless` / `both`), `at_label`

**Privacy mode:** as for `/api/almanac`. Rounded mode computes from the rounded site. Hidden mode returns `available: false` with the privacy reason, computes nothing and computes nothing. Available responses include `location_display`.

**No side effect** (since #88; GPS-030): the station keeps no target. To mark the object on the sky map, pass the same text as `target=` to `/api/almanac`. The web UI's Sky & Objects tab does.

## GET /api/ping

```json
{"server_receive_epoch_ms": 1790907077246.781, "server_send_epoch_ms": 1790907077246.781}
```

The server side of an NTP-like four-timestamp exchange. The client records t1 before sending and t4 on receipt:
- offset = ((t2 − t1) + (t3 − t4)) / 2
- delay = (t4 − t1) − (t3 − t2)

Add a cache-busting query (`?n=<random>`); the server ignores it. The estimate assumes a symmetric path and is limited by browser timer resolution, so the UI labels the offset **inferred** and the RTT **observed**. Implementation: `pingOnce()` in `web/src/api/client.ts`.

## GET /api/auth

Whether admin is enabled and whether the request's `Authorization` header is valid. It never returns the token or its hash. Type: `AuthState`.

```json
{"demo": false, "auth_required": true, "admin_configured": true, "authenticated": false}
```

- `auth_required` is false only in demo mode.
- `authenticated` is always true in demo mode.

## POST /api/setting

Changes a station setting. JSON body; admin token (outside demo). `GET /api/setting` returns 405.

| Body | Effect | Response |
|---|---|---|
| `{"location_display": "exact" \| "rounded" \| "hidden"}` | sets the location privacy mode in `config.json` | `{"ok": true, "location_display": "<mode>"}` |
| `{"timezone": "<IANA name>"}` or `{"timezone": null}` | sets or clears the local-time display zone override in `config.json`. Display only; the system clock stays on UTC. An unknown name gets **400**. | `{"ok": true, "timezone": "<name>" \| null}` |
| `{"sky_quality_share": true \| false}` | opt-in (default off): the sky-quality summary in `GET /api/capability` and `GET /api/diagnostics`. Never in `hidden` mode. A value that isn't a boolean gets **400** | `{"ok": true, "sky_quality_share": <bool>}` |
| `{"reset_site": true}` | **discards the stored position survey** | `{"ok": true, "reset_site": true}` |
| `{"modules_experimental": true \| false}` | the experimental modules switch. Either way `modules_enabled` is cleared, so every module is off afterwards | `{"ok": true, "modules_experimental": <bool>, "modules_enabled": []}` |
| `{"module": "<name>", "enabled": true \| false}` | one module on or off. On needs the switch (**409** otherwise), an installed module (**404**) and a valid manifest (**409**). Off always works | `{"ok": true, "module": "<name>", "enabled": <bool>, "modules_enabled": [...]}` |
| `{"module": "<name>", "config": {...} \| null}` | the module's settings (`module_config.<name>`); `null` clears them, back to the manifest defaults. Never turns a module on. Refused with **400**: not an object, over 8 KiB, a key the manifest's `[config]` doesn't declare, a value of the wrong type (`float`, `int`, `string`/`path` up to 300 characters, `table`), or a position-like key at any depth (`lat`, `lon`, `alt_m`, `site`…); **404** not installed; **409** invalid manifest. A change restarts the supervisor's module set | `{"ok": true, "module": "<name>", "config": {...}}` |
| anything else | nothing | **400** `{"ok": false, "error": "expected location_display, timezone, sky_quality_share, reset_site, modules_experimental or module"}` |

The new UI uses `location_display` (Administration → Location privacy) and `timezone` (Administration → Local time zone). `reset_site` is on Administration → Position survey (typed confirmation). The module settings are on Administration → Experimental modules. `sky_quality_share` is on Administration → Capability record.

## GET /api/modules

The experimental modules switch, every module installed in the modules folder and each one's setting. Read only, no token. Facts come from each module's manifest (`module.toml`); the web service never imports module code. Type: `ModulesState` (`web/src/api/types.ts`). Code: `gps_time_pi/modkit/settings.py`.

```json
{"experimental": true,
 "modules": [{"name": "sdr-pps-marker", "installed": true, "valid": true, "errors": [], "version": "0.1.0",
              "maturity": "research", "types": ["source"], "summary": "...",
              "permissions": {"network": false, "devices": [], "storage": "none"},
              "enabled": true, "runs": true, "host_runs": true, "state": "running", "reason": null,
              "config": {"fs_nominal": 2400000},
              "config_schema": {"fs_nominal": {"type": "float", "unit": "Hz", "description": "SDR sample rate as set"}},
              "readiness": [{"check": "rtl_tcp running", "ok": true, "detail": "active"},
                            {"check": "PPS injected at the dongle", "ok": null, "detail": "not observable from here: ..."}],
              "latest": {"kind": "observation", "time_ns": 1793026812000000000, "age_s": 3.0, "items_kept": 20,
                         "values": {"markers": {"value": 10, "unit": null, "provenance": "observed"},
                                    "clock_error_ppm": {"value": 23.0, "unit": "ppm", "provenance": "calculated"}},
                         "left_out": 0}}],
 "supervisor": {"reporting": false, "age_s": null, "detail": "no status from gps-time-modules (not running, or not readable)"},
 "note": "..."}
```

- `enabled`: the owner turned it on. `runs`: the switch is on, the module is enabled, its manifest is valid and it has a `source` entry, so the supervisor is asked to run it.
- `host_runs`: whether the module host runs this module at all. It is `false` for a module without a `source` entry (an analysis, such as `analysis-tower-delay-check`, which runs from its own command line). The UI then says so, rather than showing a state.
- `state`, `reason` (observed): from the supervisor's status file in `/run/gps-time-modules/` (`GTP_MODULES_STATUS`). Shown only while the supervisor reports, at most 60 s old; otherwise `null`, which the UI shows as UNKNOWN, never as stopped.
- `latest`: the newest item the module emitted, from the same status file (the supervisor keeps each module's last 20 in RAM). `null` while the supervisor isn't reporting.
  - **What it gives:** `kind` (`observation` or `result`), `time_ns`, `age_s`, `items_kept`, and up to 40 `values`, each with its unit, its provenance label and any note (cut to 300 characters).
  - **What is left out, and counted in `left_out`:** a value without one of the six provenance labels (never relabeled), one that isn't a single value, and **any position-like value** (`lat`, `lon`, `alt_m`, `position` and the like). Positions aren't shown here, whatever a module emits.
- A module named in `modules_enabled` but not installed is listed with `installed: false`.
- `config`: the owner's settings for it (`module_config`; `{}` = the manifest's defaults). `config_schema`: what its manifest declares under `[config]` (type, unit, default, description).
- `readiness`: for the SDR modules, what each needs that the station can observe, from `/api/sdr` (`gps_time_pi/sdr.py`); `null` for other modules. `ok` is `true` or `false` as observed, and `null` (UNKNOWN) for what can't be observed from the web service, such as the PPS injected at the dongle.
  - `sdr-pps-marker`: `gps-time-rtl-tcp.service` active; `fs_nominal` and an `rtl_tcp` plan in its settings; the injected PPS (always `null`).
  - `reference-adsb`: the 1090 and 978 MHz `aircraft.json` written within 60 s; at least one of them.

## GET /api/sdr

The optional SDR stack (`docs/deploy/sdr-stack.md`), read only, no token. The web service starts, stops and configures none of it. Code: `gps_time_pi/sdr.py`; type `SdrStatus`. Built at most once every 5 s, with one `systemctl show` (no privilege needed).

```json
{"installed": true,
 "units": [{"unit": "gps-time-readsb.service", "what": "readsb (1090 MHz)",
            "active": {"value": "active", "unit": null, "provenance": "observed"}, "sub": "running", "enabled": "enabled",
            "restarts": {"value": 0, "unit": "count", "provenance": "observed"},
            "cpu_s": {"value": 2950.1, "unit": "s", "provenance": "observed"},
            "cpu_avg_pct": {"value": 22.8, "unit": "% of one core", "provenance": "calculated"},
            "memory_mib": {"value": 21.4, "unit": "MiB", "provenance": "observed"}}],
 "dongles": [{"port": "1-1.2", "serial": "00001090", "product": "RTL2838UHIDIR", "role": "1090 MHz",
              "speed_mbps": {"value": 480, "unit": "Mb/s", "provenance": "observed"},
              "dvb_driver": {"value": false, "unit": null, "provenance": "observed"}}],
 "feeds": [{"band": "1090", "path": "/run/readsb/aircraft.json", "present": true,
            "age_s": {"value": 0.6, "unit": "s", "provenance": "observed"},
            "aircraft": {"value": 23, "unit": "count", "provenance": "observed"}, "fresh": true}],
 "note": "Read only: ..."}
```

- `units`: the four SDR units, readsb's own package unit and the module supervisor, when installed. For a running unit:
  - `cpu_s` and `memory_mib` come from its cgroup (`cpu.stat`, `memory.current`);
  - `cpu_avg_pct` is CPU time divided by the time since the unit started, in % of one core (calculated).
  - `null` (UNKNOWN) when not running or not readable. `units` is `null` when `systemctl` can't be run, and then `installed` is `null` too.
- `dongles`: RTL2832U devices (USB IDs `0bda:2838`, `0bda:2832`) from `/sys/bus/usb/devices`. `role` is the role whose serial matches `/etc/default/gps-time-sdr`. `dvb_driver` is true when the DVB-T driver holds the device. `null` when sysfs can't be read.
- `feeds`: each decoder's `aircraft.json`: age since it was last written, and how many aircraft are in it. **No position is read out**. `fresh`: written within 60 s.

## GET /api/sky-obstruction

The learned sky-obstruction map (addendum §10–11; `architecture/sky-obstruction-map.md`). No token. Code: `gps_time_pi/skymap.py`; type `SkyObstructionResult`. Everything in it is `inferred` from observed C/N₀; it never names a cause.

```json
{"available": true, "format": "gps-time-sky-obstruction/1", "az_step": 10, "el_step": 5,
 "summary": {"days": 12, "satellite_minutes": 92592, "reports_sampled": 17280, "cells_total": 648,
             "cells_with_data": 564, "cells_classified": 564, "clear_pct": 93, "state": "learned", "untracked_reported": true},
 "sectors": [{"sector": "W", "az_centre": 270, "state": "obstructed", "text": "Expected obstruction below ~30°",
              "below_deg": 30, "cells_classified": 68, "cells": 68, "cn0_median": 32.5, "provenance": "inferred"}],
 "cells": [{"az0": 270, "el0": 20, "samples": 64, "tracked_pct": 35, "used_pct": 28, "cn0_mean": 31.6, "cn0_sd": 2.0,
            "band_median": 42.6, "delta_db": -11.0, "class": "blocked"}],
 "losses": {"counts": {"EXPECTED": 3, "NOT EXPLAINED": 1, "UNKNOWN": 0, "SET": 1}, "since": "service start",
            "recent": [{"utc": "2026-10-27T11:20:00Z", "gnss": "GPS", "sat": 14, "az": 272.0, "el": 18.0, "cn0_before": 24.0,
                        "class": "EXPECTED", "note": "expected environmental loss: this direction is normally blocked here",
                        "provenance": "inferred"}]},
 "sky_wide": {"count": 0, "recent": []},
 "thresholds": {"min_cell_samples": 20, "blocked_db": 8.0, "attenuated_db": 4.0, "blocked_tracked": 0.5,
                "attenuated_tracked": 0.8, "learned_days": 2},
 "file": {"name": "sky-obstruction.json", "last_write_utc": "2026-10-27T11:00:00Z", "unsaved": true, "problems": []},
 "note": "Learned from this station's own satellites: ...", "provenance": "inferred", "location_display": "exact"}
```

- `cells`: every cell with data. `class` is `clear`, `attenuated`, `blocked` or `unknown` (too few samples or no reference). `delta_db` is the cell's mean C/N₀ minus the median of its elevation band (±5°). `tracked_pct` is used for the class only when `summary.untracked_reported` is true (the receiver lists satellites it isn't tracking).
- `sectors`: eight 45° sectors; `state` `obstructed` (with `below_deg`), `attenuated`, `clear` or `unknown`.
- `losses`: a satellite tracked in one fresh report and gone (or at C/N₀ 0) in the next, at most 30 s later: `EXPECTED` (the cell is blocked or attenuated), `NOT EXPLAINED` (the cell is clear), `SET` (below 5°), `UNKNOWN` (too little data there). RAM only, the last 200, counted since the service started.
- `sky_wide`: a report where at least 4 satellites above 30°, in at least 3 quadrants and at least half of those tracked there, were lost or dropped by 10 dB. The note says the map does not explain it and that the evidence does not establish a cause.
- **Hidden mode:** `{"available": false, "reason": "...", "location_display": "hidden"}`. Nothing is collected either.

## GET /api/capability

The station's capability record (`gps_time_pi/capability.py`), the form a coordinator join will carry. No token. It never holds an exact position. Type `Capability`.

```json
{"format": "gps-time-capability/1", "generated_utc": "2026-10-27T12:00:00Z",
 "station_id": "ed25519:<sha-256 of the public key>", "software_version": "1.6.0-rc.1",
 "timing": {"state": "GPS_PPS", "source": "PPS", "provenance": "calculated"},
 "gnss": {"driver": "u-blox", "firmware": "..."},
 "sdr": {"installed": true, "receivers": [{"role": "1090 MHz"}]},
 "location": {"precision": "exact", "lat": null, "lon": null,
              "note": "exact positions are never published in the capability record; choose rounded to share one"},
 "sky_quality_opt_in": false, "sky_quality": null,
 "sky_quality_note": "off (opt-in: POST /api/setting {\"sky_quality_share\": true})",
 "availability": "owner only"}
```

- `station_id`: from `station-key.pub`; `null` without a key.
- `location`: latitude and longitude only in `rounded` mode, to 0.1°; `null` in `exact` and `hidden`.
- `sdr.receivers`: roles only, never serials.
- `sky_quality`: when opted in and not `hidden`: `{state, days, clear_pct, cells_classified, sectors: [{sector, state, below_deg}], provenance: "inferred", note}`. Never the grid, any time, or losses.

## POST /api/admin

Runs a management action. JSON body `{"action": "<name>"}`; admin token (outside demo). `GET /api/admin` returns 405. Actions are fixed argv lists (`system.ACTIONS`, `system.DELAYED`), with no shell and no arguments taken from the request. Each is authorized by the polkit rule `system/50-gps-time-pi.rules`.

| `action` | Runs | Response `detail` |
|---|---|---|
| `flush_logs` | `systemctl start gps-time-pi-logflush.service` (root oneshot that copies the RAM log to SD) | stderr/stdout (≤ 300 chars) |
| `restart_gpsd` | `systemctl restart gpsd.service` | stderr/stdout |
| `restart_chrony` | `systemctl restart chrony.service` | stderr/stdout |
| `restart_web` | `systemctl restart gps-time-pi.service`, detached, after 1 s | `restarting in 1 s` |
| `reboot` | `systemctl reboot`, detached, after 2 s | `rebooting in 2 s` |
| other | nothing | `unknown action` (`ok: false`) |

Response: `{"ok": bool, "action": "<action>", "detail": "..."}`. In demo mode the response is `{"ok": true, "action": "...", "simulated": true, "detail": "demo mode: <action> was not executed"}` and nothing runs. The web UI has these actions on Administration → Station actions (`/app/`).

---

## GET /app/

The new web UI: the React app built into `web/dist` (`cd web && corepack pnpm run build`). Decision: `docs/decisions/ADR-0004-web-ui-at-app.md`.

- `/app` redirects (301) to `/app/`, keeping the query.
- `/app/` and `/app/index.html` return `index.html` with `Cache-Control: no-store`.
- `/app/assets/*` (Vite content-hashed names) return `public, max-age=31536000, immutable`. Other files return `max-age=300`.
- Content types come from the extension: `.js`, `.css`, `.woff2`, `.svg`, `.png`, `.json`, … (`server._WEB_TYPES`).
- A path whose last segment has no extension (a client-side route) returns `index.html`. A missing file with an extension returns 404.
- Paths that resolve outside the dist directory (`..`, encoded `%2e%2e`, backslashes, symlinks pointing out) or contain NUL return 404.
- If `web/dist/index.html` does not exist, every `/app/` path returns **503** `text/plain` with build instructions.

**Location.**
- `GTP_WEB_DIST` sets the directory; the default is `<repo>/web/dist` next to the `gps_time_pi` package.
- Files are read per request and never written.
- The deploy bundle ships `web/dist`, and `install.sh` copies it to `/opt/gps-time-pi/web/dist`.

**Data source.** Add `?source=demo` to run the UI on the client-side demo adapter with no API calls. See [README](README.md#using-the-api-from-the-web-ui).

## GET / and the retired page paths

`/` and the paths of the retired legacy pages (`/legacy`, `/almanac`, `/history`, `/admin`, `/configure`, `/zones`) return **302** to `/app/`, keeping the query string, so old bookmarks land on the web UI. The legacy pages, `/static/*` (including `/static/custom.css`) and `/api/dashboard` were removed after v1.4.0; `/static/*` now returns 404.

## GET /time

`text/plain` UTC timestamp with microseconds and a newline, e.g. `2026-10-02 02:11:15.701151 UTC`.

---

## Privacy notes

- **Applied by the server:**
  - `/api` → `timezone`: in `hidden` mode the zone is never derived from the position (a zone narrows the position to a region); `rounded` mode uses the rounded position. The operator's override is returned in every mode, as their own choice;
  - `/api` → `location`;
  - `/api` → `sidereal`;
  - `/api` → `gps.sats`: azimuth and elevation are null in `hidden` (`config.privacy_sats()`); kept in `exact` and `rounded`;
  - `/api/almanac` and `/api/object`: rounded site in `rounded`, nothing in `hidden`;
  - `/api/diagnostics`;
  - `/api/sky-obstruction`: nothing in `hidden` (not collected either); `/api/capability`: a position only in `rounded`, the sky-quality summary never in `hidden`.
  - Helper: `config.privacy_site()`, the same rounding as `config.displayed_location()`. Tests: `tests/test_location_privacy.py`.
- **Not positions:** `/api/survey` → `fixes` are relative offsets; `stats` are scatter magnitudes.
- **Residual, by design:** in `hidden` mode `/api` still lists which satellites are tracked and their C/N₀. The set of satellites above the horizon at a given time still narrows the position, but only coarsely: far more than the ~11 km of `rounded` mode. The precision has not been quantified. The list is kept so that GNSS health stays visible; drop it too if that residual is unacceptable.
- **File paths:** `/api/survey` → `persistence.path`/`previous_checkpoint` expose absolute paths on the station.
