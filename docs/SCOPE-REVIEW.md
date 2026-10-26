# GPS Time — Full Scope Review

A check of everything discussed against what is built, specced, or still missing. Status: **Done** (merged), **Next** (scheduled), **Specced** (written, not scheduled), **Gap** (discussed but not written down anywhere yet).

## 1. Timing station (core)

| Item | Status | Where |
|---|---|---|
| GPS/PPS stratum-1 NTP on a Pi | Done | core |
| Timing-chain diagnostics, PPS state machine, source-aware banner | Done | CHG-PPS-HEALTH-DIAGNOSTICS |
| One event per outage, evidence kept on SD | Done | |
| PPS poller thread, missed vs unread pulses | Done | |
| Boot ACQUIRING state | Done | |
| Survey saved safely across restarts | Done | |
| Stability (ADEV/MDEV/TDEV), time scales, independent references | Done | SPEC-TIMING-METROLOGY |
| NMEA offset recommendation, DHCP self-source fix | Done | |
| Log flush with caps | Done | |
| Oscillator temperature log | Done | |
| Oscillator profile fit (portable, tied to board serial hash) | Next | ROADMAP-OSCILLATOR-AND-MISC |
| PPS evidence capture script | Done | |
| NTS (secure NTP) | Specced | SPEC-TIMING-METROLOGY |
| PTP output (needs CM4/CM5/Pi 5) | Specced | SPEC-TIMING-METROLOGY |
| Fixed 1500 MHz CPU test vs 600 MHz | **Gap** — suggested, never run | |
| Stability history survives restarts (minute summaries on SD) | **Gap** — noted, not built | |
| Validation against true UTC (not just the station's own PPS) | **Gap** | see §7 |
| Antenna cable-delay compensation (matters at ns level with F9T) | **Gap** | |

## 2. Dashboard and UX

| Item | Status |
|---|---|
| New UI at `/`, legacy removed, strict CSP | Done (v1.5.0 pending) |
| Local-time clock with UTC and epoch, 12/24 h | Done |
| Sunrise/sunset/noon shifts in h/m/s, sunset prominence | Done |
| Screenshot mode, red night theme, show/hide modules | Done |
| Earth shadow, satellite passes, sky map, object lookup | Done |
| Admin auth, station actions, survey reset, power/throttle card | Done |
| Kiosk full-screen clock | **Gap** — asked for, not built |
| Mobile layout and installable offline app (PWA) | **Gap** — asked for, not built |
| Web-based signed updates | Specced (low priority) — ROADMAP-WEB-UPDATES |

## 3. Hardware

| Item | Status | Where |
|---|---|---|
| Pi 4 + Uputronics MAX-M8Q (Debian 13) | Tested | README |
| Antenna outdoors | Next (owner) | |
| Dual-band ZED-F9T / F9P profile | Next | docs/hardware/zed-f9-dual-band.md |
| Reference node parts list | Specced | HARDWARE-REFERENCE-NODE |
| Other boards (Turris Omnia, USB PPS on Linux) | Noted | ROADMAP-OSCILLATOR-AND-MISC, desktop roadmap |

## 4. Radio and ranging

| Item | Status | Where |
|---|---|---|
| SDR roadmap (WWV, frequency calibration, meteor scatter, H-line, grid frequency, scope checks) | Specced | ROADMAP-SDR-RF-OBSERVATORY |
| RF node on separate hardware, MLAT, TDOA | Specced | SPEC-RF-NODE-AND-TDOA |
| Capture requests between stations, FM two-tower trial | Specced | SPEC-RF-TASKING-AND-FM-TDOA-TRIAL |
| Reference signal catalog (ATSC, FM, NOAA, ADS-B, AIS, radiosondes, WWV, AM, LTE sync) and trust cluster | Specced | SPEC-RF-REFERENCE-SIGNALS-AND-TRUST |
| Tower delay prediction and auto-tune from surveyed position | Specced | README vision, SPEC-EXTENSIBILITY starter modules |
| ADS-B aircraft as moving references | Specced | README vision, SPEC-EXTENSIBILITY |
| Networked SDR (rtl_tcp, SoapyRemote, OpenWebRX) | Specced | ROADMAP-OSCILLATOR-AND-MISC |

## 5. Sensors and science

| Item | Status | Where |
|---|---|---|
| Seismometer, infrasound, VLF lightning, all-sky camera, muons, magnetometer, SID, weather | Specced | ROADMAP-SENSOR-FUSION |
| Earth tides, ionosphere, water vapor, crustal motion | Specced | ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE |
| Cross-sensor events (lightning, bolides, quakes, solar storms) | Specced | ROADMAP-SENSOR-FUSION |
| Acoustic thunder ranging (3D channel mapping with microphones + VLF start time + weather) | **Gap** — discussed, not written into any spec | |
| Feeding existing networks (Blitzortung, Raspberry Shake, Global Meteor Network, HiSPARC) | Partly — mentioned for Shake only | |

## 6. Platform and community

| Item | Status | Where |
|---|---|---|
| Module architecture, safety, API stability, governance, data licence | Next | SPEC-EXTENSIBILITY |
| Universal observation format (SigMF + `gpstime:`), look-back buffers | Next | SPEC-OBSERVATION-FORMAT-AND-TASKING |
| Coordinator tier | Specced | SPEC-COORDINATOR |
| Desktop tray app | Specced | ROADMAP-DESKTOP-FIELD-APP |
| MIT licence, third-party notices, history scan | Done | |
| Public README with vision | Next | README-VISION-SECTION |
| Docs website (e.g. MkDocs on GitHub Pages) | **Gap** | |
| Prebuilt Pi image or one-line installer for newcomers | **Gap** | |
| Legal notes: receive-only, local RF and privacy laws, ADS-B data terms | **Gap** | |

## 7. Gaps to add

1. **Accuracy validation plan.** Today's figures show agreement with the station's own PPS, not with UTC. Options: compare PPS from two independent receivers with a scope or time-interval counter; compare against a GPSDO; or later, a second station on dual-band hardware with known cable delays. Needed before any claim about accuracy to UTC. First step done in #126: the system clock against the receiver's PPS on a wire (`validation/second-pulse.md`); PPS against UTC still needs a second reference.
2. **Antenna and cable delay calibration** for dual-band hardware.
3. **CPU clock experiment** (600 vs 1500 MHz fixed) with Stability page numbers.
4. **Stability history persistence** across restarts.
5. **Kiosk clock, mobile layout, PWA.**
6. **Acoustic thunder ranging** as a sensor-fusion module.
7. **Network partners**: a short section on contributing data to Blitzortung, Raspberry Shake, Global Meteor Network, HiSPARC.
8. **Docs website** and a **prebuilt image / one-line installer**.
9. **Legal and safety notes** for RF receiving and data sharing.

## 8. Release path

1. Thursday: rc.11 soak check, then v1.4.0 (or report).
2. Go public.
3. v1.5.0: legacy removal, deployed and soaked.
4. Modules + observation format, with the four starter modules.
5. Dual-band station, then the first RF node and the FM trial.

## Corrections (2026-10-21)

Checked against the repository after this review was added (#113):

- **README vision:** done, not next. Merged in #110 and updated in #112 ("Where this is going").
- **New UI location:** served at `/app/`; `/` redirects there (ADR-0004). Not served at `/` itself.
- **SPEC-RF-REFERENCE-SIGNALS-AND-TRUST:** now in the repository (`docs/specs/`), #114.
- **Oscillator profile fit:** now next in `STATUS.md` (it was future when this review was written), #114.

## Added since (2026-10-21)

- **SDR PPS time markers (research):** [`specs/SPEC-SDR-PPS-MARKER.md`](specs/SPEC-SDR-PPS-MARKER.md). Belongs with §4 (radio and ranging). Research step 1 (synthetic detector and time model) is built as a module, `modules/sdr-pps-marker/`, #115; the bench steps are not started.
