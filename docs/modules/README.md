# Building a module

A module adds a sensor, a reference signal, an analysis or a dashboard card without touching the timing core. Spec: [`../specs/SPEC-EXTENSIBILITY.md`](../specs/SPEC-EXTENSIBILITY.md). Decision: [ADR-0007](../decisions/ADR-0007-module-architecture.md).

**Where things stand:** the interfaces, manifest, schemas, `ctx`, loader and scaffolder exist (`gps_time_pi/modkit/`, `tools/new_module.py`). Every module runs in its own sandboxed process ("Safety" below). The web service never loads modules. A station runs them only under `gps-time-modules.service`, which is installed but not enabled.

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

Modules are off by default, behind two settings: the **experimental modules switch** (`modules_experimental`) and each module's own setting (`modules_enabled`). With the switch off, no module runs. Turning the switch on, or off, clears `modules_enabled`, so after it every module is off until it is turned on by itself.

On a station:

1. Copy the module to `/opt/gps-time-pi/modules/<name>/`, readable by everyone (`sudo chmod -R a+rX`).
2. In the web UI, **Administration → Experimental modules** (admin token): turn the switch on, then turn the module on. Or by hand in the station config: `{"modules_experimental": true, "modules_enabled": ["my-sensor"]}`. Optional: `"module_config": {"my-sensor": {...}}`, and `"module_limits"` to lower the host's maximums.
3. If it needs a device or the network, also add a drop-in to the service (`sudo systemctl edit gps-time-modules`): `PrivateDevices=no` plus `DeviceAllow=/dev/...`, or `IPAddressAllow=...`. The manifest permission alone isn't enough.
4. `sudo systemctl enable --now gps-time-modules`. Status (RAM): `/run/gps-time-modules/status.json`, also shown on the Administration card.

The supervisor checks the config file at each 10 s status publish and restarts its set of modules when the module settings change, so the switches take effect without restarting the service. The web service only reads manifests for the card; it never imports module code.

The host refuses a module, with the reason, when:
- its manifest is invalid;
- it needs a newer interface;
- it asks for storage the host doesn't give;
- the sandbox isn't available on the platform.

A module whose entry point doesn't import, or isn't the right kind of class, fails in its own process; the host never imports module code. Everything a module emits is checked against the schemas, and invalid items are dropped and counted.

## Safety

Each module runs in its own process (`gps_time_pi/modkit/runner.py`). Layers, outside in:

| Layer | What it enforces |
|---|---|
| `gps-time-modules.service` | systemd hardening as the web service, plus `PrivateDevices=yes` and `IPAddressDeny=any`: no module gets a device or the network unless the owner adds a drop-in. Totals: `MemoryMax=768M`, `CPUQuota=60%`, `TasksMax=128`. The supervisor keeps only `CAP_SETUID`, `CAP_SETGID`, `CAP_CHOWN` and `CAP_DAC_READ_SEARCH`. |
| Module user | Each module process drops to `gps-time-mod`, which has no supplementary groups. File permissions keep it out of the station config (exact position), the admin token and the station key. A module refuses to run as root. |
| Resource limits | Per process: address space (`[limits] memory_mib`, default 256, at most 512), file size (the storage cap), 64 open files, no core dumps. |
| Host watch | CPU share over 60 s (`[limits] cpu_percent`, default 25, at most 50), resident memory, output lines up to 1 MiB and 50 items per second. A module over a cap is killed, with the reason. |
| Storage | `ctx.storage` only: a size cap, and for `disk:` storage a write-rate cap of 4 MiB per hour (to spare the SD card). |
| Permission guard | A Python audit hook, installed before the module's code is imported, that can't be removed. It blocks: sockets without `network = true`; device files not listed in `devices`; writes outside the module's storage; starting processes; loading native libraries through ctypes; signalling processes; opening the paths the host denies. |

The guard binds Python code; a C extension could get round it. That is why the outer layers are OS-level: the module user, the resource limits and the service's own sandbox. Not yet: a separate user per module (all modules share `gps-time-mod`, so they could read each other's storage if file modes allowed it; storage folders are 0700).

On Windows (desktop demo) the sandbox isn't available. `python -m gps_time_pi.modkit demo` then runs the module unenforced, and says so; the host refuses unenforced modules everywhere else.

## Example

- [`modules/sdr-pps-marker/`](../../modules/sdr-pps-marker/README.md), the first module: a research source that finds the PPS pulse inside an SDR's samples. Its live capture (#140) reads an RTL-SDR through `rtl_tcp`, a separate service (`system/gps-time-rtl-tcp.service`, not installed by `install.sh`). It needs `network = true`, limited to localhost by a drop-in on the module service, and RAM storage. `python -m gps_time_pi.modkit demo sdr-pps-marker` runs it on synthetic data.
- [`modules/reference-adsb/`](../../modules/reference-adsb/README.md), the pattern for self-reported references: aircraft on 1090 and 978 MHz from a local decoder's `aircraft.json`.
  - Positions are `external` and checked before use; rejections are counted by reason.
  - It is both a `reference` (`list`, `predict`) and a `source`, because the host runs a module's `source` entry; the source emits what the reference computes.
  - `python -m gps_time_pi.modkit demo reference-adsb` replays its synthetic fixtures.
- [`modules/reference-broadcast-towers/`](../../modules/reference-broadcast-towers/README.md), the pattern for references from public records: FM, ATSC and NOAA Weather Radio transmitters.
  - The module has no network permission. The operator builds its offline cache with `build_cache.py` from exported records, and every position keeps its source and date.
  - `python -m gps_time_pi.modkit demo reference-broadcast-towers` predicts from its synthetic cache.
- [`modules/analysis-tower-delay-check/`](../../modules/analysis-tower-delay-check/README.md), the first `analysis`: measured against predicted tower delays, from PPS-marker-timed observation files. It finds the ATSC A/53 field sync, and does FM correlation between two sites' captures (TDOA, where the unknown emission time cancels). Needs numpy (a station dependency).
  - It emits `result/1` with inferred verdicts that never name a cause.
  - The host runs only `source` entries, so an analysis runs from its own command line: `python -m tower_delay_check demo` (from its folder).
