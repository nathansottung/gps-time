#!/bin/bash
# GPS Time Pi installer — run on the Pi from the repo root: sudo bash install.sh
set -e
DEST=/opt/gps-time-pi
EPH_URL="https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp"
EPH=$DEST/gps_time_pi/data/de440s.bsp

VENV=$DEST/venv

echo "== Installing Python dependencies (venv: $VENV) =="
# Debian Bookworm's system Python is externally managed (PEP 668): pip may not
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
cp -r gps_time_pi $DEST/
[ -f $DEST/config.json ] || echo '{}' > $DEST/config.json

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

echo "== Enabling chrony tracking log (RAM-backed) for the History page =="
grep -q "^log tracking" /etc/chrony/chrony.conf || echo "log tracking" >> /etc/chrony/chrony.conf
if grep -q "^logdir" /etc/chrony/chrony.conf; then
  sed -i 's#^logdir.*#logdir /run/chrony-log#' /etc/chrony/chrony.conf
else
  echo "logdir /run/chrony-log" >> /etc/chrony/chrony.conf
fi
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
for f in config.json config.json.prev dashboard.json timing-events.json custom.css; do
  if [ -f "$DEST/$f" ]; then chown gps-time:gps-time "$DEST/$f"; fi
done

echo "== polkit rule: the service may restart chrony/gpsd/itself, flush logs, reboot =="
install -d -m 0755 /etc/polkit-1/rules.d
install -m 0644 system/50-gps-time-pi.rules /etc/polkit-1/rules.d/50-gps-time-pi.rules
# Emergency rollback drop-in (root service), kept on the station; not enabled.
install -D -m 0644 system/gps-time-pi-root-rollback.conf "$DEST/rollback/gps-time-pi-root-rollback.conf"

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

echo "== Installing service =="
cp gps-time-pi.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable gps-time-pi
systemctl restart gps-time-pi
echo "Done. Open http://$(hostname -I | awk '{print $1}')/"
