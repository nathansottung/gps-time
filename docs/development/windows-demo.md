# Windows / VS Code demo mode

Demo mode exists so web UI work does not require a Raspberry Pi, gpsd, chrony, GNSS hardware, Skyfield or Internet access.

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

`/` redirects to the web UI at `http://127.0.0.1:8080/app/`. Build it first (`cd web && corepack pnpm run build`); until then `/app/` answers 503 with the build command. It shows the demo banner because the server reports demo mode. See `docs/api/` for the endpoints.

## Demo properties

- same web UI and HTTP API as the Pi
- sample chrony/GNSS/NTP-client data
- sample solar data
- live browser-to-demo-server RTT/clock-estimate probe
- Configure shows or hides pages and Overview cards; the choice is stored in the browser, not on the server
- admin actions are simulated: nothing runs on your machine

## No-dependency goal

The demo server uses the Python standard library. Missing Skyfield does not block it because demo astronomy is fixture data. Real Pi astronomy still uses Skyfield/JPL data.
