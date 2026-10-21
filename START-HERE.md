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

The current version is **v1.4.0-rc.11**, a pre-release. `/api` and the web UI footer report the version read from the tag. The deployed historical baseline was v1.3.0. The 2026-09-07 source review still contains unresolved blockers; this bundle is a development starting point, not a claim of stable/hardened timing appliance status.
