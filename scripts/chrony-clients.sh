#!/bin/bash
# Publishes `chronyc -n clients` for the unprivileged web service.
#
# chronyd answers `clients` only over its Unix socket, and chronyc must create
# its reply socket inside /run/chrony to use it. The web service (user
# gps-time, /run read-only) can't, and must not: that socket controls chronyd,
# including stepping the clock. This helper runs as _chrony
# (gps-time-pi-chrony-clients.service), runs this one fixed command, takes no
# input, and writes the output to a file in /run (RAM, not the SD card).
# gps_time_pi/chrony.py reads the file and ignores it once it is stale.
OUT_DIR="${RUNTIME_DIRECTORY:-/run/gps-time-pi}"
OUT="$OUT_DIR/chrony-clients.txt"
INTERVAL="${GTP_CLIENTS_INTERVAL_S:-15}"
last_error=""
while true; do
  if out=$(chronyc -n clients 2>&1); then
    if printf '%s\n' "$out" > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"; then
      last_error=""
    fi
  else
    # No file is better than an old one: the web service then reports UNKNOWN.
    rm -f "$OUT" "$OUT.tmp"
    # Log a failure once, not every interval.
    if [ "$out" != "$last_error" ]; then
      echo "chronyc -n clients failed: $out" >&2
      last_error="$out"
    fi
  fi
  [ -n "${GTP_CLIENTS_ONCE:-}" ] && break
  sleep "$INTERVAL"
done
