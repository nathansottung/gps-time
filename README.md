# GPS Time

GPS Time turns a Raspberry Pi and a GNSS receiver with a PPS output into a Stratum-1 NTP server for your network, running offline. It shows how good its time is, and why: every stage from satellite to NTP client is either observed or marked UNKNOWN.

![The Overview page of the web UI: timing chain stages, local time and timing quality](docs/screenshots/overview.png)

*The Overview page in the desktop demo (synthetic data), taken in screenshot mode with location privacy set to rounded.*

**Status: v1.4.0-rc.11, pre-release.** It is soak-tested on one development Pi before v1.4.0. Open issues: [`docs/STATUS.md`](docs/STATUS.md).

## Quick start

**Demo on a PC** (no Pi, receiver or Internet needed; sample data). Needs Python 3.11+ and Node 22 with corepack:

```bash
cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run build && cd ..
./scripts/run-demo.sh                          # http://127.0.0.1:8080/ (writes only under .dev/)
```

On Windows: `powershell -ExecutionPolicy Bypass -File .\scripts\run-demo.ps1` ([details](docs/development/windows-demo.md)).

**Install on a Pi** (Raspberry Pi OS Lite, Debian 13 Trixie; Debian 12 Bookworm expected to work):

1. Generate the wiring snippets for your board: `python3 tools/generate_config.py --profile uputronics` (other profiles: [`docs/HARDWARE-PROFILES.md`](docs/HARDWARE-PROFILES.md)).
2. Follow [`docs/deploy/fresh-pi-install.md`](docs/deploy/fresh-pi-install.md): serial and PPS setup, chrony, the deploy script, the checks.
3. Open `http://<your-pi>/`.

Upgrading a 1.4 station: [`docs/deploy/upgrade-1.4-station.md`](docs/deploy/upgrade-1.4-station.md). The station serves plain HTTP: use it on a trusted LAN, or put a TLS reverse proxy in front.

## Supported hardware

| | Hardware | Known limits |
|---|---|---|
| **Tested** | Raspberry Pi 4 + Uputronics GPS/RTC board (u-blox MAX-M8Q, PPS on GPIO 18), Debian 13 (Trixie, Python 3.13) | One development unit. Its antenna and site give a weak signal (best C/N₀ about 25 dB-Hz), which shows up as PPS outages. |
| **Expected to work** | Adafruit Ultimate GPS HAT, SparkFun GNSS Flex pHAT, Waveshare L76X (only after soldering PPS to GPIO 4) | Profiles exist; not run by the project. |
| | USB GNSS receivers (`usb-gps` profile) | NMEA only, no kernel PPS: millisecond-level time, not microsecond. |
| | Raspberry Pi 5; Debian 12 (Bookworm, Python 3.11) | Untested on hardware (Debian 12's Python 3.11 runs in CI). |

Antenna placement matters as much as the receiver. Wiring and profile details: [`docs/HARDWARE-PROFILES.md`](docs/HARDWARE-PROFILES.md).

## Planned hardware

- **Dual-band u-blox ZED-F9T / ZED-F9P:** fewer outages, more satellites, raw data for PPP. Next on the list: [`docs/hardware/zed-f9-dual-band.md`](docs/hardware/zed-f9-dual-band.md).
- **SDR nodes** timed by a station: [`docs/roadmap/ROADMAP-SDR-RF-OBSERVATORY.md`](docs/roadmap/ROADMAP-SDR-RF-OBSERVATORY.md), [`docs/specs/SPEC-RF-NODE-AND-TDOA.md`](docs/specs/SPEC-RF-NODE-AND-TDOA.md).
- **Sensors** on timed nodes (seismic, infrasound, VLF lightning, muons, all-sky camera): [`docs/roadmap/ROADMAP-SENSOR-FUSION.md`](docs/roadmap/ROADMAP-SENSOR-FUSION.md).
- Reference parts list for all tiers: [`docs/hardware/HARDWARE-REFERENCE-NODE.md`](docs/hardware/HARDWARE-REFERENCE-NODE.md).

## Features

**Now:**

- **Serves time:** gpsd and chrony with the PPS refclock; honest fallback states (network, holdover, unsynchronized). The web UI never drives the clock.
- **Shows the timing chain:** receiver → satellites → PPS → chrony, with outages recorded as events and evidence kept on the SD card. It never names a cause the evidence can't establish.
- **Measures itself:** Allan, modified Allan and time deviation; chrony's error bound; comparison with independent NTP servers; an oscillator-versus-temperature log; time scales and leap-second expiry.
- **Knows its sky, offline:** sun and moon times, a sky map, the Earth's shadow and satellite illumination.
- **Respects privacy:** location exact, rounded or hidden everywhere; a screenshot mode for sharing.
- **One web UI** served by the station: no CDN, no external fonts, no analytics. Admin actions need a token; the service runs unprivileged.

Every value is labeled observed, calculated, modeled, predicted, inferred or external.

**Planned:** PPS history views, NTS and PTP, a trained oscillator model for holdover, a desktop app for laptops in the field, SDR and sensor nodes, and a coordinator for networks of stations. Phases and status: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Accuracy

Measured on the tested development unit (Pi 4, MAX-M8Q, weak antenna site), from the station's own readings. Details: [`docs/development/raspberry-pi-deploy.md`](docs/development/raspberry-pi-deploy.md).

| Measurement | Result | When |
|---|---|---|
| chrony's RMS offset from the PPS reference | 244 ns | after a 14-day run (rc.8, 2026-10-19) |
| PPS interval, kernel timestamps, 600 pulses | 1.000 000 s ± 1.3 µs | rc.10, 2026-10-19 |
| Allan deviation (includes outages) | 1.7 × 10⁻⁶ at 1 s; 2.2 × 10⁻⁸ at 100 s | 14-day run |
| Holdover: one 56-minute loss of PPS | clock off by +1.7 µs afterwards | 2026-10-17 (one event) |
| Missed PPS pulses in a weak-signal window | 9.9 % | rc.10, 2 h 17 min |

These are the station's agreement with its own PPS reference. Accuracy against UTC has not been measured: that needs an independent reference, which this unit doesn't have.

## Where this is going

Today, GPS Time is a precise network time server on a Raspberry Pi. That is the foundation, not the goal.

A clock you can trust to well under a microsecond, at a position you know to the centimeter, is a scientific instrument. Put several of them in a network and they can agree on *when* something happened. From *when* and *where*, you can measure *what* happened and *how far away* it was.

The project grows in steps. Each step adds hardware and unlocks new measurements.

| Step | Hardware | What it can do | Status |
|---|---|---|---|
| **1. Precise time** | Raspberry Pi + GPS/PPS board | Stratum-1 NTP for your network; full diagnostics of the timing chain; stability analysis; holdover; sky, Sun and satellite tools | **Working now** |
| **2. Precise position** | Dual-band GNSS (u-blox ZED-F9T/F9P) + good antenna | Centimeter-level station position; Earth tides (the ground rises and falls ~30 cm a day); ionosphere and water-vapor measurements; more robust timing | Planned |
| **3. Radio ranging** | Add an SDR (e.g. RTL-SDR) | Compute the exact distance and signal delay to every known broadcast tower from the station's surveyed position; tune to those towers automatically; measure arrival times and check them against the prediction | Planned |
| **4. A network of stations** | Several stations + a coordinator | Calibrate stations against each other and against known towers; build a trusted cluster; locate radio transmitters by time difference of arrival (fox hunts, interference) | Planned |
| **5. More sensors** | Infrasound, seismometer, VLF lightning, cameras, muon detectors | Locate and map lightning (radio flash + thunder arrival times); detect meteors, quakes and storms across stations; catch cosmic-ray air showers | Planned |

### The idea behind radio ranging

Radio travels about 300 meters per microsecond. Once a station knows its own position precisely, the distance to any licensed broadcast tower is just geometry, and so is the time a signal should take to arrive. The station can:

1. Look up nearby towers and their frequencies from public licence data.
2. Predict each tower's signal delay from the surveyed position.
3. Tune to each tower, measure when its signal actually arrives, and compare.

Every match builds confidence in the station's clock and position. Every mismatch is something to explain. With several stations doing this together, the network calibrates itself from known transmitters and can then locate unknown ones.

### Aircraft as moving references

Aircraft broadcast their own GPS position over ADS-B. A station that hears one knows exactly how far away it is, and so how long its signal should take to arrive. Dozens of aircraft at once give a constant stream of checks, and several stations hearing the same aircraft can calibrate against each other. Reported positions are treated as external data, and outliers are rejected.

### Build on it

Everything after step 1 is built as a **module**: a source (a sensor or receiver), a reference (signals with known positions), an analysis, or a dashboard card. Each module follows one documented pattern, ships with test data so it runs without hardware, and never touches the timing core. Start with [docs/modules/README.md](docs/modules/README.md) (`python tools/new_module.py <name> --type source` creates one), or open a feature request with your module idea.

### What we will and won't claim

Every figure shown in the UI and docs says whether it was **observed**, **calculated**, **modeled**, **predicted**, **inferred** or **external**. Planned features are marked as planned until they have run on real hardware. Accuracy figures come from measurements, not datasheets.

Full details: [docs/ROADMAP.md](docs/ROADMAP.md).

## Docs, contributing, license

- [`docs/ROADMAP.md`](docs/ROADMAP.md) (phases), [`docs/STATUS.md`](docs/STATUS.md) (every item, with PRs), [`docs/INDEX.md`](docs/INDEX.md) (all documents), [`docs/api/`](docs/api/) (HTTP API), [`docs/README.md`](docs/README.md) (design rules).
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md). Vulnerabilities, privately: [`SECURITY.md`](SECURITY.md).
- MIT License ([`LICENSE`](LICENSE)). Third-party software and data keep their own licenses: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
