# Deployment runbook — what was actually run

The complete command record from this build's deployment, including the
failures and their fixes, so the whole setup can be reproduced or repaired
from VS Code without archaeology. This public copy is a **sanitized example derived from the v1.3.0 deployment record**.
Example values below use Pi address `192.168.1.10`, hostname `ntp`, and user `pi`; substitute your own deployment values.

## 0. System layer (done once, before this app)

Applied on the Pi — exact contents live in `examples/`:

- `/boot/firmware/config.txt` ← `examples/config.txt.snippet`
  (UART on, Bluetooth off, pps-gpio on 18, rv3028 RTC, CPU locked 600 MHz)
- `/etc/default/gpsd` ← `examples/gpsd.default`, then
  `sudo systemctl enable --now gpsd`
- `/etc/chrony/chrony.conf` ← `examples/chrony.conf.snippet` appended
  (NMEA noselect + PPS prefer + fallback pool), then restart chrony
- Reboot after config.txt changes

For different hardware, generate these instead:
`python3 tools/generate_config.py --profile uputronics` (or flags).

## 1. Getting the code onto the Pi

From the workstation, in the folder holding the zip:

```bash
scp gps-time-pi.zip pi@192.168.1.10:~
```

On the Pi:

```bash
cd ~ && unzip -o gps-time-pi.zip
grep -c "RAM-backed" ~/gps-time-pi/install.sh   # must print 1 (right version)
cd ~/gps-time-pi
sudo bash install.sh
sudo systemctl restart gps-time-pi
sleep 3 && curl -s localhost/api | grep -o '"app": "[^"]*"'   # → "app": "1.3.0"
```

`install.sh` does: pip install skyfield; copy app to `/opt/gps-time-pi`;
one-time DE440s download with recorded SHA-256 (verified on reruns); chrony
`log tracking` with `logdir /run/chrony-log` (RAM); install/enable the
logsync + logflush units; restart chrony; install/enable the web service.
Reruns are idempotent.

## 2. Field fixes applied during deployment (now baked into the repo)

**Mars/DE440s:** first almanac load crashed — DE440s carries only the Mars
*barycenter*. Fixed in `astro.py` (`"mars barycenter"`); already in this tree.

**logsync exec bit:** the unzip dropped the execute permission on
`scripts/logsync.sh`, and `cp` over an existing file keeps the destination's
permissions, so chmod-ing the home copy didn't fix `/opt`. Applied on the Pi:

```bash
sudo chmod +x /opt/gps-time-pi/scripts/logsync.sh
sudo sed -i 's#ExecStart=/opt#ExecStart=/bin/bash /opt#; s#ExecStop=/opt#ExecStop=/bin/bash /opt#' \
  /etc/systemd/system/gps-time-pi-logsync.service /etc/systemd/system/gps-time-pi-logflush.service
sudo systemctl daemon-reload
sudo systemctl start gps-time-pi-logsync      # → active (exited) is correct
sudo systemctl restart chrony                 # completes the move to RAM logging
```

This repo's units now invoke via `/bin/bash` and install.sh chmods, so fresh
installs don't need any of that.

## 3. Everyday operation (no SSH normally needed — use /admin)

```bash
sudo systemctl restart gps-time-pi    # restart web app
systemctl status gps-time-pi          # health + recent log
curl -s localhost/api | python3 -m json.tool | head -30
journalctl -u gps-time-pi -e         # app logs if something's wrong
```

Update to a new version = repeat section 1 (scp → unzip -o → install.sh →
restart). Verify with the version curl.

## 4. Network time distribution (home router)

- Clients: in the home router's LAN/DHCP settings, set the **NTP server**
  (DHCP option 42) to `192.168.1.10`. Propagates as
  DHCP leases renew (hours); appears in the `/` clients table.
- The router itself (optional): point its own NTP client at
  `192.168.1.10` as primary, with a public server as secondary.
- Windows (ignores DHCP NTP), admin PowerShell:
  ```powershell
  w32tm /config /manualpeerlist:192.168.1.10 /syncfromflags:manual /update
  Restart-Service w32time
  w32tm /resync
  ```
- macOS: System Settings → Date & Time → time server `192.168.1.10`
  (or `sudo systemsetup -setnetworktimeserver 192.168.1.10`).
- Phones/IoT mostly hardcode vendor NTP; catching them needs a UDP-123
  NAT redirect on the gateway (deferred; see docs/project-history.md).

## 5. Current deployed state & known items

- Stratum 1 on GPS/PPS; survey and history accumulating; RAM logging active
  (verify: /admin → Logging → "RAM (tmpfs)")
- Antenna: intermittent DC-feed fault observed; currently
  holding link (peak SNR ~36 dB — low for an active antenna, consistent
  with a marginal connection). Failure signature and diagnosis chain:
  docs/project-history.md
- Open tune: NMEA refclock offset (~0.035) — cosmetic only
- Verify LAN clients populate after DHCP option 42 propagates
