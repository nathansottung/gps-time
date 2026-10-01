# GPS Time Pi — PPS Observability and GNSS Integrity Improvements

## Context

A real-world failure/recovery state exposed an observability gap in the current GPS Time Pi dashboard.

Observed state:

- GNSS receiver continues receiving satellites.
- Approximately 10 satellites have usable signal.
- Strongest observed signals were approximately:
  - GPS 14: 43 dB
  - GPS 3: 41 dB
  - GPS 2: 32 dB
  - GPS 17: 32 dB
- Timing DOP reported: 0.73.
- GPS and GLONASS satellites remain visible.
- NMEA/GNSS telemetry continues to reach the application.
- The green PPS/status LED on the Uputronics HAT flashes once per second.
- Despite this, the system is not currently using PPS for synchronization and has fallen back to network time.

This is important because it demonstrates that "GPS working" and "PPS synchronization working" are not the same state.

The current UI does not expose enough of the timing pipeline to immediately determine where the failure occurred.

---

# 1. Model the Timing Pipeline Explicitly

Do not represent GNSS/PPS health as one boolean state.

Treat the timing chain as independently observable stages:

1. GNSS RF reception
2. GNSS receiver/navigation solution
3. GNSS time solution
4. Receiver PPS/timepulse generation
5. Linux kernel PPS device
6. PPS event reception
7. chrony PPS source
8. chrony PPS lock/selection
9. System clock synchronization
10. NTP service state

Conceptually:

```
GNSS satellites
    ↓
GNSS receiver
    ↓
Receiver time solution
    ↓
Hardware PPS/timepulse
    ↓
GPIO 18
    ↓
Linux PPS subsystem
    ↓
/dev/pps0
    ↓
chrony
    ↓
System clock
    ↓
NTP clients
```

The dashboard should expose enough information to determine which boundary has failed.

---

# 2. Add a Timing Health / Signal Chain Panel

Add a diagnostic panel similar to:

```
GNSS RF          HEALTHY
Tracked          10 satellites
Best C/N0        43 dB-Hz
Timing DOP       0.73

GNSS TIME        HEALTHY
Fix age          0.4 s

KERNEL PPS       HEALTHY
Device           /dev/pps0
Last pulse       0.23 s ago
Pulse rate       1.000 Hz

CHRONY PPS       NOT SELECTED
Reach            377
Last sample      ...
Offset           ...

SYSTEM CLOCK     FALLBACK
Source           Network NTP
Stratum          ...

NTP SERVER       HEALTHY
Clients          ...
```

Exact wording/layout can follow the existing UI design.

The important requirement is that these states remain independent.

---

# 3. Distinguish "PPS Present" From "PPS Selected"

These are different conditions.

- **PPS PRESENT** — /dev/pps0 is receiving approximately one event per second.
- **PPS AVAILABLE** — chrony recognizes the PPS source.
- **PPS LOCKED** — chrony has sufficient reference information to use PPS correctly.
- **PPS SELECTED** — chrony currently considers PPS its preferred synchronization source.

A PPS source can therefore be physically healthy while chrony is not using it.

Do not label all of these conditions simply "PPS failed."

---

# 4. Record PPS Event Age

Expose:

- Timestamp of most recent PPS event
- Seconds since last PPS
- Current PPS frequency
- Consecutive PPS events
- PPS interruption duration
- Last PPS recovery time

Suggested states:

- HEALTHY — Last PPS < 1.5 seconds
- DEGRADED — Last PPS 1.5–3 seconds
- LOST — No PPS > 3 seconds

Thresholds should ideally be configurable rather than hard-coded.

Avoid declaring a hardware failure solely from these states.

---

# 5. Add PPS-Loss Event Logging

Create persistent events when PPS disappears.

Example:

```
PPS LOSS
Start: 2026-09-28 03:14:22 UTC
End:   2026-09-28 03:37:41 UTC
Duration: 23m 19s

GNSS fix during event: YES
Tracked satellites: 9–12
Median C/N0: ...
NMEA available: YES
Kernel PPS events: NO
chrony source: Cloudflare/NIST/etc.
System clock max excursion: ...
```

This should feed the previously planned PPS-loss history graph.

Do not generate an event every second while PPS is absent. Generate one event with a start and end.

---

# 6. Improve PPS-Loss Graphing

Implement the previously scoped PPS-loss visualization.

Useful views:

- PPS availability vs time
- Duration of each outage
- Number of PPS outages per day/week/month
- Total PPS-unavailable time
- Longest PPS outage
- Current uninterrupted PPS uptime
- Historical availability percentage

Example:

```
PPS availability — last 24 hours

███████████████████████░░████████████████
                       ↑
                    23m loss
```

This should distinguish:

- GNSS unavailable
- PPS unavailable
- PPS available but chrony rejected it
- PPS selected

These should not all appear as the same failure.

---

# 7. Preserve "Time to Lose 1 Second"

Continue implementing the previously requested oscillator/holdover metric.

When GNSS/PPS disappears, estimate:

- Current clock frequency error
- Estimated drift per hour/day
- Estimated time until: 1 µs, 10 µs, 100 µs, 1 ms, 10 ms, 100 ms, 1 second error

Display measured values separately from projections.

For example:

```
HOLDOVER

Current estimated frequency error: +0.82 ppm

Projected error:
1 ms      ~20 minutes
10 ms     ~3.4 hours
100 ms    ~1.4 days
1 second  ~14 days
```

Values above are illustrative only; calculate them from actual chrony/system measurements.

Do not imply the estimate is guaranteed.

---

# 8. Add GNSS Integrity Monitoring

The project should now include passive GNSS interference/integrity monitoring.

This is observational only. Do not automatically conclude that an anomaly represents intentional jamming or spoofing.

Collect historical metrics such as:

- satellites visible
- satellites used
- constellation
- C/N0 per satellite
- aggregate/median C/N0
- elevation
- azimuth
- DOP values
- fix type
- reported receiver position
- receiver clock information where available
- PPS availability
- PPS timing behavior
- chrony offset
- chrony frequency estimate
- system clock behavior

Create baselines so unusual changes can be identified.

---

# 9. Detect Possible RF Interference

Potential interference indicators can include:

- simultaneous C/N0 reduction across many satellites
- abrupt loss of satellites across multiple constellations
- elevated noise/interference metrics if exposed by the receiver
- loss of navigation solution despite previously strong geometry
- repeated synchronized satellite loss/recovery patterns

Classify conservatively.

Example:

```
GNSS INTEGRITY WARNING

Signal strength across 9 tracked satellites decreased
by a median of 14 dB-Hz within 8 seconds.

GPS affected: YES
GLONASS affected: YES

PPS: LOST
Navigation solution: LOST

Classification:
Possible RF interference

Confidence:
Moderate
```

Do NOT report "GPS JAMMING DETECTED" unless the available receiver measurements can actually establish that conclusion.

---

# 10. Detect Possible Spoofing / Navigation Anomalies

Potential indicators include:

- impossible or improbable position jumps
- sudden clock/time discontinuities
- coherent changes across satellite measurements
- position movement inconsistent with a stationary receiver
- GNSS position inconsistent with the surveyed station location
- abnormal receiver clock behavior
- satellite geometry/measurement inconsistencies where receiver telemetry permits

Because this station is normally stationary, the known receiver location provides a particularly useful integrity reference.

Example:

```
POSITION ANOMALY

Surveyed location deviation:
Previous baseline: 2.3 m
Current: 487 m

GNSS signal levels remain normal.
Satellite count remains normal.
PPS remains present.

Classification:
GNSS navigation anomaly

Possible causes:
- receiver error
- multipath
- poor solution
- configuration problem
- spoofing/interference
- other GNSS anomaly
```

Do not automatically classify it as spoofing.

---

# 11. Correlate GNSS and PPS Events

This is particularly important given the current observed failure.

If GNSS signals = healthy, GNSS navigation = healthy, receiver/HAT PPS indication = apparently active, and kernel PPS = absent, then RF jamming is an unlikely explanation.

The application should instead classify the event approximately as:

```
PPS PATH ANOMALY

GNSS reception remained healthy during PPS loss.

Possible failure boundary:
receiver PPS output / GPIO / kernel PPS interface
```

Similarly, GNSS signal collapse + PPS loss should be classified differently:

```
GNSS RECEPTION ANOMALY
```

This distinction is important for future integrity monitoring.

---

# 12. Add an Event Correlation Engine

Create a generic event model rather than implementing each anomaly independently.

Possible event types:

- GNSS_SIGNAL_LOSS
- GNSS_SIGNAL_DEGRADATION
- GNSS_FIX_LOSS
- GNSS_POSITION_ANOMALY
- GNSS_TIME_ANOMALY
- PPS_LOSS
- PPS_RECOVERY
- PPS_JITTER_ANOMALY
- CHRONY_PPS_REJECTED
- CHRONY_SOURCE_CHANGE
- HOLDOVER_START
- HOLDOVER_END
- SYSTEM_CLOCK_STEP
- NTP_FALLBACK
- GNSS_INTEGRITY_WARNING

Each event should contain:

- start timestamp
- end timestamp
- duration
- severity
- measured evidence
- relevant before/during/after metrics
- classification
- confidence where appropriate

Avoid speculative causal labels.

---

# 13. Preserve Evidence Around Anomalies

Maintain a rolling in-memory buffer of detailed GNSS/timing telemetry.

When an anomaly occurs, preserve a bounded window such as: 5 minutes before, event duration, 5 minutes after.

This provides forensic information without requiring high-frequency telemetry to be written continuously to the SD card.

This should integrate with the existing goal of minimizing SD-card writes.

---

# 14. Multi-Station Correlation — Future Roadmap

Design the event format so multiple GPS Time Pi stations can eventually compare integrity events.

Example:

```
Station A
Signal degradation: 14:03:12 UTC

Station B — 18 km away
Signal degradation: 14:03:13 UTC

Station C — 43 km away
No anomaly
```

This could help distinguish:

- local antenna/environment problems
- receiver hardware failures
- local RF interference
- geographically distributed GNSS anomalies

This belongs in the coordinator/analysis tier rather than requiring every Raspberry Pi station to perform heavy analysis.

Do not require cloud infrastructure.

---

# 15. Receiver Upgrade Path

The current u-blox MAX-M8Q should remain supported.

However, document that more advanced integrity monitoring may benefit from future receivers exposing:

- multiple GNSS frequency bands
- AGC measurements
- RF interference/jamming indicators
- richer raw GNSS measurements
- receiver clock information
- carrier phase
- pseudorange
- per-satellite quality metrics

Do not make a receiver upgrade a prerequisite for the current implementation.

---

# 16. Immediate Diagnostic Requirement

For the currently observed condition, add documentation instructing the operator to collect:

```
ls -l /dev/pps*
sudo ppstest /dev/pps0
chronyc sources -v
chronyc sourcestats -v
chronyc tracking
```

Current evidence indicates:

- GNSS RF reception is active.
- Strong satellites are present.
- Timing DOP is good.
- GNSS/NMEA telemetry is being received.
- The Uputronics HAT green LED visibly pulses approximately once per second.
- PPS is nevertheless apparently unavailable to the synchronization stack.

Therefore do not diagnose the active antenna as failed from the currently available evidence.

The next diagnostic objective is determining whether PPS events reach `/dev/pps0`, and if they do, why chrony is not using them.

---

# 17. Implementation Constraints

Maintain the existing project architecture principles:

- Raspberry Pi station remains lightweight.
- Heavy historical/cross-station analysis belongs in the optional coordinator tier.
- Operation must remain useful without Internet access.
- Do not make cloud services mandatory.
- Minimize SD-card writes.
- Preserve privacy controls.
- Do not expose precise station location when location privacy is enabled.
- Keep diagnostic claims evidence-based.
- Clearly distinguish measurements, derived estimates, and hypotheses.
- Do not modify unrelated timing behavior while implementing observability.
- Add tests for state classification and event transitions.
- Document the new architecture and terminology under `/docs/`.

---

# Acceptance Goal

After these changes, an operator seeing the current real-world condition should be able to open the dashboard and determine within seconds:

1. Are satellites being received?
2. Does the receiver have valid GNSS time?
3. Is hardware/kernel PPS present?
4. Is chrony receiving PPS?
5. Is chrony selecting PPS?
6. What is currently disciplining the system clock?
7. When did the failure begin?
8. Has this happened before?
9. How much has the clock drifted during the outage?
10. Does the evidence indicate an RF/GNSS anomaly or a local PPS/software-path failure?

The dashboard should diagnose the timing chain rather than simply report that synchronization has been lost.
