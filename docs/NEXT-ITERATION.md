# Next iteration — implementation backlog

This is the short coding backlog derived from the source review and subsequent project scoping.

## Must fix first

- Move GPS/survey sampling into an independent background collector.
- Reject duplicated/stale GPS observations from the position survey.
- Correct chrony history field semantics and explicitly label correction vs uncertainty.
- Replace privileged unauthenticated management GET actions with a restricted administration design.
- Run the web/status process without broad root privileges.
- Replace whole-history SD rewrites with bounded RAM buffers and incremental/atomic checkpoints.
- Show checkpoint health and the current potential data-loss window.
- Reconcile source archive, installer, units, and deployment documentation.
- Complete dataset provenance/third-party notices before a public stable release.

## High-value additions

### NTP client activity

Surface IP-only NTP requesters from chrony's client statistics:

- IP address
- first seen
- last seen
- request count
- approximate polling interval
- active/recent/stale state

This means **"who is requesting time from this Pi"**, not **"whose clock has been verified"**.

### Reference-source panel

Show:

- PPS selected/healthy state
- NMEA time-label/reference state
- internet fallback reachability and current use
- RTC support state
- current stratum and reason for it
- source change / loss / reacquisition timeline

Never continue presenting the appliance as GPS Stratum 1 when GPS is gone and another reference or holdover state is actually in use.

### Device timing / amateur radio

Later add optional measurement of client clock offset. JS8Call/WSJT-X computers are a useful early profile because GPS-backed LAN NTP works without internet and these modes are time-sensitive.

### Custom dashboard

Saved layouts and widgets should control presentation only. Extensions should consume the documented observation/status interface without gaining implicit control of chrony or system time.

### Environmental collector

Start with external temperature, humidity, and pressure. Keep CPU/enclosure/outdoor measurements separately identified and timestamp every observation with timing-quality metadata.

## Additional worthwhile features

- Satellite azimuth/elevation sky plot with signal strength.
- GPS/PPS/source state-change timeline.
- Config export/import with secrets and private location excluded by default.
- Redacted diagnostic bundle for support issues.
- Prometheus `/metrics` and optional remote log shipping.
- Read-only JSON schema/version endpoint for third-party integrations.
- Commissioning self-test: PPS, gpsd, chrony, RTC, NTP serving, RAM logging, storage checkpoint, and allowed-network checks.
- Explicit health states for GPS antenna/fix/PPS rather than one combined "GPS" indicator.
- Holdover characterization as a measured hardware/profile property, not a universal claim.
