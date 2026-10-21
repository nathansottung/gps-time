# Current implementation scope

## Historical baseline

The v1.3.0 codebase already contains GPS/PPS/chrony status, NTP serving, timing/source displays, satellite table, NTP client table, astronomy/almanac, position survey, chrony tracking history (its log in RAM, copied to the SD card hourly), themes and system diagnostics.

## Development scaffold added in 1.4.0-dev

- new configurable multi-page dashboard used by real and demo modes
- Windows desktop demo using sample data and only Python standard-library requirements for the demo server
- widget visibility/size flags stored in JSON
- configuration editor endpoint gated to demo/loopback/explicit trusted mode
- browser HTTP RTT and NTP-like browser-clock estimate
- yesterday/today/tomorrow solar data supplied to the new dashboard API path
- build script for repo and Pi deployment archives
- PowerShell/Bash Pi deployment helpers
- expanded `/docs/` architecture and roadmap contract

(The configurable dashboard, its JSON layouts and the editor were removed with the legacy pages after v1.4.0; the station UI is now the web UI at `/app/`, with per-browser show/hide in Configure.)

## Before stable release

Close or disposition the source-review findings in `../review/source-review-2026-09-07.md` and `../review/GPS-Time-Independent-Review-2026-09-27.md`, especially fresh-fix survey semantics, chrony history field meaning, bounded persistence and administrative security.

Progress (2026-09-27, candidate — see `../provenance/CHG-001-002-foundation-correction.md`):

- **Fresh-fix survey semantics:** fresh-epoch gating implemented and tested (CHG-001). Collection no longer depends on page/API traffic, but still runs inside the web process; pre-existing survey samples are preserved and reported as legacy.
- **Fresh-install logging failure** (logsync execute bit): fixed and guarded by packaging tests (CHG-002); not yet re-verified on a Pi.
- Still open: chrony history field meaning, bounded persistence, administrative security, and the remaining 2026-09-27 review findings.
