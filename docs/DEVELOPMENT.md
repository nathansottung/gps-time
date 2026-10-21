# Development setup

This repository is designed to be edited on a normal Windows, macOS, or Linux workstation and deployed to a Raspberry Pi for hardware validation.

## Open in Visual Studio Code

1. Install **Git**, **Python 3**, and **Visual Studio Code**.
2. Extract the repository ZIP to a normal development folder. Do not develop inside the ZIP.
3. In VS Code choose **File → Open Folder…** and select the repository folder (`gps-time`).
4. Install the recommended Python extension when VS Code offers it.
5. Open **Terminal → New Terminal**.
6. Create a development branch before changing code:

   ```bash
   git switch -c dev/foundation-hardening
   ```

   If the folder has not yet been initialized as a Git repository, use the GitHub setup steps below first.

## Local checks

Most of the project uses the Python standard library. The astronomy layer additionally uses Skyfield on the Pi.

Run these safe workstation checks before deployment:

```bash
python -m compileall gps_time_pi tools
python tools/generate_config.py --help
python -m unittest discover -s tests -t . -v
```

Hardware-dependent functions (`gpsd`, `chronyc`, Raspberry Pi diagnostics, systemd administration, PPS, RTC) require the Pi and should be mocked or tested on the Pi rather than assumed to work on a workstation.

## Deploy a development build to the Pi

The current deployment record is in `docs/deployment-runbook.md`. Preserve that file as the historical record of what was actually run.

For development, prefer deploying a branch or a versioned ZIP, then verify the reported application version and timing state before changing the next component.

Do not use the timing dashboard as proof that the Pi's absolute UTC error equals the smallest number displayed. Keep clock correction, reference uncertainty, and client clock verification as separate measurements.

## Recommended branch sequence

1. `fix/foundation-measurement` — stale GPS/survey observations, chrony history semantics, browser timing exchange.
2. `fix/security-boundaries` — read-only default, unprivileged web process, authenticated/restricted administration.
3. `feat/ram-persistence` — bounded RAM buffers, incremental checkpoints, persistence status.
4. `feat/ntp-client-activity` — IP-only NTP requester history and activity view.
5. `feat/device-timing` — optional verified client clock measurements, including amateur-radio computers.
6. `feat/custom-dashboard` — saved layouts and widgets without granting extensions control of the timing core.
7. `feat/environment` — first weather/environment collector using the shared observation model.

Keep each branch small enough that timing behavior can be tested before merging it.

## New desktop workflow (1.4.0-dev)

For the current Windows demo/configuration workflow, use [`development/windows-demo.md`](development/windows-demo.md). The demo uses the production dashboard renderer with sample providers.

Build/deploy instructions are in [`development/raspberry-pi-deploy.md`](development/raspberry-pi-deploy.md).
