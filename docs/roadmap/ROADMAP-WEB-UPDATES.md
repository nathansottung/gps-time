# ROADMAP — Web-Based Updates and Config Upload

## Status

FUTURE, low priority. Do not start until the station has run stably on v1.4.0.

## Goal

Let an operator on the local network update the station software, or upload a new config file, from the web UI, without SSH.

## Requirements

1. **LAN only.** Refuse uploads from addresses outside the configured local subnets, in addition to the existing Host and Origin checks.
2. **Admin token, never the system password.** The web service never sees or handles the Pi's login password.
3. **Signed releases.** The station accepts only bundles signed with the project's release key, whose public half is installed on the station. The admin token alone must not be enough to install code.
4. **Separate privileged installer.** The web service (unprivileged, sandboxed) only verifies and stages the upload. A root-owned systemd unit, triggered through polkit or a path unit, applies it. The web service never runs as root.
5. **Keep the previous release.** Install side by side and switch over, so rollback is one step.
6. **Automatic rollback.** After the restart or reboot, a health check (service up, `/api` answers, version matches) must pass within a set time, or the station reverts to the previous release.
7. **Config upload.** Accept only known config files, validate them against a schema, show a diff before applying, and back up the old file.
8. **Audit log.** Every upload, apply, and rollback is logged to the journal with time, source IP, version, and result. Never log the token.
9. **UI.** An Updates page in the Administration section: current version, upload, signature status, diff or release notes, Apply and reboot, and rollback.

## Out of scope

- Fetching updates from the Internet automatically.
- Updating the OS or apt packages.

## Open questions

- Where the release signing key lives and how it is rotated.
- Whether to use minisign, signify, or GPG for signatures.
