# ADR-0008: Coordinator skeleton: one container, signed HTTP messages, SQLite

**Status:** Accepted (owner request, 2026-10-26: "coordinator skeleton for TrueNAS"). Spec: `specs/SPEC-COORDINATOR.md` (PLANNED).

## Context

Every multi-station feature needs the coordinator tier. The spec fixes the roles, identity by key pair with owner approval, devices dialling out, signed messages, a container set with one config file, and privacy rules. It leaves open the transport (MQTT or WebSocket), the database (PostgreSQL + TimescaleDB likely) and federation. The owner's coordinator hardware is a TrueNAS SCALE box on the LAN.

## Decision

- **`coordinator/` at the repository root**, its own package `gps_time_coordinator`, outside `gps_time_pi`. It isn't in the station bundle, and the station never imports it.
- **One container** (Python 3.13 slim + `cryptography`, the station's pin), installed on TrueNAS SCALE as a custom app from `compose.yaml`. It runs as the apps user 568:568, with a read-only root filesystem and no capabilities.
- **Identity:** the station's existing Ed25519 key (`gps_time_pi/station_key.py`). `station_id` is the same fingerprint that signs its observation files. The coordinator keeps the public key from the first join and refuses another key for that ID.
- **Messages:** a JSON envelope signed over its canonical form, with `seq` increasing per station (no replays). `join` creates a pending device; `events` is accepted only from approved ones. Approval and revocation are CLI commands inside the container.
- **Transport for the skeleton:** HTTP POST, stations dialling out. This keeps "devices dial out" from the spec. The persistent connection (MQTT or WebSocket over TLS) stays an open question; the envelope doesn't depend on it.
- **Storage for the skeleton:** SQLite on the `data` dataset, with a retention window. PostgreSQL stays the likely choice once processing services need it.
- **Privacy:** no position is stored. Position fields are removed from everything before insert until consent handling exists.

## Consequences

- A coordinator can be stood up and exercised (`demo-client`) without touching any station.
- **Open, and to be decided before the first station sends:**
  - TLS (a reverse proxy on the NAS, or in the container);
  - the persistent transport;
  - the station-side sender: a store-and-forward queue in RAM with summarized events only, to respect the SD-card rule, and off by default;
  - one-time-code approval;
  - the event schema (the station's event model, with provenance labels on every value).
- Moving to PostgreSQL later changes `store.py` only.
