# CHG-001 + CHG-002 — GNSS fresh-epoch gating and fresh-install logging repair

**Date:** 2026-09-27
**Baseline:** `gps-time-development-2026-09-18.zip` (SHA-256 `c1edc2e92979911e093cc444527b1dbdf8e332afa08834e0bb325fb8acb76829`), version `1.4.0-dev`
**Review source:** `docs/review/GPS-Time-Independent-Review-2026-09-27.md` findings GPS-001, GPS-002 and GPS-010
**Status:** candidate for review. Not deployed to a Pi.

---

## CHG-001 — GNSS fresh-epoch gating

### Root cause

`gps.snapshot()` did three jobs inside HTTP request handling: it polled gpsd (at most every 5 s), maintained a cache, and fed the site survey (at most once per 60 s of wall-clock time).

- On an empty gpsd poll, once 60 s had passed, the cache refresh kept the **old TPV** (`tpv or _cache["tpv"]`) and reset the cache timestamp. The old fix then reported `data_age_s = 0.0`.
- Survey ingestion checked only wall-clock spacing, never whether the receiver epoch was new.
- The result: one real fix followed by gpsd silence was counted again every minute for as long as anyone kept a page open. The survey sample count grew and its standard error shrank toward zero with no new evidence. The review reproduced this: `n` went 1 → 6 and `se_horiz_m` went to 0.0.
- Sampling happened only when a browser or API client called `/api`, `/api/almanac` or `/api/object`.
- Shared state had no lock, so concurrent requests could count one epoch several times.

### Behavioral contract (now enforced)

1. **Collection is independent of page/API traffic.** One background thread (`gps.start_collector()`, started by `server.main()` outside demo mode) polls gpsd every `POLL_INTERVAL_S` = 5 s. `gps.snapshot()` and `gps.observing_site()` are read-only: they never poll gpsd and never touch the survey.
2. **Freshness is a property of receipt, not of cache reads.** TPV and SKY each carry a monotonic receipt time that is set only when that report actually arrived in a poll. Empty polls change nothing, so `data_age_s` keeps growing during silence.
3. **Staleness is explicit.** A TPV older than `TPV_STALE_S` = 10 s is reported as `fix: null`, `live: null`, `stale: true`, with `last_fix`, `last_fix_time` and `data_age_s` so the dashboard can keep showing the last known fix, labeled stale with its age. Astronomy then falls back to the stored site with `position_provenance: "stored"`. SKY has the equivalent `sky_stale` / `sky_age_s` fields.
4. **Each survey sample has an observation identity.** The identity is the receiver epoch (TPV `time`, parsed and range-validated as UTC). A sample is accepted only if all of these hold:
   - the TPV arrived in the current poll;
   - it is `mode == 3`;
   - latitude and longitude are finite and in range, and the epoch parses;
   - the epoch is **strictly later** than the last accepted epoch;
   - at least `SURVEY_MIN_SPACING_S` = 60 s of **monotonic** time has passed since the last acceptance.
5. **One epoch counts at most once.** The epoch is claimed atomically under a state lock before the survey write, and gpsd polling is single-flight. Concurrent calls can't double-count.
6. **Rejections are observations, not evidence.** Every non-accepted poll is counted by reason (`no_tpv`, `no_3d_fix`, `invalid`, `repeat_epoch`, `older_epoch`, `rate_limited`). The session counters are exposed in `/api/survey` → `ingest`.
7. **Fresh and legacy samples are distinguished.** `site_stats()` (in `/api` → `survey`) now reports `n` (total), `n_fresh` (accepted under this rule), `n_legacy` (samples that predate it) and `ingest_rule` (`"fresh-epoch-v1"`).

### Treatment of existing (possibly contaminated) survey history

**Nothing is deleted or reset.**

- On the first accepted fresh sample, the site record gains `ingest_rule: "fresh-epoch-v1"` and `legacy_samples_before_fresh_gating: <n at that moment>`.
- A pre-survey plain mean counts as 1 legacy sample.
- Existing means, variances (`m2_*`) and the convergence `history` are kept exactly as they were.
- The legacy samples stay folded into the running mean and standard error, because the Welford accumulator can't separate them after the fact. The UI therefore shows the split ("N fresh-gated, M legacy") so a reader can judge the survey.
- If the station owner wants a survey made only of gated samples, the existing **Reset position survey** action (`/admin`) starts one. That is an explicit owner decision; this change does not make it.

### Files changed

| File | Change |
|---|---|
| `gps_time_pi/gps.py` | collector thread, `poll_once()`, epoch parsing/validation, freshness/staleness fields, rejection counters, locks; `snapshot()` made read-only |
| `gps_time_pi/config.py` | re-entrant lock around survey mutation/reset; legacy marker; `n_fresh`/`n_legacy`/`ingest_rule` in `site_stats()` |
| `gps_time_pi/server.py` | starts the collector in `main()` (not in demo); `/api` → `gps` exposes `last_fix`, `last_fix_time`, `stale`, `data_age_s`, `sky_stale`, `sky_age_s`; `/api/survey` exposes `ingest` |
| `gps_time_pi/demo.py` | fixture carries the same new fields |
| `gps_time_pi/static/dashboard.js` | GNSS card shows "(stale)", data age, and the fresh/legacy split (text only) |
| `gps_time_pi/templates/legacy.html` | same text additions in the legacy view |

---

## CHG-002 — fresh-install logging repair

### Root cause

- `scripts/logsync.sh` shipped as mode 0644 in both 2026-09-18 archives: ZIP extraction or a Windows build drops the execute bit.
- `gps-time-pi-logsync.service` and `gps-time-pi-logflush.service` executed the script directly. On a fresh install that fails with systemd status 203/EXEC.
- `install.sh` runs under `set -e`, so `systemctl enable --now gps-time-pi-logsync.service` failing is expected to abort the installer before the web service is installed. (This is inferred; it hasn't been executed on a Pi.)
- The admin **Flush logs** action executed the script directly too.
- `docs/deployment-runbook.md` stated this had already been fixed in the repository. That wasn't true for the 2026-09-18 archive.

### Fix

- Both units now run `ExecStart`/`ExecStop=/bin/bash /opt/gps-time-pi/scripts/logsync.sh …`.
- `install.sh` runs `chmod 0755 $DEST/scripts/*.sh` after copying and before enabling any unit. Either measure alone is sufficient.
- The admin `flush_logs` action runs `["/bin/bash", ".../logsync.sh", "flush"]`.
- `tools/build_bundles.py` sets explicit archive modes: `.sh` files get 0755 and everything else 0644, in both the tar and the ZIP. Tar ownership is normalized to uid/gid 0 (`root`). Modes no longer depend on the build machine's filesystem.

### Files changed

`system/gps-time-pi-logsync.service`, `system/gps-time-pi-logflush.service`, `install.sh`, `gps_time_pi/system.py`, `tools/build_bundles.py`, `docs/deployment-runbook.md`.

---

## Tests added (first automated tests in the repository)

Run with `python -m unittest discover -s tests -t . -v`. Standard library only; no hardware, network or real waiting. CI (`.github/workflows/ci.yml`) now runs them.

**`tests/test_gnss_freshness.py`** (15 tests)

- **The reviewed failure:** one fresh fix, then gpsd silence while the collector keeps polling and snapshots are read repeatedly for five minutes.
  - Survey `n` stays exactly 1.
  - `data_age_s` rises monotonically to 305 s.
  - The fix is reported stale, with `last_fix` still available.
- Two genuinely different epochs, 61 s apart, give `n == 2` (`n_fresh == 2`).
- The same epoch is rejected when repeated. So is an older epoch, and a new epoch that arrives sooner than 60 s.
- Mode 2, NaN or out-of-range coordinates, a missing time and an unparsable time are all rejected.
- A wall-clock jump does not affect sample spacing, which uses monotonic time.
- 50 calls to `snapshot()` and `observing_site()` poll gpsd zero times and ingest nothing.
- **Concurrency:** 8 threads polling the same epoch, with a deliberately slowed survey write, give `n == 1` and 7 `repeat_epoch` rejections.
- **Real HTTP path:** 30 concurrent `/api` requests across 3 simulated minutes cause no gpsd polls and no new samples, and the API reports the fix stale with a growing age.
- **Collector independence:** with no reader at all, the collector ingests 4 distinct epochs by itself and survives exceptions from gpsd.
- **Legacy preservation:** an existing 5-sample survey keeps its history and is marked `legacy_samples_before_fresh_gating = 5`, giving `n = 6` (5 legacy + 1 fresh). A plain pre-survey mean counts as 1 legacy sample.
- Epoch parser accepts and rejects the expected formats.

**`tests/test_packaging.py`** (6 tests)

- A static checker flags any systemd `Exec*=` line that directly executes a `.sh` file. A self-test proves it flags the exact reviewed line.
- All units in the repository pass the checker.
- Admin actions that run a `.sh` use an interpreter.
- `install.sh` chmods the scripts after copying them and before enabling units.
- A real `build_pi_tar()` and `build_repo_zip()` are run into a temporary directory:
  - `.sh` members are 0755 and everything else is 0644;
  - tar ownership is 0/0;
  - the packaged units pass the checker, and the packaged `install.sh` contains the chmod;
  - the ZIP is intact.

**Evidence that the tests detect the failures** (run in scratch copies, not committed):

- Against the unmodified 2026-09-18 code, all 6 packaging tests fail. The freshness tests error, because the old API had no collector.
- Mutating the fix makes specific tests fail:

| Mutation | Tests that fail |
|---|---|
| Remove the epoch-identity check | 3 |
| Offer the cached TPV instead of this poll's | the reviewed-failure test |
| Move the epoch claim after persistence and drop the poll lock | the concurrency test (8 ≠ 1) |
| Restore the original units | 3 packaging tests |

---

## Known limitations

- **The collector is a thread inside the web process, not a separate service.** Collection no longer depends on page or API traffic, but it still stops when `gps-time-pi.service` is stopped. A separate unprivileged collector service is the planned follow-up (review CHG-011).
- **Legacy samples can't be separated out.** They stay inside the running mean and standard error (see the survey-history section above). The standard error still assumes independent samples; relabeling it and adding block statistics are separate changes (review GPS-009, CHG-006, CHG-019).
- **Epoch ordering is tracked in memory only.** After a web-service restart, the first fresh fix is accepted even if its epoch is older than the last persisted one. It is still a genuinely new receiver report, so no duplicate evidence can arise.
- **gpsd leap-second timestamps** (`…:60Z`) are rejected as invalid. That skips at most one candidate at a leap second.
- **Survey persistence is unchanged:** batched writes at most every 15 min, and `atexit` doesn't run on SIGTERM (review GPS-013).
- **`scripts/logsync.sh flush` still exits non-zero** when no RAM log exists yet. That is harmless but shows as a failed oneshot; it's left for the persistence redesign (review CHG-013).
- **The installer and systemd behavior haven't been executed on a Raspberry Pi or a systemd host.** The package tests check the artifacts statically and structurally only.
- **The ZIP/tar are not yet byte-reproducible.** Only modes and ownership are normalized (review CHG-015).
- `gps_time_pi/templates/index.html` is an unused duplicate of the pre-change `legacy.html` and was left untouched.
