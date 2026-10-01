#!/bin/bash
# GPS Time Pi installer — run on the Pi from the repo root: sudo bash install.sh
set -e
DEST=/opt/gps-time-pi
EPH_URL="https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp"
EPH=$DEST/gps_time_pi/data/de440s.bsp

echo "== Installing Python dependencies =="
apt-get install -y python3-pip >/dev/null
pip3 install --break-system-packages --quiet skyfield

echo "== Copying application to $DEST =="
mkdir -p $DEST
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
cp system/gps-time-pi-logsync.service system/gps-time-pi-logflush.service system/gps-time-pi-logflush.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gps-time-pi-logsync.service gps-time-pi-logflush.timer
systemctl restart chrony

echo "== Installing service =="
cp gps-time-pi.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gps-time-pi
echo "Done. Open http://$(hostname -I | awk '{print $1}')/"
