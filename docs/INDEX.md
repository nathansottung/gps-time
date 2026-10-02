# GPS Time documentation index

Start with [`README.md`](README.md). It defines the repo documentation contract and non-negotiable architecture rules.

## Specifications (owner-provided, imported 2026-10-01)
- `specs/CHG-PPS-HEALTH-DIAGNOSTICS.md` — REQUIRED change: PPS health, failure diagnostics, timing-chain observability, 20 required tests
- `specs/PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md` — timing-pipeline stages, PPS-loss events and graphs, holdover projections, GNSS integrity/interference/spoofing monitoring
- `specs/ADDENDUM-SKY-SOLAR-SATELLITE.md` — roadmap addendum: Earth shadow and satellite illumination, solar time and geometry, sky obstruction, observing conditions, provenance
- `specs/TASK-PPS-CHAIN.md` — implementation task for the PPS timing-chain backend (branch `feat/pps-chain`)

## Architecture
- `architecture/system-overview.md`
- `architecture/compute-tiers.md`
- `architecture/observation-model.md`
- `architecture/timing-core-boundaries.md`
- `architecture/timing-chain.md` — GNSS → PPS → chrony stages, PPS state machine, status banner, outage events, `/api/timing-chain`

## Roadmap
- `roadmap/current-scope.md`
- `roadmap/feature-registry.md` — canonical comprehensive feature inventory
- `roadmap/ROADMAP-DESKTOP-FIELD-APP.md` — FUTURE, not scheduled: cross-platform desktop field / ham-radio app (laptop + GNSS receiver as an off-grid time source); starts only after the Pi station specs are complete
- legacy planning: `PROJECT-SCOPE.md`, `NEXT-ITERATION.md`, `ideas-ledger.md`

## Science
- `science/quantity-registry.md`
- `science/timing-metrology.md`
- existing: `GNSS-SURVEY-AND-INSTALLATION.md`, `almanac-design-scope.md`

## SDR / RF
- `sdr/overview.md`
- `sdr/timing-model.md`
- existing: `open-lightning-network.md`, `platform-extensions.md`

## Dashboard
- `dashboard/README.md`
- professional concept image: kept outside the repository (provenance unrecorded; not distributed)

## Web prototype
- `../web/` — React/Vite UI being ported to become the Pi UI; served by the station at `/app/` and wired to the API through a typed client (`web/src/api/`). Legacy pages stay until parity.
- `dashboard/web-ui-parity.md` — legacy features the new UI still lacks
- `../web/guidelines/Guidelines.md` — UI guidelines all project UI must follow

## API
- `api/README.md` — station HTTP API conventions and index
- `api/endpoints.md` — every route: parameters, responses, side effects, privacy notes

## Development
- `development/windows-demo.md`
- `development/raspberry-pi-deploy.md`
- `development/new-machine.md` — setting up a new development machine (clone, identity, line endings, Python, pnpm, tests)
- existing: `DEVELOPMENT.md`, `GITHUB-PUBLISHING.md`, `deployment-runbook.md`

## Hardware
- `hardware/README.md`
- `HARDWARE-PROFILES.md`

## Licensing / decisions / provenance
- `licensing/open-source-policy.md`
- `decisions/` (ADR-0004: web UI served at `/app/` beside the legacy pages)
- `provenance/change-log.md`

## Source review
- `review/source-review-2026-09-07.md`
- `review/review-evidence-2026-09-07.zip`
- `review/GPS-Time-Independent-Review-2026-09-27.md` — independent whole-repository review of the 2026-09-18 archive

## Change records
- `provenance/change-log.md`
- `provenance/CHG-001-002-foundation-correction.md` — GNSS fresh-epoch gating; fresh-install logging repair
