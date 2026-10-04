# First Pi deploy of the 1.4 line: checklist

For upgrading a working v1.3 station to **v1.4.0-rc.4**. For a newly flashed Pi, use [`fresh-pi-install.md`](fresh-pi-install.md) instead. Work top to bottom and stop at any step that doesn't match what's written.

Nothing in the 1.4 line has run on a Pi yet. This deploy is the first test of the unprivileged service, the polkit rule, the venv installer and the deploy scripts. Background: `docs/development/raspberry-pi-deploy.md`, `docs/releases/v1.4.0-rc.4.md`, ADR-0005.

**What will happen to the station**

- `install.sh` **restarts chrony**. PPS selection takes a few minutes to come back. NTP clients see a fallback source or an unsynchronized server until then. Pick a time when that's acceptable.
- `install.sh` makes sure `chrony.conf` has `log tracking` and `logdir /run/chrony-log`. A v1.3 station already has both, so the file shouldn't change. Nothing else in chrony, gpsd or PPS setup is touched.
- The web service changes from root to the user `gps-time`, and runs from a venv.
- Settings changes and admin actions will need the admin token.
- `/app/` (the new UI) works after the deploy: the bundle ships the built UI. The deploy script builds it on Windows first, so Windows needs Node 22 with corepack (`docs/development/new-machine.md`). The legacy pages work as before.
- The install needs the Internet on the Pi (apt, PyPI or piwheels).

Throughout, PowerShell blocks run on Windows and `sh` blocks run on the Pi. Set these once per PowerShell window, with your own values. **Don't commit them, the backups or the token anywhere in the repository.**

```powershell
$PiHost = '<pi address or hostname>'
$PiUser = '<pi user>'
$Pi = "$PiUser@$PiHost"
```

## 1. SSH key from Windows

The deploy script opens three connections (`ssh`, `scp`, `ssh`). With a key, none of them asks for the Pi password.

- [ ] Check for an existing key. If `id_ed25519.pub` is listed, skip the next step.

  ```powershell
  Get-ChildItem $HOME\.ssh\*.pub
  ```

- [ ] Create a key. A passphrase is recommended.

  ```powershell
  ssh-keygen -t ed25519
  ```

- [ ] Install the public key on the Pi. This asks for the Pi password one last time. On the first connection, ssh shows the Pi's host key fingerprint; compare it with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the Pi's own console if you can.

  ```powershell
  Get-Content $HOME\.ssh\id_ed25519.pub | ssh $Pi "umask 077; mkdir -p ~/.ssh; tr -d '\r' >> ~/.ssh/authorized_keys"
  ```

- [ ] If the key has a passphrase, load it into the agent so the deploy doesn't ask three times. The first line needs an administrator PowerShell, once.

  ```powershell
  Get-Service ssh-agent | Set-Service -StartupType Manual
  Start-Service ssh-agent
  ssh-add $HOME\.ssh\id_ed25519
  ```

- [ ] Test. It must print the Pi's hostname and user with no password prompt.

  ```powershell
  ssh -o BatchMode=yes $Pi "hostname; whoami"
  ```

## 2. Pre-flight on the Pi (read-only)

```powershell
ssh $Pi
```

- [ ] OS and polkit. Expect `bookworm` and polkit **121 or newer**. On an older polkit the rule file is ignored, so admin actions (restart, reboot, log flush) would fail; the rest still works. Decide before continuing.

  ```sh
  grep VERSION_CODENAME /etc/os-release
  pkaction --version
  ```

- [ ] Groups the service unit names. Both lines must print. **If either is missing, stop:** the new service won't start.

  ```sh
  getent group _chrony video
  ```

- [ ] Disk space and Internet. The venv needs roughly 200 MB under `/opt`.

  ```sh
  df -h /opt
  curl -sI https://pypi.org | head -1
  ```

- [ ] Timing is healthy now. Expect `#*` on the PPS refclock, `Stratum : 1`, and `active` twice.

  ```sh
  chronyc -n sources
  chronyc tracking
  systemctl is-active chrony gps-time-pi
  ```

- [ ] Note whether sudo asks for a password (`sudo -k; sudo true`). If it does, the deploy will prompt for it once.

## 3. Backups

Still on the Pi. Everything goes into one directory in your home.

- [ ] Take the backup.

  ```sh
  B=~/gps-time-backup-$(date +%Y%m%d-%H%M%S); mkdir -m 700 "$B"; echo "$B"
  # the current install: code, config.json (survey, settings), ephemeris
  sudo tar -czf "$B/opt-gps-time-pi.tar.gz" -C /opt gps-time-pi
  sudo cp -a /opt/gps-time-pi/config.json "$B/config.json"
  # timing and system configuration
  sudo cp -a /etc/chrony/chrony.conf "$B/chrony.conf"
  # config.txt is /boot/firmware/config.txt on Bookworm, /boot/config.txt before
  (cd / && sudo tar -czf "$B/system-config.tar.gz" etc/chrony etc/default/gpsd etc/systemd/system/gps-time-pi* \
     $(ls boot/firmware/config.txt boot/config.txt 2>/dev/null | head -1))
  # state before the deploy, to compare afterwards
  chronyc -n sources > "$B/before-sources.txt"; chronyc tracking > "$B/before-tracking.txt"
  curl -s localhost/api > "$B/before-api.json"; curl -s localhost/api/survey > "$B/before-survey.json"
  systemctl status gps-time-pi --no-pager > "$B/before-service.txt"
  sudo chown -R "$USER": "$B"; (cd "$B" && sha256sum * > SHA256SUMS)
  ls -l "$B"
  ```

- [ ] Check it: the install archive lists files, and `config.json` isn't empty.

  ```sh
  tar -tzf "$B/opt-gps-time-pi.tar.gz" | head -5
  wc -c "$B/config.json"
  ```

- [ ] Write down the backup directory name, then `exit`.

- [ ] Copy the backup to Windows, **outside the repository**. `config.json` holds the station's real coordinates.

  ```powershell
  New-Item -ItemType Directory -Force $HOME\gps-time-backups | Out-Null
  scp -r "${Pi}:gps-time-backup-*" $HOME\gps-time-backups\
  ```

## 4. Deploy

- [ ] Open a normal PowerShell or Windows Terminal window. It must be an interactive terminal, with no output redirection and not a VS Code task: the admin token is shown on the terminal only, and sudo may need to prompt. Set `$PiHost` and `$PiUser` again if it's a new window.

- [ ] Check out the release with a clean working tree. `git describe` must print exactly `v1.4.0-rc.4`, and `git status` must list nothing.

  ```powershell
  cd <repository folder>
  git fetch --tags
  git checkout v1.4.0-rc.4
  git status --short
  git describe --tags --dirty
  ```

- [ ] Run the deploy.

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost $PiHost -PiUser $PiUser
  ```

  What you should see, in order:

  1. the web UI build (`pnpm install`, `vite build`), then `Built ...gps-time-pi-deploy.tar.gz (SHA-256 ...)`
  2. `gps-time-pi-deploy.tar.gz: OK`, the checksum verified on the Pi
  3. `== Preflight ==` with no "Cannot install" message, then the `install.sh` sections, possibly after a sudo password prompt
  4. `== Admin token ==` followed by the token, **shown once**
  5. `Open http://<pi>/`

- [ ] **Save the token now**, in a password manager. It isn't stored anywhere in readable form.

- [ ] If the script stops with `... failed (exit N); deploy stopped.`, nothing after that step ran. Read the message, don't re-run blindly, and go to section 6 if the station is affected.

- [ ] Go back to the main branch.

  ```powershell
  git checkout main
  ```

## 5. Checks afterward

```powershell
ssh $Pi
```

**Service and user**

- [ ] The service is active, runs as `gps-time`, from the venv.

  ```sh
  systemctl is-active gps-time-pi
  systemctl show gps-time-pi -p User -p Group -p ExecStart --no-pager
  ps -eo user:12,cmd | grep "[g]ps_time_pi.server"
  ```

  Expect `active`, `User=gps-time`, and a process line starting `gps-time` with `/opt/gps-time-pi/venv/bin/python`.

- [ ] The journal has no tracebacks or permission errors.

  ```sh
  journalctl -u gps-time-pi -b --no-pager -n 40
  ```

- [ ] The version is `1.4.0-rc.4`.

  ```sh
  curl -s localhost/api | python3 -c "import sys,json; print(json.load(sys.stdin)['versions']['app'])"
  ```

**polkit**

- [ ] The rule is installed.

  ```sh
  ls -l /etc/polkit-1/rules.d/50-gps-time-pi.rules
  ```

- [ ] An allowed action works: starting the log flush as the service user prints `0`. This copies the RAM log to the SD card once, which is harmless.

  ```sh
  sudo -u gps-time systemctl start gps-time-pi-logflush.service; echo $?
  ```

- [ ] Anything else is refused: this must fail with an authentication or access error and a non-zero code. (If it wrongly succeeded, it would only restart cron.)

  ```sh
  sudo -u gps-time systemctl restart cron.service; echo $?
  ```

**Timing chain**

- [ ] chrony has selected PPS again. Wait a few minutes after the deploy if it hasn't. Expect `#*` on the PPS refclock and `Stratum : 1`, as in `before-sources.txt`.

  ```sh
  chronyc -n sources
  chronyc tracking
  ```

- [ ] The station reports the same thing. Expect a GPS/PPS status once chrony has selected PPS; before that, a fallback source or `ACQUIRING` is correct. No stage that worked before should now be UNKNOWN.

  ```sh
  curl -s localhost/api/timing-chain | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status']['code'], '|', d['status']['banner']); [print(' ', s['id'], s['status']) for s in d.get('stages', [])]"
  curl -s localhost/api/diagnostics | head -40
  ```

- [ ] Values that depend on the new groups are still there: the NTP client list isn't `None` (needs `_chrony`), and the CPU temperature is a number (needs `video`). If either is missing, note it; it's one of the items ADR-0005 lists as unverified. Timing isn't affected.

  ```sh
  curl -s localhost/api | python3 -c "import sys,json; d=json.load(sys.stdin); print('clients:', None if d.get('clients') is None else len(d['clients'])); print('cpu_temp_c:', d.get('cpu_temp_c'))"
  ```

- [ ] The survey survived: `n` is at least what `before-survey.json` shows, and `loaded_from` isn't a `.prev` or corrupt file.

  ```sh
  curl -s localhost/api/survey | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stats')); print(d.get('persistence'))"
  ```

**Token**

- [ ] The token file exists as `root:gps-time`, mode `-rw-r-----`, and the station reports admin as configured (`"admin_configured": true, "authenticated": false`).

  ```sh
  ls -l /opt/gps-time-pi/admin-token.sha256
  curl -s localhost/api/auth
  ```

- [ ] Requests without the token are refused. Expect `405`, then `401`. Don't repeat the second command: three failures from one address start a backoff.

  ```sh
  curl -s -o /dev/null -w "%{http_code}\n" localhost/api/admin
  curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d '{"action":"flush_logs"}' localhost/api/admin
  ```

- [ ] In a browser, open `http://<pi>/admin`, enter the token when asked, and run the log flush. It must succeed. This is the full path: token, unprivileged service, polkit.

**Web pages**

- [ ] The legacy dashboard and the new UI both load: expect `200` twice, then the version the UI was built from.

  ```sh
  curl -s -o /dev/null -w "%{http_code}\n" localhost/
  curl -s -o /dev/null -w "%{http_code}\n" localhost/app/
  curl -s localhost/app/version.txt
  ```

- [ ] In a browser, open `http://<pi>/app/`. The footer shows one version (the UI and the station match), and the banner names the sync source.

**From another machine**

- [ ] The station still serves time. On Windows:

  ```powershell
  w32tm /stripchart /computer:$PiHost /samples:3 /dataonly
  ```

- [ ] Record what you found, including anything that didn't match, so `STATUS.md` and ADR-0005 can be updated from it.

## 6. Rollback

First capture the evidence, whichever level you use:

```sh
journalctl -u gps-time-pi -b --no-pager -n 200 > ~/gps-time-failure.txt
systemctl status gps-time-pi --no-pager >> ~/gps-time-failure.txt
```

If **timing** is wrong (chrony not selecting PPS after 15 minutes), compare the configuration first. The deploy shouldn't have changed it:

```sh
sudo diff /etc/chrony/chrony.conf "$B/chrony.conf" && echo unchanged
```

If it differs, restore it and restart chrony: `sudo cp -a "$B/chrony.conf" /etc/chrony/chrony.conf && sudo systemctl restart chrony`. The web service doesn't discipline the clock, so a web-service problem alone doesn't call for a timing rollback.

**Level 1: root service, new code.** Use this if the service fails to start or values are missing because of the unprivileged user. It keeps the new code and the token checks.

```sh
sudo install -D -m 0644 /opt/gps-time-pi/rollback/gps-time-pi-root-rollback.conf \
     /etc/systemd/system/gps-time-pi.service.d/zz-root-rollback.conf
sudo systemctl daemon-reload && sudo systemctl restart gps-time-pi
systemctl show gps-time-pi -p User        # User= (empty) means root
```

Undo it later with:

```sh
sudo rm /etc/systemd/system/gps-time-pi.service.d/zz-root-rollback.conf
sudo systemctl daemon-reload && sudo systemctl restart gps-time-pi
```

**Level 2: back to the v1.3 install from the backup.** Use this if Level 1 doesn't help. Set `B` to the backup directory from section 3.

```sh
B=~/gps-time-backup-<timestamp>
(cd "$B" && sha256sum -c SHA256SUMS)
sudo systemctl stop gps-time-pi
sudo mv /opt/gps-time-pi /opt/gps-time-pi.failed-$(date +%Y%m%d-%H%M%S)
sudo tar -xzf "$B/opt-gps-time-pi.tar.gz" -C /opt
# the old unit files only; chrony and gpsd configuration are not restored here
sudo tar -xzf "$B/system-config.tar.gz" -C / --wildcards 'etc/systemd/system/gps-time-pi*'
sudo rm -f /etc/polkit-1/rules.d/50-gps-time-pi.rules
sudo rm -rf /etc/systemd/system/gps-time-pi.service.d
sudo systemctl daemon-reload && sudo systemctl restart gps-time-pi
systemctl is-active gps-time-pi
curl -s localhost/api | python3 -c "import sys,json; print(json.load(sys.stdin)['versions']['app'])"
```

- The version should read as it did in `before-api.json`.
- Survey samples collected since the backup are lost; the failed directory still has the newer `config.json` if you want to keep it.
- The `gps-time` user and the venv can stay; v1.3 ignores them and uses the system Python and its skyfield.
- Remove `/opt/gps-time-pi.failed-*` once you no longer need it.
