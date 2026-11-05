# Start here

This is the GPS Time development bundle: a working GPS/PPS/NTP baseline plus the repository structure and desktop tooling for the broader timing-first platform roadmap.

## Fastest path on Windows / VS Code

1. Extract the ZIP.
2. Open the extracted `gps-time` folder in VS Code.
3. Open a PowerShell terminal.
4. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-demo.ps1
```

The same web UI used on the Pi opens at `http://127.0.0.1:8080/` with sample data (`/` redirects to `/app/`). Build the UI first (`cd web && corepack pnpm run build`); until then `/app/` answers 503 with the build command.

Use **Configure** in the web UI to show or hide pages and Overview cards, and to switch the red night theme. These choices are stored per browser.

Demo configuration lives under `.dev/` and is not committed automatically.

## Build downloadable/deployable archives

```powershell
python tools\build_bundles.py
```

Outputs under `dist/`:

- `gps-time-development.zip`
- `gps-time-pi-deploy.tar.gz`
- `SHA256SUMS.txt`

## Deploy to a Pi

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi
```

## Understand the project before changing core behavior

Read [`docs/README.md`](docs/README.md), then [`docs/roadmap/feature-registry.md`](docs/roadmap/feature-registry.md).

The current release is **v1.4.0** (2026-10-26), the first stable release of the 1.4 line, on the same commit as v1.4.0-rc.11 (`docs/releases/v1.4.0.md`). `/api` and the web UI footer report the version read from the tag. The deployed historical baseline was v1.3.0. Stable means it passed its soak run on one development Pi; the source reviews still have open findings (`docs/STATUS.md`), and it is not a claim of hardened timing appliance status. The latest release candidate is **v1.6.0-rc.8** (2026-11-04, pre-release, `docs/releases/v1.6.0-rc.8.md`): rc.7 with the aircraft stack fixed (readsb's serial required and checked, the tar1090 and skyaware978 maps, two dongles by serial, the web SDR pausing only its dongle's decoder).5 with the web SDR open to the LAN, the live aircraft map, the admin login page and a security review. rc.1 couldn't be installed; its contents are in `docs/releases/v1.6.0-rc.1.md`. It carries all the work merged after v1.4.0, including v1.5.0-rc.1, and has not run on a Pi yet. There is no v1.5.0: v1.5.0-rc.1's soak run was not clean (outages on this development unit), and the owner skipped it.
