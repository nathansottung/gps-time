# Fresh Pi install: checklist

For a newly flashed **Raspberry Pi OS Lite** with nothing on it yet, ending with a station running **v1.4.0-rc.11**. To upgrade a station that already runs v1.3, use [`first-pi-deploy.md`](first-pi-deploy.md) instead; for one that already runs a 1.4 release candidate, use [`upgrade-1.4-station.md`](upgrade-1.4-station.md).

Work top to bottom and stop at any step that doesn't match what's written. **v1.4.0-rc.6 was deployed to the Pi on 2026-10-04.** chrony selected the PPS refclock, the station reported stratum 1, and the system clock offset was about 300 ns (owner's report). The result of each individual check in this list was not recorded, and the steps added since rc.6 (the installer's DHCP change, the newer checks) have not run on a Pi.

**Assumed**

- The SD card was written with Raspberry Pi Imager, with the hostname `gpstime`, your user, SSH enabled, and the network set up. The Pi answers at `gpstime.local`.
- The GNSS board is fitted and its antenna sees the sky.
- The hardware is the project's `uputronics` profile: UART on `/dev/ttyAMA0`, PPS on GPIO 18, an RV3028 RTC. For other hardware, pick the profile or flags from `docs/HARDWARE-PROFILES.md` in step 2 and adjust the device names below.
- Windows has Python, git, and Node 22 with corepack (`docs/development/new-machine.md`).
- The Pi has Internet access during the install (apt, PyPI or piwheels, the JPL ephemeris).

**OS releases.** Written for Raspberry Pi OS on Debian 13 (Trixie, Python 3.13) and Debian 12 (Bookworm, Python 3.11). CI runs the tests on both Python versions and checks that every pinned dependency has an aarch64 wheel for each. The paths and names used below (`/boot/firmware/config.txt`, `/etc/chrony/chrony.conf`, the `_chrony` and `video` groups, `raspi-config nonint`) are the same on both. A 32-bit OS (`uname -m` prints `armv7l`) isn't covered by that wheel check.

PowerShell blocks run on Windows and `sh` blocks run on the Pi. Set these once per PowerShell window. **Don't commit your values, the generated files or the token.**

```powershell
$PiHost = 'gpstime.local'
$PiUser = '<your Pi user>'
$Pi = "$PiUser@$PiHost"
```

## 1. SSH key from Windows

- [ ] If `Get-ChildItem $HOME\.ssh\*.pub` lists no `id_ed25519.pub`, create a key (a passphrase is recommended):

  ```powershell
  ssh-keygen -t ed25519
  ```

- [ ] Install the public key on the Pi. This asks for the Pi password once. If Imager already installed your key, skip it.

  ```powershell
  Get-Content $HOME\.ssh\id_ed25519.pub | ssh $Pi "umask 077; mkdir -p ~/.ssh; tr -d '\r' >> ~/.ssh/authorized_keys"
  ```

- [ ] If the key has a passphrase, load it into the agent. The first line needs an administrator PowerShell, once.

  ```powershell
  Get-Service ssh-agent | Set-Service -StartupType Manual
  Start-Service ssh-agent
  ssh-add $HOME\.ssh\id_ed25519
  ```

- [ ] Test: this prints the hostname and your user with no password prompt.

  ```powershell
  ssh -o BatchMode=yes $Pi "hostname; whoami"
  ```

## 2. Packages, UART and PPS configuration

This step sets up the hardware side only. The chrony refclock lines come later, in step 5: chrony exits at startup if `/dev/pps0` doesn't exist yet, and it doesn't exist until the reboot.

- [ ] On Windows, generate the configuration for your hardware and LAN, and read all four files. Use your own subnet for `--allow`: it decides who may use the station as an NTP server.

  ```powershell
  cd <repository folder>
  python tools/generate_config.py --profile uputronics --allow 192.168.1.0/24
  Get-Content generated\README.txt, generated\config.txt.snippet, generated\gpsd.default, generated\chrony.conf.snippet
  ```

- [ ] Copy them to the Pi and log in.

  ```powershell
  scp -r generated "${Pi}:gps-time-generated"
  ssh $Pi
  ```

- [ ] Record the starting point. Expect `trixie` or `bookworm`, Python 3.13 or 3.11, and `aarch64`.

  ```sh
  grep VERSION_CODENAME /etc/os-release; python3 --version; uname -m
  ```

- [ ] Install the timing packages. Installing chrony replaces systemd-timesyncd.

  ```sh
  sudo apt-get update
  sudo apt-get install -y chrony gpsd gpsd-clients pps-tools polkitd python3-venv
  pkaction --version        # 121 or newer, for the admin actions
  getent group _chrony video
  ```

- [ ] Free the UART for the receiver: no login console on it, hardware on. The last line must print `0`: no serial console left in the kernel command line.

  ```sh
  sudo raspi-config nonint do_serial_cons 1
  sudo raspi-config nonint do_serial_hw 0
  grep -c 'console=serial0\|console=ttyAMA0\|console=ttyS0' /boot/firmware/cmdline.txt
  ```

  If `raspi-config` has no such option, do the same by hand: remove the `console=serial0,115200` word from `/boot/firmware/cmdline.txt`, and run `sudo systemctl disable --now serial-getty@ttyAMA0.service`. `enable_uart=1` comes from the snippet in the next step.

- [ ] Add the overlays to `config.txt`, keeping the original.

  ```sh
  sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.orig
  cat ~/gps-time-generated/config.txt.snippet | sudo tee -a /boot/firmware/config.txt
  ```

- [ ] Configure gpsd. It starts at the reboot.

  ```sh
  sudo cp /etc/default/gpsd /etc/default/gpsd.orig
  sudo cp ~/gps-time-generated/gpsd.default /etc/default/gpsd
  sudo systemctl enable gpsd.socket gpsd.service
  exit
  ```

## 3. Deploy

At this point chrony still has its default configuration (network time only), so the station will come up on a network source. That's expected until step 5.

- [ ] Open a normal PowerShell or Windows Terminal window: interactive, no output redirection, not a VS Code task. The admin token is shown on the terminal only.

- [ ] Check out the release with a clean working tree. `git describe` must print exactly `v1.4.0-rc.11`.

  ```powershell
  cd <repository folder>
  git fetch --tags
  git checkout v1.4.0-rc.11
  git status --short
  git describe --tags --dirty
  ```

- [ ] Run the deploy.

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost $PiHost -PiUser $PiUser
  ```

  What you should see, in order:

  1. the web UI build, then `Built ...gps-time-pi-deploy.tar.gz (SHA-256 ...)`
  2. `gps-time-pi-deploy.tar.gz: OK`, the checksum verified on the Pi
  3. `== Preflight ==` with no "Cannot install" message and no warnings
  4. the install sections, including the venv, the ephemeris download (about 32 MB) and `Installed web UI 1.4.0-rc.11`
  5. `== Admin token ==` followed by the token, **shown once**
  6. `Open http://gpstime.local/`

- [ ] **Save the token now**, in a password manager.

- [ ] If the script stops with `... failed (exit N); deploy stopped.`, or the installer prints `Cannot install:`, nothing after that step ran. Fix what the message names and run the deploy again.

- [ ] Go back to the main branch: `git checkout main`.

## 4. Reboot

- [ ] Reboot so the overlays take effect, and wait for the Pi to come back.

  ```powershell
  ssh $Pi "sudo reboot"
  ```

  ```powershell
  ssh -o BatchMode=yes $Pi "uptime"
  ```

## 5. Checks

```powershell
ssh $Pi
```

**UART and PPS hardware**

- [ ] The devices exist.

  ```sh
  ls -l /dev/ttyAMA0 /dev/pps0
  ```

- [ ] The receiver is talking and has a fix. `cgps` shows satellites and a 2D or 3D fix (it can take several minutes from cold); quit with `q`. The second command prints a few JSON reports.

  ```sh
  cgps -s
  gpspipe -w -n 8 | head -8
  ```

- [ ] PPS pulses arrive once per second. Let five lines print, then press Ctrl+C. The `assert` timestamps should step by 1.000 s.

  ```sh
  sudo ppstest /dev/pps0
  ```

  If there are no pulses, stop: check the antenna, the fix, and the GPIO in `config.txt`. Don't add the chrony refclocks yet.

**chrony: add the GPS/PPS refclocks**

- [ ] Append the generated lines, keeping the original, and restart chrony.

  ```sh
  sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.orig
  cat ~/gps-time-generated/chrony.conf.snippet | sudo tee -a /etc/chrony/chrony.conf
  # keep the tracking log in RAM, as install.sh set it
  sudo sed -i 's#^logdir.*#logdir /run/chrony-log#' /etc/chrony/chrony.conf
  sudo systemctl restart chrony
  systemctl is-active chrony
  ```

  If chrony isn't `active`, read `journalctl -u chrony -n 20 --no-pager`, then restore the original with `sudo cp /etc/chrony/chrony.conf.orig /etc/chrony/chrony.conf && sudo systemctl restart chrony`.

- [ ] chrony writes its tracking log to RAM. The file exists and gains a line every few minutes. If it's missing, read `journalctl -u chrony -n 20 --no-pager`; the History page stays empty without it, but timing isn't affected.

  ```sh
  ls -l /run/chrony-log/
  ```

- [ ] chrony selects PPS. Give it a few minutes. Expect a `#*` line with the name `GPS` (the PPS refclock), a `#` line named `NMEA` that is never selected, and `Stratum : 1` with `Reference ID` showing `GPS`.

  ```sh
  chronyc -n sources
  chronyc tracking
  ```

- [ ] chrony isn't polling the station itself. This prints nothing when all is well:

  ```sh
  for a in $(hostname -I); do chronyc -n sources | grep -F " $a "; done
  ```

  `install.sh` disabled NTP servers from DHCP for this reason (it commented out `sourcedir /run/chrony-dhcp` and kept the original as `chrony.conf.before-gps-time-pi`). Confirm the line is commented:

  ```sh
  grep -n "chrony-dhcp" /etc/chrony/chrony.conf
  ```

  If the loop above still prints a line, the station's address is named as a server somewhere else. Find it with `grep -rn "<that address>" /etc/chrony/`, remove it, and restart chrony. The station must not use itself as a time source. The web pages flag such a source as THIS STATION and never count it as a reference, but chrony still polls it.

**The station**

- [ ] The service is active, runs as `gps-time` from the venv, and reports the version.

  ```sh
  systemctl is-active gps-time-pi
  systemctl show gps-time-pi -p User -p ExecStart --no-pager
  journalctl -u gps-time-pi -b --no-pager -n 40
  curl -s localhost/api | python3 -c "import sys,json; print(json.load(sys.stdin)['versions']['app'])"
  ```

  Expect `active`, `User=gps-time`, `/opt/gps-time-pi/venv/bin/python`, no tracebacks, and `1.4.0-rc.11`.

- [ ] The timing chain agrees with chrony: a GPS/PPS status once chrony has selected PPS, and no stage UNKNOWN that the commands above showed working.

  ```sh
  curl -s localhost/api/timing-chain | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status']['code'], '|', d['status']['banner']); [print(' ', s['id'], s['status']) for s in d.get('stages', [])]"
  ```

- [ ] The NTP client list helper is running, and the values that depend on it and on the `video` group are present: expect `active`, a client count that isn't `None` (it can be `0` on a new station), and a CPU temperature that is a number. If the count is `None`, read `journalctl -u gps-time-pi-chrony-clients -n 20 --no-pager`. Timing isn't affected.

  ```sh
  systemctl is-active gps-time-pi-chrony-clients
  curl -s localhost/api | python3 -c "import sys,json; d=json.load(sys.stdin); print('clients:', None if d.get('clients') is None else len(d['clients'])); print('cpu_temp_c:', d.get('cpu_temp_c'))"
  ```

- [ ] polkit: the allowed action prints `0`; the other one is refused with a non-zero code.

  ```sh
  sudo -u gps-time systemctl start gps-time-pi-logflush.service; echo $?
  sudo -u gps-time systemctl restart cron.service; echo $?
  ```

- [ ] The token is configured, and requests without it are refused: expect `"admin_configured": true`, then `405`, then `401`. Run the last command once only.

  ```sh
  curl -s localhost/api/auth
  curl -s -o /dev/null -w "%{http_code}\n" localhost/api/admin
  curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d '{"action":"flush_logs"}' localhost/api/admin
  ```

- [ ] The almanac computes with the real ephemeris. This path isn't covered by the tests on Python 3.13, so check it here: expect `True` and a sunrise time, not a traceback in the journal. In `hidden` privacy mode it prints `False` with the privacy reason instead.

  ```sh
  curl -s localhost/api/almanac | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('available'), d.get('reason') or d['sun']['events'].get('sunrise'))"
  ```

- [ ] `/` redirects to the web UI and the web UI loads: `302`, then `200`, then the version the UI was built from. (rc.11 itself still serves the legacy dashboard at `/`: `200` there.)

  ```sh
  curl -s -o /dev/null -w "%{http_code}\n" localhost/
  curl -s -o /dev/null -w "%{http_code}\n" localhost/app/
  curl -s localhost/app/version.txt
  ```

**From Windows**

- [ ] Open `http://gpstime.local/app/` in a browser. The banner names the sync source, and the footer shows one version.
- [ ] In the web UI, go to Administration, enter the token, and run the log flush. It must succeed.
- [ ] The station serves time:

  ```powershell
  w32tm /stripchart /computer:$PiHost /samples:3 /dataonly
  ```

**Last**

- [ ] Reboot once more and repeat `chronyc -n sources` and the timing-chain check, to confirm the station comes up by itself. After a boot the status reads `ACQUIRING` until chrony first selects PPS.
- [ ] Record what you found, including the OS and Python versions and anything that didn't match, so `STATUS.md` and ADR-0005 can be updated from it.

## If something goes wrong

- **The service fails or values are missing because of the unprivileged user:** use the Level 1 rollback (root service, same code) in `docs/development/raspberry-pi-deploy.md` → "Rollback".
- **chrony won't start after step 5:** restore `/etc/chrony/chrony.conf.orig` as shown there.
- **No UART or PPS after the reboot:** compare `/boot/firmware/config.txt` with `config.txt.orig`, and check `docs/HARDWARE-PROFILES.md` for your board. A Pi 5 names its UARTs differently from a Pi 4.
- A fresh install has no earlier version to go back to. The worst case is to reflash the card and start again.
