#!/bin/bash
# Publishes read-only chronyc reports for the unprivileged web service:
#   chronyc -n clients  -> chrony-clients.txt  (NTP client list)
#   chronyc -n ntpdata  -> chrony-ntpdata.txt  (per-server delay, for independent references)
#
# chronyd answers these only over its Unix socket, and chronyc must create
# its reply socket inside /run/chrony to use it. The web service (user
# gps-time, /run read-only) can't, and must not: that socket controls chronyd,
# including stepping the clock. This helper runs as _chrony
# (gps-time-pi-chrony-clients.service), runs this fixed list of commands, takes
# no input, and writes the output to files in /run (RAM, not the SD card).
# gps_time_pi/chrony.py reads the files and ignores them once they are stale.
OUT_DIR="${RUNTIME_DIRECTORY:-/run/gps-time-pi}"
INTERVAL="${GTP_CLIENTS_INTERVAL_S:-15}"
declare -A last_error
while true; do
  for cmd in clients ntpdata; do
    OUT="$OUT_DIR/chrony-$cmd.txt"
    if out=$(chronyc -n "$cmd" 2>&1); then
      if printf '%s\n' "$out" > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"; then
        last_error[$cmd]=""
      fi
    else
      # No file is better than an old one: the web service then reports UNKNOWN.
      rm -f "$OUT" "$OUT.tmp"
      # Log a failure once, not every interval.
      if [ "$out" != "${last_error[$cmd]}" ]; then
        echo "chronyc -n $cmd failed: $out" >&2
        last_error[$cmd]="$out"
      fi
    fi
  done
  [ -n "${GTP_CLIENTS_ONCE:-}" ] && break
  sleep "$INTERVAL"
done
