# GPS TIME PI — PUBLIC RELEASE AND EXPANSION SCOPE

**Review date:** September 7, 2026  
**Basis:** uploaded `gps-time-pi.zip`, `deployment-runbook.md`, and `ideas-ledger.md`  
**Recommendation:** harden the measurement core, then add device timing, trusted site surveying, and environmental observations as separately testable capabilities.

## 1. Evidence boundary

The source archive was extracted and its Python modules, installer, systemd units, logging scripts, UI timing path, datasets, and relevant design documents inspected. Ten Python files compiled without syntax errors. Both shell scripts passed `bash -n`. Focused mocked probes reproduced stale-fix ingestion, live-location selection instead of survey selection, misidentified tracking-log fields, and an unauthenticated GET management route. These checks do **not** establish live PPS accuracy, LAN client accuracy, shutdown durability, electrical behavior, or astronomy accuracy on the deployed Pi. No installer or privileged action was executed, and no deployment code was changed.

Snapshot SHA-256: `6ac67e1fdc269dfdea0e81b14d359c2c4f6531c094fa38e58a861f9e1ff963db`  
Runbook SHA-256: `be289ca45398f00dccc0a7a9bdae6f14b32d99fe6451d6bd65424e022bed2536`  
Ledger SHA-256: `98628e14c79a6c1ba32e3716eddb1c164c838ca0aa8f3f75158031f3e803afd7`

Paths and line numbers below refer to the unmodified uploaded snapshot. The runbook is evidence of reported deployment, not a substitute for the archive contents. Proposed defaults and release order are recommendations, not existing behavior.

## 2. Product boundary

> A local-first station that supplies GNSS-disciplined time, maintains an explicitly qualified site position, and records observations with their timing and measurement provenance.

Keep chrony responsible for clock discipline and gpsd responsible for receiver access. The application observes and explains those services. Optional collectors and dashboards must not be prerequisites for NTP service. Sensor and export failures must not trigger clock resets, change source selection, or block time serving.

Do not expand immediately into a general Raspberry Pi management platform, arbitrary plugin marketplace, distributed scientific network, or precision geodetic instrument. Those are potential consumers of the core, not prerequisites for a useful public release.

## 3. What the archive actually contains

| Capability | Assessment |
|---|---|
| PPS/NMEA chrony configuration and gpsd integration | Implemented; successful deployment reported by the runbook; live performance not independently measured here. |
| Clock, source, satellite, client and system views | Implemented; some measurement semantics and security need correction. |
| Local astronomy and themes | Implemented; not comprehensively numerically validated in this review. |
| Running position mean/variance and convergence charts | Implemented but compromised by ingestion/freshness and uncertainty-model limitations. |
| Trusted location after fix loss | Implemented, but stale live data can defeat the intended fallback; valid live data is preferred over the surveyed mean. |
| RAM chrony tracking log and scheduled flush | Implemented but not a bounded, complete, crash-safe storage policy. |
| Batched survey/config persistence | Implemented at up to 15-minute intervals; graceful signal handling and durable checkpointing need work. |
| Remote-client clock accuracy histories | Not implemented; the existing clients table records traffic, not remote offset measurements. |
| Long-term temperature/frequency correlation | Not implemented. CPU temperature is returned by `/api`; this archive does not persist its time series. |
| Local weather collectors, remote shipping, metrics endpoint, plugin platform | Planned, not implemented in this archive. |

## 4. Release findings

### R-01 — Reconcile the deployed fixes and the distributable archive

**Priority:** before a supported public installer release.  
**Evidence:** `install.sh:38–47`; `system/gps-time-pi-logsync.service:10–11`; `system/gps-time-pi-logflush.service:6`; ZIP Unix modes.

The runbook says the units now invoke the logging script through `/bin/bash` and the installer applies executable permissions. Neither change appears in the archive. Both scripts have ZIP mode `0644`. The Mars barycenter fix *is* present in `astro.py:58`.

Generate releases from a tagged tree, preserve the executable bit or invoke the interpreter explicitly, and test the downloaded archive—not just a developer checkout. Record build commit plus version; the same `1.3.0` label does not prove content equality. The installed management action that directly invokes the shell script also needs a reliable execution path.

**Acceptance:** clean extraction onto a test Pi, successful restore/flush units, fresh install and upgrade tested, and exported release files matching the documented fix set.

### R-02 — Remove unauthenticated privileged web management

**Priority:** before sharing an accessible instance or recommending deployment to others.  
**Evidence:** `gps-time-pi.service:5–9`; `server.py:250–279,311–312`; `system.py:134–153`.

The system service has no unprivileged `User=`. The server binds all interfaces. GET routes dispatch reboot, service restarts, survey reset, and privacy changes without authentication. A mocked handler request confirmed that the GET management route dispatches the requested action without an authorization check; no real reboot occurred.

Make public operation read-only by default. Put management behind authenticated POST routes with appropriate origin/CSRF protections. Separate privileged operations into a small, allowlisted helper; do not give the entire UI unrestricted chrony/socket or root access. Escape device/hostname metadata instead of treating it as HTML. Add request, computation, and concurrency limits. Review the broad example LAN allow rule rather than assuming it fits every deployment.

The current location privacy setting is not an access-control boundary: an unauthenticated visitor can change it. A public redacted view must not share that control surface. Review indirect location disclosures from astronomical outputs as well as direct coordinate fields.

**Acceptance:** anonymous reads cannot change machine state or privacy; web process is unprivileged; rejected actions are auditable; invalid metadata renders as text; expensive requests cannot exhaust the timing appliance.

### R-03 — Decouple measurement collection from page requests

**Priority:** foundational.  
**Evidence:** `gps.py:57–85`; callers in `server.py:47–55,99–112,137–151`.

GPS refresh and survey ingestion occur inside `snapshot()`, reached by HTTP requests. No independent survey collector appears in this archive. Closing dashboard/API consumers can therefore stop survey collection even while gpsd and chrony continue to run. Multiple HTTP threads can share mutable caches and survey state without a single-writer ingestion contract.

Create one background collector service, independent of the web service, that consumes fresh receiver epochs and samples chrony/system telemetry on explicit schedules. Serve immutable cached snapshots to browsers. Keep chronology and metadata consistent across samples.

**Acceptance:** collection continues for 24 hours with no browsers; many simultaneous viewers do not change sample counts or GNSS poll rate; collection continues while the UI is stopped.

### R-04 — Stop reusing stale observations as new survey evidence

**Priority:** foundational; invalidates confidence displays.  
**Evidence:** `gps.py:62–85,105`; mocked probe results.

After an empty gpsd poll, the code can retain the old TPV while refreshing the cache timestamp. The old 3D fix can then be ingested again after the one-minute interval. In the probe, one real fix followed by simulated gpsd silence changed the sample count from 1 to 2, reported data age 0.0 seconds, and produced zero horizontal standard error from duplicated coordinates.

Track receiver epoch identity, device identity, monotonic receipt age, and independent TPV/SKY freshness. Only a fresh, valid epoch may advance the survey. Validate finite values and ranges, time validity, fix quality, and receiver consistency. An old position may remain useful as an explicitly stored site; it must never remain a fresh measurement.

Preserve existing surveys as legacy/unvalidated data until their ingestion history is understood. Offer a new survey session after the fix and antenna checks; do not silently delete the old record.

**Acceptance:** silence, repeats, reordered epochs, stale SKY, no fix, restart, and clock-step fixtures do not increase accepted observations or improve apparent precision.

### R-05 — Correct timing-field semantics

**Priority:** before publishing performance charts.  
**Evidence:** `chrony.py:162–194`; `server.py:57–65`; `templates/history.html:104–110`; official chrony references [1–3].

The history reader searches zero-based indexes 10, 9, and 8 for a nonnegative “error.” In the documented chrony 4.x layout those fields are remaining correction, combined-offset standard deviation, and number of combined sources. They are not interchangeable uncertainty fields. The reader does not select the actual root delay, root dispersion, or previous-interval maximum-error fields by their documented meaning.

A synthetic 14-column log with combined-offset standard deviation 4 µs and previous-interval maximum error 3 ms produced `err_s=4e-6`. With positive remaining correction, that correction became `err_s` instead. This does not establish that the clock was 3 ms wrong; it establishes that the returned quantity changes meaning according to the signs of unrelated fields.

Use explicit named fields and supported-version fixtures; prefer machine-readable chronyc output. Keep local/NTP-clock correction, source offset, statistical scatter, root distance, and interval maximum-error values distinct. Never invent an uncertainty band from the offset when uncertainty is unavailable. Do not center a previous-interval maximum bound around an instantaneous offset without a documented model.

Chrony's conditional system-clock bound includes absolute system correction, root dispersion, and half root delay, assuming the upstream reference is correct. It is not an independently calibrated UTC guarantee. Source reachability is also historical, not proof of a current usable PPS sample.

**Acceptance:** parser fixtures match documented layouts; missing uncertainty remains unknown; time source, source freshness, GNSS health and synchronization state are separately represented.

### R-06 — Repair the browser clock estimate before using it for comparisons

**Priority:** before a device timing UI.  
**Evidence:** `server.py:47–59`; `static/app.js:35–45`; `templates/index.html:99–104`.

`epoch_ms` is captured before serial subprocess calls and GPS polling. The browser later adds half the entire response duration. This folds server collection work into an assumed network-delay correction. A precise Pi clock can therefore feed a materially biased browser display.

Use a dedicated lightweight exchange endpoint with explicit receive/send timestamps and repeated samples. Separate network round-trip from server work; use a monotonic browser elapsed-time base; invalidate on suspension and detected clock steps. Keep this a browser estimate, not a sub-microsecond instrument. OS/device timing measurements belong in native collectors or the device's own timing telemetry.

**Acceptance:** synthetic asymmetric delay and server-work tests; clock suspension/step tests; stale estimate expires; processing delay does not masquerade as clock offset.

### R-07 — Finish the storage design instead of copying an ever-growing log

**Priority:** before unattended long-term use.  
**Evidence:** `scripts/logsync.sh:5–15`; `system/gps-time-pi-logflush.timer`; `config.py:51–78`; `system.py:118–128`.

The hourly job copies the full tracking log over the persistent copy and runs a global `sync`. The archive has no RAM-log rotation/cap or incremental archive protocol. Boot restoration can copy the whole growing archive back to RAM. Publication is not atomic and there is no flush serialization. File modification time is preserved by `cp -p`, so it is not a reliable “last successful flush” timestamp.

Config replacement uses a temporary file and rename, a good start, but lacks file/directory durability synchronization and explicit SIGTERM shutdown handling. `atexit` alone does not guarantee a flush on unhandled termination signals [10]. The unusual logsync systemd dependency arrangement also needs real shutdown-order tests.

Introduce bounded RAM buffers, closed immutable archive segments, atomic durable publication, a manifest recording last successful persisted sequence/time, and bounded retention. Separate settings from survey state. Use monotonic time for flush intervals. Never turn a disk failure into a chrony failure.

**Acceptance:** full RAM/disk, interrupted publication, concurrent flushes, normal shutdown, unexpected reboot, and bounded boot restore tests; newest failed publication leaves the previous checkpoint usable.

### R-08 — Make the surveyed site the actual site, and preserve height meaning

**Priority:** before calling this a refined site instrument.  
**Evidence:** `gps.py:73–79,116–125`; `config.py:163–173`; `astro.py:72–76`.

With a live fix present, astronomy uses that live fix instead of the surveyed average. “Exact” location output is rounded to four decimal degrees—approximately an 11 m north–south coordinate increment—regardless of survey precision. The fallback from deprecated `alt` to `altHAE` is not justified by current gpsd semantics: `alt` is undefined, and HAE and MSL are different quantities [4].

Maintain separate live fix, candidate survey, and accepted site records. Add a site lock with explicit provenance and session versioning. Display enough coordinate digits to inspect changes while stating uncertainty separately. Store antenna reference location/height, geoid model when known, ground elevation, and individual sensor heights as distinct metadata. Do not relabel an unknown datum.

**Acceptance:** locked site remains stable through noisy fixes and outages; unlocking starts an intentional workflow; moving the antenna opens a new session; unknown altitude datum remains unknown.

### R-09 — Reopen the dataset provenance audit

**Priority:** before asserting redistribution readiness.  
**Evidence:** `README.md:96–105`; `LICENSE`; `docs/almanac-design-scope.md:134–149`; bundled JSON; upstream references [5–8].

The application has an MIT license. The archive does not have an asset-by-asset third-party notice/license bundle or the data conversion scripts needed to reproduce the JSON. OpenNGC is CC-BY-SA 4.0, which is not simply a permissive MIT-style license. Preserve attribution, source and modification information, and share-alike conditions for the relevant adapted data.

The README attributes star material to Yale via d3-celestial. The current upstream d3-celestial source list describes XHIP, multiple name catalogs, and some Stellarium-derived translations. This is a provenance mismatch requiring reconstruction of the **actual** source files and revisions; it does not establish that this snapshot infringes a license. Do not treat the upstream software's BSD license as proof of every asset's origin.

Add `THIRD_PARTY_NOTICES.md`, `LICENSES/`, per-file provenance metadata, pinned source revisions/checksums, and reproducible conversion scripts. Confirm DE440s-specific redistribution terms rather than relying only on a broad “NASA = public domain” shortcut. Remove blanket statements of “no patent exposure.” A source/license audit is not patent clearance.

GPL software is itself open source. Independent aggregation is distinct from creating a combined derivative program [8]. Open-source host software does not require claiming that the GNSS receiver firmware is open source; do not redistribute firmware or board designs without appropriate rights.

**Acceptance:** every shipped asset has a defensible license/provenance record; source release and any future complete OS image have separate redistribution checklists.

### R-10 — Correct remaining release/documentation claims

**Priority:** public documentation cleanup.

The ledger says temperature and frequency streams are already logged. Frequency is in tracking logs; CPU temperature is presently returned by `server.py:39–44,79`, with no persisted temperature history found. Build a collector before promising retrospective correlation.

The README says the appliance makes no network requests after installation, but example chrony configuration includes internet pools and benchmark servers. Some chronyc invocations can also perform reverse DNS. Replace this with precise statements about optional internet fallback, local astronomy, telemetry, and deliberate data updates.

The installer installs an unpinned Skyfield package into system Python and copies onto the existing directory. Its first-download checksum is recorded from the same download, so it provides later integrity checking rather than independent first-download verification. Use isolated dependencies, a tested dependency manifest, download-to-temporary plus verified publication, and an upgrade/rollback strategy. Review examples for precise coordinates and deployment identifiers before public release; do not assume they are all fictional.

## 5. RAM-first persistence policy

These are proposed starting defaults, to be measured on the Pi rather than represented as existing behavior.

| Data | Working storage | Durable policy | Retention concept |
|---|---|---|---|
| Current status and live chart samples | Bounded RAM | None unless included in an archive batch | Hours, bounded by bytes |
| Chrony tracking and diagnostic samples | Bounded RAM segments | Closed-segment publication every 15–60 minutes | Raw 24–72 hours |
| Minute aggregates | RAM accumulation | Batched append/transaction | Around 30 days |
| Hourly aggregates | RAM accumulation | Batched publication | Around one year |
| Site survey checkpoints | RAM, single writer | Every 15 minutes plus orderly stop | Latest valid checkpoint plus a previous generation |
| Settings and accepted site | In-memory cache | Immediately after explicit user changes | Durable, versioned |
| Fault/security events | Bounded event buffer | Priority batching and optional remote export | Separately capped |
| System service journal | Explicit appliance policy | Bounded volatile journal with deliberate export, or capped persistent journal | Not silently discarded |

Preserve min/max, count, dispersion/variance where appropriate, and quality-state transitions in aggregates; an average alone hides excursions. Retention policies must distinguish missing data from successful zero readings. An hourly checkpoint means up to roughly an hour of data can be lost after the last successful checkpoint; failed flushes extend that window and must be visible.

`Storage=volatile` plus `RuntimeMaxUse=` can bound journald's memory-backed storage [9]. That is not itself a periodic SD snapshot solution. Audit all actual writers, including any syslog service, swap configuration, package/system tasks, and database journals. “Most application logging is RAM-first” is a defensible target; “the SD receives no other writes” is not established by the current installer.

Remote shipping should use closed batches, authenticated transport, station/boot/sequence identities, acknowledgment and deduplication. A failed destination must cause bounded local retry—not unlimited RAM use or blocked time service. Remote-first storage may be a separate operating mode from strict hourly local durability.

## 6. Position refinement specification

Keep Welford for numerical running statistics, but do not interpret sample count as a guarantee of absolute accuracy. The familiar `s / sqrt(N)` assumes sufficiently independent observations. Repeated receiver outputs, temporally correlated errors and a fixed bias can make the average look much more certain without locating the antenna more accurately. Multipath, blockage and antenna environment remain important [11]. A universal 1–3 m “floor” is not a measured property of this installation.

Recommended stages:

1. Freshness, identity, finite-value and range validation; explicit 3D quality criteria; accepted/rejected counts with reasons.
2. A stationary survey session with duration, antenna/hardware configuration, downtime and movement/relocation handling.
3. A geographically robust coordinate accumulator (ECEF or local east/north/up), not blind longitude averaging across discontinuities.
4. Raw scatter and block/session mean stability over separated time windows. Choose block duration from observed correlation; do not claim block means automatically remove all systematic error.
5. Optional correlation-adjusted uncertainty only after its model is validated. Label simple SE as independence-assumed, not surveyed absolute accuracy.
6. Accepted site separate from the running candidate, with manual coordinates/import from an external survey as a first-class alternative.

Suggested display: accepted position; live displacement from that position; survey duration and fresh sample count; horizontal/vertical scatter; between-block stability; receiver-reported quality; source/datum; and “absolute position accuracy not independently verified” until there is external evidence.

Receiver-reported error estimates are useful quality indicators but do not have universally reliable confidence semantics [4]. Preserve raw values and their provenance. GNSS MSL height, ellipsoidal height, surveyed orthometric height, ground elevation, and sensor mounting height must not be merged. NOAA height conversion tools require the appropriate input reference frame; a WGS84 receiver value cannot silently be treated as a NAD83 realization [12].

A future multi-band RTK/raw-observation receiver can support a precision-positioning path [13], but corrections, antenna calibration, datum, and validation are a separate hardware project. Refining this application mean does not currently send receiver timing-mode commands or alter chrony's discipline.

## 7. Cross-device timing specification

The current `chronyc clients` integration answers “who sent time requests?” It does not answer “what offset does each device have?” [1]

### First useful release

Create a small registry of deliberately enrolled devices. For each, record identity, platform, measurement method, selected reference, signed offset convention, round-trip delay when measured, uncertainty type/value, measurement age, and state. Use “observed traffic; offset unknown” for uninstrumented clients.

Start with a Linux chrony adapter and a macOS-compatible native measurement agent; add a Windows adapter using documented W32Time diagnostics [14]. Distinguish daemon-reported correction, native probe offsets to the Pi, and independently calibrated measurements. A clock compared against the Pi inherits the Pi reference assumptions; a good relative comparison does not independently establish UTC accuracy. An NTP-only appliance may not run an NTP server or expose a clock readout at all.

A browser page can provide an explicitly coarse comparison mode after R-06, but it is not a substitute for native device measurements. Use a genuine four-timestamp exchange when implementing active comparison; report delay and avoid claiming known one-way latency [15].

Keep client measurement targets separate from chrony's selectable upstream time sources to avoid accidentally disciplining the Pi to one of its own clients. Protect agent enrollment and ingestion; reject replayed/oversized/malformed records, use bounded polling, and never execute arbitrary commands supplied by a client.

Add offset history, drift trend, source changes, sleep/resume and stale-device states, per-device tolerances, and debounced alerts. Packet receipt alone must never make an “accuracy verified” badge green.

### Later precision tier

Investigate actual interface hardware timestamping capability and PTP only when a concrete accuracy requirement warrants it. Network/application timestamps and physical event timestamps are different layers; Linux documents distinct software and hardware capture points [16]. A Pi clock display with nanosecond digits does not confer that accuracy on browsers, Wi-Fi devices, cameras, ADCs, or remote sensors.

## 8. Weather-station specification

Begin with local environmental measurement, not forecast aggregation. Add one collector exposing temperature, humidity and pressure, sensor identity, calibration metadata, sample time, receipt time, stale state and measurement uncertainty where known. Keep external ambient, enclosure, receiver and CPU temperatures separately named.

Use representative, shielded and ventilated ambient placement away from device heat; wind and rainfall have their own siting requirements [17]. Store barometer elevation separately from antenna elevation. Keep measured station pressure distinct from any model-derived sea-level value. Do not use weather-varying barometric altitude to prove that GNSS elevation converged.

Initial derived views: dew point, humidity/pressure trends, and temperature versus clock frequency. Label temperature/frequency correlation as an observation, not proof that CPU temperature is the crystal temperature or sole causal factor. Rain, wind, solar/sky brightness and lightning proximity can follow as separate collectors.

For observation planning, optional cloud/sky sensors and a manually measured local horizon profile are good fits. Forecast feeds, if added, should remain an opt-in external-data category with explicit provider, update age and license.

## 9. Shared observation contract

Specify this before adding a general widget/plugin framework. A record should include:

- Schema version, station ID, device/sensor ID, boot ID, and sequence number.
- Observation UTC and monotonic receipt time; distinguish event capture from arrival/processing time.
- UTC/time-scale policy and time-quality state at observation, including uncertainty type and value or unknown.
- Measurement values with units, validity flags, calibration version and metadata.
- Accepted site/session ID, with privacy controls for exports.

Use decimal strings or another integer-safe representation for Unix nanoseconds crossing ordinary JavaScript JSON boundaries. Preserve raw evidence alongside derived values when feasible. A `t_utc_ns` field is a representation, not an accuracy certificate.

Collectors should run outside the web process with timeouts, memory/CPU/I/O budgets and bounded output. A process boundary alone is not resource isolation. Prefer a small schema and a couple of built-in collectors before arbitrary executable plugin discovery or third-party rendering code.

## 10. Expansion priorities

| Priority | Addition | Why it belongs |
|---|---|---|
| High | Commissioning/self-test and redacted support bundle | Reproducibility, no-SSH diagnostics, and faster hardware fault isolation. |
| High | Antenna/satellite quality sky plot with history | Uses existing measurements; connects signal quality to failures and survey quality. |
| High | Source/PPS/fallback/reacquisition event timeline | Explains offset or uncertainty changes rather than merely drawing them. |
| High | Device-offset history and per-device tolerance alerts | Directly fulfills cross-device timing. |
| High | Disk-write, flush, backlog and retention observability | Makes the RAM-first promise measurable. |
| High | Metrics endpoint and optional remote archive | Integration without a mandatory external database or cloud. |
| Medium | Holdover characterization | Valuable only with independent reference monitoring and a defined procedure. Internet fallback is not free-running holdover. |
| Medium | Temperature/frequency characterization | Fits clock diagnostics once both time series are actually collected. |
| Medium | Weather and astronomy-planning sensors | Extends the same station/site/time record rather than building an unrelated app. |
| Later | PTP/hardware timestamping or precision-position receiver | Hardware-specific performance tier. |
| Separate research | Lightning TOA, seismic/muon coincidence, SDR time-of-arrival | Acquisition calibration and networks are substantial additional projects. |

The existing lightning proposal should remain a research document. In-band PPS can address unknown buffering latency, but it does not by itself prove absolute waveform accuracy. ADC filtering/group delay, channel skew, sample-clock drift, dropped samples, pulse-to-UTC association, event detection and propagation models need validation. At 192 kHz the sample interval is about 5.21 µs; sub-sample interpolation is an estimation method, not a guarantee. A 1 µs timestamp error corresponds to about 300 m of propagation distance, not automatically 300 m of solved position error.

Do not make forced UDP-123 redirection, cloud forecasts, arbitrary dashboard plugins, or a multi-station scientific network prerequisites for the first polished release. A second independent timing station is a useful future validation instrument, but two disagreeing clocks alone do not identify which is correct.

## 11. Proposed release order and gates

### Release A — Trustworthy public baseline

Scope: R-01 through R-10 as applicable to safety, truthful measurement and licensing; independent collector; bounded storage; regression fixtures; release manifest; supported-hardware matrix; basic redacted diagnostics.

Gate: repeatable clean install/upgrade; no privileged anonymous mutations; fresh-only survey with no browser; correct tracking semantics; bounded RAM/disk; stated recovery window; no unknown-license shipped data; explicitly documented limits. Test antenna condition and stable baseline before advertising performance.

### Release B — Device timing

Scope: registry, Linux and macOS measurement paths, Windows adapter next, traffic-only status for unsupported clients, histories and tolerances, isolated monitoring reference set, authenticated ingestion.

Gate: measurement method and age visible for every offset; no inferred accuracy from packet counts; delay and sleep/resume tests; no timing-reference feedback loop.

### Release C — Trusted site

Scope: session-based surveying, block-stability diagnostics, accepted site lock, altitude/datum metadata, relocation handling, manual/external survey import, GNSS sky history. The R-04/R-08 correctness fixes belong in A; the richer survey workflow belongs here.

Gate: duplicate/missing/correlated observations cannot masquerade as verified absolute accuracy; accepted site stable; altitude fields unambiguous; legacy survey handling explicit.

### Release D — Environmental station

Scope: one external environmental collector, calibration/siting metadata, station pressure, derived observations, temp/frequency chart, export and metrics integration.

Gate: sensors can fail or disconnect without impacting chrony; stale values do not appear current; observations carry capture semantics; external temperature is not substituted with CPU temperature.

### Release E — Extension framework and optional research

Scope: generalize proven collector contracts, limited layout customization, hardware precision tiers and individually scoped scientific experiments.

Gate: demonstrated demand from multiple real collectors; resource isolation tests; no claim of event-level accuracy without acquisition-level evidence.

## 12. Primary references consulted

External references validate technical semantics; they do not establish what is deployed on the user's Pi. Consulted September 7, 2026.

1. Chrony 4.8 `chronyc`: tracking, clients, machine-readable output, source selection and reachability. https://chrony-project.org/doc/4.8/chronyc.html
2. Chrony 4.8 configuration: tracking log field meanings. https://chrony-project.org/doc/4.8/chrony.conf.html
3. Chrony FAQ: accuracy, delay asymmetry and reference limitations. https://chrony-project.org/faq.html
4. gpsd JSON: TPV altitude, epoch, quality estimates and validity. https://gpsd.io/gpsd_json.html
5. d3-celestial upstream source list and license. https://github.com/ofrohn/d3-celestial
6. OpenNGC upstream license declaration. https://github.com/mattiaverga/OpenNGC
7. Creative Commons BY-SA 4.0 conditions. https://creativecommons.org/licenses/by-sa/4.0/
8. GPLv3 text, including aggregation and distribution. https://opensource.org/license/gpl-3.0
9. systemd journal documentation, distributed by Debian. https://manpages.debian.org/testing/systemd/journald.conf.5.en.html
10. Python `atexit` signal limitations. https://docs.python.org/3/library/atexit.html
11. GPS.gov: positioning accuracy factors. https://www.gps.gov/gps-accuracy
12. NOAA NGS geoid service and reference-frame requirements. https://geodesy.noaa.gov/web_services/geoid.shtml
13. u-blox ZED-F9P capabilities. https://www.u-blox.com/en/product/zed-f9p-module
14. Microsoft W32Time diagnostics and offset tools. https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings
15. IETF RFC 5905: NTPv4 protocol and timestamps. https://www.rfc-editor.org/rfc/rfc5905.html
16. Linux kernel timestamp capture documentation. https://www.kernel.org/doc/html/latest/networking/timestamping.html
17. Cornell NEWA weather sensor placement guidance. https://newa.cornell.edu/placement-guide
