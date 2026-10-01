# Development change log

## 2026-09-18 — desktop/demo + roadmap consolidation scaffold

- added configuration-driven multi-page dashboard
- added Windows/Linux demo runner with sample timing/GNSS/solar/NTP-client data
- added `/configure` widget visibility/size editor with gated writes
- added browser HTTP RTT and browser-clock estimate endpoint
- retained legacy instrument page at `/legacy`
- added repo/Pi bundle builder and SCP/SSH deployment helpers
- expanded `/docs/` contract, feature registry, timing/scientific vocabulary and SDR roadmap
- copied professional dashboard concept image into `docs/mockups/` (removed from the repository 2026-10-01; kept locally by the owner)

This change does **not** claim the earlier source-review blockers are resolved.

## 2026-09-27 — CHG-001 + CHG-002 foundation correction (candidate)

- CHG-001: GNSS sampling moved to a background collector thread; `snapshot()` is read-only; survey samples require a fresh, valid, strictly newer receiver epoch; stale fixes are reported with age instead of as live; rejection reasons counted; survey statistics split into fresh-gated vs legacy samples. Existing survey data preserved and marked legacy, not reset.
- CHG-002: logsync units and admin flush invoke the script via `/bin/bash`; `install.sh` sets script permissions; bundle builder writes explicit file modes. Corrects the deployment runbook's earlier claim.
- Added the repository's first automated tests (`tests/`, stdlib `unittest`) and a CI step.
- Details, root causes, limitations: `CHG-001-002-foundation-correction.md`.

Resolves review findings GPS-001 and GPS-010. GPS-002 is partly resolved: collection is now independent of request traffic but not of the web process. Other review findings remain open.

## 2026-10-01 — publication redaction (owner-approved)

- Replaced precise station-like coordinates in docs and the demo fixture with the US Naval Observatory example (38.9217, -77.0669, 92 m MSL; ellipsoidal height ~59 m). A second "moved site" example uses the Washington Monument (38.8895, -77.0353).
- Generalized deployment-specific details: "workstation", "home router", "indoor window antenna", "mid-Atlantic" latitude; removed antenna warranty notes.
- Removed `docs/mockups/professional-dashboard-concept.png` from the repository (kept locally by the owner; provenance unrecorded).
- Values were redacted before the first git commit so they never enter repository history.

## 2026-10-01 — web UI prototype import

- Imported `web/` from `figma-web-prototype.zip` (Figma Make React 19 + Vite + Tailwind v4 prototype, 24 files) unchanged, including `web/guidelines/Guidelines.md`, the UI guidelines referenced by the project rules.
- Root `.gitignore` now excludes `web/node_modules/` and `web/dist/`.
- The prototype uses synthetic demo data and is not yet connected to `gps_time_pi`. Known import-time limitations: `web/vite.config.ts` imports `.figma/make/site.json`, which is not in the archive (builds outside Figma Make will fail until that is addressed); `web/src/index.css` loads Google Fonts over the network (conflicts with offline-first); `web/.gitattributes` declares Git LFS rules.


## 2026-10-01 — web UI made standalone; owner decisions applied

Owner decisions: the React app in `web/` will be ported to become the Pi UI (the CHG-001 edits to the legacy `gps_time_pi` pages stay as they are, no restyle); six provenance labels (observed, calculated, modeled, predicted, inferred, external); fonts self-hosted, weight 700 dropped.

- `web/` builds standalone: Figma Make plugins, `.figma/make/site.json` and the Google Analytics hook removed from `vite.config.ts`; dev/preview bind to 127.0.0.1:5173 (`GTP_WEB_HOST` opts into LAN exposure); Git LFS `.gitattributes` removed.
- Fonts bundled from `@fontsource/inter` and `@fontsource/jetbrains-mono` 5.3.0 (SIL OFL-1.1), weights 300–600; `b`/`strong` mapped to 600. The built UI makes no third-party runtime requests.
- Demo station moved to the US Naval Observatory (38.9217, −77.0669); geoid undulation sign fixed (H = 92 m, N = −33 m, h = 59 m).
- Fractional frequency offset shown as ×10⁻ⁿ (`fmtSci`); drift rates in s⁻¹.
- `ProvenanceType`, design tokens and `Guidelines.md` extended to the six labels; `docs/README.md` rule 2 updated.
- New CI workflow `.github/workflows/web.yml`: frozen-lockfile install, type-check, build, offline and font-weight guards.

The 2026-10-01 import entry's known limitations about `site.json`, Google Fonts and Git LFS are resolved by this entry.

Still open in `web/`:
- Existing tags not yet re-labeled with the new set (e.g. sun times and holdover projections should be `predicted`).
- Tailwind colour classes (`text-slate-*`, `bg-cyan-400`, …) in `GNSS.tsx`, `RadioSDR.tsx`, `Secondary.tsx` and `Timing.tsx`, which the guidelines forbid.
- The demo holdover figures are internally inconsistent: "1 s error in ~1.4 days" doesn't follow from the stated 8.4 × 10⁻⁹ s⁻¹ drift.
- The app isn't yet served by `gps_time_pi`.

## 2026-10-01 — specifications imported

- Added four owner-provided specifications under `docs/specs/` from `gps-time-specs.zip` (SHA-256 `6cf9f938…75ec53`), unchanged: `CHG-PPS-HEALTH-DIAGNOSTICS.md`, `PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md`, `ADDENDUM-SKY-SOLAR-SATELLITE.md`, `TASK-PPS-CHAIN.md`.
- Indexed in `docs/INDEX.md`. Scanned before commit: no secrets, credentials, personal identifiers or coordinates.
- These are requirements, not implemented behavior; implementation status is tracked in the roadmap and change records.

