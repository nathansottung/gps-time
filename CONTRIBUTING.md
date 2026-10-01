# Contributing

Contributions are welcome, especially reproducible fixes, hardware profiles, tests, documentation, and collectors that preserve the timing-core boundary.

## Design rules

1. The dashboard must never be required for chrony/gpsd to continue serving time.
2. A plugin/collector failure must not alter clock discipline.
3. Stale or unknown measurements must remain visibly stale or unknown.
4. Do not claim timing accuracy that the measurement method does not establish.
5. Prefer bounded RAM use and batched persistence on SD-card deployments.
6. New datasets must include provenance and licensing information.
7. Hardware-specific behavior must be documented and, where possible, tested independently from generic application logic.

## Before opening a pull request

Run:

```bash
python -m compileall gps_time_pi tools
python tools/generate_config.py --help
```

For timing, GPS, systemd, or Pi-hardware changes, include the relevant Pi-side validation and describe the hardware/software environment used.
