# GPS Time coordinator (skeleton)

**Status:** SKELETON, 0.1.0 (#127; ADR-0008). Spec: [`../docs/specs/SPEC-COORDINATOR.md`](../docs/specs/SPEC-COORDINATOR.md).

What it does:
- **Join:** a station asks to join, with a message signed by its station key. The request stays **pending** until the owner approves it.
- **Events:** once a station is approved, the coordinator takes its signed event batches and stores them in SQLite. It removes position fields first, and deletes events after the retention window.

What it doesn't do yet:
- No processing services: MLAT/TDOA, correlation, trust, GNSS processing or maps.
- No web UI.
- No TLS of its own.
- No federation.

Nothing on a station sends to it yet. The station tier is unchanged and works without it.

It runs as one container. The target is a TrueNAS SCALE box on the LAN; any Docker host works.

## Layout

| Path | What |
|---|---|
| `gps_time_coordinator/messages.py` | the signed envelope: Ed25519 over canonical JSON, `station_id` = fingerprint of the key (the same identity a station's observation files carry), `seq` increasing per station (no replays) |
| `gps_time_coordinator/server.py` | `GET /v1/health`, `POST /v1/join`, `POST /v1/events` |
| `gps_time_coordinator/store.py` | SQLite: devices (pending, approved, revoked) and events; retention |
| `gps_time_coordinator/privacy.py` | removes position fields (lat, lon, alt…, site, location) from everything stored |
| `gps_time_coordinator/config.py` | the one config file, `coordinator.toml` |
| `gps_time_coordinator/__main__.py` | `serve`, `devices`, `approve`, `revoke`, `events`, `demo-client` |
| `Dockerfile`, `compose.yaml`, `requirements.txt`, `coordinator.example.toml` | the container |

## Install on TrueNAS SCALE

Not yet tried on a TrueNAS system; the steps follow TrueNAS SCALE 24.10 (Electric Eel) and later, which run apps on Docker.

1. **Datasets.** Create `apps/gps-time-coordinator` with three child datasets (or folders): `src`, `config`, `data`. Give them to the apps user and group, 568:568.
2. **Code.** Copy this repository's `coordinator/` folder into `src`, for example from a clone over SMB.
3. **Config.** Copy `coordinator.example.toml` to `config/coordinator.toml`. Defaults are fine to start.
4. **App.** Apps → Discover Apps → Custom App → **Install via YAML**. Paste `compose.yaml` with `/mnt/POOL` changed to your pool. TrueNAS builds the image from `src` and starts it.
5. **Check:** `curl http://<nas>:8090/v1/health` returns `{"ok": true, "version": "0.1.0", "devices": {...}}`.

On another Docker host: `docker compose -f compose.yaml up -d --build`, with the three paths changed.

The container runs as 568:568 with a read-only root filesystem, no capabilities, `no-new-privileges`, and the config mounted read only. Only `/data` is written.

## Try it

From any machine with Python 3.11+ and `cryptography`:

```bash
cd coordinator
python -m gps_time_coordinator demo-client http://<nas>:8090
```

The demo client generates a throwaway key, joins (answer: pending, 202), and tries to send one synthetic event (answer: 403, not approved). Then, on the NAS:

```bash
docker exec -it gps-time-coordinator python -m gps_time_coordinator devices --state pending
docker exec -it gps-time-coordinator python -m gps_time_coordinator approve ed25519:<id>
```

The demo's next run uses a new key, so it is a new device each time; it shows the flow, not a station.

## Security notes

- **Integrity:** every write is signed. A message whose `station_id` isn't the fingerprint of its key, whose signature doesn't verify, or whose key differs from the one on record is refused. A `seq` not above the last one is refused (409), so a captured message can't be replayed.
- **Confidentiality:** plain HTTP, so events can be read on the network. Keep it on the LAN. Before anything crosses the Internet, put TLS in front (a reverse proxy on the NAS) and decide the transport (ADR-0008, open questions).
- **No device data over HTTP:** the only GET is `/v1/health`, with counts. Device lists and events are read with the CLI inside the container.
- **Positions:** never stored. The spec allows exact positions only with consent, which isn't built yet.
- **Approval:** with the CLI only, on the NAS. The spec's one-time codes and UI come later.

## Backups

Back up the `data` dataset (`coordinator.sqlite3`, in WAL mode: snapshot the dataset, or stop the app before copying the file) and `config`. `src` is the repository.

## Tests

`tests/test_coordinator.py` (repository root): config, privacy, storage, message shape, and with `cryptography` installed signatures, a station key signing messages, the HTTP flow, forgery and replay.
