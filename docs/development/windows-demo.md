# Windows / VS Code demo mode

Demo mode exists so dashboard work does not require a Raspberry Pi, gpsd, chrony, GNSS hardware, Skyfield or Internet access.

## Quick start

1. Extract the repo ZIP.
2. In VS Code: **File → Open Folder** and select the extracted `gps-time` folder.
3. Open a PowerShell terminal.
4. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-demo.ps1
```

Or run VS Code task **GPS Time: Run Windows demo**.

The script opens `http://127.0.0.1:8080/` and stores development-only configuration under `.dev/`.

The new web UI is at `http://127.0.0.1:8080/app/` once it has been built (`cd web && corepack pnpm run build`); until then `/app/` answers 503 with the build command. It shows the demo banner because the server reports demo mode. See `docs/api/` for the endpoints.

## Demo properties

- same dashboard HTML/CSS/JS as the Pi
- sample chrony/GNSS/NTP-client data
- sample solar data
- live browser-to-demo-server RTT/clock-estimate probe
- `/configure` saves widget visibility/size flags into `.dev/dashboard.json` (no admin token needed in demo mode)
- admin actions are simulated: nothing runs on your machine

## No-dependency goal

The demo server uses the Python standard library. Missing Skyfield does not block it because demo astronomy is fixture data. Real Pi astronomy still uses Skyfield/JPL data.

## Promoting a tested layout

After configuring `.dev/dashboard.json`, run:

```powershell
python tools\promote_dashboard.py
```

This validates the layout and replaces the packaged default copies in `config/` and `gps_time_pi/data/`. Commit those changes if they are intended to become the project default.
