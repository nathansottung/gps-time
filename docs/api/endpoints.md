# Endpoint reference

Conventions (errors, caching, units, privacy, demo markers) are in [`README.md`](README.md). TypeScript shapes are in `web/src/api/types.ts`; type names are given for each endpoint. The examples come from the desktop demo (`GTP_DEMO=1`) and are abbreviated.

---

## GET /api

Core status. The legacy pages and the new UI poll it every 4–5 s. It never depends on the astronomy layer. Type: `CoreStatus`.

| Field | Meaning |
|---|---|
| `epoch_ms`, `utc` | server time when the response was built |
| `state` | `[headline, "banner — detail"]` from the timing-status logic |
| `timing_status` | the same status as `/api/timing-chain` → `status`; **live mode only** (absent in demo) |
| `quality` | parsed `chronyc -n tracking`: `system_time_s` (signed, + = system clock fast), `last_offset_s`, `rms_offset_s`, `root_delay_s`, `root_dispersion_s`, plus chrony's text for `frequency` ("x ppm fast/slow"), `residual_freq`, `skew`, `update_interval`, `leap`, `stratum`, `reference`, `ref_time`. `frequency_ppm` appears only in demo payloads. |
| `fmt` | the server's human-readable strings for the legacy pages |
| `sources` | `chronyc -n sources` rows: `mode`, `state`, `state_label`, `name`, `stratum`, `poll` (log₂ s), `reach` (octal), `lastrx`, `sample`, `is_self` (the source is one of this station's own addresses, so not an external reference) |
| `sourcestats` | raw `chronyc sourcestats` text |
| `clients` | NTP client rows: `host`, `ntp_packets`, `dropped`, `last`; `[]` = no clients. **`null`** = UNKNOWN: the list couldn't be read. Source: the output of `chronyc -n clients` published every 15 s by `gps-time-pi-chrony-clients.service` (so up to about 15 s old, and ignored after 60 s); without that file, `chronyc` run directly, which works only as root. |
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
- `pps`: kernel PPS observation. Includes `device`, `device_present`, `pulse_health`, `last_event_utc`, `age_s`, `rate_hz`, `consecutive_pulses`, `missed_pulses`, `interval_stats` and `boot_config` (GPIO and edge from `config.txt`).
- `gnss`: `receiver_comms`, `satellite_reception`, `nav_time_solution`, `healthy`, plus labeled `fix`, `satellites_visible`, `satellites_used`, `best_cn0`, `median_cn0_used`, `tdop`, `data_age_s`.
- `chrony`:
  - `available.{tracking,sources,sourcestats}`
  - `selected.is_self` and `self_sources[]`: chrony sources that are this station's own address. If chrony selects one, the status is `HOLDOVER · NO EXTERNAL REFERENCE · CHRONY SELECTED THIS STATION ITSELF`, never a network failover.
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

A plain-text (`text/plain; charset=utf-8`) snapshot for support: status, PPS, GNSS, chrony, location, recent events and raw chronyc output. The location line follows the privacy mode. Takes the same `scenario` query as `/api/timing-chain` in demo mode. The new UI shows it under Timing → Timing Chain → "Generate & copy".

## GET /api/history

System-clock offset history from chrony's tracking log (`GTP_TRACKING_LOG`, default `/run/chrony-log/tracking.log` or `/var/log/chrony/tracking.log`), downsampled to at most 600 points. Type: `History`.

```json
{"available": true, "points": [{"t": 1790896336.2, "offset_s": 1.2e-08, "err_s": 5e-07}], "note": null}
```

- `t` is Unix seconds.
- `offset_s` is the offset chrony logged (observed by chrony, not an independent measurement).
- `err_s` is the logged error bound, or null.

If the log is missing, the response is `{"available": false, "points": [], "note": "chrony tracking log not found — add 'log tracking' to chrony.conf"}`. The span covered depends on the log's rotation, so a "7 d" view may show less.

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
- `night`: `{defined, sunset, sunrise, span_s, sun_segments, moon_up[], dark[]}`, or `{defined: false, note}`.
- `delta_yesterday`: today − yesterday daylight, in s.
- `delta_tomorrow`: tomorrow − today daylight, in s.
- `neighbors.{yesterday,tomorrow}.{sunrise, sunset, noon, daylight_s}` (predicted, like `sun`). The web UI shows the day-to-day shifts from these.
- `sky`: `{stars, lines, bodies, target}`.
- `sky_when`, `position_provenance`, `position_age`.
- `demo: true` in demo mode.

**Unavailable:** `{available: false, reason}`. The reason is the privacy mode, no position, the ephemeris or library problem from `astro_reason`, or `Astronomy calculation failed (<error>)` when a calculation raised (the traceback is in the journal). `/api/object` answers the same way.

Every value is **predicted** (computed from ephemerides for the date).

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

**Privacy mode:** as for `/api/almanac`. Rounded mode computes from the rounded site. Hidden mode returns `available: false` with the privacy reason, computes nothing and does not set the target. Available responses include `location_display`.

**Side effect:** the target is stored in a server-global (`_LAST_TARGET`) that `/api/almanac` uses to mark the sky map. It is shared by all clients. Not exposed in the new UI client.

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

## GET /api/dashboard

The legacy dashboard layout (the widget model of `/` and `/configure`) plus metadata. Type: `DashboardConfig`.

```json
{"schema_version": 1, "title": "GPS Time",
 "pages": [{"id": "overview", "title": "Overview", "widgets": [{"id": "time", "visible": true, "size": "wide"}]}],
 "_meta": {"writable": true, "auth_required": true, "demo": false, "path": null, "known_widgets": ["adsb", "…"]}}
```

- `_meta.writable` is true in demo mode, or when an admin token is configured. Writes still need the token.
- `_meta.path` is set only in demo mode.

## POST /api/dashboard

Body: a layout (`DashboardLayout`). It goes through the request checks in [README → Authentication](README.md#authentication-and-request-checks), so it needs the admin token outside demo mode.

It is validated by `dashboard.validate()`:
- at least 1 page and at most 20;
- unique slug ids;
- every page has a title and a widget list.

On success it is saved to `dashboard.json` (`GTP_DASHBOARD_CONFIG`, or next to `GTP_CONFIG`). Response: `{"ok": true, "dashboard": <normalized>}`, or HTTP 200 `{"ok": false, "error": "..."}` on a validation error.

`GTP_ALLOW_CONFIG_WRITE` and the loopback exception were removed. Behind a reverse proxy every client looked like loopback, so the token is now the only gate.

## POST /api/dashboard/reset

Body `{}`. Restores and saves the default layout. Same checks and response as above.

## POST /api/setting

Changes a station setting. JSON body; admin token (outside demo). `GET /api/setting` returns 405.

| Body | Effect | Response |
|---|---|---|
| `{"location_display": "exact" \| "rounded" \| "hidden"}` | sets the location privacy mode in `config.json` | `{"ok": true, "location_display": "<mode>"}` |
| `{"timezone": "<IANA name>"}` or `{"timezone": null}` | sets or clears the local-time display zone override in `config.json`. Display only; the system clock stays on UTC. An unknown name gets **400**. | `{"ok": true, "timezone": "<name>" \| null}` |
| `{"reset_site": true}` | **discards the stored position survey** | `{"ok": true, "reset_site": true}` |
| anything else | nothing | **400** `{"ok": false, "error": "expected location_display, timezone or reset_site"}` |

The new UI uses `location_display` (Administration → Location privacy) and `timezone` (Administration → Local time zone). Survey reset remains on the legacy `/admin` page.

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

Response: `{"ok": bool, "action": "<action>", "detail": "..."}`. In demo mode the response is `{"ok": true, "action": "...", "simulated": true, "detail": "demo mode: <action> was not executed"}` and nothing runs. The new UI's client has `admin()`; its buttons are still only on the legacy `/admin` page.

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
- `install.sh` and the deploy bundle do not yet copy `web/dist` to the Pi. Until they do, set `GTP_WEB_DIST` on the Pi or copy the build next to the package.

**Data source.** Add `?source=demo` to run the UI on the client-side demo adapter with no API calls. See [README](README.md#using-the-api-from-the-web-ui).

## Legacy pages

HTML from `gps_time_pi/templates/`, served with `no-store`. They stay until the new UI reaches parity (`docs/dashboard/web-ui-parity.md`).

| Path | Page | APIs used |
|---|---|---|
| `/` | configurable dashboard | `/api`, `/api/dashboard`, `/api/almanac`, `/api/ping` |
| `/configure` | layout editor (admin token prompt) | `/api/dashboard` (GET/POST), `/api/dashboard/reset`, `/api/auth` |
| `/legacy` | instrument view | `/api` |
| `/almanac` | sun, moon, night, sky map, object lookup | `/api/almanac`, `/api/object` |
| `/history` | offset chart, survey convergence | `/api/history`, `/api/survey` |
| `/admin` | system diagnostics, actions, privacy, survey reset (admin token prompt) | `/api/system`, `/api/admin`, `/api/setting`, `/api/auth`, `/api` |
| `/zones` | server-rendered IANA time-zone table (current offsets) | none |

`templates/index.html` is not served; it is an older copy of `legacy.html`.

## GET /time

`text/plain` UTC timestamp with microseconds and a newline, e.g. `2026-10-02 02:11:15.701151 UTC`.

## GET /static/*

- `/static/<file>`: legacy CSS and JS from `gps_time_pi/static/`, `max-age=300`. Only the basename is used, so subdirectories and `..` are ignored.
- `/static/custom.css`: `custom.css` from the directory holding `GTP_CONFIG`, or a placeholder comment. Every legacy page links it, so a station can restyle the legacy pages without editing the package.

---

## Privacy notes

- **Applied by the server:**
  - `/api` → `timezone`: in `hidden` mode the zone is never derived from the position (a zone narrows the position to a region); `rounded` mode uses the rounded position. The operator's override is returned in every mode, as their own choice;
  - `/api` → `location`;
  - `/api` → `sidereal`;
  - `/api` → `gps.sats`: azimuth and elevation are null in `hidden` (`config.privacy_sats()`); kept in `exact` and `rounded`;
  - `/api/almanac` and `/api/object`: rounded site in `rounded`, nothing in `hidden`;
  - `/api/diagnostics`;
  - the legacy location blocks.
  - Helper: `config.privacy_site()`, the same rounding as `config.displayed_location()`. Tests: `tests/test_location_privacy.py`.
- **Not positions:** `/api/survey` → `fixes` are relative offsets; `stats` are scatter magnitudes.
- **Residual, by design:** in `hidden` mode `/api` still lists which satellites are tracked and their C/N₀. The set of satellites above the horizon at a given time still narrows the position, but only coarsely: far more than the ~11 km of `rounded` mode. The precision has not been quantified. The list is kept so that GNSS health stays visible; drop it too if that residual is unacceptable.
- **File paths:** `/api/survey` → `persistence.path`/`previous_checkpoint`, and `/api/dashboard` → `_meta.path` in demo mode, expose absolute paths on the station.
