# Releases and the soak rule

How a GPS Time version becomes a release candidate, and how a candidate becomes a stable release. Release notes for each version are in this folder (`vX.Y.Z-rc.N.md`, `vX.Y.Z.md`).

## Release candidates

1. A release-notes PR adds `vX.Y.Z-rc.N.md` (what's new, the deploy command, what the upgrade changes on the station, what isn't verified on a Pi, open issues, rollback) and updates STATUS, INDEX, the change log and the version lines in README, START-HERE and ROADMAP.
2. It's merged with a merge commit after CI passes.
3. The annotated tag `vX.Y.Z-rc.N` goes on **that merge commit**, with a GitHub **pre-release** using the same notes.

A candidate is never deployed by a tool or an agent. The owner deploys it with the command in its notes.

## The soak rule

A stable tag `vX.Y.Z` goes only on a commit that has run on the station, unchanged, for three days, and passed a read-only check whose criteria were fixed before the run.

**1. The run.** It begins at the service start of the deployed candidate (`systemctl show gps-time-pi -p ActiveEnterTimestamp`) and lasts at least 72 hours. It is valid only if, at the check:
- the station reports exactly the candidate's version (`/opt/gps-time-pi/gps_time_pi/VERSION`, `/api`);
- the service hasn't restarted (`NRestarts=0`, the same `ActiveEnterTimestamp`);
- the Pi hasn't rebooted since before the start (`uptime -s`).

A restart, reboot or redeploy starts a new run; the 72 hours count from the new start.

**2. The check.** `python tools/soak_check.py http://<station> --expect <version>`, once. It does HTTP GETs only (plus read-only SSH for the preconditions) and changes nothing on the station. Its criteria, fixed in #95 and implemented in `evaluate()`:

| Criterion | Clean when |
|---|---|
| version | `/api` reports the expected version |
| runtime | at least 3 days of PPS reads since the service start |
| timing | timing status GPS_PPS now |
| outages | no outage event since the start, except the installer's own: "PPS NOT USED BY CHRONY" with healthy pulses within 5 minutes of the start |
| pulses | missed + unread ≤ 1 in 10,000 reads; late reads ≤ 1 in 1,000; longest gap between reads < 2.5 s |
| rtt | `/api/ping` median < 50 ms and max < 250 ms, idle and while `/api/almanac` is requested |
| stability | ADEV at 1, 10, 100 and 1000 s present; ADEV(1 s) between 1 × 10⁻⁹ and 1 × 10⁻⁵; PPS selected ≥ 99 % of samples; gaps ≤ 0.1 % |

Missing data fails a criterion: UNKNOWN is not clean.

**The record** (from v1.6.0, owner 2026-10-27). After the criteria the tool prints `[REC]` lines. They are **not criteria**: they change no exit status, and nothing is clean or not clean because of them. They record what ran beside the timing core, so a later run can be compared:

| Record | What it says | From |
|---|---|---|
| sdr | each SDR unit's state; its CPU now (two samples `--window` seconds apart, default 30) and since its start; memory; restarts; the total CPU now | `/api/sdr` (cgroup files) |
| cpu | the load averages | `/api/system` |
| usb | the RTL-SDRs on USB, with serial, role, speed and whether the DVB-T driver holds one; the throttled flags, now and since boot (under-voltage among them) | `/api/sdr`, `/api/system` |
| temperature | the SoC temperature at the check | `/api` |
| pps jitter | chrony's standard deviation for the PPS source, the RMS offset, ADEV and TDEV at 1 s | `/api/timing-chain`, `/api`, `/api/stability` |

A station before v1.6.0 has no `/api/sdr`: the record says UNKNOWN there, never zero. Turning any of these into a criterion is a criteria change: the owner's, recorded in the change log before the run it applies to.

**3. The decision.**
- **CLEAN** (exit 0):
  - the stable tag `vX.Y.Z` goes on **the same commit as the soaked candidate** (`git rev-parse vX.Y.Z-rc.N^{commit}`), not on a later `main`;
  - a docs PR adds `vX.Y.Z.md` with the soak numbers, the `[REC]` lines, and the deployment record (`development/raspberry-pi-deploy.md`);
  - a GitHub release (not a pre-release) follows.
- **NOT CLEAN** (exit 1) or unreadable (exit 2): no tag. A docs PR records the run: every criterion with its numbers, the `[REC]` lines, and each outage event with times, durations and the station's classification (an inferred boundary, never a cause). The owner decides what comes next: another run, or a new candidate.

**4. What never happens.**
- The criteria aren't relaxed, reinterpreted or rerun to get a pass.
- Outage detection isn't weakened.
- A run that fails only on outages is reported to the owner, not tagged. On the development unit these can come from its antenna and site (owner, 2026-10-19), and the station can't tell that from a fault.

**5. Who does what.**
- **The owner:** deploys, and changes the criteria. A change is recorded in the change log before the run it applies to.
- **A scheduled task** may run the check and, if clean, tag and merge the docs PR. Nothing else on the station is touched.
- If the app that runs scheduled tasks is closed at the due time, the check runs at the next launch. Any time after the 72 hours is fine; the version and restart preconditions still apply.

Work merged after the candidate (on `main`) isn't in the stable release; it goes into the next candidate.

## Record

| Release | Candidate soaked | Run | Result |
|---|---|---|---|
| v1.4.0 | v1.4.0-rc.11 (`cbd891c`) | 2026-10-19 21:20 UTC → check 2026-10-26 (6 days 17 h) | CLEAN; tagged (#124) |
| — | v1.4.0-rc.8 | 2026-10-04 → 2026-10-19 (14 days 20 h) | not clean: real outages on 2026-10-17; not tagged (#69) |
| — | v1.5.0-rc.1 (`709145f`) | 2026-10-26 18:16:55 UTC → check 2026-10-29 18:30 UTC (3.01 days) | not clean: four PPS outages (8,596 s) and 8,906 missed pulses; v1.5.0 not tagged; the owner decides (#149) |
