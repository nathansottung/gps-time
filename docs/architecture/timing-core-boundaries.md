# Timing core boundaries

## Required distinction

`GNSS PPS accuracy` ≠ `Pi system clock accuracy` ≠ `NTP client accuracy` ≠ `sensor/event timestamp accuracy`.

Each layer has its own bias, jitter and calibration state.

## Failure isolation

The following failures must not stop chrony/NTP:

- web dashboard crash
- Skyfield/ephemeris absence
- SDR disconnect
- ADS-B decoder crash
- weather-sensor failure
- terrain/data-pack corruption
- analysis-node outage
- coordinator/network outage

## Administration

The current historical admin implementation needs hardening. Stable scope calls for an unprivileged web service, read-only default operation, authenticated/authorized state-changing actions, POST semantics for mutations, and narrowly scoped privileged helpers.
