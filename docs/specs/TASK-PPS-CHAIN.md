# Task: PPS timing chain (backend)

## Standing rules
- Station tier stays lightweight and works offline. Heavy analysis belongs in the optional coordinator tier. No mandatory cloud.
- Minimize SD writes: RAM ring buffers, summarized events, atomic checkpoints.
- Label every value with one provenance label: observed, calculated, modeled, predicted, inferred, external. Never infer health for a stage we can't observe; say UNKNOWN.
- Never name a cause (jamming, spoofing, antenna failure) the evidence can't establish.
- Don't change timing behavior (chrony config, gpsd, PPS setup) unless the task says so.
- Respect location privacy mode everywhere, including diagnostics output.
- Tests must not need live GNSS, Internet, or root. Use fixtures.
- UI follows web/guidelines/Guidelines.md.
- One feature branch per task. Small commits. Update docs/ in the same branch.

## Context
The Pi spent days on network failover while GNSS stayed healthy and the HAT LED pulsed at 1 Hz. A reboot fixed it. That points to a software or startup fault, likely chrony losing usable NMEA samples so `lock NMEA` leaves PPS unused. The event log must show which link broke first.

## Task (branch feat/pps-chain)
Implement docs/specs/CHG-PPS-HEALTH-DIAGNOSTICS.md, backend only.

- New module gps_time_pi/pps.py: read /sys/class/pps/pps0/assert (timestamp#sequence) each poll. Derive last event time, age, interval, rate, consecutive pulses, missed pulses, and interval stats (mean/min/max/stdev) from a RAM ring buffer. Label these as Linux-observed, not electrical jitter. No 1 Hz disk writes.
- Extend chrony.py: parse `chronyc -n sources` and sourcestats for the PPS and NMEA refclocks (mode, state symbol, reach, offset, last sample). Track NMEA health as its own stage. Never claim a rejection reason chrony doesn't expose.
- Timing-chain model with independent stages: receiver comms, satellite reception, nav/time solution, PPS device, kernel events, NMEA refclock, chrony PPS visible, accepted, selected, system sync, fallback source, failover duration.
- PPS state machine: UNKNOWN, DEVICE_MISSING, DEVICE_PRESENT_NO_EVENTS, EVENTS_PRESENT, CHRONY_VISIBLE, CHRONY_REJECTED, CHRONY_ACCEPTED, SELECTED, LOST, RECOVERING. Configurable age thresholds (default 1.5 s / 3 s).
- Replace sync_state() so the banner always names its source: GPS/PPS STRATUM 1, NETWORK FAILOVER, DEGRADED (GNSS HEALTHY, PPS NOT SELECTED), HOLDOVER. Never report Stratum 1 GPS/PPS unless PPS is selected.
- Generic event model (start, end, duration, severity, evidence, classification, confidence). A PPS outage is one open event, closed on recovery, surviving restart through a small checkpoint file.
- Classify GNSS healthy + PPS lost as PPS PATH ANOMALY, never interference.
- JSON endpoint /api/timing-chain.
- All 20 tests listed in the CHG spec, plus one for "NMEA refclock stale while PPS pulses arrive", with fixtures for sysfs and chronyc output.
- docs/architecture/timing-chain.md: states, chrony interpretation, event schema.
- Demo mode keeps working, with synthetic data for each state.

Report when done. Don't push until I confirm.
