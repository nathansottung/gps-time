# Public release checklist

## Status

DRAFT, 2026-10-19. The repository is private. Nothing on this list has been run unless it says so. Making the repository public, and the first stable tag, are the owner's decisions; this list is what to check first.

It replaces nothing: [`GITHUB-PUBLISHING.md`](GITHUB-PUBLISHING.md) covers the first import from an archive; [`STATUS.md`](STATUS.md) tracks the release blockers; [`ROADMAP.md`](ROADMAP.md) is the outside reader's page.

## 1. History: nothing private in any commit

Making the repository public publishes every commit, not only `main` as it is today. Check the whole history, all branches and tags.

- [ ] **Secrets.** Run a secret scanner over the full history (for example `gitleaks detect --log-opts="--all"`). Expect no admin tokens, API keys, SSH keys, Wi-Fi or GitHub credentials. Any hit: rotate the secret first, then decide whether to rewrite history.
- [ ] **Coordinates.** Search all of history for decimal coordinates: `git log --all -p | grep -nE '[0-9]{2}\.[0-9]{4,}'`. The only allowed locations are the US Naval Observatory (38.9217, −77.0669) and the Washington Monument. Review finding GPS-024 removed real coordinates from the current docs; older commits may still hold them.
- [ ] **Personal infrastructure.** Search history for LAN addresses, hostnames, usernames, MAC addresses and the board serial hash: `git log --all -p | grep -nE '192\.168\.|10\.[0-9]+\.[0-9]+\.|\.local\b'`. Documentation examples (`192.168.1.50`) are fine; a real station's address is not.
- [ ] **Commit identities.** Every author and committer is a GitHub noreply address. *Checked 2026-10-19: yes (the owner's noreply, Dependabot, GitHub).*
- [ ] **Binary and archive files.** Open every committed archive and image, for example `docs/review/review-evidence-2026-09-07.zip` (5 files: review notes, a probe script and its results). Check them for coordinates and addresses like the text files.
- [ ] **Decision if anything is found:** rewrite history (`git filter-repo`) before publishing, or publish a fresh repository from a clean snapshot. Owner's choice; rewriting changes every commit hash and the PR links in `STATUS.md`.

## 2. Current tree

- [ ] The pre-commit scan from `CLAUDE.md` over the whole tree, not only new content: secrets, coordinates, personal infrastructure.
- [ ] `.gitignore` still excludes `config.json`, `generated/`, `.env*`, logs, `web/dist/` and `gps_time_pi/VERSION`.
- [ ] The dashboard mockup PNG is not in the repository (kept outside on purpose).
- [ ] The bundle builder doesn't sweep in secrets or runtime data (review GPS-022, open: partial).

## 3. Release blockers (from `STATUS.md`)

`docs/README.md` says: no stable public release until the measurement-freshness, chrony-history semantics, persistence and administrative-security items are closed or dispositioned.

- [x] chrony history semantics and the honest ± (GPS-003, GPS-007). Done in #93.
- [ ] Second soak run on the Pi, then v1.4.0. Open.
- [ ] Each remaining open review finding closed, or listed in the release notes as a known limitation. 16 were open on 2026-10-19, including unescaped `innerHTML` in the legacy view (GPS-016) and resource limits (GPS-018).
- [ ] Security items verified on a Pi, not only in tests: admin token, Host/Origin checks, unprivileged service (GPS-014, GPS-017).

## 4. Licensing and provenance

- [ ] `LICENSE` (MIT) is correct for project-authored code.
- [ ] Third-party data and code are listed with their licenses: the JPL ephemeris (`de440s.bsp`, downloaded, not committed), TLE sources, the leap-second and UT1 files, `tzfpy` zone data, fonts (`@fontsource`), Python and npm dependencies (review GPS-023, open).
- [ ] No claims in the docs that the project can't support (review GPS-026: extension docs overclaim accuracy, open).
- [ ] `licensing/open-source-policy.md` matches what is shipped.

## 5. Documentation for outside readers

- [ ] `README.md` reads correctly to someone who has never seen the project: vision, status, how to run the demo, hardware, license.
- [ ] `docs/ROADMAP.md` counts and statuses match `STATUS.md` on the release date.
- [ ] `START-HERE.md` and the deploy checklists target the release being published.
- [ ] Doc contradictions and stale pages fixed or marked historical (review GPS-025, open).
- [ ] A screenshot for the README, taken in screenshot mode (`/app/`, Alt+Shift+S) with location privacy set to rounded or hidden. Check it by eye: no coordinates, heights, client addresses or hostname.

## 6. Repository settings (GitHub)

- [ ] Branch protection on `main`: pull requests required, CI checks required, no force pushes.
- [ ] Private vulnerability reporting enabled (`SECURITY.md` points to it).
- [ ] Dependabot and secret-scanning alerts on.
- [ ] Description and topics (`raspberry-pi`, `ntp`, `chrony`, `gps`, `pps`, `gnss`, `ham-radio`).
- [ ] Issue templates (`.github/ISSUE_TEMPLATE/`) don't ask reporters for exact coordinates or public IP addresses.
- [ ] Decide whether the Discussions and Wiki tabs are on.

## 7. The release itself

- [ ] Annotated tag on the release PR's merge commit; GitHub release with the notes from `docs/releases/`.
- [ ] Release bundles attached to the GitHub release, built from the tag; not committed.
- [ ] The repository is made public only after sections 1–6 are ticked or dispositioned. Owner's step.
