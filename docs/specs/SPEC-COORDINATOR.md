# SPEC — Coordinator Tier

## Status

PLANNED. Required before any multi-station feature (MLAT, RF tasking, trust cluster, distributed science).

## Goal

A coordinator that a small group can run on its own hardware, with no mandatory cloud, that collects observations from stations and nodes, runs heavy analysis, and returns results.

## Roles

- **Station:** a GPS Time Pi with PPS timing. Light work only.
- **Node:** any timed device with sensors (SDR, seismometer, infrasound, camera). Synced to a station by PPS or NTP.
- **Coordinator:** a stronger machine (mini PC, NAS, workstation, or a container) that does correlation, solving, storage, and maps.

A group can run one coordinator. Several coordinators may later federate, sharing only what their members allow.

## Node sign-up and identity

- Each station or node generates its own key pair on first start. The private key never leaves the device.
- Joining a coordinator: the owner approves the request in the coordinator UI (or with a one-time code).
- All messages are signed. The coordinator keeps a list of approved keys and can revoke any.
- Each device publishes a capability record (see SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md), extended to list non-RF sensors.

## Transport

- Persistent connection from device to coordinator (MQTT over TLS or WebSocket over TLS). Devices dial out, so no port forwarding at home.
- Works over LAN only, or over the Internet when the owner allows.
- Store-and-forward: devices buffer events while offline and send them later, with original timestamps.

## Data model

Everything is an **event** or a **stream**, using the station's existing event model, plus:

- device ID, timing state at the moment (PPS / NTP with offset bound / MLAT-calibrated), and frequency reference state
- provenance label on every value
- privacy level of any position

Formats by sensor type:

| Data | Format |
|---|---|
| GNSS raw observations | RINEX |
| Seismic and infrasound | miniSEED (compatible with the Raspberry Shake network) |
| RF captures | SigMF (IQ plus metadata) |
| Events, results | JSON with a versioned schema |
| Images (all-sky) | JPEG/FITS plus JSON sidecar |

## Storage

- Recent raw data kept for a configurable window; long-term storage keeps events and summaries.
- Per-owner quotas.
- Raw data from a device is visible only to its owner unless shared.

## Processing services

Each is a separate module:

- MLAT and TDOA solver
- RF tasking broker
- trust scoring
- event correlation across stations (e.g. "three stations saw an infrasound pulse within 2 s")
- GNSS processing (PPP, TEC) for dual-band stations
- maps and dashboards

## Privacy and consent

- Exact positions are used inside the coordinator only with consent; members see approximate positions.
- Owners can delete their data and leave at any time.
- Public outputs (maps, results) use rounded positions.

## Deployment

- Ships as a container set (e.g. Docker Compose) with a single config file.
- Runs on x86 or ARM64.
- Backups documented.

## Open questions

- MQTT vs WebSocket.
- Database choice (PostgreSQL + TimescaleDB is a likely fit).
- Federation protocol between coordinators.
