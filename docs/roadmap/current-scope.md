# Current implementation scope

## Historical baseline

The v1.3.0 codebase already contains GPS/PPS/chrony status, NTP serving, timing/source displays, satellite table, NTP client table, astronomy/almanac, position survey, RAM-backed chrony history, themes and system diagnostics.

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

## Before stable release

Close or disposition the source-review findings in `../review/source-review-2026-09-07.md`, especially fresh-fix survey semantics, chrony history field meaning, bounded persistence and administrative security.
