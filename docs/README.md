# GPS Time documentation contract

This directory is part of the product. Coding agents and human contributors should read this file before making material changes.

## Project thesis

GPS Time is an **open-source, timing-first, offline-capable measurement platform**. GNSS/PPS establishes trustworthy time and station position. NTP is the first application; astronomy, solar calculations, networking, SDR, ADS-B, sensors, and distributed observations layer on top without becoming dependencies of the timing core.

## Non-negotiable architecture rules

1. **Timing survives optional-feature failure.** gpsd/chrony/NTP must not depend on astronomy, SDR, weather, maps, dashboard widgets, or network coordinators.
2. **Measurement meaning is explicit.** Distinguish observed, calculated, modeled, and inferred values. Do not turn statistical repeatability into absolute accuracy.
3. **Clock accuracy is not event timestamp accuracy.** A PPS-disciplined host does not make a USB SDR sample, camera frame, ADC sample, or network packet equally precise.
4. **Offline-first.** Normal station operation should not require the Internet. External NTP, live orbital/weather/space-weather feeds, software updates, and network science are optional.
5. **Open protocols and project-authored code.** Core scientific capabilities must not require a proprietary cloud or closed protocol. Third-party datasets/services remain under their own licenses.
6. **Resource isolation.** Optional collectors/modules must have bounded CPU, RAM, disk and network behavior and must not starve the timing core.
7. **Privacy is granular.** Exact station coordinates, raw IQ, and distributed observations are not public merely because they exist locally.
8. **Document the change.** New material behavior requires roadmap/status updates and, when architectural, an ADR.

## Current code state

- `v1.3.0` is the deployed historical baseline described in `deployment-runbook.md`.
- This development bundle identifies itself as `1.4.0-dev` because it adds a configurable dashboard, Windows demo mode, build/deploy tooling and expanded repository documentation.
- CHG-001/CHG-002 (2026-09-27, see `provenance/CHG-001-002-foundation-correction.md`) addressed GNSS survey freshness and the fresh-install logging failure; automated tests live in `tests/`.
- The source-review blockers in `review/source-review-2026-09-07.md` and `review/GPS-Time-Independent-Review-2026-09-27.md` are **not all resolved**. Do not tag a stable public release until the measurement-freshness, chrony-history semantics, persistence, and administrative-security items are closed or explicitly dispositioned.

## Read next

1. `architecture/system-overview.md`
2. `roadmap/feature-registry.md`
3. `science/quantity-registry.md`
4. `science/timing-metrology.md`
5. `sdr/overview.md`
6. `development/windows-demo.md`
7. `development/raspberry-pi-deploy.md`
8. `licensing/open-source-policy.md`

## Feature maturity vocabulary

- **Supported** — implemented and intended for ordinary use after listed validation.
- **Experimental** — implemented/prototyped or technically credible, but still being characterized.
- **Research** — scoped exploration; not a product capability claim.
- **Deferred** — intentionally outside the active implementation sequence.
- **Historical** — present in the baseline, but may require correction before stable release.
