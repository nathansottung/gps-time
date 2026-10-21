# Public release checklist

## Status

RUN 2026-10-21 (#100). The repository is still private. Each item says what was done and found. Making the repository public, and the first stable tag, are the owner's decisions; section 8 lists what is left for the owner.

It replaces nothing: [`GITHUB-PUBLISHING.md`](GITHUB-PUBLISHING.md) covers the first import from an archive; [`STATUS.md`](STATUS.md) tracks the release blockers; [`ROADMAP.md`](ROADMAP.md) is the outside reader's page.

## 1. History: nothing private in any commit

Making the repository public publishes every commit, not only `main` as it is today. Check the whole history, all branches and tags.

- [x] **Secrets.** All 1,231 git objects (318 reachable commits on every branch and tag, 35 unreachable local ones, all 122 remote refs including `refs/pull/*`) and all commit and tag messages, scanned with regexes for token formats, private keys, password/PSK/secret/token assignments and high-entropy strings (gitleaks and trufflehog were not installed). **Nothing found**: only test fixtures (`correct-horse-battery-staple-…`), checksums and lockfile hashes.
- [x] **Coordinates.** Decimal, DMS, NMEA sentences and ECEF searched in every object. **No real station coordinates**: the USNO example, the Washington Monument, round synthetic test values, star positions, and once (in the first Figma prototype import, since replaced) the Android emulator's default location, a public landmark. History starts at an import that was redacted before its first commit.
- [x] **Personal infrastructure.** No MAC addresses, real hostnames, usernames, Windows user paths, phone numbers or street addresses; no board serial hash. The demo's NTP client addresses and two example hosts were in `192.168.10.0/24`, the owner's LAN range: moved to RFC 5737 addresses (#99, #100). They stay in history; private addresses alone don't justify a rewrite. A personal folder name was trimmed from `development/new-machine.md`.
- [x] **Commit identities.** Every author and committer on every ref is a GitHub noreply address (the owner's, Dependabot, GitHub). One unreachable local commit has a placeholder identity; it is on no ref and won't be published.
- [x] **Binary and archive files.** The only binary ever committed is `docs/review/review-evidence-2026-09-07.zip` (one version). Its 5 files were extracted and scanned: nothing sensitive. No images, logs, ephemerides, `config.json` or bundles were ever committed.
- [x] **Decision:** **no history rewrite is needed.**
- [x] **GitHub outside git:** all 98 PR bodies and comments, the release notes, issues (none) and Actions artifacts (none) scanned: only the product's default hostname `gpstime.local`.

## 2. Current tree

- [x] The pre-commit scan over the whole tree (part of the history scan above).
- [x] `.gitignore` excludes `config.json`, `generated/`, `.env*`, logs, `web/dist/`, `gps_time_pi/VERSION`, the ephemeris and `*.sha256`.
- [x] The dashboard mockup PNG is not in the repository, and never was.
- [x] The bundle builder archives only files git tracks, and never station state or secrets even without git (review GPS-022, fixed in #100, with tests).

## 3. Release blockers (from `STATUS.md`)

`docs/README.md` says: no stable public release until the measurement-freshness, chrony-history semantics, persistence and administrative-security items are closed or dispositioned.

- [x] chrony history semantics and the honest ± (GPS-003, GPS-007). Done in #93.
- [ ] Soak run of rc.11 on the Pi, then v1.4.0. Running; the check is scheduled for 2026-10-22 (`tools/soak_check.py`).
- [x] Remaining review findings: 8 open after #100: GPS-002, 008, 018, 020, 023 (partial), 025, 028, 032. The legacy removal (#99) closed GPS-016, 027, 029 and the legacy halves of 004 and 009; #100 closes GPS-022 and GPS-026. The main open ones are listed as known limitations in `README.md`; all are in `STATUS.md`.
- [ ] Security items verified on a Pi, not only in tests: admin token, Host/Origin checks, unprivileged service (GPS-014, GPS-017).

## 4. Licensing and provenance

- [x] `LICENSE` is the standard MIT text, "Copyright (c) 2026 Nathan Sottung".
- [x] `THIRD_PARTY_NOTICES.md` lists the bundled datasets, the npm packages shipped in the web UI (MIT, ISC, BSD-3, and the fonts under OFL-1.1, whose texts ship in `third_party/licenses/`), the Python packages installed on a station, and the data a station downloads. The sky datasets were compared with their sources on 2026-10-21 (#101): `stars.json`, `constellations.json` and the named stars are d3-celestial (BSD-3), identical; the Messier list is OpenNGC (CC BY-SA 4.0), now in its own `messier.json` and rebuilt from OpenNGC. Each file keeps its own license, with attribution (`gps_time_pi/data/README.md`, `third_party/licenses/`). GPS-023 closed.
- [x] The five overclaims GPS-026 named (`platform-extensions.md`, `open-lightning-network.md`) are rephrased as "enables, subject to characterization" with a pointer to `sdr/timing-model.md` (#100).
- [x] `licensing/open-source-policy.md` points to the notices file.

## 5. Documentation for outside readers

- [x] `README.md` rewritten for outside readers (#100): what it does, what it won't claim, status and known limitations, demo, Pi setup, hardware, docs, contributing, license. `CONTRIBUTING.md` rewritten.
- [ ] `docs/ROADMAP.md` counts and statuses match `STATUS.md` on the release date.
- [ ] `START-HERE.md` and the deploy checklists target the release being published.
- [ ] Doc contradictions (GPS-025): the named stale items are fixed (runbook "idempotent", "RAM-backed history", the dashboard README, the plugin/localStorage text, the folder name); the maturity vocabulary mismatch between `docs/README.md` and the feature registry remains.
- [x] A screenshot for the README, taken in screenshot mode (`/app/`, Alt+Shift+S) with location privacy set to rounded or hidden. Check it by eye: no coordinates, heights, client addresses or hostname. Done in #104: `docs/screenshots/overview.png`, the Overview page from the desktop demo (synthetic data), 1440 × 900, privacy rounded; checked by eye (hostname masked; no coordinates, heights or client addresses on the page).

## 6. Repository settings (GitHub)

- [ ] Branch protection on `main`: pull requests required, CI checks required, no force pushes.
- [ ] Private vulnerability reporting enabled (`SECURITY.md` points to it).
- [ ] Dependabot and secret-scanning alerts on.
- [ ] Description and topics (`raspberry-pi`, `ntp`, `chrony`, `gps`, `pps`, `gnss`, `ham-radio`).
- [x] Issue templates don't ask for coordinates or addresses; the bug template now explains how to share diagnostics under privacy mode.
- [ ] Decide whether the Discussions and Wiki tabs are on.

## 7. The release itself

- [ ] Annotated tag on the release PR's merge commit; GitHub release with the notes from `docs/releases/`.
- [ ] Release bundles attached to the GitHub release, built from the tag; not committed.
- [ ] The repository is made public only after sections 1–6 are ticked or dispositioned. Owner's step.

## 8. Left for the owner

Nothing below has been done; each is the owner's step.

1. ~~Confirm the dataset sources~~: done in #101 (section 4).
2. **Wait for v1.4.0** (the scheduled soak check), or decide to go public on the pre-release.
3. ~~Take the README screenshot~~: done in #104 (section 5).
4. **Flip the repository to public** (Settings → General → Danger zone).
5. **Right after, in Settings:**
   - branch protection on `main` (pull request, CI checks required, no force pushes; not available while private on the current plan);
   - private vulnerability reporting (`SECURITY.md` refers to it);
   - secret scanning and Dependabot alerts;
   - topics (`raspberry-pi`, `ntp`, `chrony`, `gps`, `pps`, `gnss`, `stratum-1`, `ham-radio`);
   - Discussions and Wiki off unless wanted.
