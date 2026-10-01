# System overview

## Roles

GPS Time is designed around four compute roles so a Raspberry Pi does not have to become a monolithic science server.

### Tier 0 — Portable client
Typical hardware: laptop/mini PC + USB GNSS.

Purpose: coarse GNSS time/location, offline astronomy/solar/radio utilities, field ham-radio operation, basic SDR reception. PPS may be absent.

### Tier 1 — Station node
Typical hardware: Raspberry Pi 4/5 + GNSS/PPS, optional SDR/sensors.

Owns: timing reference, NTP service, station position/calibration, short-term history, local dashboard, local instrument acquisition, observation provenance.

### Tier 2 — Analysis node
Typical hardware: workstation, homelab server, NAS or higher-end mini PC.

Owns: heavy SDR DSP, cross-correlation, MLAT/TDoA solving, long-term databases, large terrain/map packs, multi-station analytics.

### Tier 3 — Network coordinator
Optional service. Owns discovery, opt-in observation requests, relays, aggregation, public views, and distributed experiment coordination. A station must remain useful without it.

## Data flow

```text
GNSS / PPS ──► timing core ──► system clock / NTP
     │                │
     │                └──► timing-quality observations
     └──► station model ──► accepted site / sky model / calibration

instrument adapters ──► observation records ──► dashboard / local history
                                  │
                                  ├──► optional analysis node
                                  └──► optional distributed network
```

## Core process boundary

The timing core should remain narrow: gpsd, LinuxPPS, chrony and configuration required to serve time. The web application observes/explains the core and may administer it through narrowly-scoped controls, but it must not become a prerequisite for chrony to serve NTP.

## Capability discovery

The application should expose capabilities rather than assume a Pi/GPIO topology:

- GNSS position available?
- UTC label available?
- PPS available?
- kernel PPS available?
- native receiver diagnostics available?
- NTP serving available?
- SDR frequency calibration available?
- SDR sample epoch characterized?
- sensor calibration available?
- hardware network timestamps/PTP available?

Widgets and experiments use declared capabilities and timing levels.
