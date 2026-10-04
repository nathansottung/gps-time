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

The same dashboard code used on the Pi opens at `http://127.0.0.1:8080/` with sample data.

Use **Configure dashboard** to:

- create multiple pages
- show/hide any registered widget on a page
- choose normal/wide card size
- import/export layout JSON

Demo changes live under `.dev/` and are not committed automatically.

When you want a demo layout to become the packaged Pi default:

```powershell
python tools\promote_dashboard.py
```

or use VS Code task **GPS Time: Promote demo layout**.

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

Add `-UseDemoLayout` if you intentionally want to promote `.dev/dashboard.json` before building/deploying.

## Understand the project before changing core behavior

Read [`docs/README.md`](docs/README.md), then [`docs/roadmap/feature-registry.md`](docs/roadmap/feature-registry.md).

The current version is **v1.4.0-rc.6**, a pre-release. `/api` and the web UI footer report the version read from the tag. The deployed historical baseline was v1.3.0. The 2026-09-07 source review still contains unresolved blockers; this bundle is a development starting point, not a claim of stable/hardened timing appliance status.
