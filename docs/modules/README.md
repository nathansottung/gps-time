# Building a module

A module adds a sensor, a reference signal, an analysis or a dashboard card without touching the timing core. Spec: [`../specs/SPEC-EXTENSIBILITY.md`](../specs/SPEC-EXTENSIBILITY.md). Decision: [ADR-0007](../decisions/ADR-0007-module-architecture.md).

**Where things stand:** the interfaces, manifest, schemas, `ctx`, loader and scaffolder exist (`gps_time_pi/modkit/`, `tools/new_module.py`). The web service doesn't load modules yet, so a station behaves exactly as before. Modules run in the host's process for now: declared permissions are recorded but not enforced, and there are no CPU or memory caps (see "Safety" below).

## 1. Create it

```bash
python tools/new_module.py my-sensor --type source      # or reference, analysis, ui
```

This creates `modules/my-sensor/`:

```
modules/my-sensor/
  module.toml          manifest
  README.md            what it does, hardware, setup, limits, provenance
  my_sensor/           Python package with a working fake (source.py)
  fixtures/sample.json data for tests and the demo
  tests/               tests that pass as created
  web/Card.tsx         UI card stub
```

Then:

```bash
python -m gps_time_pi.modkit check                 # every manifest valid?
python -m unittest tests.test_modules -v           # every module's tests
python -m gps_time_pi.modkit demo my-sensor        # run it from its fixtures, print what it emits
```

## 2. Fill in the manifest

`module.toml` (schema: [`schemas/manifest.v1.json`](../../schemas/manifest.v1.json)):

| Field | Meaning |
|---|---|
| `name` | Same as the folder. Lowercase letters, digits, hyphens. |
| `version` | The module's own version, `X.Y.Z`. |
| `types` | `source`, `reference`, `analysis`, `ui`, `receiver`. |
| `maturity` | `experimental`, `supported` or `research`. A module becomes `supported` with a maintainer, tests, docs and a record of running on real hardware. |
| `interface` | The interface version it needs, `M.m` ([interfaces.md](interfaces.md)). |
| `[entry]` | For each code type: `"package.module:Class"`. |
| `[hardware]`, `[timing]` | What it needs, and what it does when the station's timing is worse than that. |
| `[permissions]` | `network` (true/false), `devices` (paths), `storage` (`none`, `ram`, `disk:<N>MiB`). |
| `[config]`, `[emits]` | Its settings, and the streams and events it emits. |
| `[licence]` | `code` (MIT for this repository) and any bundled data's licence and source. |

## 3. Write the code

- A **source** reads a device and calls `ctx.emit(Observation(...))`. In demo mode (`ctx.config["demo"]`) it replays its fixtures. Without a device it emits nothing: never invent data.
- A **reference** lists transmitters near `site` and predicts their delay. `site` is `None` in hidden privacy mode; then nothing can be computed.
- An **analysis** turns observations into `Result`s with uncertainty, the method and the inputs used.
- Every value goes through `gps_time_pi.labels.q(value, unit, provenance)`. A value that can't be established is `None`, not a guess.
- A module reads time and timing quality from `ctx`. It never changes chrony, gpsd or PPS settings, and gets positions only through `ctx.site()`.

Interfaces and `ctx`: [interfaces.md](interfaces.md). Data contracts: [schemas.md](schemas.md). Sample data files: [observation-format.md](observation-format.md).

## 4. Enable it on a station

Modules are off by default. A module runs only when it is named in the station config:

```json
{"modules_enabled": ["my-sensor"]}
```

The loader refuses a module, with the reason, when:
- its manifest is invalid;
- it needs a newer interface;
- its entry point doesn't import, or isn't the right kind of class;
- it asks for storage the host doesn't give.

An exception in a module marks that module failed; the host carries on. Everything a module emits is checked against the schemas, and invalid items are dropped and counted.

## Safety, now and next

| Rule (spec "Module safety") | Now |
|---|---|
| Off by default; the owner enables each | Yes |
| A crash never affects timing | Yes: contained per module; the timing core doesn't use modules |
| Declared permissions only | Recorded and shown; not enforced (same process) |
| Own unprivileged process, systemd hardening | Next |
| CPU, memory, disk and SD write caps | Storage cap only (`ctx.storage`); the rest next |

## Example

[`modules/sdr-pps-marker/`](../../modules/sdr-pps-marker/README.md) is the first module: a research source that finds the PPS pulse inside an SDR's samples. `python -m gps_time_pi.modkit demo sdr-pps-marker` runs it on synthetic data.
