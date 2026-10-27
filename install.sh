#!/bin/bash
# GPS Time Pi installer — run on the Pi from the repo root: sudo bash install.sh
set -e
DEST=/opt/gps-time-pi
EPH_URL="https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp"
EPH=$DEST/gps_time_pi/data/de440s.bsp

VENV=$DEST/venv

echo "== Preflight =="
# Stop before changing anything if the station's base isn't there (review
# GPS-020). This script edits chrony.conf and restarts chrony, and the web
# service's unit names the _chrony and video groups, so without chrony it
# would fail partway through. It does not install or configure chrony, gpsd or
# PPS; see docs/deploy/fresh-pi-install.md.
problems=""
[ "$(id -u)" = 0 ] || problems="$problems\n  - not running as root: use sudo bash install.sh"
command -v chronyc >/dev/null 2>&1 || problems="$problems\n  - chrony is not installed (sudo apt-get install -y chrony)"
[ -f /etc/chrony/chrony.conf ] || problems="$problems\n  - /etc/chrony/chrony.conf is missing"
for g in _chrony video; do
  getent group "$g" >/dev/null 2>&1 || problems="$problems\n  - group $g does not exist (the service unit needs it)"
done
if [ -n "$problems" ]; then
  printf "Cannot install:$problems\nNothing was changed.\n" >&2
  exit 1
fi
command -v gpsd >/dev/null 2>&1 || [ -x /usr/sbin/gpsd ] \
  || echo "Warning: gpsd is not installed. The station will report GNSS as UNKNOWN until it is (sudo apt-get install -y gpsd)."
command -v pkaction >/dev/null 2>&1 \
  || echo "Warning: polkit is not installed. Admin actions (restart, reboot, log flush) will fail until it is (sudo apt-get install -y polkitd)."

echo "== Installing Python dependencies (venv: $VENV) =="
# The system Python on Debian 12 (Bookworm, 3.11) and 13 (Trixie, 3.13) is
# externally managed (PEP 668): pip may not
# install into it. The station's dependencies go into a venv instead, so
# apt-managed Python packages are never touched (review GPS-020).
apt-get update >/dev/null
apt-get install -y python3-venv >/dev/null
mkdir -p $DEST
# Recreate the venv if its interpreter no longer runs (e.g. after an OS Python upgrade).
if [ -x "$VENV/bin/python" ] && ! "$VENV/bin/python" -c "import sys" 2>/dev/null; then
  rm -rf "$VENV"
fi
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo "== Copying application to $DEST =="
# The legacy pages were retired after v1.4.0: remove their files from an upgraded
# station (cp -r would leave them behind). Our own code only; nothing else.
rm -rf "$DEST/gps_time_pi/templates" "$DEST/gps_time_pi/static"
rm -f "$DEST/gps_time_pi/dashboard.py" "$DEST/gps_time_pi/data/dashboard.default.json"
cp -r gps_time_pi $DEST/
# JSON schemas for module data (gps_time_pi.modkit); read-only, nothing runs from here.
rm -rf "$DEST/schemas"
cp -r schemas $DEST/
chmod -R a+rX "$DEST/schemas"
[ -f $DEST/config.json ] || echo '{}' > $DEST/config.json

echo "== Web UI (/app/) =="
# The bundle ships the built UI, so the station needs no Node. The old copy is
# removed first: asset file names carry content hashes and would pile up.
if [ -f web/dist/index.html ]; then
  rm -rf "$DEST/web/dist"
  mkdir -p "$DEST/web"
  cp -r web/dist "$DEST/web/"
  echo "Installed web UI $(cat web/dist/version.txt 2>/dev/null || echo '(version unknown)')"
else
  echo "This bundle has no built web UI: /app/ (and /) will return 503; the JSON API under /api still works."
fi

echo "== Ephemeris (JPL DE440s, ~32 MB, one-time download) =="
if [ ! -f "$EPH" ]; then
  curl -L --fail -o "$EPH" "$EPH_URL"
  sha256sum "$EPH" | awk '{print $1}' > "$EPH.sha256"
  echo "Downloaded. Recorded checksum: $(cat $EPH.sha256)"
else
  echo -n "Verifying stored ephemeris checksum... "
  if [ -f "$EPH.sha256" ] && [ "$(sha256sum "$EPH" | awk '{print $1}')" = "$(cat $EPH.sha256)" ]; then
    echo "ok"
  else
    echo "MISMATCH — re-download by deleting $EPH and re-running."; exit 1
  fi
fi
# The web service runs as gps-time, not root: whatever root's umask was, the
# code, the venv and the ephemeris must be readable by it (never writable).
chmod -R a+rX "$DEST/gps_time_pi" "$VENV"
[ -d "$DEST/web" ] && chmod -R a+rX "$DEST/web"

echo "== Enabling chrony tracking log (RAM-backed) for the History page =="
grep -q "^log tracking" /etc/chrony/chrony.conf || echo "log tracking" >> /etc/chrony/chrony.conf
if grep -q "^logdir" /etc/chrony/chrony.conf; then
  sed -i 's#^logdir.*#logdir /run/chrony-log#' /etc/chrony/chrony.conf
else
  echo "logdir /run/chrony-log" >> /etc/chrony/chrony.conf
fi

echo "== chrony: no NTP servers from DHCP (the station must not poll itself) =="
# If the router's DHCP names this station as the LAN's NTP server, chrony would
# poll the station's own address and could select it after a PPS loss. This
# comments out `sourcedir /run/chrony-dhcp` only; refclocks and pool/server
# lines are untouched. Skip with: sudo GTP_KEEP_DHCP_NTP=1 bash install.sh
bash scripts/chrony-no-dhcp-sources.sh /etc/chrony/chrony.conf \
  || echo "Warning: could not change /etc/chrony/chrony.conf; chrony may still take NTP servers from DHCP (docs/development/raspberry-pi-deploy.md)."

echo "== chrony: independent references (optional, off unless asked for) =="
# Servers chrony only measures (noselect), for the Timing -> References page.
# Nothing is added unless GTP_INDEPENDENT_REFS is set:
#   sudo GTP_INDEPENDENT_REFS=1 bash install.sh        NIST and USNO
#   sudo GTP_INDEPENDENT_REFS="a b" bash install.sh    your own servers
#   sudo GTP_INDEPENDENT_REFS=0 bash install.sh        remove them again
bash scripts/chrony-independent-refs.sh /etc/chrony/sources.d \
  || echo "Warning: the independent references were not changed (see the message above)."

cp -r scripts $DEST/
# Archives (ZIP in particular) may drop execute bits; set them explicitly.
# Units also invoke logsync.sh via /bin/bash, so either alone is sufficient.
chmod 0755 $DEST/scripts/*.sh
cp system/gps-time-pi-logsync.service system/gps-time-pi-logflush.service system/gps-time-pi-logflush.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gps-time-pi-logsync.service gps-time-pi-logflush.timer
systemctl restart chrony

echo "== Service user and permissions (unprivileged web service) =="
# The web service runs as gps-time (review GPS-014). Code stays root-owned and
# read-only to it; only the state files in $DEST are writable. The sticky bit
# stops the service from renaming or deleting root-owned entries (the code).
id gps-time >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin gps-time
chown root:gps-time "$DEST"
chmod 1775 "$DEST"
for f in config.json config.json.prev timing-events.json; do
  if [ -f "$DEST/$f" ]; then chown gps-time:gps-time "$DEST/$f"; fi
done

echo "== Optional modules: user and service (installed, not enabled) =="
# Modules run as gps-time-mod, which is in no group of the station's, so it can't
# read the config (exact position), the admin token or the station key. The
# supervisor service is installed but NOT enabled: no module runs until the owner
# enables it (docs/modules/README.md).
id gps-time-mod >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin gps-time-mod
install -m 0644 system/gps-time-modules.service /etc/systemd/system/gps-time-modules.service
systemctl daemon-reload

echo "== SDR stack (optional, off unless asked for) =="
# rtl_tcp, readsb (1090 MHz) and dump978 (978 MHz) for the SDR modules, each on the loopback
# address only or with no network. Nothing is installed unless GTP_SDR is set:
#   sudo GTP_SDR=1 GTP_SDR_PPS_SERIAL=... GTP_SDR_1090_SERIAL=... GTP_SDR_978_SERIAL=... bash install.sh
#   sudo GTP_SDR=0 bash install.sh        remove the units again (packages are kept)
# A failure here leaves the station as it was; it never stops the install (docs/deploy/sdr-stack.md).
bash scripts/sdr-stack.sh \
  || echo "Warning: the SDR stack was not changed (see the message above)."

echo "== polkit rule: the service may restart chrony/gpsd/itself, flush logs, reboot =="
# Debian's polkitd package owns this directory and sets its owner and mode.
# Create it only if it is missing; never change an existing one.
[ -d /etc/polkit-1/rules.d ] || install -d -m 0755 /etc/polkit-1/rules.d
install -m 0644 system/50-gps-time-pi.rules /etc/polkit-1/rules.d/50-gps-time-pi.rules
# Emergency rollback drop-in (root service), kept on the station; not enabled.
install -D -m 0644 system/gps-time-pi-root-rollback.conf "$DEST/rollback/gps-time-pi-root-rollback.conf"

echo "== NTP client list helper =="
# chronyd answers `chronyc clients` only over its control socket, which the
# unprivileged web service cannot and must not use. This helper runs as
# _chrony, runs that one command, and publishes the output in /run (RAM).
cp system/gps-time-pi-chrony-clients.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable gps-time-pi-chrony-clients.service
systemctl restart gps-time-pi-chrony-clients.service \
  || echo "Warning: the NTP client list helper did not start; the client list will read UNKNOWN (journalctl -u gps-time-pi-chrony-clients)."

echo "== Admin token =="
if [ ! -f "$DEST/admin-token.sha256" ]; then
  # --tty-only: the token goes to the terminal (/dev/tty) only, never to stdout,
  # so `install.sh | tee install.log` or a captured deploy log never holds it.
  if (cd "$DEST" && python3 -m gps_time_pi.admin_token --tty-only --path "$DEST/admin-token.sha256" --group gps-time); then
    echo "Keep the token shown above: admin actions and settings changes in the web UI need it."
  else
    echo "Admin token not created (no terminal). Admin actions stay disabled until you run, on the station:"
    echo "  cd $DEST && sudo python3 -m gps_time_pi.admin_token --tty-only --path $DEST/admin-token.sha256 --group gps-time"
  fi
  echo "Rotate it any time with the same command."
else
  echo "Existing admin token kept ($DEST/admin-token.sha256)."
fi

echo "== Station key (signs observation files) =="
# Ed25519, made once and never replaced: the station's identity in observation
# files. Private key 0600, owned by gps-time; the module user can't read it.
(cd "$DEST" && "$VENV/bin/python" -m gps_time_pi.station_key --path "$DEST/station-key" generate --owner gps-time)   || echo "Warning: the station key could not be created; observation files will be unsigned."

echo "== Installing service =="
cp gps-time-pi.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable gps-time-pi
systemctl restart gps-time-pi

echo "== Self-check as the service user =="
# Reads what the service reads, as gps-time, and says why astronomy would be
# unavailable (missing or unreadable ephemeris, a broken NumPy/Skyfield).
# A warning only: astronomy never blocks the timing pages.
if command -v runuser >/dev/null 2>&1; then
  (cd "$DEST" && runuser -u gps-time -- "$VENV/bin/python" -c '
from gps_time_pi import astro
s = astro.STATUS
print("Astronomy: available" if s["available"] else "Astronomy: UNAVAILABLE - " + str(s["reason"]))') \
    || echo "Astronomy: self-check could not run as gps-time (see the error above)."
fi
echo "Done. Open http://$(hostname -I | awk '{print $1}')/"
