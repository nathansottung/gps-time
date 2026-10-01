# CHG — PPS Health, Failure Diagnostics, and Web UI Observability

## Status

REQUIRED

This change is part of the core GPS Time Pi station functionality and must be implemented, tested, documented, and exposed through the web dashboard.

It is not merely a diagnostic/development feature.

---

## Motivation / Observed Real-World Incident

The station entered NTP failover and apparently remained there for multiple days.

During the incident:

- GNSS satellite reception remained available.
- Approximately 10 satellites were visible/tracked.
- Individual GPS satellites showed strong received signal levels, including approximately 41–43 dB-Hz.
- Timing DOP was approximately 0.73.
- GNSS/NMEA information continued reaching the station.
- The Uputronics GPS HAT green indicator continued flashing approximately once per second.
- The station nevertheless was not using PPS as its synchronization source and remained on network-time failover.

This exposed an important observability problem.

The existing dashboard can make GNSS reception appear healthy without making it sufficiently obvious that the precision PPS timing chain has failed.

The station must never reduce these conditions to a single "GPS available" state.

---

# Required Timing-Chain Model

The software shall independently monitor and report:

1. GNSS receiver communication
2. GNSS satellite reception
3. GNSS navigation/time solution
4. Linux PPS device existence
5. Kernel PPS event reception
6. PPS event frequency
7. Age of most recent PPS event
8. chrony PPS source visibility
9. chrony PPS reachability
10. chrony PPS acceptance
11. chrony currently selected source
12. system synchronization state
13. fallback source, when applicable
14. duration of the current degraded/failover state

Where hardware cannot directly expose a particular stage, the UI must say UNKNOWN or NOT DIRECTLY OBSERVABLE rather than infer that it is healthy.

---

# Critical Distinction

The following states are NOT equivalent:

- GNSS AVAILABLE
- PPS DEVICE PRESENT
- PPS PULSES PRESENT
- PPS AVAILABLE TO CHRONY
- PPS ACCEPTED BY CHRONY
- PPS SELECTED BY CHRONY
- SYSTEM SYNCHRONIZED

The software must not collapse them into one boolean.

For example:

- GNSS may be healthy while PPS is absent.
- PPS may be physically present while chrony rejects it.
- chrony may see PPS but temporarily select another source.
- The system clock may remain synchronized from network NTP while precision GNSS/PPS timing is unavailable.

All of these conditions must be distinguishable.

---

# Dashboard Requirement

The main station webpage shall make the current timing source and PPS state immediately visible without requiring SSH access.

A user should not have to inspect chrony manually to discover that the station has been operating on failover for several days.

Suggested presentation:

```
TIMING STATUS

GNSS
HEALTHY
10 satellites tracked
TDOP 0.73
Best C/N0 43 dB-Hz

PPS DEVICE
PRESENT
/dev/pps0

PPS SIGNAL
HEALTHY
Last pulse: 0.18 s ago
Rate: 1.000000 Hz

CHRONY PPS
NOT SELECTED
Reach: 377
Last sample: ...
Reason/status: ...

SYSTEM CLOCK
NETWORK FAILOVER

Current source: <source>
Current stratum: <value>

PPS unavailable/unused for:
2d 07h 14m
```

The exact visual design may follow the existing dashboard design system.

The information hierarchy is mandatory.

---

# Main Status Banner

The top-level status banner must distinguish precision timing from fallback.

Do NOT display a generic `SYNCHRONIZED` when GNSS/PPS timing is unavailable but Internet NTP is keeping the system clock synchronized.

Instead use states such as:

- `SYNCHRONIZED · GPS/PPS · STRATUM 1`
- `SYNCHRONIZED · NETWORK FAILOVER` / `GPS/PPS UNAVAILABLE`
- `DEGRADED · GNSS HEALTHY · PPS NOT SELECTED`
- `HOLDOVER · NO EXTERNAL REFERENCE`

Exact wording can be refined, but the source of synchronization must always be apparent.

---

# PPS Diagnostic Card

Add a dedicated PPS diagnostic card/page.

At minimum expose:

## Device

- expected PPS device
- whether `/dev/pps0` exists
- device metadata where useful
- configured GPIO
- configured PPS edge/polarity if known

## Live PPS

- latest PPS timestamp
- age of latest event
- event frequency
- consecutive pulses
- missed pulse count
- recent pulse interval statistics

Useful statistics include:

- mean interval
- minimum interval
- maximum interval
- standard deviation/jitter where meaningful

Do not imply that Linux-observed PPS jitter is equivalent to receiver or electrical PPS jitter.

Label the measurement layer.

## chrony

Expose:

- PPS source present
- source mode
- reach
- selected/not selected
- offset
- frequency/skew information where relevant
- reference/source ID
- last sample
- chrony source status symbol
- rejection/unusable state where determinable

Do not invent a causal explanation when chrony does not expose one.

---

# PPS State Classification

Implement an explicit PPS state machine.

Suggested states:

- PPS_UNKNOWN
- PPS_DEVICE_MISSING
- PPS_DEVICE_PRESENT_NO_EVENTS
- PPS_EVENTS_PRESENT
- PPS_CHRONY_VISIBLE
- PPS_CHRONY_REJECTED
- PPS_CHRONY_ACCEPTED
- PPS_SELECTED
- PPS_LOST
- PPS_RECOVERING

State names may be refined during implementation.

The important requirement is that the underlying conditions remain distinguishable.

---

# PPS Age / Watchdog

Continuously determine:

- last_pps_event
- pps_age_seconds
- pps_interval
- pps_frequency

Suggested default interpretation:

- < 1.5 seconds: HEALTHY
- 1.5–3 seconds: DEGRADED / MISSED EVENT
- > 3 seconds: PPS LOST

Thresholds should be configurable.

Do not continuously write PPS events to the SD card at 1 Hz merely to implement this feature.

Use RAM/current-state storage and persist summarized events appropriately.

---

# Failure Event Recording

When PPS disappears, create ONE outage event.

Example:

```
PPS OUTAGE

Started:
2026-09-28 03:14:22 UTC

Recovered:
2026-09-30 17:41:09 UTC

Duration:
2d 14h 26m 47s

GNSS remained available:
YES

GNSS fix remained available:
YES

Satellite range:
8–13

Median C/N0:
...

Kernel PPS:
NO EVENTS

chrony fallback:
NETWORK NTP
```

Do not create thousands of duplicate "PPS failed" events.

The event remains open until recovery.

---

# Recovery Event

When PPS returns, automatically close the outage.

Record:

- recovery timestamp
- total outage duration
- GNSS condition during outage
- source used during outage
- maximum observed system offset
- holdover/fallback behavior
- time required for chrony to accept PPS again
- time required for PPS to become selected again

Preserve this for historical analysis.

---

# Historical UI

Add PPS history to the web UI.

Required views:

- current PPS uptime
- last PPS outage
- longest PPS outage
- outages in last 24 hours
- outages in last 7 days
- PPS availability percentage
- total PPS unavailable time
- timeline of PPS state
- relationship between PPS loss and GNSS availability

The timeline should distinguish at least:

- GNSS healthy + PPS healthy
- GNSS healthy + PPS failed
- GNSS failed + PPS failed
- PPS present + chrony not using PPS
- network failover
- holdover

---

# Diagnostic Snapshot

Add a user-facing diagnostic output that can be copied/downloaded from the web UI.

Example:

```
GPS TIME PI DIAGNOSTIC SNAPSHOT
Generated: <UTC timestamp>

GNSS:
Receiver communication: OK
Fix: OK
Satellites visible: 14
Satellites used: 10
TDOP: 0.73
Best C/N0: 43 dB-Hz

PPS:
Device: /dev/pps0
Device present: YES
Events detected: NO
Last event: <timestamp>
Age: 2d 04h 18m
Expected GPIO: 18

CHRONY:
PPS source visible: YES/NO
PPS selected: NO
Current selected source: <source>
System stratum: <value>

SYSTEM:
Timing mode: NETWORK FAILOVER
Failover duration: 2d 04h 17m

RECENT EVENTS:
<events>
```

This should make remote troubleshooting possible without requiring the operator to SSH into the station.

Provide a COPY DIAGNOSTICS control.

Optionally provide DOWNLOAD DIAGNOSTICS.

Do not include precise location when privacy/location hiding is enabled.

---

# Advanced Diagnostics

The diagnostic page should additionally expose useful read-only information currently obtained manually from commands equivalent to:

```
ls -l /dev/pps*
ppstest /dev/pps0
chronyc sources -v
chronyc sourcestats -v
chronyc tracking
```

plus relevant PPS kernel/device information.

The web service should obtain the underlying information safely.

DO NOT implement arbitrary shell-command execution from the browser.

The dashboard remains read-only with respect to these diagnostics.

---

# Current Incident Classification

Based on currently observed evidence, the present incident should initially be represented as:

```
GNSS RECEPTION:          HEALTHY
GNSS TELEMETRY:          HEALTHY
HARDWARE PPS INDICATOR:  OBSERVED FLASHING AT ~1 Hz
KERNEL PPS:              UNKNOWN UNTIL TESTED
CHRONY PPS:              APPARENTLY NOT SELECTED
SYSTEM CLOCK:            NETWORK FAILOVER
```

The software must NOT currently classify this as:

- ANTENNA FAILURE
- GPS JAMMING
- GPS SPOOFING
- PPS HARDWARE FAILURE

because the available evidence does not establish any of those causes.

The next diagnostic boundary is whether `/dev/pps0` exists and whether the Linux PPS subsystem is receiving events.

---

# Relationship to GNSS Integrity Monitoring

This work is also foundational to the planned GNSS jamming/spoofing/integrity-monitoring feature.

A PPS-path failure must not be mistaken for RF interference.

Example: GNSS SIGNALS HEALTHY + NAVIGATION HEALTHY + PPS LOST should generate `PPS PATH ANOMALY` rather than `POSSIBLE GNSS JAMMING`.

Conversely: MASS C/N0 COLLAPSE + MULTI-CONSTELLATION SATELLITE LOSS + NAVIGATION LOSS + PPS LOSS may justify `POSSIBLE GNSS RF INTERFERENCE`.

The event-correlation layer must use evidence from multiple subsystems.

---

# Tests Required

Add automated tests covering at minimum:

1. `/dev/pps0` absent.
2. `/dev/pps0` present but no events.
3. Healthy 1 Hz PPS.
4. Single missed PPS.
5. Sustained PPS loss.
6. PPS recovery.
7. PPS visible to chrony but rejected.
8. PPS accepted but not selected.
9. PPS selected normally.
10. GNSS healthy while PPS fails.
11. GNSS and PPS fail together.
12. Network failover after PPS loss.
13. Return from failover to PPS.
14. Outage event created once.
15. Outage event correctly closed.
16. Duration survives service restart where appropriate.
17. Diagnostic snapshot contains correct state.
18. Privacy mode does not leak precise coordinates.
19. Existing offline/demo mode continues functioning.
20. UI does not report Stratum 1 GPS/PPS when PPS is not actually selected.

Use fixtures/mocks where hardware is unavailable.

Do not make tests depend on live Internet or live GNSS reception.

---

# Documentation

Document this architecture under `/docs/`.

At minimum document:

- GNSS/PPS timing chain
- PPS state definitions
- chrony state interpretation
- failover behavior
- diagnostic data sources
- outage/event schema
- dashboard status semantics
- troubleshooting procedure
- distinction between GNSS RF health and PPS health

The documentation should allow a future coding/review agent to understand why these distinctions exist.

---

# Acceptance Criteria

This change is complete when the following scenario can be diagnosed from the web interface alone:

The station has good satellite reception and valid GNSS telemetry, but has been operating on network failover for two days.

Without SSH, the operator must be able to determine:

1. GNSS is still being received.
2. Whether `/dev/pps0` exists.
3. Whether PPS events are reaching Linux.
4. When the most recent PPS event occurred.
5. Whether chrony sees PPS.
6. Whether chrony accepts PPS.
7. Whether chrony currently selects PPS.
8. Which source currently disciplines the system clock.
9. How long the station has been in failover.
10. When the failure began.
11. Whether similar failures happened previously.
12. What happened to system clock accuracy during the outage.

The dashboard must never imply that GPS/PPS precision timing is healthy solely because GNSS satellites are visible or because the system remains synchronized through network NTP.

---

# Immediate Operator Action

Before rebooting or restarting chrony during the current incident, capture:

```
ls -l /dev/pps*
timeout 8 sudo ppstest /dev/pps0
chronyc sources -v
chronyc sourcestats -v
chronyc tracking
dmesg | grep -i pps
```

This evidence should be preserved before remediation because the current multi-day failure provides a useful real-world validation case for this change.
