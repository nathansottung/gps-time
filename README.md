# GPS Time

**Development status: v1.4.0-rc.8 (pre-release).** GPS Time began as a Raspberry Pi GPS/PPS Stratum-1 NTP appliance and is being structured as an **open-source, timing-first, offline-capable measurement platform**.

GNSS establishes *when* and *where*. The platform then layers on local astronomy/solar/geodesy, network metrology, sensors, SDR/RF observation, ADS-B/UAT, and eventually opt-in distributed science—without making any of those optional capabilities dependencies of the timing core.

> The historical v1.3.0 timing appliance works as a development baseline, but a source review identified measurement-freshness, chrony-history semantics, persistence and administrative-security work that must be resolved/dispositioned before a stable public release. See [`docs/review/source-review-2026-09-07.md`](docs/review/source-review-2026-09-07.md).

## Desktop demo first

The easiest way to work on the UI is Windows + VS Code with sample data:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-demo.ps1
```

Open `http://127.0.0.1:8080/`.

Demo mode uses the **same dashboard renderer** as the Pi. `/configure` supports multiple pages, widget show/hide flags, card width, and JSON import/export. No GPS receiver, chrony, gpsd or Internet connection is required to run the demo server.

See [`docs/development/windows-demo.md`](docs/development/windows-demo.md).

## Current baseline capabilities

- GNSS/PPS status via gpsd + chrony
- Stratum-1 NTP architecture with optional Internet fallback
- explicit synchronization states
- timing quality, oscillator and source visibility
- GNSS position/satellite table and a historical fixed-site survey implementation
- NTP client IP activity
- astronomy/almanac and local sidereal information
- RAM-backed chrony tracking history / periodic persistence scaffolding
- system diagnostics and light/dark/night themes
- hardware configuration generator for multiple GNSS profiles
- configurable multi-page dashboard development scaffold
- browser HTTP round-trip/clock-estimate probe

## Platform roadmap

The canonical feature inventory is [`docs/roadmap/feature-registry.md`](docs/roadmap/feature-registry.md). Major families include:

- timing metrology, holdover and light-distance-equivalent uncertainty
- accepted site / geodesy / learned GNSS obstruction maps
- offline Sun/Moon/solar-energy/magnetic/terrain/radio calculations
- USB GNSS and precision GNSS hardware tiers
- multiple SDRs, spectrum/RFI, WWV/CHU, WSPR/FST4W, meteor/satellite reception
- ADS-B 1090, UAT 978 and MLAT integration
- timing-aware SDR calibration and authorized amateur/test-beacon TDoA research
- weather/environmental/optical/magnetic/acoustic sensors
- satellite/aircraft/radiosonde Sun/Moon transit predictions
- open VLF lightning-network research
- decentralized, opt-in distributed observation records and requests
- optional PTP/common-view GNSS/White Rabbit research tiers

## Architecture

The Pi remains a **Station Node**. Heavy DSP, long-term storage and multi-station solving can move to optional **Analysis Nodes** or **Network Coordinators**.

Read [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md).

## Scientific naming and units

Quantities should use canonical scientific terminology and unambiguous units. Friendly ELI5 copy supplements the expert value rather than replacing it.

See [`docs/science/quantity-registry.md`](docs/science/quantity-registry.md) and [`docs/science/timing-metrology.md`](docs/science/timing-metrology.md).

## Build and deploy

Build repo and Pi archives:

```bash
python tools/build_bundles.py
```

Windows deploy helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi
```

See [`docs/development/raspberry-pi-deploy.md`](docs/development/raspberry-pi-deploy.md).

## Hardware

The current deployed reference hardware is a Raspberry Pi 4 + Uputronics MAX-M8Q GPS/RTC HAT with GPIO PPS. Additional HAT/USB profiles are documented and generated through `tools/generate_config.py`.

See [`docs/HARDWARE-PROFILES.md`](docs/HARDWARE-PROFILES.md), [`docs/GNSS-SURVEY-AND-INSTALLATION.md`](docs/GNSS-SURVEY-AND-INSTALLATION.md), and [`docs/hardware/README.md`](docs/hardware/README.md).

## Open-source policy

Project-authored code, protocols, schemas, calibration formats, reference implementations and documentation are intended to remain open source. Third-party firmware, datasets, libraries and services retain their own licenses and are documented/provenanced rather than silently relicensed.

See [`docs/licensing/open-source-policy.md`](docs/licensing/open-source-policy.md).

## Documentation contract

`/docs/` is part of the product. Human contributors and coding agents should start at [`docs/README.md`](docs/README.md). Material features, architectural decisions, maturity state, licensing constraints and implementation history belong in the repository—not only in chat history.

## License

MIT for project-authored code unless a file explicitly says otherwise. See [LICENSE](LICENSE).
