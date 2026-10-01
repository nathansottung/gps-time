# GPS Time — Independent Whole-Repository Engineering Review

**Review date:** 2026-09-27
**Reviewer:** Claude (independent; the 2026-09-07 review was treated as evidence, not authority)
**Mode:** Review / audit / roadmap reconciliation only. No source files were modified, nothing was committed, pushed, deployed or installed.

Evidence labels used throughout:

- **FACT** — directly observed in the verified archive or reproduced by a test in this review.
- **INFERENCE** — reasoned from code plus documented tool behavior, not executed on a Pi.
- **RECOMMENDATION** — proposed change; not existing behavior.
- **UNVERIFIED** — a claim (in docs or elsewhere) this review could not confirm.

---

## 1. Archive verification

| Item | Result |
|---|---|
| Primary archive | `gps-time-development-2026-09-18.zip` |
| Location found | Not at its original path (`…\pi_ntp\`). Found in the Windows Recycle Bin (`$RB0OOJH.zip`) via the Recent-Files shortcut target. Hashed and copied **read-only**; nothing was restored or deleted. |
| SHA-256 (computed) | `c1edc2e92979911e093cc444527b1dbdf8e332afa08834e0bb325fb8acb76829` — **matches expected** |
| Entries | 97 files, single top-level directory `gps-time/` |
| Optional deploy archive | `gps-time-pi-deploy-2026-09-18.tar.gz` (Recycle Bin `$RY121OU.gz`) |
| SHA-256 (computed) | `b11a73031c18f3dbbc15a908678d19093f74ec9302170e82027c0577f2222ebc` — **matches expected** |
| Deploy entries | 45 regular files under `gps-time/` |
| Bundle SUMS file | `gps-time-bundle-SHA256SUMS-2026-09-18.txt` (Recycle Bin) lists exactly the two expected hashes |
| Working tree | `…\pi_ntp\gps-time` (97 files, 2,399,210 bytes) is **byte-identical** to the extracted dev ZIP (`diff -rq` clean). Tree manifest SHA-256 (sorted `sha256  path` lines): `b9c7cd2c3b3bea8acf75bd2c4332479793fbe8d7244f71f39885deaa13738fff` |
| Deploy ↔ dev correspondence | **FACT:** all 45 deploy files are byte-identical to the same paths in the dev ZIP. Rebuilding with `tools/build_bundles.py` from the dev tree yields the same 45 names and identical contents (archive bytes differ; see GPS-022). The deploy tarball plausibly — and content-wise exactly — corresponds to the dev source. |
| Version strings | `gps_time_pi/__init__.py:1` → `1.4.0-dev`. Docs reference v1.3.0 as the deployed baseline. Demo mode reports `versions.app = "demo"` (`demo.py:87`), not the package version. |
| Top-level structure | `.github/ .vscode/ config/ docs/ examples/ gps_time_pi/ scripts/ system/ tools/` + `install.sh gps-time-pi.service README.md START-HERE.md SECURITY.md CONTRIBUTING.md LICENSE .gitignore .editorconfig` |
| Evidence archive | `docs/review/review-evidence-2026-09-07.zip` inspected: review markdown, `probe_uploaded_snapshot.py`, `probe-results.json`, README, manifest. Its probes target the older snapshot (SHA `6ac67e1f…`). This review wrote and ran its own probes against the verified 2026-09-18 archive. |

**Verification limitations:** ZIP entry timestamps are 2026-09-02 … 2026-09-18, so the dev ZIP was not produced by a single `build_bundles.py` run from a fresh checkout; build provenance (commit, builder) isn't recorded anywhere. No `.git` metadata exists, so file history can't be verified.

---

## 2. Executive engineering status

**What is solid (FACT unless noted)**

- The **timing core itself is standard and well chosen**: gpsd (`-n`) → SHM NMEA refclock (`noselect`) + kernel PPS refclock `lock NMEA prefer` → chrony, with Internet pool fallback (`examples/chrony.conf.snippet`). The application **observes** chrony/gpsd and doesn't sit in the discipline path. If the web service dies, chrony keeps serving NTP.
- Astronomy is import-guarded (`astro.py:31-53`); missing Skyfield/ephemeris degrades to "unavailable" without touching `/api`.
- **Windows demo works as claimed:** stdlib-only, no gpsd/chrony/Skyfield/Internet, same `dashboard.html`/`dashboard.js`/CSS as the Pi, config confined to `.dev/`. Verified by an in-process smoke test with outbound sockets blocked (§17).
- Dashboard layout validation is allowlist-based (known widget IDs, constrained page IDs, 256 kB cap, atomic `os.replace`). No path traversal or arbitrary-file-write found. Static file serving uses `basename()` and resists traversal (tested).
- The documentation contract (`docs/README.md`, `timing-core-boundaries.md`, `sdr/timing-model.md`, `GNSS-SURVEY-AND-INSTALLATION.md`) is **scientifically sound** and mostly more careful than the code. The main problem is that the code hasn't caught up with its own docs.

**What is scaffold**

- Configurable dashboard (pages / visibility / size / import-export): real, but minimal.
- Browser RTT and clock estimate: experimental; not used for the displayed time.
- The RF observatory, ADS-B, transits and distributed widgets are **static placeholders** (`dashboard.js:27-30`). No SDR, ADS-B, UAT, MLAT, sensor, collector, event, or distributed code exists.

**What blocks a stable public release** (details in §5)

1. **Fresh install from the shipped archive fails** (GPS-010): `logsync.sh` ships mode 0644, the units exec it directly, and `install.sh` (`set -e`) aborts before installing the web service. The runbook claims this was fixed; it wasn't.
2. **Survey freshness bug still present and reproduced** (GPS-001/002): silent gpsd → the same fix is re-counted every minute, and data age resets to 0 s.
3. **Timing semantics:** History "uncertainty" band is a mixture of three unrelated chrony columns (GPS-003). The new dashboard's "UTC reference" clock is the **browser's** clock (GPS-004). NMEA-only installs are labeled "GPS/PPS · Stratum 1" (GPS-005).
4. **Security:** root web service on :80 with unauthenticated **GET** reboot/restart/reset/privacy endpoints, CSRF-able from any web page a LAN user visits (GPS-014). The privacy "hidden" mode leaks longitude through sidereal time (GPS-015).
5. **Persistence:** the "RAM-backed" log is unbounded, copied whole every hour, non-atomic, and (on fresh installs) never flushed at all (GPS-011/012/013).
6. **Provenance/licensing** is incomplete (GPS-023), and precise coordinates that may be real appear in docs (GPS-024).
7. There are **no automated tests** (GPS-031).

**What is safe to iterate on now**

- Dashboard CSS/HTML/widget rendering in demo mode (same renderer as the Pi, isolated `.dev/` config).
- Pure-logic fixes testable with mocks: GNSS freshness gating, chrony parsers, sync-state classification, unit/label corrections.
- Documentation corrections and provenance files.
- Avoid touching `install.sh`, systemd units or chrony config without a Pi test pass (§18).

**Can the project evolve without breaking the timing core?** Yes, **structurally** (INFERENCE): chrony/gpsd are independent processes, and the web app is only an observer. The risks are operational. The web app runs as root, can restart/reboot the core via CSRF, loads the Pi with per-request subprocess and Skyfield work (GPS-018), and its logging scheme can eventually fill `/run` (GPS-011). All of these are fixable incrementally without a rewrite.

---

## 3. Repository / architecture map

```text
                    ┌──────────── Raspberry Pi (Station node) ─────────────┐
 GNSS receiver ─UART─► gpsd (-n) ──SHM 0 "NMEA" (noselect)──┐              │
      │                   │                                  ▼              │
      └──PPS─GPIO─► pps-gpio → /dev/pps0 ──PPS "GPS" (lock NMEA, prefer)─► chronyd ─► system clock ─► NTP :123 (allow LAN)
                          │                                  ▲   │ log tracking → /run/chrony-log/tracking.log (tmpfs)
                          │                  pool.ntp.org ───┘   │
                          │ TCP 2947 (?WATCH)                     │ chronyc tracking/sources/sourcestats/clients (subprocess, per request)
                          ▼                                       ▼
            gps_time_pi.server  (python3 -m, ROOT, 0.0.0.0:80, ThreadingHTTPServer)
              ├─ gps.py      snapshot(): 5 s cache of TPV/SKY, *and* survey ingestion (side effect)
              ├─ chrony.py   parsers, sync_state(), history() reads tracking.log
              ├─ config.py   config.json: privacy mode + Welford survey (15-min batched writes, atexit flush)
              ├─ astro.py    Skyfield + DE440s (guarded), catalog.py + data/*.json
              ├─ dashboard.py  dashboard.json layout load/validate/save
              ├─ system.py   diagnostics + admin actions (systemctl restart/reboot, logsync flush)
              ├─ demo.py     fixture providers when GTP_DEMO=1
              └─ templates/ + static/  (/ dashboard, /configure, /legacy, /almanac, /history, /admin, /zones)
            logsync.service (boot restore / shutdown flush)   logflush.timer (hourly cp -p RAM → /var/log/chrony)
                    └──────────────────────────────────────────────────────┘
 Workstation: scripts/run-demo.* (demo on 127.0.0.1:8080, .dev/)  tools/build_bundles.py → dist/  scripts/deploy-to-pi.* (scp + ssh sudo install.sh)
```

**Data flow facts that matter**

- **All GNSS sampling and survey ingestion happen inside HTTP request handling** (`server.py:55` → `gps.snapshot()`; also `server.py:118,164`). No browser → no survey.
- **Every `/api` call spawns 4 `chronyc` subprocesses plus a gpsd socket session.** The new dashboard polls `/api`, `/api/dashboard` and `/api/almanac` every 5 s per open browser (`dashboard.js:35-36`).
- Persistence surfaces: `/opt/gps-time-pi/config.json` (survey + privacy), `/opt/gps-time-pi/dashboard.json` (layout), `/run/chrony-log/tracking.log` → `/var/log/chrony/tracking.log`.

---

## 4. Implementation status matrix

| Feature family | Implemented | Harden | Experimental scaffold | Planned (documented) | Research | Deferred |
|---|---|---|---|---|---|---|
| GNSS/PPS → chrony → NTP (system config) | ✔ (examples + generator; runbook reports deployment) | privileges, fallback labeling | | capability discovery | | |
| Sync-state classification | ✔ | ✔ GPS-005/006 | | | | |
| Timing-quality panel | ✔ | ✔ GPS-007/008 | | error budget, light-distance of *uncertainty* | | |
| Timing history (chrony tracking.log) | ✔ | ✔ GPS-003/012 | | | | |
| PPS-loss / holdover timeline & statistics | ✘ | | | ✔ (registry A) | holdover validation | |
| Allan/TDEV/MTIE | ✘ | | | | ✔ | |
| RAM logging / persistence | partial (tmpfs logdir + hourly copy) | ✔ GPS-011/013 | | bounded segments/rollups | | |
| GNSS satellites table / DOP | ✔ | label units GPS-027 | | sky-obstruction map | | |
| Site survey (Welford) | ✔ | ✔ GPS-001/002/009 | | sessions, accepted site, ENU, blocks | | |
| Astronomy / almanac (Skyfield) | ✔ | privacy GPS-015, caching GPS-018 | | offline data packs | | |
| Sidereal time | ✔ | privacy leak | | | | |
| NTP client visibility (`chronyc clients`) | ✔ (traffic only, no offsets) | escaping, DNS | | enrolled device offsets | | |
| Browser RTT / clock estimate | | | ✔ | | | |
| Configurable dashboard (pages/visibility/size/import/export) | | | ✔ | reorder, per-widget settings, presets | | |
| Legacy instrument page | ✔ | escaping, clock bias GPS-028 | | | | |
| Admin (diagnostics + actions) | ✔ | ✔ GPS-014 (security) | | authn/authz | | |
| Location privacy modes | ✔ (direct fields only) | ✔ GPS-015 | | granular export privacy | | |
| Windows demo mode | ✔ | GPS-019 | | | | |
| Build bundles | ✔ | GPS-022 | | | | |
| Pi deployment scripts / installer | ✔ | GPS-010/020/021 | | offline installer | | |
| Hardware config generator | ✔ | GPS-005/032 | | capability tiers | | |
| USB GNSS | profile only (NMEA-only generator path) | labeling | | Linux/Windows abstraction | | |
| SDR (any) | ✘ (placeholder widget) | | | inventory, spectrum, WWV, WSPR | epoch/TDoA | |
| ADS-B 1090 / UAT 978 / MLAT | ✘ (placeholder) | | | adapters | | |
| Sensors / weather | ✘ | | | ✔ | | |
| Lightning (VLF) | ✘ | | | | ✔ | |
| Distributed observations | ✘ (placeholder) | | | observation model (doc) | ✔ | |
| PTP / White Rabbit / 10 MHz out | ✘ | | | | ✔ | ✔ |
| UDP-123 NAT redirect for IoT | ✘ | | | | | ✔ (runbook) |

---

## 5. Findings

Severity is about impact on the project's stated guarantees (timing integrity, measurement meaning, privacy, safe operation). Confidence reflects evidence quality.

### GPS-001 — Stale gpsd TPV is re-ingested as new survey observations, and its apparent age is reset
- **Severity:** High · **Confidence:** High (reproduced)
- **Files:** `gps_time_pi/gps.py:57-85`, `:105`; `gps_time_pi/config.py:102-124`
- **Observed (FACT):** `snapshot()` polls gpsd at most every 5 s. If a poll returns no TPV and more than 60 s have passed since the last refresh, `_cache.update(t=now, tpv=tpv or _cache["tpv"])` (line 65) keeps the **old TPV** and sets `t=now`, so `data_age_s` reads 0.0. Ingestion (lines 76-83) is gated only by wall-clock spacing (`now - _last_site_write > 60`). It doesn't check whether the receiver epoch (`tpv["time"]`) is new. Probe P3: one real fix, then five minutes of gpsd silence → survey `n` went from 1 to 6, `data_age_s` stayed 0.0, `live.time` stayed the original epoch, and `se_horiz_m` = 0.0.
- **Impact:** The persisted survey (written to SD) gains fabricated samples, and its standard error shrinks without new evidence. Duplicates can't be identified later. The live/stored provenance also reports "live" for a dead receiver. Trigger conditions: gpsd stopped, serial silent, USB receiver unplugged. A receiver that has only lost its fix still sends mode-1 TPVs, which are handled correctly (INFERENCE).
- **Fix (RECOMMENDATION):** Keep separate `rx_mono` timestamps for TPV and SKY, set only when that class was actually received in this poll. Never refresh them from cache. Ingest only when the TPV is mode 3, has finite and in-range lat/lon, a parseable `time`, and an epoch strictly newer than the last ingested epoch, and `rx_mono` is fresh (≤ ~10 s). Use `time.monotonic()` for spacing. Mark `live=None` when the TPV is stale, so the stored-site provenance applies.
- **Regression test:** Fake `_poll` + fake clocks: silence, repeated identical epoch, older (reordered) epoch, mode 2, NaN/out-of-range lat, missing `time`, and wall-clock step must each leave `n` unchanged. `data_age_s` must grow during silence, and `live` must become `None` after the freshness threshold.

### GPS-002 — Survey collection is request-driven and not single-writer
- **Severity:** Medium · **Confidence:** High (collection dependence: FACT; race: reproduced with an artificially widened window)
- **Files:** `gps.py:57-85`; callers `server.py:55,118,164`; `ThreadingHTTPServer` `server.py:381`
- **Observed:** No browser/API traffic → no sampling or survey. Concurrent requests share `_cache`, `_last_site_write` and `_FIXES` without a lock. Probe P4: four simultaneous requests during a slow `update_site` ingested one epoch four times (`n=4`). In production the window is shorter (INFERENCE), but it's the same code path.
- **Impact:** Sample counts depend on how many viewers there are and when they look. That violates the "measurement is explicit" rule.
- **Fix:** Short term: a module lock around poll+ingest, plus epoch-identity gating (GPS-001 makes duplicates impossible even if the race remains). Long term: a separate collector process (CHG-011).
- **Test:** A threaded test with N concurrent `snapshot()` calls on one epoch → `n` increments by at most 1. Later: a collector runs 24 h with no browser.

### GPS-003 — History "uncertainty" is a mixture of unrelated chrony columns; the band is invented when missing
- **Severity:** High · **Confidence:** High (reproduced)
- **Files:** `chrony.py:162-194` (docstring 165-166 lists the wrong column layout); `templates/history.html:24-27,106-109`
- **Observed:** The chrony 4.x `tracking.log` layout (per `chrony.conf` docs) is: Date, Time, IP, St, Freq, Skew, **Offset**(6), L(7), **Co**(8), **Offset sd**(9), **Rem. corr.**(10), Root delay(11), Root disp.(12), Max. error(13). The code takes the first non-negative value among indexes 10, 9, 8. Probe P1: row A → `err_s = 2.5e-7` (remaining correction); row B (negative remaining correction) → `err_s = 4e-6` (offset SD). Co (a source **count**) is next in the fallback. The page labels this "reported uncertainty" and, when it's null, draws `±|offset|` as the band (line 106).
- **Impact:** Published charts mix unrelated quantities depending on the sign of an unrelated field. The page's narrative ("balloon during holdover") isn't supported by what is plotted.
- **Fix:** Parse by named columns with a version-checked header. Expose `offset_s`, `offset_sd_s`, `remaining_correction_s`, `root_delay_s`, `root_dispersion_s`, `max_error_s`, `freq_ppm`, `skew_ppm`, `leap`, `n_combined`. Plot offset with the offset-SD band, and max error as its own series, labeled "chrony max-error bound (assumes reference correct)". Never synthesize a band.
- **Test:** Fixture logs (chrony 4.x layout, banner lines, short/legacy lines, negative remaining correction) → exact field mapping. Missing uncertainty stays `null`.

### GPS-004 — The new dashboard's "UTC reference" clock shows the browser's clock, not the station's
- **Severity:** High · **Confidence:** High
- **Files:** `static/dashboard.js:17` (card "UTC reference"), `:33` (`tick()` uses `new Date()`), `:34` (the probe computes an offset but it's never applied)
- **Observed (FACT):** The hero time is `new Date()` formatted in UTC. It sits next to the station's sync state ("SYNCHRONIZED · Stratum 1"). The legacy page did use a (biased) server-time estimate (`app.js:44-46`); the new default page regressed.
- **Impact:** A browser that is seconds off displays wrong time labeled as the station reference. This contradicts rule 3 at the product's most visible surface.
- **Fix:** Display `Date.now() + offset_est` from the `/api/ping` exchange, using the minimum-RTT sample of the last N. Show "station time via HTTP estimate ±RTT/2" and hide the time until an estimate exists. Optionally show the browser offset separately.
- **Test:** A JS unit test (or node harness) with a mocked `Date.now` skewed by +3 s and simulated ping responses → the displayed time is within RTT/2 of the server time.

### GPS-005 — NMEA-only configurations are reported as "GPS/PPS · Stratum 1 · SYNCHRONIZED"
- **Severity:** Medium · **Confidence:** High (reproduced)
- **Files:** `tools/generate_config.py:93-95` (NMEA-only path uses `refid GPS … prefer`); `chrony.py:113-117`
- **Observed:** Probe P2d: an NMEA-only tracking/sources state yields `('SYNCHRONIZED', 'GPS/PPS · Stratum 1')`. The generator's own `usb-gps` note says "Expect ~10-100 ms, not microseconds".
- **Impact:** A millisecond-class convenience clock is presented as a PPS stratum-1 reference.
- **Fix:** Classify by configured capability, not refid text. Detect PPS via the refclock driver (`chronyc -c sources` mode `#` + name, or a `/dev/pps*` presence check at startup) and use distinct refids (`NMEA`, `PPS`). Label NMEA-only as "SYNCHRONIZED (GNSS serial time, ms-class)".
- **Test:** State-table tests for {PPS profile, NMEA-only profile, both present}.

### GPS-006 — Sync-state edge cases mislabel real conditions
- **Severity:** Medium · **Confidence:** High (reproduced)
- **Files:** `chrony.py:10-14,29-35,108-129`; `templates/legacy.html:115-116`; `dashboard.js:24`
- **Observed (FACT, probes P2b/c/e/f):**
  - Missing or failed `chronyc` → `tracking()` returns `{"error": …}` → state **ACQUIRING**. Should be "UNKNOWN / chrony unavailable".
  - PPS reach `"1"` (7 of the last 8 polls missed) → **SYNCHRONIZED**. `reach` only goes to `0` after 8 missed polls (~128 s at poll 4), so HOLDOVER detection lags.
  - `lastrx` is displayed as seconds with a unit appended; chronyc prints suffixed intervals (`"17m s"` observed in the probe message).
  - A LAN stratum-1 upstream at stratum 2 → "Running on **internet** fallback sources".
  - "NO GPS FIX … fallback internet sources" is asserted without checking which source is selected.
- **Fix:** Use `chronyc -c -n` (CSV, no DNS). Add an explicit UNKNOWN state. Derive PPS presence independently (see §7). Name fallbacks from the selected source's address class/config. Parse `lastrx` units.
- **Test:** Table-driven tests on captured `chronyc -c` fixtures.

### GPS-007 — "± uncertainty" shows root dispersion only and implies a symmetric statistical uncertainty
- **Severity:** Medium · **Confidence:** High
- **Files:** `server.py:61,68-69`; `units.py:34-40`; `dashboard.js:18`
- **Observed (FACT):** `system_pair = "<System time> ± <root dispersion>"`. Per the chronyc documentation, the conditional bound is `|system time offset| + root dispersion + ½ root delay` (assuming the upstream reference is correct). "System time" is the correction chrony is **still slewing out**, not the clock error versus UTC.
- **Impact:** Understated bound on NTP fallback (root delay can be tens of ms), and a "±" that reads like a standard uncertainty.
- **Fix:** Report `max_error_bound_s = |sys| + rootdisp + rootdelay/2`, labeled "chrony error bound (conditional on reference)". Label System time as "remaining slew correction". Keep the light-distance display for the bound, not the offset.
- **Test:** Unit test of the bound computation; UI label snapshot.

### GPS-008 — "Projected 1 s holdover" uses the raw oscillator frequency, which describes a free-running clock, not trained holdover
- **Severity:** Medium · **Confidence:** High
- **Files:** `static/dashboard.js:11,18`; `docs/science/timing-metrology.md:42`
- **Observed (FACT):** `1 / |Frequency ppm|`. chrony's `Frequency` is how wrong the clock would be **without** chrony's correction. During real holdover chrony keeps applying the learned correction, so error growth is driven by residual frequency error (≈ Skew), frequency wander and temperature. Illustration with the demo values: raw 2.14 ppm → 1 s in 5.4 days, 1 µs in 0.47 s. Trained (skew 0.018 ppm) → 1 µs in ≈ 56 s, 1 ms in ≈ 15 h, before temperature effects. The label conflates regimes that differ by orders of magnitude.
- **Fix:** Show two explicitly labeled projections, "free-running (untrained)" and "trained holdover (model: skew only, no temperature)". Mark both *modeled*. Validation comes from outage data (§7).
- **Test:** Unit tests for both projections at the §7 thresholds.

### GPS-009 — Survey precision labeled "repeatability"/"±" but computed assuming independent samples
- **Severity:** Medium · **Confidence:** High
- **Files:** `config.py:133-160`; `dashboard.js:20`; `legacy.html:139-143`; `history.html:36-40,189-193`
- **Observed (FACT):** SE = sd/√n on roughly one fix per minute. GNSS errors are autocorrelated over minutes to hours (the project's own `GNSS-SURVEY-AND-INSTALLATION.md:14-16` says so). The UI shows "Survey repeatability ±0.18 m" (demo) and "mean position ±x". `history.html:193` asserts a "~1 m systematic floor", which isn't measured for this installation.
- **Fix:** Relabel as "standard error (independence assumed; not absolute accuracy)". Later, add block-mean statistics (CHG-019).
- **Test:** UI string tests; no numeric change.

### GPS-010 — Fresh install from the shipped archives fails; the runbook says this was fixed
- **Severity:** High · **Confidence:** High for the modes (FACT); Medium-High for the systemd consequence (INFERENCE, not run on a Pi)
- **Files:** `scripts/logsync.sh` (mode 0644 in **both** archives); `system/gps-time-pi-logsync.service:10-11`, `system/gps-time-pi-logflush.service:6` (exec the script directly); `install.sh:3,38-41`; `docs/deployment-runbook.md:66-67`
- **Observed:** The runbook states "This repo's units now invoke via `/bin/bash` and install.sh chmods". Neither is true in this archive. On a fresh install, `cp -r scripts` preserves 0644, so `ExecStart` fails with 203/EXEC (INFERENCE). `systemctl enable --now …logsync.service` then returns non-zero, and `set -e` aborts `install.sh` at line 41. At that point `logdir` in chrony.conf has already been rewritten, but `gps-time-pi.service` has never been installed (INFERENCE). Upgrades on the existing Pi probably survive because `cp` onto an existing file keeps its chmod'ed mode, but line 39 overwrites the Pi's hand-patched `/bin/bash` units.
- **Also:** `system.py:137` runs the script directly (the admin flush fails the same way).
- **Fix:** `ExecStart=/bin/bash /opt/gps-time-pi/scripts/logsync.sh restore` (and ExecStop and the flush unit). Add `install -m 0755` for scripts in `install.sh`. Set tar member modes explicitly in `build_bundles.py`. Correct the runbook.
- **Test:** A clean Raspberry Pi OS image (or container with systemd) install from the built tarball: all units active, installer exits 0. Upgrade test over an existing install.

### GPS-011 — "RAM-backed" tracking log is unbounded, copied whole each hour, non-atomic, and restored whole at boot
- **Severity:** Medium · **Confidence:** High (code FACT; growth magnitudes are INFERENCE)
- **Files:** `scripts/logsync.sh:8-16`; `install.sh:31-37`; timer `system/gps-time-pi-logflush.timer`
- **Observed:** Nothing caps or rotates `/run/chrony-log/tracking.log`. The flush is `cp -p RAM DISK && sync` (global sync, overwrite in place, no temp+rename, no fsync of the file/dir). Restore copies the whole disk file back into tmpfs.
  - Estimate: a PPS refclock at the default poll 4 gives ~5.4k lines/day × ~140 B ≈ 0.75 MB/day ≈ 0.27 GB/yr.
  - `/run` is typically sized at 10–20 % of RAM, so it fills over months to a couple of years. `/run` also holds chrony's and systemd's own runtime files.
  - After 6 months, each hourly flush rewrites ~135 MB. That's ~3 GB/day of SD writes, **more wear than logging directly to SD**.
  - `cp -p` preserves mtime, so "Last SD flush" (`system.py:126-129`) reports the time of the last chrony write included, not flush success.
  - A power cut mid-copy can leave a truncated disk copy, which the next boot restores.
- **Fix:** See §9. Short term: size-capped rotation in `/run` plus `chronyc cyclelogs`, flush with temp+fsync+rename, a manifest with last-success time, and the restore limited to the last segment.
- **Test:** Fill tests (tmpfs of limited size), an interrupted-copy test, and a restart test proving the previous checkpoint survives.

### GPS-012 — Tracking-log path is chosen once at import; the `logdir` directives conflict
- **Severity:** Medium · **Confidence:** Medium (INFERENCE; depends on boot ordering and operator sequence)
- **Files:** `chrony.py:152-159`; `tools/generate_config.py:99-100`; `examples/chrony.conf.snippet:10`; `install.sh:33-37`
- **Observed:** `TRACKING_LOG` is fixed at module import. If `/run/chrony-log/tracking.log` doesn't exist yet when the web service starts (which is likely on a fresh install where restore failed, per GPS-010), the server reads `/var/log/chrony/tracking.log` until restarted. Separately, the generator and examples emit `logdir /var/log/chrony`. If they are appended **after** `install.sh`, chrony writes to SD while the web app reads a stale RAM copy restored at boot, and the hourly flush then **overwrites chrony's live SD log with that stale RAM copy**.
- **Fix:** Resolve the path per request (or read chrony's effective `logdir`). Remove `logdir`/`log` lines from generated snippets and let the installer own them.
- **Test:** A config-combination test (install then append snippet) in a VM.

### GPS-013 — Survey/config durability: SIGTERM skips `atexit`; a corrupt config silently resets; no fsync
- **Severity:** Medium · **Confidence:** High (Python behavior is documented)
- **Files:** `config.py:37-48,51-78`
- **Observed:** Survey updates persist at most every 15 min. The "flush on exit" is `atexit`, which Python doesn't run on an unhandled SIGTERM (what `systemctl stop/restart` sends). Every deploy/restart can lose up to 15 min of survey. `load()` treats a parse error as `{}`, and the next save overwrites the corrupt file, silently erasing the survey. There's no fsync of the temp file or directory before/after `os.replace`. `json.dump` runs while other threads may mutate the same dict.
- **Fix:** A SIGTERM handler calling a flush. Write tmp → fsync → rename → fsync dir. On a parse error, move the corrupt file aside (`config.json.corrupt-<ts>`) and surface a warning. Copy the dict under the lock before dumping.
- **Test:** Send SIGTERM in a subprocess test and assert persisted state; corrupt-file test.

### GPS-014 — Root web service with unauthenticated, CSRF-able GET endpoints that reboot, restart the timing core and change privacy
- **Severity:** High · **Confidence:** High
- **Files:** `gps-time-pi.service:5-9` (no `User=`, so root); `server.py:33` (`0.0.0.0`), `:32` (port 80), `:291-292` (`/api/admin?action=` via GET), `:316-327` (`/api/setting` via GET: privacy, `reset_site=1`); `system.py:134-154`; `templates/admin.html:35-36,97,104`
- **Observed (FACT):** Any client that can reach port 80 can reboot the Pi, restart chrony/gpsd, erase the survey, or set privacy to `exact`. There's no authentication, no Origin/Host checking, and GET semantics. Any web page viewed by any LAN user can do the same with `<img src="http://<pi>/api/admin?action=reboot">` (the IP is guessable/scannable). Browser Private-Network-Access protections are partial and shouldn't be relied upon.
- **Impact:** Remote-triggerable denial of service against the NTP service, plus destruction of survey data. `SECURITY.md` and `timing-core-boundaries.md` acknowledge this is unfinished.
- **Fix:** CHG-007/008/009: POST-only mutations with Origin+Host allowlists → admin disabled by default → unprivileged `User=` with systemd hardening and a narrowly scoped privileged helper (polkit rule allowing only `restart chrony|gpsd|gps-time-pi` and `reboot`) → authentication.
- **Test:** GET to mutation routes → 405. Cross-origin POST → 403. Process UID ≠ 0. Admin disabled by default.

### GPS-015 — Privacy modes don't cover derived outputs; "hidden" still leaks longitude to a few hundred meters
- **Severity:** Medium · **Confidence:** High
- **Files:** `server.py:81` (sidereal is computed from the real site regardless of mode), `:103-144` (`/api/almanac` sun/moon events, sky), `astro.py:380-391`; `config.py:32` (default `exact`), `:163-173`
- **Observed (FACT):** `/api` returns local sidereal time to 1 s alongside `epoch_ms`. Longitude = 15 × (LST − GAST). 1 s of LST = 0.00417° of longitude ≈ **360 m** at 39° N, so even `hidden`/`rounded` (~8.7 km in longitude) is defeated. Solar noon/sunrise/sunset times in `/api/almanac` also constrain latitude/longitude. The privacy setting is itself changeable by anyone (GPS-014).
- **Fix:** Apply the privacy mode to every location-derived output (sidereal, almanac, sky, survey). Round the inputs to those computations in hidden/rounded modes, or omit them. Consider `rounded` as the default for the anonymous view.
- **Test:** In hidden mode, no response field (recursively) lets you recover longitude to better than the mode's resolution (property test comparing outputs at two sites 5 km apart).

### GPS-016 — Unescaped `innerHTML` for chrony/gpsd/DNS-derived strings (legacy view)
- **Severity:** Low · **Confidence:** Medium
- **Files:** `templates/legacy.html:108,152-158,160-164,175-178`; `admin.html:76-77`
- **Observed:** Source names, client hostnames (reverse DNS; `chronyc` is run without `-n`), receiver firmware strings and the state detail are interpolated unescaped. Exploitability depends on resolver sanitization (glibc usually rejects odd PTR characters; INFERENCE). The new `dashboard.js` escapes consistently.
- **Fix:** Reuse `esc()`; run `chronyc -n`.

### GPS-017 — No Host/Origin validation: DNS-rebinding reads, and CSRF-able JSON writes where writes are enabled
- **Severity:** Medium · **Confidence:** High
- **Files:** `server.py:239-245,352-374`
- **Observed (FACT, smoke test):** `POST /api/dashboard` with `Content-Type: text/plain` (a CORS "simple request") was accepted. In production, writes are loopback-only. But writes are open to all in demo, with `GTP_ALLOW_CONFIG_WRITE`, or behind a local reverse proxy (all clients appear as 127.0.0.1). No Host check means a rebinding attacker page can read `/api` (location, client IPs).
- **Fix:** Require `Content-Type: application/json`, check `Origin` and `Host` against configured names/addresses, and document the reverse-proxy implication.

### GPS-018 — Resource isolation: per-request subprocess fan-out, uncached heavy astronomy, unbounded threads, no systemd limits
- **Severity:** Medium · **Confidence:** Medium (structure is FACT; load magnitude is INFERENCE, not measured on a Pi)
- **Files:** `server.py:49-91,103-144,381`; `dashboard.js:35-36`; `gps-time-pi.service`
- **Observed:** Each browser, every 5 s, triggers 4 `chronyc` processes, a gpsd session (up to 3 s), and a full-day Skyfield computation ×3 plus lunar/night/sky. There's no caching, no thread cap, and no `CPUQuota`/`Nice`/`MemoryMax`. `chronyc` without `-n` does reverse DNS; offline with an unreachable resolver, calls can hit the 3 s timeout and the state degrades to ACQUIRING (via GPS-006). Physical side effect: sustained CPU load raises SoC temperature, which shifts the crystal frequency that chrony must track, so dashboard load perturbs the measured quantity.
- **Fix:** Cache the almanac per (date, tz, rounded site) and poll it every 5–10 min. Take `/api` from a collector snapshot (CHG-011). Use `chronyc -c -n`. Bounded worker pool. systemd `Nice=10`, `CPUQuota=`, `MemoryMax=`.
- **Test:** A load test with 10 simulated browsers on a Pi: record CPU %, SoC temperature and chrony frequency/skew, and compare with 0 browsers.

### GPS-019 — Demo mode isn't isolated from host-affecting routes, and fixture data is unlabeled outside `/`
- **Severity:** Medium · **Confidence:** High
- **Files:** `server.py:289-292` (only `/api/system` is demo-guarded; `/api/admin` isn't), `:314-327`; `demo.py:78,87`; templates `legacy/almanac/history/admin.html` (no demo badge)
- **Observed (FACT):** `GET /api/admin?action=…` dispatches in demo mode (verified with an unknown action). On a Linux workstation using `run-demo.sh`, `action=reboot` runs `systemctl reboot` as the developer. polkit commonly allows local active sessions to reboot (INFERENCE). The demo ignores the privacy setting (`hidden` still returns exact demo coordinates), so privacy UI can't be exercised. Only `/` shows "SAMPLE DATA". `/legacy`, `/history` and `/almanac` render fixtures without a badge (legacy includes "sample data" only in the state text).
- **Good:** config stays under `.dev/`; `GTP_BIND=127.0.0.1`; no deployment defaults are modified unless `promote_dashboard.py` is explicitly run.
- **Fix:** In demo, `/api/admin` returns a simulated response. Apply privacy to demo output. Add a global demo banner via a shared template include or `app.js`.

### GPS-020 — Installer: unpinned system-Python pip, trust-on-first-use ephemeris, no service restart on upgrade, no rollback
- **Severity:** Medium · **Confidence:** High
- **Files:** `install.sh:9-10,17-29,47`
- **Observed (FACT):**
  - `pip3 install --break-system-packages skyfield` is unpinned and can conflict with apt-managed Python packages.
  - The DE440s checksum is recorded from the first download itself (no independent verification).
  - `systemctl enable --now gps-time-pi` doesn't restart an already-running service, so an upgrade keeps running old code until a manual restart (the runbook adds a manual restart).
  - `cp -r` over `/opt` leaves stale files; there's no rollback. `apt-get install` runs without `apt-get update`. chrony/gpsd/pps-tools aren't installed or checked.
- **Fix:** A venv under `/opt/gps-time-pi/venv` with a pinned, hashed `requirements.txt`. Pin the DE440s SHA-256 in-repo. Staged install into versioned directories with a symlink swap and `systemctl restart`. Preflight checks for chrony/gpsd.

### GPS-021 — Deploy scripts continue after failed native commands
- **Severity:** Low · **Confidence:** High
- **Files:** `scripts/deploy-to-pi.ps1:6-16`; `scripts/deploy-to-pi.sh:10`
- **Observed:** In Windows PowerShell 5.1, `$ErrorActionPreference='Stop'` doesn't stop on non-zero exits from `python`/`scp`/`ssh`. A failed build can upload a **stale** `dist/` archive. `ssh` without `-t` means sudo can't prompt, so it relies on NOPASSWD sudo. The comment "sudo will prompt remotely" is inaccurate. Fixed `/tmp` name.
- **Fix:** Check `$LASTEXITCODE` after each native call. Use `ssh -t`. Verify the uploaded archive's SHA-256 remotely before installing.

### GPS-022 — Bundle builder ignores `.gitignore`, sweeps in secrets/runtime data, and isn't reproducible
- **Severity:** Medium · **Confidence:** High (reproduced)
- **Files:** `tools/build_bundles.py:17-57`
- **Observed (FACT):**
  - With `.env`, `.venv/…`, `config.json`, `generated/…` and `gps_time_pi/data/de440s.bsp` present, the dev ZIP included **all of them**, and the Pi tar included `de440s.bsp`.
  - Two builds 2 s apart gave different tar SHA-256s (gzip header and member mtimes). Builds on Windows produce member modes `0o666` with empty uname, and **no execute bits**.
- **Fix:** An explicit allowlist or `git ls-files`-based manifest. Normalize `TarInfo` (mtime = `SOURCE_DATE_EPOCH`, uid/gid 0, mode 0644/0755 by path), `gzip.GzipFile(mtime=0)`. Embed version, commit and a file manifest.
- **Test:** Build twice → identical hashes. Planted `.env` → excluded.

### GPS-023 — Third-party data provenance and license records are incomplete; blanket legal claims persist
- **Severity:** Medium · **Confidence:** Medium (UNVERIFIED origins)
- **Files:** `gps_time_pi/data/catalog.json`, `stars.json`, `constellations.json`; `docs/almanac-design-scope.md:137,143,145-146`; `docs/mockups/professional-dashboard-concept.png`; `LICENSE`
- **Observed:** There's no `THIRD_PARTY_NOTICES`, `LICENSES/` or per-dataset manifest (source URL, revision, checksum, conversion script). `almanac-design-scope.md` still says "No patent exposure", "Yale Bright Star Catalog — Public domain" and "DE440s — Public domain". The star data's actual origin is unverified (the 2026-09-07 review noted a d3-celestial source mismatch; still unresolved). The Messier subset is described as OpenNGC-derived (CC BY-SA 4.0), which requires attribution and share-alike on the adapted data. The 1.9 MB mockup PNG has no provenance: it looks generated, and includes a partial callsign, coordinates, SDO imagery and map imagery (UNVERIFIED origin).
- **Fix:** CHG-016. Treat this as a provenance task, not a legal opinion.

### GPS-024 — Potentially real precise coordinates and deployment details in public-bound docs
- **Severity:** Medium (privacy) · **Confidence:** Medium (whether these are real is UNVERIFIED)
- **Files:** `docs/dashboard-expansion-plan.md:458-461,519,1849-1852,1905`; `docs/almanac-expansion-review.md:900-906` (six-decimal coordinates with a lock date — redacted 2026-10-01); `gps_time_pi/demo.py:78` and the mockup (≈1 km and ≈10 m coordinates — redacted 2026-10-01); `docs/deployment-runbook.md` (router model, workstation type, an antenna warranty note — generalized 2026-10-01)
- **Observed:** Six-decimal coordinates (~0.1 m) with a lock date recur consistently. RFC1918 examples are fine. The mock at `dashboard-expansion-plan.md:460-461` gave an ellipsoidal height **greater** than the MSL height (site values redacted 2026-10-01). In that region the geoid undulation is about −33 m, so h ≈ H − 33 m (the demo fixture has the correct sign).
- **Fix:** The owner should confirm and replace these with obviously synthetic coordinates, fix the h/H example, and generalize the runbook's personal infrastructure notes.

### GPS-025 — Documentation contradictions and staleness
- **Severity:** Low (except the runbook claim, covered in GPS-010) · **Confidence:** High
- **Items (FACT):**
  - `deployment-runbook.md:46` says "Reruns are idempotent" (partly true; see GPS-020).
  - `README.md:32` and `current-scope.md:5` say "RAM-backed chrony history". This is imprecise: only chrony's `logdir` is on tmpfs; journald, driftfile, config.json and dashboard.json write to SD.
  - `dashboard/README.md:25,28` lists page create/rename/delete and import/export as *planned*; they're implemented.
  - `platform-extensions.md:66` describes a localStorage layout and a `plugins/` directory, superseded by `dashboard.json`.
  - `DEVELOPMENT.md:9` says the folder is `gps-time-pi`; the archive uses `gps-time`.
  - `docs/README.md` maturity vocabulary (Supported/Experimental/Research/Deferred/Historical) doesn't match the registry's values (Planned, Required correction, Future hardware, Experimental roadmap).
  - `PROJECT-SCOPE.md`/`NEXT-ITERATION.md`/`ideas-ledger.md` duplicate registry content (drift risk).
  - ADR-0002 says demo "swaps providers". In reality it's `if DEMO_MODE` branches in 4 of ~10 data routes (GPS-019).

### GPS-026 — Extension docs overclaim event-timing accuracy (violates rule 3)
- **Severity:** Medium · **Confidence:** High
- **Files and fixes:**
  - `docs/platform-extensions.md:48` says µs muon coincidence "is exactly what this platform provides". The host clock isn't the detector's timestamp path.
  - `:25` says "disciplined clock directly improves [WSPR] frequency/drift measurement". PPS disciplines the Pi's system clock, **not** the SDR's oscillator.
  - `:51` says MLAT/lightning/seismic/muon are "the same measurement". Fine conceptually, but MLAT networks typically use SDR sample-counter timestamps synchronized via aircraft, not host GPS time.
  - `docs/open-lightning-network.md:10-11` says the Pi "already provides a GPS/PPS-disciplined clock at that level".
  - `:63` says in-band PPS "turns a $15 codec into a µs-absolute instrument". In-band PPS establishes sample-to-PPS association; absolute accuracy still depends on the input network, AC-coupling distortion of the PPS edge, channel skew and anti-alias group delay. The doc itself notes some of this at `:120-123`.
- **Fix:** Rephrase to "enables…, subject to characterization" and reference `sdr/timing-model.md`.

### GPS-027 — Quantity/unit labeling issues
- **Severity:** Low · **Confidence:** High
- **Items:** see §11 (C/N₀ "proxy … dB" → dB-Hz; "Orthometric height" from gpsd `altMSL` with an unspecified geoid; `alt` fallback into `alt_hae` at `gps.py:74`; `lastrx` "s"; the runbook "SNR ~36 dB").

### GPS-028 — Browser clock estimators are biased or unstable
- **Severity:** Low · **Confidence:** High
- **Files:** `static/app.js:36-43`; `server.py:63`; `dashboard.js:21,34`
- **Observed:** The legacy estimator uses `epoch_ms` captured **before** the chronyc/gpsd work and adds half of the whole request duration. Server processing (up to seconds) is folded in. Any sample differing by >50 ms **replaces** the estimate, so a slow request resets it to a biased value. The dashboard probe (`/api/ping`, correct 4-timestamp form) averages all 24 samples rather than using the min-RTT sample, and doesn't state its sign convention.
- **Fix:** One estimator module based on `/api/ping` with min-RTT selection, used by both pages (CHG-005).

### GPS-029 — Dashboard configuration hardening gaps
- **Severity:** Low · **Confidence:** High (smoke test)
- **Files:** `dashboard.py:103-110,137-146`; `configure.js:7,18`
- **Observed:**
  - A page title of 5,000 chars was accepted (no cap; the top-level title is capped at 80).
  - Import validates only `pages[]`. A page without `widgets` crashes `render()`.
  - There's no revision/ETag, so concurrent editors are last-writer-wins.
  - Widget order can't be edited.
  - A malformed `dashboard.json` silently falls back to defaults with no warning.
  - Two identical default copies (`config/` and `gps_time_pi/data/`) are a drift risk; only the latter is used by code.
- **Assessment:** The data model (ordered widget arrays per page, `schema_version`) can evolve to reorder, per-widget settings (add a `settings` object with a per-widget schema) and presets (named documents) **without a rewrite** (INFERENCE). Add a `schema_version: 2` migration path in `validate()` now.

### GPS-030 — Shared global object-target state and non-portable strftime
- **Severity:** Low · **Confidence:** High
- **Files:** `server.py:130,147,168` (`_LAST_TARGET` is global, so one user's object query changes another user's sky chart); `server.py:143,184` (`%-I` raises on Windows; only reachable when Skyfield is present, since demo returns earlier).

### GPS-031 — No automated tests; CI is compile-only
- **Severity:** Medium · **Confidence:** High
- **Files:** `.github/workflows/ci.yml:15-18`; no `tests/` directory
- **Fix:** A stdlib `unittest` harness starting with CHG-001; add `node --check` and `bash -n` to CI.

### GPS-032 — Hardware-generator defaults assume a Pi 4-class board
- **Severity:** Low · **Confidence:** Medium (UNVERIFIED on Pi 5)
- **Files:** `tools/generate_config.py:76-78` (CPU lock `arm_freq=600` on by default for every profile/model), `:69-70` (`disable-bt` for any ttyAMA; Pi 5 UART/BT topology differs), `:91` (NMEA offset 0.1 s guess; the runbook measured ~0.035), `:24-25` (SparkFun GPIO22 mapping is taken from vendor docs, not tested). Waveshare's PPS-mod caveat is correctly documented.
- **Fix:** A `--pi-model` flag with per-model overlays; mark CPU lock as opt-in with a stated trade-off; make NMEA offset calibration a documented step.

---

## 6. Timing / GNSS correctness review

**Quantity-by-quantity (FACT unless noted):**

| Quantity | Where | Correct? |
|---|---|---|
| Time offset (system vs chrony's NTP time) | `chrony.py:88-96,134` "System time", sign handled (slow → negative) | Parsing correct. **Meaning mislabeled:** it's the remaining slew correction, not error vs UTC (GPS-007). |
| System time error / uncertainty | `server.py:61,68` uses root dispersion alone | **Incorrect bound** (omits ½ root delay and \|offset\|); "±" implies a standard uncertainty (GPS-007). |
| Reference-source offset | `sources()` keeps `sample` as a raw string | Not parsed; shown verbatim. Acceptable but not machine-usable. |
| Fractional frequency offset | `quality.frequency` raw string ("x ppm slow") | Correct source field; `parsePpm` drops the sign. Labeled "oscillator correction", which is fine. |
| Skew | raw string | Shown; not used in holdover (GPS-008). |
| RMS offset | parsed | Correct field; label "historical clock residual" is acceptable. |
| History offset | `tracking.log` col 6 | Correct column. |
| History "err" | cols 10/9/8 | **Incorrect / mixed** (GPS-003). |
| PPS presence | inferred from `reach != 0` of the source named "GPS" | Lags up to 8 polls; name-based (GPS-005/006). No kernel-level PPS check. |
| PPS selection | Reference ID contains GPS/PPS + stratum 1 | Works for the example config; breaks for NMEA-only (GPS-005). |
| GNSS navigation fix | gpsd TPV mode | Correct, but the cached stale TPV persists (GPS-001). |
| Holdover | stratum 1 on "GPS" with reach 0 | Only occurs when no fallback is selectable (offline). With the example pool (selectable), PPS loss → chrony selects the pool → "DEGRADED", which is correct (**fallback synchronization ≠ holdover**). The detail text misreports `lastrx` units. |
| Fallback sync | stratum ≠ 1 → "internet fallback" | Mislabels LAN upstreams (GPS-006). |
| Unsynchronized | Leap status "Not synchronised" | Correct. chronyc failure falls to ACQUIRING (GPS-006). |
| Survey position | Welford on lat/lon/alt | Arithmetic correct; inputs not fresh-gated (GPS-001); SE assumes independence (GPS-009); longitude averaging is fine except at the antimeridian. |
| Heights | gpsd `altMSL` / `altHAE` (fallback to deprecated `alt`) | `alt` is not HAE. Skyfield needs ellipsoidal height, so preferring HAE is correct; the fallback to MSL is a small (tens of m) astronomy error and a semantic mislabel. |

**chrony field interpretation.** chronyc output is parsed from human-readable text, which is locale/version-fragile and does DNS. **RECOMMENDATION:** switch to `chronyc -c -n tracking|sources|sourcestats|clients`. That gives CSV with stable field order and numeric seconds, and no reverse DNS.

**Survey freshness — independent answers to the brief (§D):**

| Question | Answer |
|---|---|
| Can stale positions be counted as new observations? | **Yes — reproduced** (GPS-001). |
| Can cached data refresh apparent age? | **Yes — reproduced:** `data_age_s` = 0.0 on a 5-minute-old TPV. |
| Can repeated fixes shrink survey uncertainty? | **Yes — reproduced:** `se_horiz_m` → 0.0 from identical samples. |
| Does collection depend on page/API requests? | **Yes** (FACT; the only call sites are HTTP handlers). |
| Can multiple browser requests alter sample collection? | **Yes:** the race double-ingests one epoch (reproduced with a widened window). The normal 60 s spacing is per process, so the viewer count doesn't raise the steady-state rate, but whether any sampling occurs at all depends on viewers. |
| Smallest safe correction | Epoch-identity + monotonic freshness gating + single-flight lock in `gps.py` (CHG-001, §20). |

---

## 7. PPS-loss / holdover data-model recommendation (design only)

**Where it belongs (RECOMMENDATION):** a new **timing collector** process (`gps-time-collector.service`), separate from the web server and from chrony/gpsd. It runs unprivileged (member of the `_chrony` group if the chronyd socket is needed; `chronyc -c tracking/sources` also works over localhost UDP), with `Nice=` and a memory cap. It is a strict **observer**: it never writes chrony config or sets the time. It publishes (a) an atomically replaced snapshot JSON in `/run/gps-time/`, (b) an append-only event log, and (c) rollups (§9). The web server only reads these.

**Signals (1 Hz loop):**

1. **Kernel PPS** — `/sys/class/pps/pps0/assert` (`<sec>.<nsec>#<sequence>`, world-readable). A sequence increment means a pulse arrived. This is the only signal with 1-s resolution that is independent of chrony's poll and reach lag.
2. **chrony** — `chronyc -c -n sources` (selected source, state, reach, lastrx) and `tracking` (ref ID, stratum, leap, offsets, freq, skew, root delay/dispersion). Every 1–2 s.
3. **gpsd** — TPV mode/time, SKY used/visible, and optionally the gpsd `PPS` class (`?WATCH={"pps":true}`).
4. **Context** — CPU/SoC temperature (proxy for oscillator temperature; label it as a proxy), throttling flags.

**State machine (per time step) → events:**

| Derived state | Condition |
|---|---|
| `PPS_LOCKED` | kernel PPS sequence advancing (≤1.5 s since the last pulse) **and** chrony selected PPS (`*`) |
| `PPS_PRESENT_UNSELECTED` | pulses arriving but chrony isn't selecting them (e.g. `lock NMEA` failing, or no fix — a receiver can emit a free-running PPS without a fix; module-dependent, UNVERIFIED for MAX-M8Q defaults) |
| `FALLBACK_SYNC` | no PPS selection; chrony selected another source (NTP) |
| `HOLDOVER` | no PPS selection **and** no selected source; chrony coasting on the learned frequency |
| `UNSYNCHRONIZED` | leap = not synchronised |
| `UNKNOWN` | collector can't read chrony/pps |

**Event record** (one per transition; intervals are formed by pairing):

```json
{"schema":"gps-time.timing-event/1","station_id":"…","boot_id":"…","seq":1234,
 "type":"state_change","from":"PPS_LOCKED","to":"HOLDOVER",
 "t_utc":"2026-09-27T12:00:03.000Z","t_mono_ns":"123456789000",
 "cause":{"pps_last_seq":98765,"pps_gap_s":2.0,"gnss_mode":1,"chrony_selected":null},
 "chrony":{"stratum":1,"freq_ppm":-2.140,"skew_ppm":0.018,"root_disp_s":3.1e-5,"root_delay_s":1e-9,"last_offset_s":-9e-8},
 "context":{"soc_temp_c":44.2},
 "provenance":"observed"}
```

At reacquisition, also record `reacq_first_pps_offset_s`: the first PPS-measured offset after return, from chrony's `Last offset` or the first PPS source sample. **This is the only direct measurement of accumulated holdover error without an independent reference.** Also record `time_to_reselect_s` (PPS back → chrony `*`) and `time_to_settle_s` (to |offset| < threshold).

**Statistics** (computed from events; stored as rollups):

- PPS availability timeline; outage intervals and durations.
- Current and longest lock streak.
- Mean and median outage duration.
- Mean time between PPS-loss events = total locked time / number of loss events (label it an observed rate over the stated window).
- Reacquisition time distribution.
- Chrony source-transition counts.
- Holdover intervals, **kept distinct from** fallback intervals. Internet fallback isn't holdover.

**Clock behavior before/during/after an outage:** before — chrony freq/skew/offset series (observed). During holdover — **there is no reference, so chrony's own offset isn't a measurement of error.** The error during the outage is *modeled* unless an independent reference exists (a second GNSS receiver, a remote stratum-1 with its own uncertainty, or a second station). After — the reacquisition offset (observed, one point per outage).

**Uncertainty during holdover — two modeled curves, always labeled *modeled*:**

- **Raw oscillator (untrained):** `|Δt(τ)| ≈ |y_raw|·τ`, with `y_raw` = chrony Frequency.
- **Trained holdover:** `|Δt(τ)| ≈ |Δt₀| + σ_y·τ + ½·|D|·τ²`, with `σ_y` from skew (≈ frequency uncertainty), `D` a drift/aging term estimated from the frequency history (optionally a temperature coefficient fitted against the SoC-temperature proxy), and `Δt₀` the error bound at loss.
- **Time to threshold** for ±1 µs, 10 µs, 100 µs, 1 ms, 10 ms, 100 ms and 1 s: solve for τ for each curve. Show the light-distance equivalent `c·threshold` (299.8 m, 3.0 km, 30 km, 300 km, 3,000 km, 30,000 km, 299,792 km).
- **Validated vs extrapolated:** a threshold is "validated" only if the observed reacquisition offsets from real outages of duration ≥ τ stayed within it (report N outages). Beyond the longest observed outage, mark "extrapolated". Controlled antenna-disconnect experiments (with fallback sources set `noselect` for the test) are the way to build this evidence.

**Placement in code:** `gps_time_pi/collector/` (poller, state machine, event writer, rollups) + `gps_time_pi/timing_model.py` (pure functions: projections and threshold solving, fully unit-testable) + `system/gps-time-collector.service`. The UI comes later and only reads.

**Registry update needed:** `feature-registry.md` §A lists "Time-to-1ms/10ms/100ms/1s". Add 1 µs/10 µs/100 µs, raw-vs-trained, validated-vs-extrapolated, kernel-PPS availability, streaks/MTBF/reacquisition.

---

## 8. Security review

| Area | Finding |
|---|---|
| Web server privilege | root (no `User=`) — GPS-014 |
| systemd User/Group | none; no hardening directives (`NoNewPrivileges`, `ProtectSystem`, …) |
| Bind | `0.0.0.0:80` in production, `127.0.0.1:8080` in demo (good) |
| Admin endpoints | GET, unauthenticated, reboot/restart/flush — GPS-014 |
| GET vs POST | state changes via GET (`/api/admin`, `/api/setting`); dashboard writes via POST (good) |
| AuthN/AuthZ | none; dashboard writes are gated by loopback IP (bypassed behind a local proxy) |
| CSRF | GET mutations trivially CSRF-able; POST accepts `text/plain` — GPS-017 |
| Host/Origin | not checked → DNS rebinding — GPS-017 |
| Request validation | dashboard: good allowlist; page title length uncapped; almanac/object params validated (tz allowlist, ISO date, regex) — good |
| Path traversal | none found (`basename` for static; tested `..%2f`) |
| Layout import | server-side validation authoritative (good); client import is minimal |
| File handling | atomic replace for config/dashboard (good); no fsync; corrupt config silently reset — GPS-013 |
| Command execution | fixed argv lists; `shell=True` only with constant strings (`system.py:149,152`) — acceptable, but replace with argv |
| Shell scripts | `logsync.sh` has no `set -e`, and flush exits non-zero when the file is absent; deploy scripts ignore failures — GPS-021 |
| Exact location exposure | `/api` exposes 4-decimal coordinates by default (`exact`); derived leakage in hidden mode — GPS-015 |
| Client IP exposure | `/api` lists LAN NTP client IPs to any viewer (LAN privacy, Low) |
| Error leakage | `str(e)` returned with HTTP 200 (`server.py:346-350`) — Low |
| DoS | unbounded threads; expensive endpoints; no caching — GPS-018 |
| Unprivileged-migration caveat | `chronyc clients` needs the chronyd Unix socket (root or chrony group) per chronyc docs — verify on the target chrony version. Plan group membership or a helper before dropping root. |

Honest statement for docs: *"The current web interface must be treated as fully trusted-LAN-only. Anyone who can load a page on the LAN, including through a malicious web page visited by a LAN user, can restart or reboot the station."*

---

## 9. RAM / persistence review

**Is "RAM-backed logging" technically precise?** No (FACT). Only chrony's `logdir` (tracking log) is on tmpfs. Survey/config (`/opt/gps-time-pi/config.json`, every ≤15 min), dashboard.json, chrony's driftfile, journald (persistent by default on Raspberry Pi OS when `/var/log/journal` exists — INFERENCE), apt and pip all write to the SD card. More precise wording: "chrony's tracking log is written to tmpfs and copied to SD hourly."

| Aspect | Current | Assessment |
|---|---|---|
| /run tmpfs logging | `logdir /run/chrony-log` | OK in principle |
| Periodic flush | hourly `cp -p` whole file + global `sync` | Write amplification grows linearly with file size (GPS-011) |
| Shutdown flush | `ExecStop` of logsync (Before=chrony, so it stops after chrony) | Ordering plausible; **broken on fresh install** (GPS-010) |
| File-copy strategy | in-place overwrite | Not atomic; truncation risk |
| Retention | none | Unbounded in RAM and on SD |
| Bounded RAM | no | `/run` can fill (INFERENCE: months–years) |
| Atomicity | no | — |
| Boot restore | copies the whole history into RAM | Grows boot RAM use |
| Failed flush handling | not surfaced | Admin shows mtime-based "last flush" (wrong semantics) |
| Last-successful-checkpoint | none | — |
| journald | not configured | Unbounded persistent journal possible |
| Config writes | atomic rename, no fsync; SIGTERM loses ≤15 min | GPS-013 |

**Recommended bounded event/rollup architecture (RECOMMENDATION; defaults to be measured on a Pi):**

| Tier | Content | Where | Durability | Retention |
|---|---|---|---|---|
| Hot ring | 1 Hz collector samples (PPS seq, chrony offset/freq/skew/root, GNSS mode/used, temp) | collector RAM, fixed-size ring (~86,400 × ~64 B ≈ 5.5 MB/day) | none | 24 h |
| Segments | closed hourly segments of the ring (compressed CSV/JSONL) | write tmp → fsync → rename → fsync dir into `/var/lib/gps-time/segments/` | hourly + SIGTERM | 3–7 days by byte cap |
| Minute rollups | count, min, max, mean, sd per quantity + state-time fractions | RAM accumulation → append to daily file | hourly batch | ~90 days |
| Hour rollups | same | append | daily batch | years (tiny) |
| Events | state transitions (§7) | append-only; flush within ≤5 min (rare, high value) | frequent small batch | years (tiny) |
| Manifest | last persisted `seq` / UTC / boot_id per stream; last flush success/failure | atomic replace | each flush | — |
| chrony tracking.log | keep only as diagnostics: size-capped in `/run` via `chronyc cyclelogs` + rotate; **stop copying whole files to SD** | tmpfs | none | e.g. 20 MB |
| journald | `Storage=volatile`, `RuntimeMaxUse=32M` (or capped persistent) as an explicit appliance policy | — | — | bounded |

Rules: rollups keep min/max/count so excursions aren't hidden; missing data ≠ zero. Surface "last successful checkpoint" and "failed flushes" in the UI. A disk failure must never affect chrony.

---

## 10. Windows demo / dashboard review

**Windows demo (all verified in §17 unless marked):**

- Runs without Pi hardware, gpsd, chrony, Skyfield or Internet — **FACT** (all routes 200 with outbound sockets blocked; no connection attempts recorded).
- Same renderer: `/` serves the same `dashboard.html`, `dashboard.js` and `dashboard.css` in both modes — **FACT** (ADR-0002 holds for `/`). Legacy/history/almanac/admin also share templates, but their demo data paths vary.
- Fixture labeling: `/` shows "SAMPLE DATA" (from `DATA.demo`). **Other pages don't** — GPS-019.
- Config under `.dev/`: `config.json` and `dashboard.json` were written there only — **FACT**.
- Deployment defaults are untouched unless `promote_dashboard.py` or `deploy -UseDemoLayout` is run explicitly. **Note:** promotion rewrites two tracked files, and a Pi that already has `/opt/gps-time-pi/dashboard.json` keeps its own layout (defaults are only fallbacks).
- Scripts: `run-demo.ps1`, `.cmd` and `.sh` set identical env. `.ps1`/`.sh` parse cleanly. `run-demo.ps1` needs `-ExecutionPolicy Bypass` (documented).
- Risk: `/api/admin` isn't demo-guarded (GPS-019).

**Dashboard configuration:** validation is sound for file-write/path safety. The client escapes consistently in `dashboard.js`/`configure.js`. Gaps are in GPS-029. The scaffold can evolve to drag/reorder (array order already exists), multiple pages (done), widget-specific configuration (add `settings` + per-widget schema in `validate()` under `schema_version: 2`) and presets (named layout documents) **without a rewrite**. The main structural change needed is moving widget definitions into a registry that also declares data dependencies and capability requirements (§3 "capability discovery").

---

## 11. Scientific naming / unit review (against `docs/science/quantity-registry.md`)

| Location | Current | Issue | Recommendation |
|---|---|---|---|
| `dashboard.js:22`, `legacy.html:171` | "C/N₀ proxy", "`x dB`" | gpsd `ss` is receiver-reported C/N₀ in **dB-Hz** | "C/N₀ (receiver-reported), dB-Hz" |
| `docs/deployment-runbook.md:104` | "peak SNR ~36 dB" | same | "peak C/N₀ ~36 dB-Hz" |
| `dashboard.js:20` | "Orthometric height … mean-sea-level display" | gpsd `altMSL` uses an unspecified receiver geoid | "MSL height (receiver geoid model; H approx.)" |
| `gps.py:74` | `alt_hae = altHAE or alt` | `alt` is deprecated and not HAE | Don't fall back; leave unknown |
| `server.py:68`, `dashboard.js:18` | "System time offset ± root dispersion" | offset vs remaining correction vs bound | GPS-007 wording |
| `dashboard.js:18` | "Fractional frequency offset: 2.14 ppm fast" | OK quantity; the sign word is chrony's | Keep; add "(uncorrected oscillator)" |
| `dashboard.js:18` | "Projected 1 s holdover" | raw vs trained | GPS-008 |
| `dashboard.js:18` | light-distance of *offset* | registry intends light distance of **uncertainty** | apply to the error bound |
| `dashboard.js:20` | "Survey repeatability ±" | it's SE of the mean | GPS-009 |
| `dashboard.js:21` | "Browser RTT" / "Browser clock estimate +x ms" | RTT correct; offset sign undefined | "station − browser = +x ms" |
| `history.html:24` | "reported uncertainty" | mixed quantity | GPS-003 |
| `legacy.html:36` | "PPS age … seconds since last refclock sample" | `lastrx` has unit suffixes | parse units |
| `docs/dashboard-expansion-plan.md:460-461` | HAE > MSL at a site where N ≈ −33 m | sign error | h = H + N (corrected with the 2026-10-01 USNO example values) |
| Almanac | "Local sidereal time" | correct term (apparent/GAST-based, `astro.py:384`) | say "apparent" explicitly |
| Registry | "irradiance vs irradiation" | correctly distinguished in the registry | enforce when implemented |
| Registry | RTT vs one-way delay | correctly distinguished | don't display one-way delay without asymmetry knowledge |

No broad rewrite is recommended; fold these into CHG-006.

---

## 12. SDR / RF architecture review

**Assessment:** `docs/sdr/overview.md` and `docs/sdr/timing-model.md` are **correct in their core position** (FACT): they separate sampling-rate accuracy from sample-epoch accuracy, tier SDR-0…SDR-4, model group delay as `τ(f, BW, Fs, gain, T, config)`, and note that GNSS L1 reception doesn't provide a PPS edge. No SDR code exists. The overclaims are in `platform-extensions.md` and `open-lightning-network.md` (GPS-026).

**Gaps to add (RECOMMENDATION):**

1. **Four distinct quantities, stated separately:** host-clock accuracy (chrony) · SDR LO frequency accuracy · SDR sample-rate accuracy · sample-epoch accuracy. On RTL2832U designs the LO and sample clock share one crystal, so one ppm correction applies to both. On other SDRs they may not; the calibration schema should allow both.
2. **USB transport:** bulk-transfer buffering and scheduling jitter (ms-scale), and **silent sample drops** (librtlsdr doesn't flag them). The epoch model must include continuity checks (sample counters, or injected markers).
3. **Frequency reference tiers:** stock crystal (tens of ppm), TCXO (~1 ppm), external 10 MHz/GPSDO input (device-dependent). **The Pi's PPS discipline doesn't touch any SDR oscillator.**
4. **WWV/CHU Doppler** (HamSCI-style) needs ≲ mHz-level frequency accuracy at 5–15 MHz. A 1 ppm TCXO gives ~10 Hz error at 10 MHz, which swamps ionospheric Doppler (~0.1–1 Hz). Mark this feature as **requiring an external GPSDO reference tier** (SDR-4 frequency class), not "SDR-1".
5. **WSPR/FST4W** needs ~±1 s time (trivially met by NTP) and a few-Hz frequency accuracy at HF (TCXO adequate). The host clock helps the *slot timing*, not frequency.
6. **Hardware timestamping / PPS alignment:** list concrete device classes when researched (SDRs with PPS/10 MHz inputs, KrakenSDR-style coherent multi-channel). Keep "generic RTL-SDR" at SDR-0/1 for event timing.
7. **Calibrated vs uncalibrated observation flag** in every RF observation record (power in dBFS unless calibrated to dBm — already in the quantity registry).

**Tier review:** the SDR-0…4 ladder mixes frequency and epoch capability. Suggest two axes: **F-tier** (frequency/rate: uncal, ppm-calibrated, externally referenced) × **E-tier** (epoch: host-receipt, PPS-associated, hardware-timestamped). The registry's roadmap items map as: spectrum/RFI (F0/E0), WSPR (F1/E0), ADS-B decode (F0/E0), MLAT (special: aircraft-synchronized, see §13), WWV Doppler (F2/E0), meteor scatter (F1/E0), satellite (F1/E0), TDoA fox hunt (F1/E1+), VLF lightning (separate acquisition path, E1 via in-band PPS).

**Nanosecond claims:** no doc was found claiming a generic RTL-SDR becomes ns-timestamped. `platform-extensions.md:48` implies µs event timing from the platform (GPS-026).

---

## 13. ADS-B / UAT / MLAT architecture review

**Can optional adapters be supported without touching the timing core?** Yes (INFERENCE from architecture), if they follow this pattern:

- **Separate processes and units:** `readsb` (1090) and `dump978-fa` (978, US only) run as their own systemd services with their own users, `CPUQuota`/`Nice`/`MemoryMax`/`IOWeight`. They're never `Requires=`/`Wants=` of chrony, gpsd or gps-time-pi, and are only `After=` network.
- **Read-only integration:** a GPS Time adapter reads readsb's JSON (`/run/readsb/aircraft.json`-style) or Beast TCP output. It never feeds data into chrony. A decoder crash must render as "unavailable".
- **Device identity:** RTL-SDRs often ship with serial `00000001`. Require unique EEPROM serials (`rtl_eeprom -s`, which modifies the device, so it needs explicit user action) and bind by serial in each decoder config. Add an inventory module that lists serial/model/TCXO and assignment, and refuses to start two decoders on one device.
- **Timing truth for MLAT (FACT-level domain knowledge, moderate confidence):** common MLAT clients time messages with the **SDR sample counter** (the 12 MHz Beast timestamps), and the network synchronizes receivers using ADS-B position reports from aircraft seen by multiple stations. A GPS/PPS-disciplined Pi clock doesn't materially improve RTL-SDR MLAT. Only receivers with native GNSS timestamping (a different hardware class) change this. Document it so the platform doesn't claim MLAT benefits it doesn't provide.
- **Compute split:** local decode and local MLAT client metadata on the Station; any project-run MLAT/TDoA **solver** belongs on an Analysis Node or Coordinator (ADR-0001 is consistent).
- **Licensing:** readsb, dump1090 variants, dump978 and mlat-client/server are third-party open-source projects under their own licenses (commonly GPL-family; **UNVERIFIED per project**, so record each). Integrate by process boundary and documented protocols; don't vendor or relicense. External feeders (ADS-B Exchange, FlightAware, etc.) are optional services with their own terms.
- **USB/power budget:** two SDRs plus a GNSS HAT on a Pi 4 is plausible but needs measurement (USB current, CPU for 978 demod). An admission check should refuse to start decoders above configured CPU/temperature thresholds (INFERENCE).

---

## 14. Offline / data-pack review

| Component | Install-time network | Runtime network | Optional external data |
|---|---|---|---|
| apt (`python3-pip`) | yes (`install.sh:9`) | — | — |
| Skyfield via pip (unpinned) | yes (`install.sh:10`) | no | — |
| DE440s ephemeris | yes (JPL URL, TOFU checksum) | no (loaded locally; `astro.py:44-47`) | — |
| Skyfield timescale | — | no (`timescale(builtin=True)`, `astro.py:47`; uses Skyfield's bundled ΔT/leap-second tables, which **age** — valid to the Skyfield release's data horizon; UNVERIFIED exact horizon) | Newer IERS data (optional pack) |
| chrony NTP fallback | — | **yes if configured** (pool, NIST, Cloudflare in the examples; the pool is selectable) | This is the "optional external NTP" |
| `chronyc` reverse DNS | — | **yes, implicitly** (no `-n`); degrades offline (GPS-018) | — |
| Browser dashboard | — | no external assets (no CDNs/fonts found) — FACT | — |
| Demo | none | none — FACT (tested) | — |
| gpsd | — | local only | — |

**Recommendations:**

- `chronyc -n` everywhere.
- Pinned wheels plus a pinned DE440s hash shipped as an **offline dependency pack** (`.tar` with a manifest: name, version, source URL, license, SHA-256, retrieved date), installable from a USB path (`install.sh --offline /media/usb/gps-time-pack`).
- Surface the ephemeris coverage (1850–2149, enforced at `astro.py:25`) and the **age of Skyfield's builtin ΔT/leap-second data** in the UI ("time-scale data as of <date>").
- The docs already require age/validity disclosure (`open-source-policy.md` "Offline packs"); the code doesn't implement it yet.

---

## 15. Open-source / license / provenance review

| Material | Status | Evidence |
|---|---|---|
| Project Python/JS/HTML/CSS, scripts, tools, docs | Project-authored; MIT (`LICENSE`, © 2026 Nathan Sottung) — **clear** | files lack SPDX headers (recommend adding) |
| `gps_time_pi/data/catalog.json` (Messier subset, stars, planets) | Third-party-derived; the doc says OpenNGC (CC BY-SA 4.0) | no notice file, no source revision, no conversion script → **provenance missing** |
| `stars.json`, `constellations.json` | Third-party-derived; the doc says Yale BSC / d3-celestial (BSD-3) | origin **UNVERIFIED** (the prior review flagged a mismatch; unresolved) |
| JPL DE440s | Downloaded at install from JPL; not in the archive | redistribution terms should be recorded from JPL/NAIF rather than "public domain" shorthand |
| Skyfield (MIT), NumPy (BSD), jplephem, sgp4, certifi | pip-installed, not bundled | record in a dependency manifest |
| chrony (GPL-2.0), gpsd (BSD-2), pps-tools | OS packages, not bundled | separate programs; no license interaction with MIT code (aggregation) |
| Mockup PNG | Unknown origin (appears generated), embeds imagery resembling SDO/NASA and maps | **provenance missing** — record origin or remove from the public repo |
| Vendor firmware (u-blox etc.) | not included | correct; never imply it's open |
| Future ADS-B/MLAT tools | third-party (GPL-family, per-project UNVERIFIED) | adapters only; process boundary |

**What can't credibly be described as project-owned open source:** the astronomy datasets (until provenance is reconstructed), the mockup, receiver/SDR firmware, JPL data, and any third-party decoder.

**Can future project-authored protocols/solvers remain open?** Yes. Nothing in the architecture requires a closed dependency (FACT), and ADR-0003 plus `open-source-policy.md` commit to it. The main hazard is accidentally making a GPL tool a *linked* dependency of a project module (INFERENCE). Keep third-party tools behind process/protocol boundaries.

**Remove unsupported legal assertions:** `almanac-design-scope.md:137` ("No patent exposure") and the "public domain" rows (`:143,145`) should become "license as recorded in `THIRD_PARTY_NOTICES.md` (to be verified)". This review gives no legal guarantee.

---

## 16. Hardware / deployment review

**Hardware profiles** (`tools/generate_config.py`, `docs/HARDWARE-PROFILES.md`):

- **Uputronics** (GPIO18 PPS, RV3028 RTC, ttyAMA0): consistent with the runbook's deployed hardware. Reasonable.
- **Adafruit Ultimate GPS HAT** (GPIO4 PPS, no RTC overlay): matches the vendor-documented default PPS pin (per the doc; not independently verified here).
- **Waveshare L76X**: correctly documented as needing a solder modification for PPS. The generator emits a PPS config without verifying the mod; `ppstest` in the checklist covers it.
- **SparkFun GNSS Flex** (PPS1 → GPIO22): taken from vendor docs (UNVERIFIED here). Capability depends on the mounted module (documented).
- **USB GNSS:** correctly NMEA-only in the generator and docs; **mislabeled by the app** (GPS-005).
- PPS GPIO assumption: all PPS profiles assume `/dev/pps0`. Multiple PPS devices (e.g. PPS2 on SparkFun) aren't handled.
- RTC overlays: only rv3028. `backup-switchover-mode=1` is specific to RV3028 (fine).
- Serial: `ttyAMA0` + `disable-bt` assumes a Pi 3/4 topology. Pi 5 differs (UNVERIFIED specifics; add a `--pi-model`).
- Warnings: good NMEA-only warning; but the CPU lock is applied by default (GPS-032).
- Receivers don't have equivalent timing capability: the docs say so. The app doesn't yet expose capability tiers (planned).

**Build/deploy** (`tools/build_bundles.py`, `promote_dashboard.py`, `deploy-to-pi.*`, `install.sh`, units):

- Archive contents: the Pi tar = `PI_TOP` list (45 files); correct and excludes `.dev/`. The dev zip excludes `.dev/`/`dist`/`__pycache__` but **includes `.env`, `.venv`, `config.json`, `generated/`** — GPS-022.
- `.dev/` accidental inclusion: excluded — FACT.
- Reproducibility: **no** (tar hash changes run to run; zip depends on checkout mtimes) — FACT.
- Idempotence: mostly, but no restart on upgrade and no stale-file cleanup — GPS-020.
- Safe remote paths/quoting: fixed paths (`~/gps-time-deploy`, `/tmp/gps-time-pi-deploy.tar.gz`); the host/user are quoted in `.sh`; `rm -rf ~/gps-time-deploy` is bounded to the home dir. Acceptable.
- Error handling: `.sh` has `set -euo pipefail` (good); `.ps1` doesn't check native exit codes — GPS-021.
- Rollback: none.
- Version reporting: `/api` `versions.app`, but no commit/build ID.
- Dashboard promotion: validates and writes both default copies; explicit opt-in (good).
- Dependency installation: unpinned system pip — GPS-020.
- Runtime/offline assumptions: see §14.
- systemd units (static): the web unit has no `User=`, no hardening, and `After=network.target chrony.service` (fine). logsync has `DefaultDependencies=no`, `After=local-fs.target`, `Before=chrony.service`. Plausible, but it has no `Conflicts/Before=shutdown.target` and needs a real shutdown-order test. The flush timer's `OnBootSec=30min` is fine.

---

## 17. Tests executed

All run on Windows 11 (Git Bash + PowerShell 5.1), Python 3.14.7, Node v24.14.1, in scratch copies under the session scratchpad. **The working tree wasn't modified.**

| # | Command (abridged paths) | Result |
|---|---|---|
| 1 | `Get-FileHash -Algorithm SHA256` on the Recycle-Bin archives; `sha256sum dev.zip deploy.tar.gz` on copies | Both match the expected hashes |
| 2 | `unzip -q dev.zip`; `tar xzf deploy.tar.gz`; `diff -rq dev/gps-time <working tree>` | IDENTICAL |
| 3 | per-file `cmp` deploy vs dev | 0 differences (45 files) |
| 4 | Python `tarfile`/`zipfile` mode listing | `scripts/logsync.sh` 0644 in the tar and zip; `install.sh` 0644; `run-demo.sh`/`deploy-to-pi.sh` 0755 |
| 5 | `python -m compileall -q gps_time_pi tools` (scratch copy) | exit 0 |
| 6 | `python tools/generate_config.py --help` | exit 0 |
| 7 | `bash -n install.sh scripts/*.sh` | all OK |
| 8 | `node --check gps_time_pi/static/*.js` + every inline `<script>` extracted from the templates | all OK (14 scripts) |
| 9 | PowerShell `Parser::ParseFile` on `run-demo.ps1`, `deploy-to-pi.ps1` | 0 parse errors |
| 10 | `demo_smoke.py`: in-process `ThreadingHTTPServer` with the demo env (`GTP_DEMO=1`, `.dev/` paths), `socket.create_connection` patched to block non-loopback | all 18 page/API routes 200; traversal attempts 404; **0 external connection attempts**; privacy→hidden stored in `.dev/config.json` but demo `/api` still returns exact coordinates; `/api/admin?action=bogus` dispatched ("unknown action"); POST dashboard valid ✔, `text/plain` accepted ✔ (CSRF-style), unknown widget/malformed/oversize/`../x` page id rejected ✔; 5,000-char page title accepted; reset ✔; only `config.json`/`dashboard.json` created under `.dev/` |
| 11 | `timing_probe.py` P1: synthetic chrony-4.x 14-column tracking.log | `err_s` = remaining correction (row 1), offset SD (row 2) → mixed quantity confirmed |
| 12 | P2: `sync_state` table | NMEA-only → SYNCHRONIZED "GPS/PPS"; reach "1" → SYNCHRONIZED; reach 0 + lastrx "17m" → HOLDOVER "17m s"; LAN upstream → "internet fallback"; chronyc missing → ACQUIRING |
| 13 | P3: mocked gpsd, one fix then silence, clock advanced 61 s ×5 | survey `n` 1→6, `data_age_s` 0.0, `se_horiz_m` 0.0 — **stale-fix ingestion reproduced** |
| 14 | P4: 4 concurrent `snapshot()` threads, one epoch, `update_site` slowed 200 ms | `n=4` — race confirmed (window artificially widened) |
| 15 | `python tools/build_bundles.py` in a scratch copy; compare to the supplied tar | same 45 names, 0 content differences; rebuilt modes `0o666`, empty uname (Windows) |
| 16 | build twice, 2 s apart | tar SHA-256 differs (`90720240…` vs `353a023c…`); zip identical (same mtimes) |
| 17 | planted `.env`, `.venv/lib/big.py`, `generated/…`, `config.json`, `de440s.bsp`; rebuild | all five in the dev zip; `de440s.bsp` also in the Pi tar |
| 18 | Secret/PII scan (`grep` for credentials, keys, usernames, host paths, IPs, coordinate patterns) | no credentials/keys; copyright name in LICENSE (expected); RFC1918 examples; **precise coordinates in two docs** (GPS-024) |

**Tools unavailable / not run:** `shellcheck` (not installed); Skyfield (not installed, so astronomy numerics and `%-I` on Windows untested); systemd, chrony, gpsd and a Raspberry Pi (none). No installer, deploy or privileged action was executed.

---

## 18. Limitations

- **No Raspberry Pi, systemd, chrony, gpsd or GNSS hardware** was available. Installer failure (GPS-010), unit ordering, `/run` growth rates, CPU/temperature effects (GPS-018), chronyc DNS stalls and actual PPS/holdover behavior are **INFERENCE**.
- **Astronomy numerical accuracy** wasn't validated (Skyfield absent).
- **Live timing performance** (PPS jitter, offset, client accuracy) wasn't measured. Nothing here certifies accuracy.
- **chronyc field semantics** are based on chrony 4.x documentation knowledge. Capture real `chronyc -c` output from the deployed Pi for the fixtures.
- **Hardware pin mappings** (Adafruit/SparkFun/Waveshare) and Pi 5 UART topology weren't verified against current vendor documents.
- **Third-party licenses** (datasets, ADS-B tools) are recorded as reported or UNVERIFIED. This is not a legal opinion.
- **Whether the coordinates in the docs are real** is unknown to this review.
- The archives were recovered from the Recycle Bin by hash. Their identity is verified, but where they came from wasn't investigated further.

---

## 19. Recommended implementation sequence

Each unit should be one small PR/branch with tests, and no unit should mix phases.

### Phase 1 — Foundation (correctness, install, security, persistence)

**CHG-001 — Fresh-epoch GNSS gating + first test harness** *(next change — full prompt in §20)*
- Scope: `gps.py` freshness/epoch identity/monotonic spacing/single-flight lock; legacy-survey provenance marker; `tests/` stdlib harness; CI runs the tests.
- Files: `gps_time_pi/gps.py`, `gps_time_pi/config.py` (marker only), `tests/test_gnss_freshness.py`, `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `docs/provenance/change-log.md`, `docs/roadmap/feature-registry.md`, `docs/roadmap/current-scope.md`.
- Non-goals: background collector, survey statistics model, UI labels, deleting existing surveys.
- Acceptance: GPS-001 tests pass; the stale scenario doesn't change `n`; `data_age_s` grows during silence; concurrent calls ingest ≤ 1 per epoch.
- Dependencies: none.

**CHG-002 — Installer and log-unit execution fix**
- Scope: units invoke `/bin/bash …/logsync.sh`; `install -m 0755` scripts; `systemctl restart gps-time-pi` after install; `logsync.sh` flush tolerates a missing file (exit 0) and uses tmp+rename; correct the runbook claim.
- Files: `system/*.service`, `install.sh`, `scripts/logsync.sh`, `system.py:137` (invoke via bash), `docs/deployment-runbook.md`, change-log.
- Non-goals: bounded storage redesign (CHG-013), venv (CHG-015).
- Acceptance: clean-image install exits 0 with all units active; upgrade over an existing install works; flush with no RAM file exits 0.
- Test: Pi or systemd container; `bash -n`; a unit test for the admin argv.
- Dependencies: none (can run in parallel with CHG-001).

**CHG-003 — chrony tracking-log parser by named columns; honest History chart**
- Scope: header-aware parser returning named fields; the History page plots offset ± offset SD and max error separately; no synthesized band; time-based downsampling.
- Files: `chrony.py`, `templates/history.html`, `demo.py` (history fixture fields), `tests/test_chrony_tracking.py`, docs (quantity registry note, change-log).
- Non-goals: collector, persistence.
- Acceptance: fixtures map exactly; missing SD → no band.
- Dependencies: CHG-001 (harness).

**CHG-004 — Sync-state and chronyc hardening**
- Scope: `chronyc -c -n`; UNKNOWN state; capability-based PPS vs NMEA-only classification; fallback source classification; `lastrx` unit parsing; path resolution per request (GPS-012).
- Files: `chrony.py`, `server.py`, `tools/generate_config.py` (distinct refids; drop `logdir`/`log` lines), `examples/chrony.conf.snippet`, `tests/test_sync_state.py`, `docs/HARDWARE-PROFILES.md`.
- Non-goals: kernel PPS reading (CHG-012).
- Acceptance: state table tests incl. NMEA-only, chronyc failure, LAN upstream.
- Dependencies: CHG-001. **Needs** captured `chronyc -c` fixtures from the real Pi.

**CHG-005 — Station-time display and a single browser clock estimator**
- Scope: shared estimator on `/api/ping` (min-RTT of last N, invalidate on visibility change); dashboard hero and legacy use it; label and sign convention.
- Files: `static/app.js` or a new `static/clock.js`, `static/dashboard.js`, `templates/legacy.html`, `docs/science/timing-metrology.md`.
- Non-goals: native device timing.
- Acceptance: with a browser clock skewed +3 s, displayed time within RTT/2 of server time; no display before the first estimate.
- Test: node harness with mocked `Date.now`/`fetch`.

**CHG-006 — Timing/survey quantity labels**
- Scope: error bound = |sys|+rootdisp+rootdelay/2; "remaining slew correction"; raw vs trained holdover projections (pure functions); survey "SE (independence assumed)"; C/N₀ dB-Hz; MSL wording; no `alt` fallback.
- Files: `server.py`, `units.py`, `static/dashboard.js`, `templates/legacy.html`, `templates/history.html`, `gps.py:74`, `docs/science/quantity-registry.md`.
- Non-goals: new metrics.
- Acceptance: unit tests for the bound and projections; label snapshot review.
- Dependencies: CHG-003/004.

**CHG-007 — Security step 1: no GET mutations, Origin/Host checks, admin off by default, escaping**
- Scope: `/api/admin` and `/api/setting` → POST with JSON; `Content-Type` + `Origin` + `Host` allowlist; `GTP_ENABLE_ADMIN=0` default (read-only UI shows "admin disabled"); `esc()` in legacy/admin; demo `/api/admin` simulated.
- Files: `server.py`, `templates/admin.html`, `templates/legacy.html`, `static/app.js`, `SECURITY.md`, `docs/architecture/timing-core-boundaries.md`.
- Non-goals: authentication, privilege drop.
- Acceptance: GET mutation → 405; cross-origin POST → 403; admin disabled by default; demo can't invoke systemctl.
- Test: HTTP tests in the harness.

**CHG-008 — Security step 2: unprivileged service plus a scoped privileged helper**
- Scope: `User=gps-time`, systemd hardening (`NoNewPrivileges`, `ProtectSystem=strict`, `ReadWritePaths=`, `PrivateTmp`, `CAP_NET_BIND_SERVICE` or port change); a polkit rule allowing only the specific unit restarts and reboot; `chronyc clients` access via group or helper.
- Files: `gps-time-pi.service`, `install.sh`, new `system/polkit` rule, `system.py`.
- Non-goals: login UI.
- Acceptance: process UID ≠ 0; allowed actions work; everything else is denied.
- Test: on a Pi.
- Dependencies: CHG-002, CHG-007.

**CHG-009 — Security step 3: admin authentication**
- Scope: local admin password set at install (scrypt hash), session cookie `HttpOnly; SameSite=Strict`, CSRF token, lockout/rate limit, audit log of admin actions.
- Non-goals: multi-user roles, TLS (document reverse-proxy TLS).
- Dependencies: CHG-007/008.

**CHG-010 — Privacy coverage**
- Scope: apply the location mode to sidereal, almanac, sky and survey outputs; decide the default mode for the anonymous view; privacy change behind admin.
- Files: `server.py`, `config.py`, `astro.py` callers, `demo.py`, `docs/…privacy`.
- Acceptance: the longitude-recovery property test (GPS-015).
- Dependencies: CHG-007.

**CHG-011 — Background collector process (single writer)**
- Scope: `gps-time-collector.service` sampling gpsd/chrony on schedules; atomic snapshot in `/run/gps-time/`; survey ingestion moves here; the web reads snapshots.
- Non-goals: event model (CHG-012), rollups (CHG-013).
- Acceptance: 24 h of collection with no browser; viewer count doesn't change the sample rate; web restart doesn't interrupt collection.
- Dependencies: CHG-001/004.

**CHG-012 — PPS-loss / holdover event model (collector-side, no UI)** — per §7.
- Files: `gps_time_pi/collector/timing_events.py`, `gps_time_pi/timing_model.py`, tests with synthetic PPS sequences and chrony fixtures, `docs/science/timing-metrology.md`, `docs/roadmap/feature-registry.md`, a new ADR ("Timing event model").
- Acceptance: synthetic outage fixtures produce the correct intervals, streaks, MTBF and reacquisition times; holdover is distinct from fallback.
- Dependencies: CHG-011.

**CHG-013 — Bounded persistence**
- Scope: §9 tiers; stop whole-file tracking.log copies; tracking.log cap in `/run`; SIGTERM flush; fsync; corrupt-file quarantine; manifest; UI "last successful checkpoint"; journald policy doc.
- Acceptance: fill/interrupt/restart/power-cut simulations keep the previous checkpoint valid; RAM and disk are bounded.
- Dependencies: CHG-011/012.

**CHG-014 — Resource controls**
- Scope: almanac cache; dashboard almanac poll interval; bounded worker pool; systemd `Nice`/`CPUQuota`/`MemoryMax` for web and collector.
- Acceptance: the 10-browser load test on a Pi shows no measurable change in chrony skew beyond baseline (define the metric first).

**CHG-015 — Release engineering**
- Scope: allowlist/`git ls-files` bundling; deterministic tar/zip; explicit modes; embedded version+commit+manifest; deploy scripts check exit codes and verify the remote hash; installer venv with a pinned hashed requirements file and pinned DE440s SHA-256; versioned install dir plus rollback.
- Acceptance: two builds give identical hashes; planted `.env` excluded; clean install and rollback tested.

**CHG-016 — Provenance and publication hygiene**
- Scope: `THIRD_PARTY_NOTICES.md`, `LICENSES/`, `data/MANIFEST.json` (source, revision, license, checksum, transform); reconstruct or replace the star/constellation data; remove blanket legal claims; mockup provenance or removal; replace possibly-real coordinates; fix the h/H example; SPDX headers.
- Acceptance: every shipped asset has a record; the owner signs off on sanitization.

**CHG-017 — Documentation reconciliation**
- Scope: runbook claims; GPS-025/026 corrections; maturity vocabulary unified; registry additions (§7 metrics, WWV reference-clock requirement, SDR F×E tiers); ADR for collector/persistence.
- Acceptance: no doc claims behavior the code doesn't have (checklist review).

### Phase 2 — Dashboard, survey, offline

- **CHG-018 Dashboard evolution:**
  - schema v2 with `settings` per widget and a migration;
  - reorder UI;
  - presets;
  - page-title cap;
  - import validation;
  - revision/ETag;
  - global demo banner.
  - Non-goal: plugin execution.
- **CHG-019 Survey sessions:**
  - ENU/ECEF accumulator;
  - block statistics;
  - candidate vs accepted site with lock;
  - manual/external coordinate import;
  - legacy-survey disposition.
- **CHG-020 Offline data packs:**
  - pack manifest format;
  - `install.sh --offline <dir>`;
  - ephemeris/time-scale data age in the UI.

### Phase 3 — Hardware and instruments

- **CHG-021 GNSS capability tiers + USB GNSS:**
  - capability discovery API;
  - Pi model–aware generator.
- **CHG-022 First environmental collector:**
  - BME280-class;
  - uses the observation record;
  - stale handling.
- **CHG-023 SDR inventory:**
  - serial registry and assignment;
  - udev rules;
  - no decoding.
- **CHG-024 ADS-B/UAT adapters:**
  - read-only readsb/dump978 JSON adapters;
  - separate units;
  - MLAT metadata display only.

### Phase 4 — Advanced metrology and distributed research

- **CHG-025 Timing lab:**
  - ADEV/MDEV/TDEV from collector data;
  - controlled holdover experiments procedure.
- **CHG-026 Observation record schema v1:**
  - spec plus validator;
  - adds boot_id/seq, capture vs receipt time, time-scale, integer-safe ns, GUM-style uncertainty (u, k, type), clock state at capture, SDR F/E tiers, calibration ID, consent/sharing scope, position precision class, signature.
- **CHG-027 Distributed request/accept protocol:**
  - research spec only;
  - coordinator optional;
  - solving on the Analysis tier.

(On §N: `docs/architecture/observation-model.md` is a sound minimum but lacks the CHG-026 fields listed above. Without them, multi-station GNSS/RF/lightning/seismic/optical solvers can't weigh or de-duplicate observations correctly.)

---

## 20. Next recommended change

**CHG-001 — Fresh-epoch GNSS gating for survey ingestion, plus the project's first automated tests.**

**Why first:**

1. It's the only defect that **silently corrupts persisted scientific data**: the survey on the SD card. The corruption can't be undone retroactively, because duplicate samples can't be told apart later. Every other top finding is either a display or labeling error (reversible) or a deployment/security issue with a workaround (trusted LAN, manual chmod already applied on the deployed Pi).
2. It's **small, pure-logic and fully testable on Windows** with mocks. No Pi is needed to prove correctness.
3. It establishes the **test harness and CI hook** that every later change needs.
4. It closes the item the project's own docs name first ("fresh-fix survey semantics").

CHG-002 (installer exec bit) is equally small and can proceed in parallel. It's second only because the deployed station is already hand-patched and fresh installs are blocked for other reasons anyway.

### Ready-to-paste implementation prompt

````text
You are implementing ONE small change (CHG-001) in the GPS Time repository
(Python 3 stdlib web app that observes gpsd/chrony on a Raspberry Pi).
Repository root contains: gps_time_pi/ (package), tools/, scripts/, system/,
docs/, .github/workflows/ci.yml. Version string: gps_time_pi/__init__.py = "1.4.0-dev".
There is currently NO tests/ directory and CI only runs compileall.

Do not commit, push, deploy, or run install.sh / systemctl. Do not touch
install.sh, systemd units, chrony/gpsd config, templates, JS, or CSS.

## Problem (verified by reproduction)

gps_time_pi/gps.py:
- snapshot() (lines ~57-85) polls gpsd at most every 5 s via _poll().
- On an empty poll, if >60 s since the last refresh, line ~65 does
  `_cache.update(t=now, tpv=tpv or _cache["tpv"], ...)` — it KEEPS the old TPV
  and resets the cache time, so `data_age_s` (line ~105) reports 0.0 for stale data.
- Survey ingestion (lines ~76-83) calls config.update_site(...) whenever the cached
  TPV is mode 3 and `now - _last_site_write > 60` (wall clock). It never checks
  that the receiver epoch (tpv["time"]) is new. Result: one real fix followed by
  gpsd silence is re-counted every minute; survey n grows and the standard error
  shrinks to 0 with no new evidence.
- snapshot() runs inside HTTP request threads (ThreadingHTTPServer). _cache,
  _last_site_write and _FIXES are shared without a lock; concurrent requests can
  ingest the same epoch more than once.

Reproduction to turn into tests: mock gps._poll to return one mode-3 TPV
(time "2026-09-20T12:00:00.000Z") then ({},{},{},{}) forever; advance the clock
61 s five times; today config.site_stats(config.load())["n"] goes 1 -> 6 and
snapshot()["data_age_s"] stays 0.0.

## Required behavior

In gps_time_pi/gps.py only (plus the small config.py marker below):

1. Track receipt freshness per class with time.monotonic():
   `_cache["tpv_rx_mono"]`, `_cache["sky_rx_mono"]` set ONLY when that class
   was received in the current poll. Never refresh them from cached data.
   Keep the 5 s poll throttle, measured with monotonic time.
2. `data_age_s` = monotonic age of the last actually-received TPV (None if never).
3. Define TPV_STALE_S = 10.0. If the last TPV is older than that, snapshot()
   returns fix=None, mode=None, live=None (so the existing stored-site fallback in
   observing_site() and server.core_api() applies automatically). Satellite (SKY)
   data older than a SKY_STALE_S = 10.0 returns an empty satellite list.
4. Survey ingestion is allowed only when ALL hold:
   - the TPV was received in THIS poll (fresh), mode == 3;
   - lat/lon are finite floats with |lat| <= 90, |lon| <= 180;
     altitudes, if present, finite (otherwise pass None);
   - tpv["time"] parses as an ISO-8601 UTC timestamp and is STRICTLY later
     than the last ingested epoch (store `_last_ingested_epoch`);
   - monotonic time since last ingestion >= 60 s (replace wall-clock check).
   Rejected candidates must not change survey state. Keep a small in-memory
   counter dict of rejections by reason (e.g. {"stale":…, "repeat_epoch":…,
   "invalid":…, "rate":…}) exposed as snapshot()["survey_ingest"] for later UI use.
5. Wrap the poll + cache update + ingestion in a module-level threading.Lock
   (single-flight): concurrent callers wait and then reuse the refreshed cache.
6. Preserve the public shape of snapshot()'s return dict (existing keys and
   meaning) apart from the stricter freshness semantics and the one added key.
7. Legacy provenance marker (gps_time_pi/config.py): when update_site() first
   runs on a site that lacks key "ingest_rule", set
   site["legacy_samples_before_fresh_gating"] = current n_lat (0 if none) and
   site["ingest_rule"] = "fresh-epoch-v1". Do not alter existing means/variances
   and do not delete any survey data.

## Tests (new, stdlib unittest only, no network, no hardware)

Create tests/__init__.py (empty) and tests/test_gnss_freshness.py. Set
GTP_CONFIG to a temp file BEFORE importing gps_time_pi modules (config reads it at
import; config also registers an atexit writer). Reset module globals between
tests (gps._cache, locks/counters, config._CACHE). Inject fake clocks by
patching gps.time.monotonic / gps.time.time and fake gpsd via gps._poll.
Cover at least:
- silence after one fix: n stays 1 across 5 x 61 s; data_age_s increases;
  after >10 s, live is None and fix is None.
- identical epoch repeated by gpsd every poll: n stays 1.
- older (reordered) epoch: rejected.
- new epoch every 61 s: n increments each time.
- new epoch but <60 s since last ingestion: rejected ("rate").
- mode 2 fix, NaN lat, lat 95, missing "time": rejected, n unchanged.
- wall-clock step backwards/forwards (patch time.time only): ingestion
  spacing still governed by monotonic time.
- 8 threads calling snapshot() concurrently with one fresh epoch: n increments
  by exactly 1 (patch config.update_site to sleep 0.1 s to widen the window).
- legacy marker: pre-existing site with n_lat=5 and no ingest_rule gets
  legacy_samples_before_fresh_gating == 5 after first accepted fix.
Run with: python -m unittest discover -s tests -v

## CI and docs

- .github/workflows/ci.yml: add a step `python -m unittest discover -s tests -v`.
- CONTRIBUTING.md: add the unittest command to "Before opening a pull request".
- docs/provenance/change-log.md: new dated entry describing CHG-001 and stating
  that the survey is now fresh-epoch gated, that pre-existing survey samples are
  marked legacy (count recorded), and that collection still depends on HTTP
  requests (independent collector remains planned).
- docs/roadmap/feature-registry.md §B "Fresh-only independent GNSS collector":
  change status to "Partially addressed (fresh-epoch gating in request path);
  independent collector planned".
- docs/roadmap/current-scope.md "Before stable release": note freshness gating
  done; collector independence still open.
Do not edit docs/review/source-review-2026-09-07.md (historical record).

## Non-goals (do not do these)

- No background collector/service, no systemd changes.
- No change to Welford math, standard-error formulas, or UI labels.
- No changes to chrony.py, server.py routes, templates, or JavaScript.
- No deletion or reset of existing survey data.

## Acceptance

- `python -m compileall gps_time_pi tools` passes.
- `python -m unittest discover -s tests -v` passes on Windows and Linux.
- Demo mode still works: run the server with GTP_DEMO=1 and confirm GET /api and
  / return 200 (demo does not call gps.snapshot()).
- Report: files changed, test output, and any behavior you could not verify
  without Raspberry Pi hardware.
````
