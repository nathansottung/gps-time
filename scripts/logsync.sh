#!/bin/bash
# RAM-log sync: chrony writes its tracking log to tmpfs (/run/chrony-log)
# to spare the SD card; this script restores it at boot and flushes it to
# disk hourly and at shutdown.
RAM=/run/chrony-log
DISK=/var/log/chrony
case "$1" in
  restore)
    mkdir -p "$RAM" "$DISK"
    chown _chrony:_chrony "$RAM" 2>/dev/null || true
    [ -f "$DISK/tracking.log" ] && cp -p "$DISK/tracking.log" "$RAM/" || true
    ;;
  flush)
    mkdir -p "$DISK"
    [ -f "$RAM/tracking.log" ] && cp -p "$RAM/tracking.log" "$DISK/" && sync
    ;;
  *) echo "usage: $0 restore|flush"; exit 1;;
esac
