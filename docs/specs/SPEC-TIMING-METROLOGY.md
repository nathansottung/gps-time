# SPEC — Timing Metrology, Time Scales, and Time Distribution

## Status

NEXT. Station-tier work; runs on the Pi without extra hardware except item 5.

Follows project rules: offline-first, provenance labels on every value, no SD writes at 1 Hz, privacy mode respected, tests with fixtures only.

---

## 1. Stability analysis (Allan deviation)

- Compute overlapping Allan deviation (ADEV), modified ADEV (MDEV), and time deviation (TDEV) from chrony PPS offset history.
- Averaging times from 1 s up to the longest span the stored data supports.
- Show as a log–log plot with confidence bars, plus a table of key points (1 s, 10 s, 100 s, 1000 s, 1 day).
- Label as **calculated**, and state the measurement layer: Linux/chrony view of PPS, not the receiver's electrical PPS.
- Data source: RAM ring buffer for recent seconds; minute summaries for long spans. No extra SD writes.
- Validate the math against published reference data sets in tests.

## 2. Network Time Security (NTS)

- Optional chrony NTS server so clients can authenticate the time they receive.
- Needs a TLS certificate. Document both a local CA option for LAN use and a public certificate option.
- Off by default. Installer flag to enable. Dashboard shows NTS state and certificate expiry.
- Never change chrony settings unless the operator turns this on.

## 3. Time scales panel

Show, all **calculated** from the disciplined clock:

- UTC, local time (existing big clock)
- TAI (UTC + 37 s at present)
- GPS time (UTC + 18 s at present), GPS week number and seconds of week
- Unix epoch (existing)
- Modified Julian Date and Julian Date
- Local sidereal time (existing; obeys privacy mode)
- Leap-second table source, its expiry date, and a warning well before expiry
- Next scheduled leap second, if any

UT1−UTC needs IERS data from the Internet; show it only if a cached file exists, labeled **external** with its date.

## 4. Independent references

- Continuously compare the station against a small set of public servers (e.g. NIST, USNO) as `noselect` sources.
- Show each source's offset and delay history, labeled **external**.
- Flag when the station disagrees with most independent references by more than a set threshold. Report it as a disagreement, never as a cause.
- Works without Internet; shows "no external references reachable" instead of failing.

## 5. PTP output (hardware-dependent)

- IEEE 1588 grandmaster using `linuxptp`, disciplined from the same PPS.
- Requires a board whose Ethernet has hardware timestamping (CM4/CM5, Pi 5, or a supported NIC). Detect support at runtime; on a Pi 4 show "not supported on this hardware".
- Dashboard shows PTP state, clock class, and client count where available.
- Off by default.

## 6. Smaller items

- Installer step that disables chrony's DHCP-provided sources so the station never polls itself.
- Show the configured and suggested NMEA offset side by side (existing calibration).
- Record chrony `serverstats` (packets served, dropped) as a simple service-health view.

## Order

1, 3, 4, 6, then 2, then 5.

## Tests

Each item needs fixture-based tests. Item 1 must check against known reference values. No live Internet or GNSS in tests.
