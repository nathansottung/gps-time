# Build and deploy to Raspberry Pi

## Build archives

From Windows/VS Code:

```powershell
python tools\build_bundles.py
```

Outputs:

- `dist/gps-time-development.zip` — full development/repo archive
- `dist/gps-time-pi-deploy.tar.gz` — deployment-oriented archive
- `dist/SHA256SUMS.txt`

## One-command-ish deployment

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi
```

This builds, uploads with `scp`, extracts over SSH and runs `sudo bash install.sh`.

Bash equivalent:

```bash
./scripts/deploy-to-pi.sh 192.168.1.50 pi
```

## Important

The current installer is still based on the historical v1.3 deployment model and may use Internet access at install time for Python dependencies/JPL ephemeris. Runtime offline operation is a design goal; a future offline dependency/data bundle remains planned.

The hardware/gpsd/chrony configuration remains installation-specific. Generate and review it with `tools/generate_config.py` before applying it.

To deploy the current `.dev/dashboard.json` intentionally:

```powershell
.\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi -UseDemoLayout
```

Without `-UseDemoLayout`, local demo experiments are not promoted into the deployment archive.
