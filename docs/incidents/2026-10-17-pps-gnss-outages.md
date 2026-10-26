# 2026-10-17: PPS and GNSS outages during the rc.8 soak run

**Status:** closed as an incident; cause not established. Written 2026-10-26 (#127) from the records made at the time. No new measurements.

**Station:** the development unit (Raspberry Pi 4, Uputronics MAX-M8Q board, its current antenna and site), running v1.4.0-rc.8 since 2026-10-04 without a restart.

**Sources:**
- `development/raspberry-pi-deploy.md` → "Soak run of v1.4.0-rc.8" and "First hours of v1.4.0-rc.10";
- `provenance/change-log.md` (#69, #70, #72, #73);
- chrony's tracking log, copied off the station. It is real station data, so it is kept outside the repository.

## Summary

Between 19:04 and 20:35 UTC the station lost kernel PPS ten times, about 71 minutes in all. The longest loss lasted 56 minutes. The owner confirmed the outages were real. chrony did not switch to a network source: it coasted on its last GPS-disciplined frequency, and its first offset after the 56-minute gap was **+1.68 µs**.

The system journal recorded nothing about the outages. Because of these outages, v1.4.0 was not tagged on rc.8. They led to rc.9 (#70, #72, #73), and v1.4.0 was later tagged on rc.11 after a clean soak (#124).

## What the station recorded

Ten outage events, 19:04 to 20:35 UTC. The classifications are the station's own (`inferred`). Each names the boundary in the signal path that the evidence points to, never a cause (`gps_time_pi/timing_chain.py`, `classify`):

| Classification | Events | Rule |
|---|---|---|
| PPS PATH ANOMALY | 5 | kernel PPS events stopped while GNSS stayed healthy. Boundary: receiver PPS output, GPIO or kernel PPS interface |
| PPS AND GNSS TELEMETRY UNAVAILABLE | 4 | neither kernel PPS events nor fresh GNSS telemetry. Boundary unknown |
| GNSS RECEPTION ANOMALY | 1, 19:39:29 to 20:35:34 (3365 s) | PPS stopped together with satellite reception or the navigation solution, while the receiver still talked. Boundary: GNSS reception / receiver solution |

At the start of the events the receiver used 0 satellites, with C/N₀ about 22–23 dB-Hz (`observed`).

## How the clock behaved

From chrony's tracking log (`observed`). chrony writes no tracking line while it has no usable samples, so its silences mark the outages:

| Gap in chrony updates (UTC) | Length | chrony's first offset afterwards |
|---|---|---|
| 19:03:35 to 19:07:03 | 208 s | +0.07 µs |
| 19:15:20 to 19:18:16 | 176 s | +0.08 µs |
| 19:29:28 to 19:35:05 | 337 s | −0.42 µs |
| 19:39:37 to 20:35:40 | 3363 s (56 min) | **+1.68 µs** |

- **No failover.** GPS was the reference again at the first entry after each gap. The banner's NETWORK FAILOVER states didn't apply.
- **Holdover:** about 1.7 µs in 56 minutes, roughly 5 × 10⁻¹⁰ average fractional frequency error (`calculated`). One event on one board at room temperature, not a holdover specification. One update (16 s) later the offset was −0.16 µs.
- **NTP service to clients** during the gaps wasn't recorded.

## What isn't known

- **The cause.** The evidence fits several explanations, and the station's records can't tell them apart. The owner's assessment (2026-10-19) is that this unit's weak signal, best C/N₀ about 25 dB-Hz, is a limit of its antenna and site. That is the owner's assessment of the installation, not a finding about this event.
- **What the receiver reported in detail during the gaps.** No raw NMEA, satellite-by-satellite C/N₀ series or receiver status was kept. The station held only summaries in RAM, and the journal had nothing.
- **How much of rc.8's 9 % missed-pulse count these events explain.** They account for about 4,300 s of 112,588 missed pulses over the 14-day run. rc.9 later split "missed" (the kernel's sequence number skipped) from "unread" (the station read late). On rc.10's first hours, the missed pulses were real absences, with 0 unread. Whether rc.8's whole count had the same make-up is not known.

## What changed because of it

| Change | PR | Why |
|---|---|---|
| Outage evidence written to the SD card per event: a 10 s timeline, chrony lines ±5 min, capped at 20 MiB, no position | #73 | the journal had nothing, and a reboot would have lost the RAM evidence |
| PPS read on its own thread; missed and unread pulses counted separately | #70 | to tell real absences from reading late |
| Tracking-log flush made append-only, with caps | #72 | found on the same run: hourly full copies to the SD card |
| v1.4.0 waited for a clean soak; outage detection not weakened | owner, 2026-10-19 | the criteria in #95 count every outage except the installer's |
| rc.11 soak: 6 days 17 h, no outages besides the installer's chrony restart; v1.4.0 tagged | #124 | |

Since rc.9, an event like this leaves its own evidence file on the SD card (`/api/evidence`). The PPS evidence capture script (`scripts/capture-pps-evidence.sh`) is the step to run before rebooting during an incident.

## Follow-ups (not scheduled by this write-up)

- **Antenna and site:** the owner's step. The station will show any change in C/N₀ and outage counts.
- **Raw receiver data around an outage:** not captured today (#73 lists what isn't). The dual-band plan (`hardware/zed-f9-dual-band.md`) and a second station (`deploy/second-station.md`) would give an independent view of the same sky.
- **An outside check of holdover:** the second pulse (`validation/second-pulse.md`) against a reference that keeps running through an outage. Not the receiver's own PPS, which stops with it.
