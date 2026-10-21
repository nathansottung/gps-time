# ADR-0007: Modules through one kit, off by default, outside the timing core

**Status:** Accepted (owner request, 2026-10-21; SPEC-EXTENSIBILITY order of work steps 1–2).

## Context

Every feature after the timing core (sensors, reference signals, analyses, cards) was to be built as a module (`specs/SPEC-EXTENSIBILITY.md`). The first module, `modules/sdr-pps-marker`, existed as a library with no way to load it.

## Decision

- **One kit**, `gps_time_pi/modkit/`, standard library only:
  - interfaces (Source, Reference, Analysis; Observation, Result, Transmitter), with semver `INTERFACE_VERSION` 1.0.0;
  - manifest checks;
  - versioned JSON schemas in `schemas/`;
  - `ctx` (clock, timing quality, privacy-filtered site, config, emit, log, capped storage);
  - the loader and host.
- **Modules live in `modules/<name>/`** with one layout. `tools/new_module.py` creates it with a working fake and passing tests.
- **Off by default.** A module runs only when it is named in the station config (`modules_enabled`). The web service doesn't use the kit yet, so a station's behaviour is unchanged.
- **Contained.** A module's exception fails that module only. Everything emitted is checked against the schemas. Modules get positions only through `ctx.site()` and can't reach chrony, gpsd or PPS settings through the kit.
- **The Pi bundle** ships the kit and `schemas/`, but not `modules/`.

## Consequences

- Contributors have one pattern, and tests that run on a laptop.
- **Not yet:** process isolation and resource caps. Modules run in the host's process, so declared permissions (network, devices) are recorded but not enforced. Before any module runs on a station by default, each module gets its own unprivileged process (a systemd unit with the web service's hardening) and CPU and memory caps. Until then, enabling a module trusts its code.
- Wiring the host into the web service (status, cards) is a later step.
