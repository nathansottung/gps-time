# GPS Time Pi — consolidated working scope

**Consolidated:** September 9, 2026  
**Status:** working scope and recommended sequencing; not a frozen specification, code change, or authorization to implement every backlog item.

## 1. Purpose and evidence boundary

> A secure, customizable, open-source GPS-disciplined timing appliance that explains the quality of its time and provides a documented foundation for device-clock monitoring, site information, and timestamped observations.

The user's directions are: trustworthy timing first; open-source readiness; customization; security; predominantly RAM-first logging with periodic SD persistence; refined stationary location and altitude information; cross-device timing; and eventual weather-station use. Amateur-radio computer timing, including JS8Call and WSJT-X workflows, was added in the current discussion.

The implementation baseline is the uploaded `gps-time-pi.zip` and the runbook's reported v1.3.0 deployment. The archive SHA-256 is `6ac67e1fdc269dfdea0e81b14d359c2c4f6531c094fa38e58a861f9e1ff963db`, matching the snapshot identified in the earlier review. No new hardware measurements or regression tests were run for this consolidation, and no application code was changed.

Sources:
- `deployment-runbook.md`: reported deployed setup and field fixes.
- `ideas-ledger.md`: existing features and wanted/deferred ideas; not proof that every claim is correct or every idea is committed to the next release.
- `GPS-Time-Pi-Review-and-Scope-2026-09-07.md`: earlier source review, mocked findings, technical corrections, and proposed release gates.
- Archive design documents: `docs/dashboard-expansion-plan.md`, `docs/customization-and-hardware.md`, and `docs/platform-extensions.md`. These include historical proposals and must not override later findings or be mistaken for current implementation.
- Current conversation: timing-first customization/security direction and amateur-radio timing use case.

Where the ledger and the review disagree, both positions are retained below and the discrepancy is explicitly identified. Recommendations and proposed defaults are not presented as implemented behavior.

## 2. Scope layers

### Timing foundation — essential

Keep chrony responsible for clock discipline and NTP service, and gpsd responsible for receiver access. The application observes, explains, records, and narrowly administers that foundation. Timing must remain useful without astronomy, weather, remote storage, or the dashboard running.

Make a timing-only installation a supported goal. Retain the existing astronomy capability as an optional layer, not an unwanted feature to delete.

### Measurement and observation layer — essential enabling work

Collect measurements independently of web requests. Share versioned observations with source identity, observation/capture time, receipt time, time-quality state at capture, validity, units, and uncertainty type/value or an explicit unknown. Include site/session identity where relevant and enforce privacy on export.

A fine-grained timestamp representation does not certify equally fine measurement accuracy. Old observations retain their original quality state after the station recovers.

### Presentation and integration layer — extensible

Support configurable views and external API clients. Initially favor validated data collectors and declarative widgets over arbitrary executable plugin installation or third-party JavaScript. Extension failures must be contained through permissions, timeouts, and resource limits, then tested under realistic load.

## 3. Existing baseline: preserve, but do not mistake existence for validation

| Area | What the uploaded materials report/contain | Qualification |
|---|---|---|
| GPS/PPS NTP | chrony/gpsd configuration, GPS time-of-day labeling plus PPS, optional internet fallback | Working deployment is reported, not independently remeasured here. |
| Timing dashboard | Live/local/UTC clock, synchronization states, offset/uncertainty presentation, oscillator/source statistics | Uncertainty semantics, freshness, and browser comparison need correction. |
| Receiver and client views | Satellite table and signal levels, NTP requesters, firmware/software visibility | Client traffic is not client clock accuracy. |
| Astronomy | Sun, moon, darkness windows, object search, sky chart, local ephemeris calculations | Preserve existing functionality; dataset provenance and site-selection behavior need review. |
| Site survey | Running position statistics, narrowing chart, fallback stored location, privacy modes | Stale-data ingestion and confidence claims need correction; accepted-site workflow is incomplete. |
| Storage | RAM-based chrony logging, hourly/shutdown flush design, batched configuration writes | Not yet a complete bounded, durable, crash-tested persistence policy. |
| Customization | Themes, custom CSS, plain HTML templates, API endpoints | Not yet the planned user-arrangeable dashboard or safe extension framework. |
| Operations | System diagnostics, management routes, installer, hardware configuration profiles, documentation | Privileged management and release reproducibility are blockers for a supported public baseline. |

## 4. Required corrections and completion work

The following map to R-01 through R-10 in the earlier review. They are not optional feature ideas.

| ID | Area | Required work | Completion evidence |
|---|---|---|---|
| F-01 | Release parity | Reconcile live field fixes with source/archive; make logging-script execution reliable; record commit/version identity. | Downloaded archive passes clean install and upgrade checks, not just the developer checkout. |
| F-02 | Security | Replace anonymous state-changing GET routes; run the web process without broad privilege; authenticated administration through a narrow allowlist; validate/escape inputs; bound expensive requests. | Anonymous reads cannot reboot, reset, restart, or change privacy; malformed input cannot become code or markup. |
| F-03 | Independent collection | One independently scheduled collector/single ingestion owner; cached snapshots for readers. | Collection continues with the UI stopped; extra viewers do not increase sample counts or receiver polls. |
| F-04 | Fresh observations | Distinguish receiver epoch from poll time; reject stale, duplicate, invalid, and reordered fixes; keep receiver and satellite-data ages separate. | Simulated silence/repeats cannot increase survey confidence or make stale data appear fresh. |
| F-05 | Timing semantics | Parse named chrony quantities correctly; separate offset, correction, scatter, reference uncertainty, and synchronization/source health; unknown remains unknown. | Supported-format fixtures match intended fields; history never invents an uncertainty band. |
| F-06 | Browser comparison | Separate the lightweight timestamp exchange from the full dashboard request; account for server work; expire stale/suspended estimates. | Delay/suspension tests pass; browser results remain explicitly estimates rather than device-clock certification. |
| F-07 | RAM-first storage | Bounded buffers/segments, incremental durable publication, retention, accurate successful-checkpoint status, serialized flushes, explicit shutdown handling. | Disk/RAM full, interrupted write, shutdown, restart, concurrent flush, and bounded restore tests preserve the last valid checkpoint. |
| F-08 | Site and altitude | Separate live fix, candidate survey, and accepted site; downstream calculations use the deliberately selected site; preserve coordinate precision and height meaning. | Locked site survives noise/outage; movement opens a new session; unknown height datum stays unknown. |
| F-09 | Open-source assets | Reopen asset-specific provenance review; record licenses, source revisions, modifications, and reproducible data conversion. | Every distributed asset has a defensible record; no blanket assertion of legal/patent clearance. |
| F-10 | Documentation/install | Correct claims about logged temperature and no post-install network access; isolate/test dependencies; distinguish recorded checksums from independently trusted inputs; support safe updates/rollback. | Documentation describes tested behavior and limits; public examples omit deployment-specific private details. |

### Explicit discrepancies to resolve

The ledger labels the dataset audit complete, while the review identifies unresolved provenance work. The ledger says temperature and frequency are already logged; the review found live CPU temperature but no persisted temperature series. The runbook says script execution fixes were included in the repository; the reviewed archive lacks some of those fixes.

Older documents imply an unconditional isolation guarantee and automatic precision for scientific event timing. Replace those with testable resource boundaries and acquisition-specific validation requirements. Preserve the historical documents, but mark them superseded where appropriate.

The runbook records an intermittent antenna DC-feed fault. Recheck its current condition before a new long-running site survey or public performance characterization; this document does not establish that the fault is still present or resolved.

## 5. Additions in the working scope

### A-01 — Cross-device clock monitoring

Create an enrolled-device view distinct from passive NTP requester visibility. Track identity/platform, comparison method, selected reference, signed offset, measurement age, delay where available, uncertainty/quality, history, and tolerance status. Show unsupported devices as traffic observed/offset unknown.

Use appropriate native timing telemetry or comparison adapters for Linux, Windows, and macOS; exact first-platform order remains to be selected. Keep monitoring targets separate from selectable upstream sources to avoid reference loops. Start read-only: no automatic remote clock correction is included in the first monitoring scope.

### A-02 — Amateur Radio Station Timing profile

Treat JS8Call/WSJT-X use as an application of A-01 and ordinary NTP distribution, not a new radio application or synchronization protocol.

Deliver setup instructions for supported operating systems, client timing checks, an offline cold-start test, stale/unsynchronized status, and sleep/resume/GPS-loss checks. Check for application-level clock adjustments as part of operating guidance. A station profile can focus the dashboard on GPS status, radio-computer offset, and readiness criteria.

The earlier suggestion of a client-to-Pi offset below 100 ms is a proposed project target only: it is not a verified measurement, a formal JS8Call requirement, or a guarantee of UTC accuracy. Reference quality must be assessed separately.

Direct transceiver control, RF-frequency calibration, coherent SDR timing, and event-level PPS capture are not implied by this profile.

### A-03 — Customizable dashboard

Add show/hide/reorder/resize of panels, saved layouts, selectable units/timezones, and upgrade-safe configuration. Candidate presets are Timing, Astronomy, Weather, and Amateur Radio; preset names are proposals.

Preserve existing themes, custom CSS, and external frontend access. A displayed timing or sensor value must retain validity/freshness information even in a custom layout. Exact per-browser versus station-wide layout behavior remains open.

### A-04 — Trusted-site refinement

After F-04/F-08, add deliberate survey sessions, fresh accepted/rejected counts, raw scatter, stability across time blocks, accept/lock/reset/relocate workflows, manual or externally surveyed site input, and source/datum metadata.

Do not silently discard prior surveys. Preserve them as legacy/unvalidated when the ingestion history is uncertain, with an explicit route to start a new session.

Refinement of the application's stored position is not automatically receiver timing-mode configuration or improved chrony discipline. Antenna position, ground elevation, and each weather sensor's mounting height remain separate.

### A-05 — Complete persistence and optional remote archive

Add configurable checkpoint/retention policies and storage-health visibility. Keep frequently changing telemetry RAM-first, explicit settings/accepted-site changes deliberately durable, and a visible potential-loss window since the last successful save.

Review system journals, syslog, swap, and other writers rather than claiming the whole OS writes only on the application schedule. Remote exports use bounded retries and do not block timing. Protocol/destination and exact defaults remain undecided.

Earlier starting values (15–60 minute telemetry batches, 15 minute survey checkpoints, 24–72 hour raw history, about 30 days of minute aggregates, and about one year of hourly aggregates) are proposals to size and test, not fixed requirements.

### A-06 — Receiver and timing diagnostics

Add a satellite sky plot/history, PPS/source/fallback/reacquisition event timeline, actual persisted temperature series and frequency correlation, commissioning self-tests, redacted support bundles, a metrics endpoint, and opt-in state-change alerts.

Keep host CPU, enclosure, receiver, and ambient temperatures distinct. Holdover characterization is planned, but internet fallback and operation without any external reference must be separate states. Published performance must identify method, configuration, and evidence; do not infer a calibrated UTC guarantee from local residuals.

### A-07 — Initial weather station

Start with one isolated collector for external temperature, humidity, and pressure. Record sensor identity, placement, calibration information, observation/receipt times, time quality, validity, and units. Add simple trends and derived values such as dew point; distinguish measured station pressure from derived sea-level pressure.

A disconnected or faulty sensor should become unavailable, not stale-but-current or a failure of the NTP service. CPU temperature is not an outdoor weather substitute. Exact hardware is not selected.

### A-08 — Documented integration contract

Version the existing API rather than assuming API-first presentation already provides a stable developer contract. Define the shared observation schema before generalizing collectors. Publish at least two practical examples: device-clock observations and an environmental collector.

Prefer separately running processes with allowlisted data access, bounded resources, and core-rendered widgets. External dashboards/analysis should be possible without running their workload on the Pi. A full arbitrary-code plugin system or marketplace is not the initial deliverable.

## 6. Optional later work and research backlog

| Group | Retained ideas | Boundary |
|---|---|---|
| Additional station sensing | Rain, wind, sky brightness/cloud observations, local horizon profile, lightning proximity, magnetometer | Separate collectors after the basic observation interface works. |
| Advanced timing characterization | More advanced stability statistics, defined holdover experiments, authenticated network-time options, independent comparison station | Separately specified and validated; not claims already earned by the current installation. |
| Precision hardware | RTK/timing-receiver upgrade, hardware timestamps, PTP, frequency-reference outputs | Different hardware/performance tier; no current precision guarantee. |
| Distributed/scientific experiments | VLF lightning location, SDR arrival-time/MLAT experiments, seismic/acoustic observations, muon coincidence | Acquisition calibration and network/solver requirements need separate research scopes. |
| Optional astronomy/network convenience | Larger object catalogs, satellite-related integrations, forecast feeds, forced NTP redirection | Not prerequisites for a polished local timing appliance; assess freshness, source rights, and security separately. |

Do not turn the project into a general-purpose Pi control panel, a mandatory cloud service, or a distributed scientific network merely to release the timing core. Retaining a research idea does not commit the next release to implementing it.

## 7. Recommended iteration order

This order reconciles the previous review with the user's renewed emphasis on customization. It is a recommendation, not an assigned version schedule.

| Iteration | Scope | Gate |
|---|---|---|
| 1. Correct and preserve | Archive/deployment parity, regression fixtures, fresh-only collection, timing/browser semantics, secure read-only UI, bounded durable storage, basic accepted-site correctness, provenance cleanup | Clean install/upgrade and fault tests; no anonymous mutations; no false confidence; previous data preserved. |
| 2. Make the core independently usable | Separate collector/UI/admin boundaries, versioned observations, timing-only install path, basic metrics/diagnostics | UI stopped or collector failures cannot stop NTP; collection is viewer-independent; resource limits tested. |
| 3. Deliver device timing and useful customization | Enrolled clients, first native measurement paths, amateur-radio setup/offline checks, saved layouts and read-only widgets | Every measured offset has method/age/quality; layouts preserve validity; unsupported devices remain unknown. |
| 4. Complete site and first weather collector | Rich survey sessions, accepted-site metadata, external temperature/humidity/pressure, temperature/frequency history, optional archive/alerts | Stable site handling and trustworthy timestamped sensor records; sensor/export failure contained. |
| 5. Generalize proven extensions | Publish examples and collector contract; add optional sensors/hardware tiers individually | New integrations do not need edits to clock-control code and make no unvalidated precision claims. |

Open-source packaging/security corrections are not deferred until iteration 5. Likewise, fresh-only surveying and correct accepted-site selection are iteration-1 fixes, not postponed with the richer survey interface.

## 8. Choices not yet frozen

Exact supported OS/hardware versions; first client adapter order; client tolerance thresholds; authentication/access model; storage sizes/retention/checkpoint defaults; remote archive protocol; layout sharing; initial weather sensor; advanced hardware tiers; and release version numbers still need selection during implementation planning.

Before engineering work, preserve the working deployment/configuration, reconcile it with the repository, and add regressions for the reviewed defects. Avoid a wholesale rewrite or discretionary alteration of the working chrony/gpsd configuration while changing the UI. Test significant changes on the Pi, while keeping local development/test tooling in VS Code.

## 9. Definition of a successful polished baseline

A user can install GPS Time Pi only for dependable local NTP. The dashboard honestly distinguishes fresh measurements, historical/stale records, and unknown uncertainty. Opening or closing it does not control data collection. Administration is restricted, privacy is applied consistently, RAM and disk use stay bounded, and the recovery/loss window is visible. A second user can add weather observations or ham-computer timing without forking the timing core or inheriting unsupported precision claims.
