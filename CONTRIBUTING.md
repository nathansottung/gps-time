# Contributing to GPS Time

Contributions are welcome: fixes with a test that shows them, hardware profiles with evidence, tests, documentation, and collectors that keep to the timing-core boundary. For anything larger than a fix, open an issue first so the design can be agreed before the work.

## Design rules

These come from [`docs/README.md`](docs/README.md), the project's documentation contract. Read it before a material change.

1. **Timing survives everything else.** gpsd, chrony and NTP must never depend on the web UI, astronomy, SDR, sensors or a network service. A failing module must not alter clock discipline. Don't change chrony, gpsd or PPS configuration unless that is the point of the change.
2. **Say where every value comes from.** Each value carries exactly one provenance label: observed, calculated, modeled, predicted, inferred or external (`web/guidelines/Guidelines.md`). A stage that can't be observed shows UNKNOWN, never a guess. Stale data stays visibly stale.
3. **Don't claim more than the measurement shows.** No causes the evidence can't establish (jamming, spoofing, antenna failure). Repeatability is not absolute accuracy. The host clock's accuracy is not a USB sample's or a packet's.
4. **Offline first.** No mandatory cloud, no runtime CDN, web fonts from elsewhere or analytics.
5. **Spare the SD card.** RAM ring buffers, summarized events, atomic checkpoints. Nothing is written to disk every second.
6. **Respect location privacy everywhere,** including diagnostics, exports and derived values.
7. **Datasets bring their provenance and license** (`THIRD_PARTY_NOTICES.md`, `docs/licensing/open-source-policy.md`).

The web UI follows [`web/guidelines/Guidelines.md`](web/guidelines/Guidelines.md) exactly.

## Setting up

[`docs/development/new-machine.md`](docs/development/new-machine.md) covers a new machine: Python 3.11+, Node 22 with corepack (pnpm), git settings. The desktop demo needs no Pi, gpsd, chrony or Internet: `./scripts/run-demo.sh` (or `scripts\run-demo.ps1` on Windows), then open http://127.0.0.1:8080/.

## Checks (all must pass; CI runs them)

```sh
python -m compileall gps_time_pi tools tests
python tools/generate_config.py --help
python -m unittest discover -s tests -t . -v
cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run typecheck && corepack pnpm run test && corepack pnpm run build
```

Tests must not need live GNSS, the Internet or root. Use the fixtures in `tests/fixtures/`, temporary sysfs trees and manual clocks. CI runs Python 3.11 and 3.13 (the system Pythons of Debian 12 and 13) and Node 22. It fails on runtime CDN, font-host or analytics URLs and on font weight 700.

For changes to timing, GNSS, systemd units, `install.sh` or Pi hardware, say what you ran on a Pi and on which hardware and OS.

## Pull requests

- **Branches:** one branch per change, from `main`, with small commits. PRs are merged with a merge commit once CI passes.
- **Docs in the same PR:** update `docs/` alongside the code. That means a dated entry in `docs/provenance/change-log.md`, an ADR in `docs/decisions/` for an architectural change, and `docs/STATUS.md` (change the affected rows and add the PR link; if nothing changes status, say so in the PR).
- **Before committing:** check new content for secrets, credentials, precise coordinates and personal infrastructure.
  - Never commit a real station's coordinates. The only example location is the US Naval Observatory (38.9217, −77.0669); a second example point is the Washington Monument.
  - Use documentation addresses (192.0.2.x, 198.51.100.x, 203.0.113.x) and example hostnames.

## Hardware profiles

A new profile needs the evidence listed in [`docs/HARDWARE-PROFILES.md`](docs/HARDWARE-PROFILES.md) → "Adding profiles": vendor wiring, the PPS pin, sample `ppstest`, `gpsmon` and `chronyc sources -v` output, and the Pi model and OS it was tested on. A receiver that only outputs NMEA is not a precision-timing profile.

## Reporting bugs

Use the issue templates. The diagnostic snapshot (PPS Diagnostics → COPY) applies the station's location privacy mode, so set it to rounded or hidden before pasting one, and remove addresses and hostnames you don't want public. Security problems go privately: see [`SECURITY.md`](SECURITY.md).

## License

By contributing you agree that your contribution is licensed under the project's MIT License ([`LICENSE`](LICENSE)).
