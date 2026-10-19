# Timing chain: GNSS → PPS → chrony → system clock

**Status:** backend implemented on `feat/pps-chain` (2026-10-01). There is no UI yet.
**Requirements:** [`../specs/CHG-PPS-HEALTH-DIAGNOSTICS.md`](../specs/CHG-PPS-HEALTH-DIAGNOSTICS.md), [`../specs/TASK-PPS-CHAIN.md`](../specs/TASK-PPS-CHAIN.md)
**Code:** `gps_time_pi/pps.py`, `gps_time_pi/timing_chain.py`, `gps_time_pi/chrony.py` (parsers), `gps_time_pi/labels.py`
**Tests:** `tests/test_timing_chain.py`, with fixtures in `tests/fixtures/chrony/`

## Why this exists

In September 2026 the station ran on network failover for days. Throughout that time, the GNSS receiver tracked about 10 satellites at up to 43 dB-Hz, timing DOP was 0.73, NMEA kept arriving, and the HAT LED pulsed at 1 Hz. The old dashboard made GNSS look healthy, and nothing showed that chrony was not using PPS. A reboot fixed it.

"GNSS is healthy" and "PPS disciplines the clock" are different facts. Each stage of the chain is therefore observed and reported on its own, so that the first broken link is visible.

## Stages

`/api/timing-chain` → `stages[]`. Each stage has `id`, `label`, `status`, `summary` and `evidence`. Evidence values carry a provenance label.

| # | id | What is observed | Source |
|---|---|---|---|
| 1 | `receiver_comms` | Fresh gpsd reports from the receiver | gpsd collector (`data_age_s`) |
| 2 | `satellite_reception` | Satellites used and visible, best and median C/N₀ (dB-Hz), TDOP | gpsd SKY |
| 3 | `nav_time_solution` | Fix type (3D, 2D or none) | gpsd TPV |
| 4 | `receiver_pps_output` | Always **NOT_OBSERVABLE**. Software can't measure the receiver's PPS pin, and a LED isn't a measurement | — |
| 5 | `pps_device` | Whether `/dev/pps0` and `/sys/class/pps/pps0` exist, device name, configured GPIO and edge | filesystem, `config.txt` (read-only) |
| 6 | `kernel_events` | Last kernel PPS timestamp, age, rate, consecutive and missed pulses, interval statistics | `/sys/class/pps/pps0/assert` |
| 7 | `nmea_refclock` | chrony's NMEA/serial refclock: reach, last sample age, `STALE` or `OK` | `chronyc -n sources` |
| 8 | `chrony_pps_visible` | Whether the PPS refclock appears in chrony's source list | `chronyc -n sources` |
| 9 | `chrony_pps_accepted` | Source state symbol `+`, `-` or `*` | `chronyc -n sources` |
| 10 | `chrony_pps_selected` | Source state symbol `*` | `chronyc -n sources` |
| 11 | `system_sync` | Leap status, stratum, reference, chrony's remaining correction, root delay and dispersion | `chronyc -n tracking` |
| 12 | `fallback_source` | What disciplines the clock when PPS doesn't | `chronyc -n sources` |
| 13 | `failover_duration` | How long PPS has been unavailable or unused (from the open outage event) | event tracker |

Stage status is one of:
- `OK`, `DEGRADED` or `FAILED`;
- `UNKNOWN`, meaning it couldn't be determined;
- `NOT_OBSERVABLE`, meaning no software observation is possible;
- `NOT_APPLICABLE`, for example no NMEA refclock is configured;
- `INFO`.

**A stage is never reported OK because a neighbouring stage is OK.**

## Identifying the PPS and NMEA refclocks

Refids differ between profiles. The project's PPS profile names the PPS refclock `GPS`, while its NMEA-only profile names the NMEA refclock `GPS`. Names alone therefore can't identify a source.

`chrony.refclock_config()` reads `/etc/chrony/chrony.conf`, following its `include` and `confdir` directives, without modifying anything. It applies these rules:
- **PPS refclock:** `refclock PPS …`, or a `SOCK`/`SHM` refclock whose refid contains "PPS". Its `lock` reference is recorded.
- **NMEA/serial refclock:** the first other `SHM`/`SOCK` refclock.
- **Default refids:** follow chrony's rule, `PPS0`, `SHM0` and so on.

If the configuration can't be read, conventional names are assumed (`PPS*`/`GPS` for PPS, `NMEA` for serial), and `chrony.refclocks.identified_from` says `"assumed default names"`.

## chrony interpretation

All calls use `chronyc -n`: numeric addresses with no reverse DNS, which keeps them fast and offline-safe. The parsers in `chrony.py` are pure functions:
- `parse_sources` reads the mode, the state symbol, reach (octal, plus a count of the 8 bits), and LastRx with its `m/h/d/y` suffixes. It also splits the last sample into adjusted offset, measured offset and error bound.
- `parse_sourcestats` reads samples, span, frequency, skew, offset and standard deviation.
- `parse_tracking` reads the tracking fields plus the reference name.

The PPS source status comes straight from chrony's own symbols:

| chrony | `pps_status` | Meaning reported (chrony's documented meaning) |
|---|---|---|
| `*` | `SELECTED` | current best source, disciplining the clock |
| `+` / `-` | `ACCEPTED` | acceptable; combined (`+`) or excluded by the combining algorithm (`-`) |
| `?`, `x` or `~` with reach > 0 | `REJECTED` | not selectable / falseticker / too variable |
| any state, reach = 0 | `VISIBLE_NO_SAMPLES` | listed but no samples in the last 8 polls |
| absent from the list | `NOT_VISIBLE` | — |
| no PPS refclock configured | `NOT_CONFIGURED` | — |
| `chronyc` failed | `UNKNOWN` | — |

**No rejection reason is added beyond what chrony shows.** The single exception is a stated observation, never a claimed cause. It applies when the PPS refclock is configured with `lock <X>` and refclock X is `STALE`: the classification then records `lock_reference_stale: true` with a note.

The NMEA refclock counts as `STALE` when reach = 0, LastRx is absent, or LastRx > max(3 × 2^poll, 30 s). The 30 s floor is configurable.

## PPS state machine

`PPSStateMachine` combines kernel pulse health with chrony's PPS status:

| State | Condition |
|---|---|
| `UNKNOWN` | Kernel PPS not observable (no `/sys/class/pps`, or unreadable) and chrony doesn't show PPS selected |
| `DEVICE_MISSING` | PPS subsystem present, no `pps0` device |
| `DEVICE_PRESENT_NO_EVENTS` | Device present, kernel sequence still 0 |
| `EVENTS_PRESENT` | Pulses arriving; chrony doesn't list PPS or chrony's status is unknown |
| `CHRONY_VISIBLE` | Pulses arriving; PPS listed but no samples |
| `CHRONY_REJECTED` | Pulses arriving; chrony shows `?`, `x` or `~` with samples |
| `CHRONY_ACCEPTED` | Pulses arriving; chrony shows `+` or `-` |
| `SELECTED` | chrony shows the PPS refclock as `*` (also when the kernel side isn't observable) |
| `LOST` | Pulses were seen before, but the last one is older than the LOST threshold |
| `RECOVERING` | Pulses resumed after `LOST`, and chrony isn't selecting PPS yet |

Kernel pulse health thresholds are set by `GTP_PPS_DEGRADED_S` and `GTP_PPS_LOST_S`:
- `HEALTHY`: age < 1.5 s;
- `DEGRADED`: 1.5–3 s;
- `LOST`: > 3 s.

**Measurement layer.** Every PPS figure is Linux's kernel CLOCK_REALTIME timestamp of the interrupt. Interval statistics include interrupt latency and the effect of the clock being disciplined. **They are not the receiver's or the electrical PPS jitter**, and the API says so in `pps.measurement_layer`.

Two counters, both from the kernel's own sequence number, between two events the station read:

- **Missed pulses**: the pulses the elapsed kernel time calls for, minus the ones the kernel counted. These never reached Linux.
- **Unread pulses** (since rc.9): pulses the kernel counted that the station didn't read one by one, because two or more arrived between its polls. They were not lost.

The monitor also counts its own polls, the late ones (more than 1.5 s apart) and the longest gap, so a slow poller can be told apart from missing pulses. All of this lives in a RAM ring (600 events), and nothing is written to disk at 1 Hz.

## Status banner (replaces `sync_state()`)

`timing_chain.timing_status()` is stateless and always names what disciplines the clock. `/api` returns it as `timing_status`, and `state` remains as `[headline, banner — detail]` for the legacy pages.

| code | headline | banner |
|---|---|---|
| `GPS_PPS` | SYNCHRONIZED | `SYNCHRONIZED · GPS/PPS · STRATUM 1` |
| `DEGRADED` | DEGRADED | `DEGRADED · GNSS HEALTHY · PPS NOT SELECTED`. The detail names the network source. Also `DEGRADED · GNSS SERIAL TIME (NMEA) · PPS NOT SELECTED` |
| `NETWORK_FAILOVER` | NETWORK FAILOVER | `SYNCHRONIZED · NETWORK FAILOVER · GPS/PPS UNAVAILABLE` |
| `HOLDOVER` | HOLDOVER | `HOLDOVER · NO EXTERNAL REFERENCE` |
| `GNSS_NMEA` | SYNCHRONIZED | `SYNCHRONIZED · GNSS SERIAL TIME (NMEA) · STRATUM n` (no PPS refclock configured) |
| `REFCLOCK` | SYNCHRONIZED | another reference clock |
| `UNSYNCHRONIZED` | UNSYNCHRONIZED | leap status "Not synchronised" |
| `ACQUIRING` | ACQUIRING | `ACQUIRING · PPS NOT YET SELECTED SINCE BOOT`. A boot-phase overlay: `underlying` keeps the banner that names the current source. It never masks `GPS_PPS` or `UNSYNCHRONIZED` |
| `SOURCE_UNKNOWN` / `UNKNOWN` | — | chrony's source list or tracking is unavailable |

**`GPS_PPS` requires chrony's `*` on the PPS refclock.** The tracking reference alone isn't enough, because chrony keeps showing the last reference (e.g. `GPS`, stratum 1) during holdover. `tests/test_timing_chain.py::test_20` checks every fixture combination.

## Classification

`classify()` runs whenever PPS isn't selected. It is labeled `inferred`:

| Evidence | Classification |
|---|---|
| Kernel PPS events stopped, GNSS reception and solution healthy | **PPS PATH ANOMALY**. Possible boundary: receiver PPS output / GPIO / kernel PPS interface |
| PPS events stopped, and reception or solution failed while the receiver still talks | **GNSS RECEPTION ANOMALY** ("evidence does not establish a cause") |
| PPS events stopped, and GNSS telemetry is unavailable too | PPS AND GNSS TELEMETRY UNAVAILABLE |
| Pulses arriving, chrony not selecting PPS | **PPS NOT USED BY CHRONY**, with chrony's symbol meaning and, when observed, the stale `lock` reference |
| No PPS device | PPS DEVICE MISSING |
| Pulses arriving, chrony status unknown | UNKNOWN |

Jamming, spoofing, interference and antenna failure are **never** named; the tests assert it. GNSS integrity monitoring (C/N₀ baselines, position anomalies) is a separate future feature in `../specs/PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md`.

## Events

**Generic schema** (`gps-time.event/1`): `id`, `type`, `start_utc` and `start_epoch`, `end_utc`, `duration_s`, `open`, `severity`, `classification`, `initial_classification`, `confidence`, `boundary`, `classification_provenance: "inferred"`, `evidence`, `recovery`, `notes`. Optional fields are `restarts[]` and `start_bound`.

**Opening a `PPS_OUTAGE`.** One event is opened when PPS has not been `SELECTED` for `GTP_PPS_OUTAGE_DEBOUNCE_S` (default 30 s).
- **Boot rule.** Until PPS is first selected after a boot, the station is `ACQUIRING`: no outage is opened, and the banner says so.
  - If PPS is not selected within `GTP_PPS_ACQUIRE_WINDOW_S` (default 1800 s = 30 min) of boot, one outage opens **backdated to boot time** (`start_bound: "boot"`).
  - Boot time comes from `/proc/uptime`. The kernel `boot_id` and a `pps_selected` flag are checkpointed once per boot, on the first selection. A web-service restart later in the same boot therefore doesn't re-enter ACQUIRING.
  - The rule applies only when the service started observing inside the window. If it started later, or boot time is unavailable, nothing is known about the earlier part of the boot, so the debounce rule applies and the event says so (`start_bound: "service_start"`). The true start may be earlier.
- **After PPS has been selected in this boot**, a loss opens an outage after the 30 s debounce, starting at the loss.
- `/api/timing-chain` → `boot` reports the phase, boot time, time since boot, deadline and whether PPS was selected this boot.
- An event is never opened or closed while chrony's state is unknown and pulses are present.

**Evidence collected while open:**
- the evidence at the start and the latest evidence;
- the range of satellites used;
- the fallback sources used;
- the largest |chrony remaining correction| (a chrony estimate, not an independent error measurement);
- whether GNSS was ever unhealthy.

**Recovery.** The event closes when chrony selects PPS again. It records:
- the recovery time and total duration;
- the time from pulses returning until chrony accepted PPS, and until it selected PPS;
- the fallback sources;
- the maximum correction.

**Checkpoint.** The tracker writes to `timing-events.json` next to `config.json` (override with `GTP_EVENTS_PATH`), using a temp file, fsync and atomic rename. It writes only when an event opens, closes or changes classification, and at most every 15 minutes while open. It never writes at 1 Hz.
- After a restart, an open event resumes with its original start.
- If PPS was re-selected while the service was down, the recovery is recorded with `end_bounds_utc`, the interval in which it happened.
- A corrupt checkpoint is moved aside to `.corrupt-<ts>`, not overwritten.
- The last 50 closed events are kept.

## API

| Endpoint | Content |
|---|---|
| `GET /api/timing-chain` | `gps-time.timing-chain/1`: `status`, `pps_state`, `pps`, `gnss` (counts only), `chrony`, `classification`, `stages`, `events`, `raw` (chronyc -n text) |
| `GET /api/diagnostics` | Plain-text snapshot for copying: state of every stage, recent events, raw chronyc output. Location appears only according to the privacy mode (`hidden` → "Hidden (privacy mode)") |
| `GET /api` | Adds `timing_status`. `state` uses the new banner |

Both new endpoints are read-only and run no commands supplied by the browser. In demo mode, `?scenario=` selects one of the synthetic scenarios in `gps_time_pi/demo.py` (`TIMING_SCENARIOS`):
- `pps_selected`, `pps_path_anomaly`, `pps_unused_nmea_stale`, `pps_rejected`;
- `network_failover`, `holdover`, `recovering`, `device_missing`, `chrony_unknown`, `acquiring`.

Each runs the real pipeline on synthetic inputs and is marked as synthetic data.

## Collection and resources

`TimingChainService` starts with the web server, outside demo mode, with two threads (since rc.9):

- **`pps-poller`**, every second, 0.25 s after the whole second: reads the PPS sysfs file and hands the newest PPS timestamp to the stability recorder (`architecture/stability-analysis.md`). It does nothing else, so nothing slow can delay reading a pulse.
- **`timing-chain`**, every second, 0.45 s after the whole second: runs three `chronyc -n` calls every 5 s, reads the GNSS cache (which never polls gpsd), evaluates the chain, updates the outage events, and feeds the references and NTP-service trackers.

Before rc.9 one thread did both, so a slow evaluation (a `chronyc` call, an event checkpoint) postponed the next PPS read. Both threads run on a fixed grid, so their reads don't drift across the pulse.

`start()` evaluates the chain once before the server takes requests. No HTTP request ever reads the PPS or evaluates the chain: they all return the latest evaluation. Outage detection is unchanged: it still works from the age of the newest kernel event, every second.

It doesn't depend on browser traffic. A failure in either thread never stops the server. It does **not** change chrony, gpsd or PPS configuration.

## Web UI (`/app/`)

The new UI shows the chain from `/api/timing-chain` in three places.

**Banner.** One banner at the top of every page, plus the header chip, both built by `bannerView()` in `web/src/components/timing.tsx`. It shows `status.banner`, the detail and, during an open outage, "PPS unavailable for <duration> (since <UTC>[ or earlier])". Two guards keep it from overstating timing:
- **Inconsistent report:** a `GPS_PPS` status while chrony's selected source is not the PPS refclock is shown as `TIMING STATUS UNKNOWN · INCONSISTENT REPORT`, never as Stratum 1 GPS/PPS.
- **Missing source:** a status with no source qualifier gets the selected source appended, so a bare `SYNCHRONIZED` is never shown.
- No chain, or an unreachable station, gives `TIMING STATUS UNKNOWN`.

The header's stratum and reference come from the same timing-chain snapshot. `/api` is used only when there is no chain at all.

**Timing-chain card.** First on the Overview page, and repeated on the PPS page. Five columns in the spec's order:
- **GNSS:** health, satellites used/visible, TDOP, best C/N₀.
- **PPS device:** present/missing, path, GPIO.
- **PPS signal (kernel):** pulse health, age of the last pulse, rate.
- **chrony PPS:** status, refclock, reach, last sample, chrony's symbol and meaning. With reach 0, chrony's `+0ns` sample is shown as "no samples".
- **System clock:** mode, current source, stratum, how long PPS has been unavailable or unused.

**PPS Diagnostics page.** Read-only, with these sections:
- answers to the 12 acceptance questions of CHG-PPS-HEALTH-DIAGNOSTICS;
- classification (inferred);
- Device (path, presence, sysfs name and path, GPIO, edge);
- Live PPS, with the measurement layer labeled. Includes age, rate, consecutive and missed pulses, sequence resets, interval mean/min/max/std dev (kernel timestamp spacing, not electrical jitter) and the thresholds;
- chrony PPS refclock (symbol and meaning, reach, last sample, poll, offset ± error bound, frequency/skew, std dev, NMEA lock, selected source);
- outage events with recovery details (fallback sources, largest chrony correction, time to accept and select);
- stages;
- verbatim raw `chronyc -n` output and sysfs values;
- the diagnostic snapshot.

**COPY DIAGNOSTICS / DOWNLOAD.** Both fetch `/api/diagnostics` fresh on each click.
- COPY uses the Clipboard API when the page is a secure context. A station on plain http over the LAN isn't one, so the fallback is a hidden textarea with `execCommand('copy')`.
- DOWNLOAD saves `gps-time-diagnostics-<UTC>.txt` from a Blob.
- Nothing is sent anywhere, and the station applies the privacy mode to the text.

**Demo scenarios.** In demo mode (server `GTP_DEMO` or `?source=demo`) the PPS page offers a scenario selector, and `?scenario=<name>` sets it from the URL. Banner, header, card and page all follow the selected scenario.

## Troubleshooting procedure

1. **Is `kernel_events` OK?**
   - No, with `pps_device` FAILED: the PPS device doesn't exist. Check the `pps-gpio` overlay (`config.txt`, configured GPIO) and `dmesg | grep -i pps`.
   - No, with the device present: no events reach Linux. Run `sudo ppstest /dev/pps0`, then check the HAT seating, the GPIO and the overlay edge setting.
2. **Is `chrony_pps_visible` FAILED?** The PPS refclock is missing from chrony's configuration.
3. **Is `nmea_refclock` STALE while the PPS `lock` names it?** chrony needs recent samples from the lock refclock before it uses PPS. Check gpsd and the SHM/SOCK refclock.
4. **Is chrony's symbol `x`, `~` or `?`?** Check `offset_s`, `error_bound_s` and the NMEA offset. chrony doesn't report a further reason.
5. **Capture evidence before rebooting:** `/api/diagnostics`, `ls -l /dev/pps*`, `timeout 8 sudo ppstest /dev/pps0`, `chronyc sources -v`, `chronyc sourcestats -v`, `chronyc tracking`, `dmesg | grep -i pps`.

## Not yet implemented

- **PPS state timeline** and **history views** (uptime, availability %, outages per day or week, longest outage). The UI shows the open and recent events only.
- A per-event `ppstest`-style listing, and kernel/dmesg PPS information.
- Holdover projections (time to 1 µs … 1 s).
- GNSS integrity monitoring and the forensic telemetry window.
- Multi-station correlation.

**The real incident has not been replayed.** Fixtures model its shape, but no `chronyc` output or sysfs readings were captured from the Pi during the failure.
