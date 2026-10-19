#!/bin/bash
# RAM-log sync for chrony's tracking log.
#
# chrony writes /run/chrony-log/tracking.log (tmpfs) to spare the SD card. This
# script, run as root by systemd:
#   flush    (hourly timer, and at shutdown) appends only the lines written since
#            the last flush to the SD copy, then enforces two size caps;
#   restore  (boot) puts the newest part of the SD copy back into RAM, so the
#            History page has data again.
#
# Caps (bytes; environment overrides for tests):
#   RAM:  when tracking.log passes GTP_LOG_RAM_MAX it becomes tracking.log.1
#         (replacing the previous one) and chrony is told to reopen its logs
#         (chronyc cyclelogs). RAM use stays under twice the cap.
#   SD:   when the SD copy passes GTP_LOG_DISK_MAX it becomes the .prev copy
#         (replacing the previous one). SD use stays under twice the cap.
#
# The SD copy is named station-tracking.txt, not *.log, so Debian's chrony
# logrotate rule (/var/log/chrony/*.log) leaves it alone and keeps no rotated
# full copies of it. Before rc.9 the whole RAM log was copied to
# /var/log/chrony/tracking.log every hour; that old copy and its rotated
# versions are no longer written and age out under logrotate.
RAM="${GTP_LOG_RAM:-/run/chrony-log}"
DISK="${GTP_LOG_DISK:-/var/log/chrony}"
RAM_MAX="${GTP_LOG_RAM_MAX:-8388608}"       # 8 MiB
DISK_MAX="${GTP_LOG_DISK_MAX:-16777216}"    # 16 MiB
CHRONYC="${GTP_CHRONYC:-chronyc}"
LIVE="$RAM/tracking.log"
OUT="$DISK/station-tracking.txt"
STATE="$DISK/.station-tracking.state"       # "<inode of the RAM log> <bytes already on SD>"
OLD="$DISK/tracking.log"                    # the pre-rc.9 full copy, read only for a first restore

append_new() {   # append_new FILE FROM: bytes of FILE after offset FROM go to the SD copy
  local file="$1" from="$2" size
  size=$(stat -c %s "$file") || return 1
  [ "$size" -gt "$from" ] || return 0
  tail -c +$((from + 1)) "$file" | head -c $((size - from)) >> "$OUT" || return 1
}

case "$1" in
  flush)
    mkdir -p "$DISK" || exit 1
    [ -f "$LIVE" ] || exit 0                 # nothing written yet: not an error
    ino=$(stat -c %i "$LIVE") || exit 1
    size=$(stat -c %s "$LIVE") || exit 1
    sino=""; soff=0
    [ -f "$STATE" ] && read -r sino soff < "$STATE"
    # A new file (rotated, or RAM lost at a reboot) or a shorter one starts from 0.
    if [ "$sino" != "$ino" ] || ! [ "$soff" -le "$size" ] 2>/dev/null; then soff=0; fi
    append_new "$LIVE" "$soff" || exit 1
    sync "$OUT" 2>/dev/null || sync
    printf '%s %s\n' "$ino" "$size" > "$STATE.tmp" && mv -f "$STATE.tmp" "$STATE" || exit 1

    if [ "$(stat -c %s "$OUT")" -gt "$DISK_MAX" ]; then
      mv -f "$OUT" "$OUT.prev"
    fi
    if [ "$size" -gt "$RAM_MAX" ]; then
      mv -f "$LIVE" "$RAM/tracking.log.1"
      "$CHRONYC" cyclelogs > /dev/null 2>&1 || true
      # Lines chrony wrote between the flush above and reopening its log went to .1.
      append_new "$RAM/tracking.log.1" "$size"
      sync "$OUT" 2>/dev/null || sync
      rm -f "$STATE"                         # the next file starts at 0
    fi
    ;;
  restore)
    mkdir -p "$RAM" "$DISK"
    chown _chrony:_chrony "$RAM" 2>/dev/null || true
    [ -f "$LIVE" ] && exit 0                 # RAM already has a log (service restart, not a boot)
    src="$OUT"
    [ -f "$src" ] || src="$OLD"              # first boot after the upgrade
    [ -f "$src" ] || exit 0
    # The newest part only (half the RAM cap), from the first whole line.
    if [ "$(stat -c %s "$src")" -gt $((RAM_MAX / 2)) ]; then
      tail -c $((RAM_MAX / 2)) "$src" | sed '1d' > "$LIVE" || exit 1     # drop the cut first line
    else
      cp "$src" "$LIVE" || exit 1
    fi
    chown _chrony:_chrony "$LIVE" 2>/dev/null || true
    # These lines are already on the SD card: don't append them again.
    printf '%s %s\n' "$(stat -c %i "$LIVE")" "$(stat -c %s "$LIVE")" > "$STATE.tmp" && mv -f "$STATE.tmp" "$STATE"
    ;;
  *) echo "usage: $0 restore|flush"; exit 1;;
esac
