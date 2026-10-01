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

Missed pulses are counted when the time between two observed events exceeds the number of sequence increments. All of this lives in a RAM ring (600 events), and nothing is written to disk at 1 Hz.

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
- A startup grace of `GTP_PPS_STARTUP_GRACE_S` (default 300 s) gives chrony time to select PPS after boot.
- If PPS was already unused at service start, the event says so (`start_bound: "service_start"`): the true start may be earlier.
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
- `network_failover`, `holdover`, `recovering`, `device_missing`, `chrony_unknown`.

Each runs the real pipeline on synthetic inputs and is marked as synthetic data.

## Collection and resources

`TimingChainService` starts with the web server, outside demo mode. On each 1 Hz tick it:
1. reads the PPS sysfs file;
2. runs three `chronyc -n` calls every 5 s;
3. reads the GNSS cache, which never polls gpsd;
4. evaluates the chain.

It doesn't depend on browser traffic. A tick failure never stops the server. It does **not** change chrony, gpsd or PPS configuration.

## Troubleshooting procedure

1. **Is `kernel_events` OK?**
   - No, with `pps_device` FAILED: the PPS device doesn't exist. Check the `pps-gpio` overlay (`config.txt`, configured GPIO) and `dmesg | grep -i pps`.
   - No, with the device present: no events reach Linux. Run `sudo ppstest /dev/pps0`, then check the HAT seating, the GPIO and the overlay edge setting.
2. **Is `chrony_pps_visible` FAILED?** The PPS refclock is missing from chrony's configuration.
3. **Is `nmea_refclock` STALE while the PPS `lock` names it?** chrony needs recent samples from the lock refclock before it uses PPS. Check gpsd and the SHM/SOCK refclock.
4. **Is chrony's symbol `x`, `~` or `?`?** Check `offset_s`, `error_bound_s` and the NMEA offset. chrony doesn't report a further reason.
5. **Capture evidence before rebooting:** `/api/diagnostics`, `ls -l /dev/pps*`, `timeout 8 sudo ppstest /dev/pps0`, `chronyc sources -v`, `chronyc sourcestats -v`, `chronyc tracking`, `dmesg | grep -i pps`.

## Not yet implemented

- **Dashboard UI** (PPS card, timeline, COPY DIAGNOSTICS control). The task covered the backend only.
- **History views** (availability %, outages per day or week).
- Holdover projections (time to 1 µs … 1 s).
- GNSS integrity monitoring and the forensic telemetry window.
- Multi-station correlation.

**The real incident has not been replayed.** Fixtures model its shape, but no `chronyc` output or sysfs readings were captured from the Pi during the failure.
