#!/bin/bash
# Clip recording (docs/deploy/clips.md): the recorder unit, the RAM folder, and where clips go. Run by
# install.sh every time; it installs the unit and the folder, and changes the folder only when asked:
#   GTP_CLIPS_DIR=/mnt/usb/clips    a USB drive or NAS mount, never the SD card's file system
#   GTP_CLIPS_DIR=ram               back to /run/gps-time-clips (the default)
#   GTP_CLIPS_MAX_MB=64             the cap (1..100000 MB; default 64)
# Kept in /etc/default/gps-time-clips. Never touches chrony, gpsd or PPS.
set -u
ROOT="${GTP_CLIPS_TEST_ROOT-}"            # tests only: a prefix for every path written
UNITS="$ROOT/etc/systemd/system"
TMPFILES="$ROOT/etc/tmpfiles.d/gps-time-clips.conf"
DIR_DROPIN="$UNITS/gps-time-clip.service.d/gps-time-dir.conf"
ENVFILE="$ROOT/etc/default/gps-time-clips"
SRC="$(cd "$(dirname "$0")/.." && pwd)/system"
say() { echo "Clips: $*"; }
fail() { say "$*; nothing changed." >&2; exit 1; }
kv() { [ -f "$ENVFILE" ] && sed -n "s/^$1=\\(.*\\)\$/\\1/p" "$ENVFILE" | tail -n 1; }

DIR="${GTP_CLIPS_DIR-}"; [ -z "$DIR" ] && DIR="$(kv GTP_CLIPS_DIR)"
MAX="${GTP_CLIPS_MAX_MB-}"; [ -z "$MAX" ] && MAX="$(kv GTP_CLIPS_MAX_MB)"; [ -z "$MAX" ] && MAX=64
[ "$DIR" = ram ] && DIR=""
[[ "$MAX" =~ ^[0-9]{1,6}$ ]] && [ "$MAX" -ge 1 ] && [ "$MAX" -le 100000 ] || fail "GTP_CLIPS_MAX_MB='$MAX' must be 1..100000"
if [ -n "$DIR" ]; then
  [[ "$DIR" =~ ^/(mnt|media|srv)/[A-Za-z0-9._/-]{1,200}$ ]] && [[ "$DIR" != *..* ]] \
    || fail "GTP_CLIPS_DIR='$DIR' must be a folder under /mnt, /media or /srv (where USB drives and NAS mounts go)"
  [ -d "$ROOT$DIR" ] || fail "$DIR doesn't exist (mount the drive first)"
  # Never the SD card: the folder must be on another file system than /.
  [ "$(stat -c %d "$ROOT$DIR")" != "$(stat -c %d "$ROOT/")" ] || fail "$DIR is on the SD card's file system"
  chown gps-time:gps-time "$ROOT$DIR" 2>/dev/null || true
fi

install -d -m 0755 "$UNITS" "$(dirname "$TMPFILES")" "$(dirname "$ENVFILE")"
install -m 0644 "$SRC/gps-time-clip.service" "$UNITS/gps-time-clip.service"
install -m 0644 "$SRC/gps-time-clips.tmpfiles" "$TMPFILES"
systemd-tmpfiles --create "$TMPFILES" >/dev/null 2>&1 || true
{
  echo "# Written by gps-time-pi install.sh (scripts/clips.sh)."
  [ -n "$DIR" ] && echo "GTP_CLIPS_DIR=$DIR"
  echo "GTP_CLIPS_MAX_MB=$MAX"
} > "$ENVFILE.tmp" && chmod 0644 "$ENVFILE.tmp" && mv -f "$ENVFILE.tmp" "$ENVFILE"
if [ -n "$DIR" ]; then
  install -d -m 0755 "$(dirname "$DIR_DROPIN")"
  printf '[Service]\n# Written by scripts/clips.sh: the one folder the owner named.\nReadWritePaths=%s\n' "$DIR" > "$DIR_DROPIN"
  chmod 0644 "$DIR_DROPIN"
else
  rm -f "$DIR_DROPIN"
  rmdir "$(dirname "$DIR_DROPIN")" 2>/dev/null || true
fi
systemctl daemon-reload >/dev/null 2>&1 || true
say "clips go to ${DIR:-/run/gps-time-clips (RAM)}, capped at $MAX MB. Recording needs rtl_tcp (GTP_SDR=1 with a PPS-role serial)."
exit 0
