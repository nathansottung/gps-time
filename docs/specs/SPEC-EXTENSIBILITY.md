# SPEC — Building on GPS Time: Module Architecture

## Status

NEXT. Defines how every future feature is added. New features after v1.5.0 should be built as modules under this spec.

## Goal

Anyone should be able to add a sensor, a reference signal, an analysis, or a dashboard card without touching the timing core, by following one documented pattern, with tests that run on a laptop and no hardware.

## Principles

1. **The timing core stays small and stable.** Modules read time and timing quality from it; they never change chrony, gpsd or PPS settings.
2. **One pattern for every module.** Same layout, same manifest, same tests.
3. **Every value is labeled.** Provenance (observed, calculated, modeled, predicted, inferred, external) and units are required, not optional.
4. **Every module runs without hardware.** A fixture or demo source is part of the module.
5. **Modules are optional.** A station with none enabled behaves exactly as today.
6. **Privacy is inherited.** Modules get positions only through the station's privacy-filtered API.

## Module types

| Type | What it does | Examples |
|---|---|---|
| **source** | Reads a device and emits timestamped observations | SDR capture, Raspberry Shake, infrasound, VLF receiver, muon detector, weather sensor |
| **reference** | Describes signals with known or self-reported transmitter positions, and predicts their delay at this station | ATSC towers, FM towers, NOAA, ADS-B aircraft, AIS ships, WWV |
| **analysis** | Turns observations into results | Tower delay check, MLAT solve, lightning location, thunder ranging, oscillator fit |
| **ui** | Adds a card or page to the dashboard | Receivers page, lightning map, reference-signal table |

A module may contain more than one part (e.g. a source and its UI card).

## Layout

```
modules/<name>/
  module.toml          manifest
  README.md            what it does, hardware, setup, limits, provenance
  <name>/              Python package (source / reference / analysis)
  web/                 optional UI card(s)
  fixtures/            recorded or synthetic data for tests and demo
  tests/
```

## Manifest (`module.toml`)

- name, version, type(s), maturity (`experimental`, `supported`, `research`)
- hardware required (none, SDR, sensor model…)
- timing needed (e.g. "ms", "µs", "100 ns") and what it does if the station's timing is worse
- permissions needed (none, network, device access)
- config schema
- events and streams it emits, with schema versions
- licence of any bundled data, with source and attribution

## Interfaces (Python)

- `Source.start(ctx)`, `Source.stop()`; emits `Observation` objects through `ctx.emit()`.
- `Reference.list(site)` returns transmitters with position, frequency, bandwidth and position source; `Reference.predict(site, tx, t)` returns expected delay with uncertainty.
- `Analysis.handle(observation)` or `Analysis.run(window)`; emits `Result` objects.
- `ctx` gives: current time, timing quality (state, offset bound), privacy-filtered site, config, logger, storage with size caps.

Each interface is documented with types, units and an example in `docs/modules/`.

## Data contracts

- **Observation:** time (UTC, ns), timing-quality snapshot, value(s) with units and provenance, source module, schema version.
- **Event:** the existing event model (start, end, severity, evidence, classification, confidence).
- **Result:** value(s), uncertainty, method, inputs used, provenance.
- Schemas are versioned JSON Schema files in `schemas/`. Breaking changes need a new version.
- Exchange formats: RINEX (GNSS), miniSEED (seismic/infrasound), SigMF (RF), JSON (events).

## UI cards

- Cards follow `web/guidelines/Guidelines.md` and use the existing components (MetricRow, ProvenanceTag, MaturityBadge).
- A module's card is listed on the Configure page and can be shown or hidden.
- Cards must render from the demo adapter with the module's fixtures.

## Tooling

- `tools/new_module.py <name> --type source` creates the full layout, manifest, a fake source, a test and a UI card stub that pass out of the box.
- `pytest modules/<name>` and `pnpm test` run a module's tests alone.
- CI runs every module's tests and validates every manifest and schema.
- `--demo` mode runs all enabled modules from their fixtures.

## Reference modules to build first (as examples)

1. **reference-adsb:** aircraft report their own GPS position, so the station knows the true distance and time of flight to each. Shows the pattern for self-reported references; rejects outliers.
2. **reference-broadcast-towers:** loads public licence data for FM/ATSC/NOAA towers near the rounded site; predicts delays from the surveyed position.
3. **analysis-tower-delay-check:** given a capture from an SDR source, compares measured against predicted arrival times.
4. **source-weather:** simple BME280-class sensor; the minimal source example.

These four teach every module type and become templates for contributors.

## Documentation

- `docs/modules/README.md`: the guide, start to finish, using `source-weather` as a worked example.
- `docs/modules/interfaces.md`, `docs/modules/schemas.md`.
- `docs/architecture/overview.md`: a one-page diagram of core, modules, coordinator.
- Each roadmap item links to the module type it will become.

## Community

- Issue labels: `good first issue`, `module idea`, `hardware`, `science`, `docs`.
- Issue templates: new module proposal (what it measures, hardware, timing needed, data licence).
- A "Modules" table in the README listing each module, maturity and maintainer.
- Contributors keep ownership credit in each module's README.

## Order of work

1. Interfaces, manifest, schemas, `ctx` and the module loader, with no behaviour change to the station.
2. `new_module.py` and the docs guide.
3. `source-weather` example.
4. `reference-adsb` and `reference-broadcast-towers`.
5. `analysis-tower-delay-check`.
6. Move existing optional features (sky tools, references page) to modules where it simplifies them.
