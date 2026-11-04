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
- **The Pi bundle** ships the kit and `schemas/`, but not `modules/`. *Amended: since #146 (owner, 2026-10-27) `install.sh` installs the bundled modules, all off, so the bundle ships `modules/` too. That half was missed until v1.6.0-rc.1 failed to install (#155); `tests/test_bundle_install.py` now runs `install.sh` from a built bundle.*

## Consequences

- Contributors have one pattern, and tests that run on a laptop.
- **Isolation (added in #120):** every module runs in its own process as the unprivileged `gps-time-mod` user, under a hardened supervisor service that is installed but not enabled. Per process: memory and file-size limits, CPU share, memory and output watched by the host, and a permission guard for network, devices, writes, processes and ctypes. Details: `docs/modules/README.md`, "Safety". Still open: one user per module.
- **Experimental modules switch (added in #125):** Administration → Experimental modules, behind the admin token. A master switch (`modules_experimental`, off by default) gates every module; turning it on or off clears `modules_enabled`, so modules stay off until each is turned on by itself. The web service reads manifests (`modkit/settings.py`) and the supervisor's status file to list them, and never imports module code. The supervisor re-reads the config, so a change needs no restart.
- Wiring module output into the web service (cards) is a later step.
