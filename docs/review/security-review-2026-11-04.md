# Security review, 2026-11-04 (rc.6)

The owner's rc.6 list, item 4: "A fresh security review of everything else; fix High/Critical."

**Scope:** everything but the three rc.6 changes made alongside it: the web SDR open to the LAN (#172), the tar1090 aircraft map (#173) and the admin login page (#174). Those are reviewed in their own PRs and ADR amendments (ADR-0009, ADR-0005).
**Method:** a read-only pass over `main` at `9205a62` (after #172), each finding checked by reading the code path end to end.
**Threat model:** an attacker on the home LAN, or a web page a LAN user visits. Location privacy counts as High: precise coordinates leaking in hidden or rounded mode.

**Result:** no Critical and no unauthenticated state change. Two High, both location leaks, fixed in #175. One Medium was fixed in #171 before rc.5. The rest stay open, listed below.

## High (fixed in #175)

| | Finding | Fix |
|---|---|---|
| H1 | **Clip metadata kept the exact position after the privacy mode changed.** A clip recorded in exact mode carries `gpstime:position` at full precision. `GET /api/clips/file?ext=sigmf-meta` needs no token, so anyone on the LAN could read it after the owner switched to rounded or hidden. | `clips.redacted_meta`: a download goes out at the current mode. In rounded mode the position is cut to 0.1° and 10 m; in hidden mode it is nulled. The signature, which no longer matches, is removed, and a `gpstime:position_note` says why. The file on the drive is unchanged. Test: `tests/test_clips.py` → `test_a_download_follows_the_current_privacy_mode`. |
| H2 | **Airband bookmarks kept the exact site's footprint.** A refresh in exact mode stores each nearby facility with `distance_km` from the exact site, and `GET /api/airband` (no token) returned them whatever the mode. Facility positions are public, so the distances trilaterate the station; the list alone places it within 80 km. | `airband.privacy_changed`, called when the mode is set: hidden deletes the NASR set and leaves OpenWebRX+ the built-ins only; rounded after an exact refresh drops the distances. `status()` applies the same rule to whatever file it finds. Test: `tests/test_airband.py` → `test_a_stricter_mode_withdraws_what_the_refresh_learned`. |

## Medium

- **M1, root trusting files the web service's user can write** (`/opt/gps-time-pi` is group-writable by `gps-time`).
  - **Fixed in #171:** the root `gps-time-websdr-signout.service` runs no Python, and the web SDR installer's Python runs isolated (`-I`).
  - **Open:** `python -m` with `WorkingDirectory=/opt/gps-time-pi` in `gps-time-modules.service` and in `install.sh` (as root); `chown` and `migrate import` following symlinks there.
  - **Who can use it:** someone who already runs code as `gps-time`. A LAN attacker can't do it directly.
  - **Proposed:** keep `/opt/gps-time-pi` root-owned, move the service's state to a subfolder, run root Python with `-P`/`-I`, and use `O_NOFOLLOW`/`chown -h`. This is its own change, because it moves every state file.
- **M2, denial of service from the LAN.**
  - **What:** the web server reads up to 2 MB of POST body before any check, has unlimited threads and no idle timeout, and no `MemoryMax=`/`TasksMax=`. A new `/api/almanac` date costs seconds of CPU.
  - **Effect:** a LAN script could starve the in-process timing poller.
  - **Status:** open. Proposed: `Handler.timeout`, checks before the body is read, a request semaphore, unit caps, and a limit on almanac dates.

## Low (open)

- **L1:** the admin token crosses the LAN in clear (plain HTTP). With the rc.6 login page it crosses once per sign-in; the cookie then goes with every request. TLS would be its own change.
- **L2:** the installers pin the first or any matching key but import every key in the downloaded file into the keyring. Proposed: export only the pinned fingerprint.
- **L3:** the DE440s ephemeris is trust-on-first-use. Proposed: pin its SHA-256.
- **L4:** clip audio and IQ download without a token, by design so far. H1 covers the position; the recordings themselves are the owner's call.
- **L5:** some error answers include exception text, which can name internal paths.
- **L6:** the optional coordinator accepts unlimited join requests. Proposed: a cap on pending joins.

## Checked and found sound

- **Host and Origin checks** block DNS rebinding and cross-site POSTs. The token is compared in constant time, with backoff.
- **Admin actions** are fixed argv lists with no shell. The polkit rule names exact units and verbs, and feeder names are `[a-z0-9]{1,32}`.
- **No path traversal:** the web dist, evidence IDs, clip names, migration's tar entries and module names are all checked.
- **No unsafe deserialization;** no `dangerouslySetInnerHTML`; the CSP is strict.
- **Hidden mode is respected** across `/api`, the almanac, objects, shadow, satellites, time zone, capability, sky obstruction, diagnostics, survey, evidence, oscillator export, `/api/sdr` and gpsd redaction.
- **The web service fetches nothing.**
- **Installer inputs** are validated, and the decoders bind to the loopback.
- **The module sandbox** drops privileges before it imports module code.
- **`config.json` and the station key** are written 0600.
