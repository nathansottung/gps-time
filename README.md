# GPS Time

**Development status: v1.4.0-rc.11 (pre-release).** A Raspberry Pi Stratum-1 time server that shows how good its time is, and why.

GPS Time turns a Raspberry Pi and a GNSS receiver with a PPS output into an NTP server for your network. It watches every stage of the timing chain (receiver, satellites, PPS pulse, chrony) and says plainly what it can observe and what it can't. Around that core it adds offline sky and solar tools. Everything runs on the Pi, without the Internet.

![The Overview page of the web UI: timing chain stages, local time and timing quality](docs/screenshots/overview.png)

*The Overview page in the desktop demo (synthetic data), taken in screenshot mode with location privacy set to rounded.*

## Vision

A small, offline station that keeps exact time and shows honestly how good that time is.
On that timing core: measurement, sky and radio science, each value labeled with where it came from.
Later, a network of such stations doing opt-in distributed science. Phases and status: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## What it does today

- **Serves time.** gpsd and chrony with the PPS refclock: stratum 1 when PPS is selected, with honest fallback states (network, holdover, unsynchronized). The web UI never drives the clock; timing keeps working if it fails.
- **Shows the timing chain.** Receiver → satellites → navigation solution → PPS device → pulses → chrony, each stage observed or marked UNKNOWN. PPS outages are recorded as events with evidence kept on the SD card, and classified only as far as the evidence goes (no guessed causes).
- **Measures itself.** Allan, modified Allan and time deviation from kernel PPS timestamps; chrony's offset with its standard deviation and its error bound; comparison with independent NTP servers; NTP service counters; an oscillator-versus-temperature log; time scales (TAI, GPS time, MJD) with leap-second table expiry.
- **Knows its sky, offline.** Sun and moon times with twilight and night bars for any date from 1850 to 2149, a sky map and object lookup, the Earth's shadow over the station and satellite illumination (from a locally cached orbital-element file).
- **Respects privacy.** The station's location can be shown exactly, rounded to about 11 km, or hidden everywhere (pages, API, diagnostics, derived values). A screenshot mode masks coordinates, heights, client addresses and the hostname on screen.
- **One web UI** at `/app/` (`/` redirects there), served by the station itself: no CDN, no web fonts from elsewhere, no analytics. Dark and red night themes, and pages and cards you can hide per browser.
- **Safe administration.** Read-only by default. Service actions and settings need an admin token, are POST-only and same-origin, and run through a fixed polkit rule; the web service runs unprivileged.

Every value carries a provenance label: observed, calculated, modeled, predicted, inferred or external.

## What it won't claim

- A cause the evidence can't establish (jamming, spoofing, antenna failure). It reports what it observes.
- Health for a stage it can't observe; that stage shows UNKNOWN.
- Statistical repeatability as absolute accuracy, or the host clock's accuracy as the accuracy of an SDR sample, camera frame or network packet.

## Status and known limitations

This is a pre-release. The release candidate is being soak-tested on a development Raspberry Pi before v1.4.0. An independent review of the code (`docs/review/`) found 32 issues; the open ones are tracked in [`docs/STATUS.md`](docs/STATUS.md). The main ones:

- Holdover estimates still use the raw oscillator frequency, not a trained model (GPS-008); the UI marks them as planned.
- Expensive requests aren't rate-limited and the service has no systemd resource limits yet (GPS-018).
- The installer trusts the ephemeris download on first use and pip dependencies aren't hash-pinned (GPS-020).
- The station serves plain HTTP. Use it on a trusted LAN, or put a TLS reverse proxy in front.

## Try it without a Pi

The demo serves the same web UI with sample data. It needs Python 3.11+ and, for the UI, Node 22 with corepack.

```bash
cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run build && cd ..
./scripts/run-demo.sh                          # http://127.0.0.1:8080/ (writes only under .dev/)
```

On Windows: `powershell -ExecutionPolicy Bypass -File .\scripts\run-demo.ps1`. Details: [`docs/development/windows-demo.md`](docs/development/windows-demo.md).

## Run it on a Pi

You need a Raspberry Pi 4 on Raspberry Pi OS Lite (Debian 12; Debian 13 is tested in CI but not yet on a Pi; the Pi 5 is untested), a GNSS receiver with its PPS output wired to a GPIO pin, and an antenna with a view of the sky.

1. Generate the hardware snippets for your board: `python3 tools/generate_config.py --profile uputronics` (or another profile; see [`docs/HARDWARE-PROFILES.md`](docs/HARDWARE-PROFILES.md)).
2. Follow the checklist for a newly flashed Pi: [`docs/deploy/fresh-pi-install.md`](docs/deploy/fresh-pi-install.md). It covers the serial and PPS setup, chrony, the deploy script and the checks.
3. Open `http://<your-pi>/`.

Station already running an earlier 1.4 build: [`docs/deploy/upgrade-1.4-station.md`](docs/deploy/upgrade-1.4-station.md).

## Hardware

The reference build is a Raspberry Pi 4 with the Uputronics GPS/RTC board (u-blox MAX-M8Q, PPS on GPIO 18). Profiles exist for several other HATs and for USB receivers (NMEA-only, so no microsecond timing). A dual-band u-blox ZED-F9T / ZED-F9P profile is planned: [`docs/hardware/zed-f9-dual-band.md`](docs/hardware/zed-f9-dual-band.md).

Antenna placement matters as much as the receiver: a weak signal shows up as PPS outages.

## Documentation

- [`docs/ROADMAP.md`](docs/ROADMAP.md): every spec and roadmap, by phase, with status.
- [`docs/STATUS.md`](docs/STATUS.md): every item and review finding, with the pull requests that delivered it.
- [`docs/INDEX.md`](docs/INDEX.md): all documentation. [`docs/README.md`](docs/README.md): the project's design rules.
- [`docs/api/`](docs/api/): the station's HTTP API.

## Contributing, security, license

- Contributions are welcome: see [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Report vulnerabilities privately: see [`SECURITY.md`](SECURITY.md).
- The project's own code and documentation are under the MIT License ([`LICENSE`](LICENSE)).
- Third-party software and data keep their own licenses: see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
