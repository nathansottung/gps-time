#!/bin/bash
# Keep Linux's DVB-T TV driver off RTL-SDR dongles (run by sdr-stack.sh and websdr.sh).
#
#   bash scripts/rtl-dvb-blacklist.sh [root] [proc-modules]
#
# A plugged-in RTL2832U dongle is claimed by dvb_usb_rtl28xxu (with rtl2832 and rtl2832_sdr),
# and SDR software then can't open it. This writes /etc/modprobe.d/gps-time-rtl-sdr.conf, so
# the driver stays off from the next boot whether or not Debian's rtl-sdr package (which has a
# blacklist of its own) is installed, and unloads it now if it's loaded.
#
# Only these four modules are named. Shared modules (dvb_core, videodev, regmap_i2c, which an
# RTC driver may use) are never unloaded by name. Nothing in /boot or the initramfs changes.
# Arguments, for tests: a prefix for the file written, and the /proc/modules to read.
set -u
ROOT="${1-}"
PROC_MODULES="${2:-/proc/modules}"
CONF="$ROOT/etc/modprobe.d/gps-time-rtl-sdr.conf"
MODULES="rtl2832_sdr dvb_usb_rtl28xxu rtl2832 rtl2830"

install -d -m 0755 "$(dirname "$CONF")"
{
  echo "# Written by gps-time-pi (scripts/rtl-dvb-blacklist.sh): the DVB-T driver must not claim RTL-SDRs."
  echo "# Remove this file and reboot to let it claim them again."
  for m in $MODULES; do echo "blacklist $m"; done
} > "$CONF.tmp" && chmod 0644 "$CONF.tmp" && mv -f "$CONF.tmp" "$CONF" \
  || { rm -f "$CONF.tmp"; echo "DVB-T driver: could not write $CONF." >&2; exit 1; }
echo "DVB-T driver: blacklisted from the next boot ($CONF)."

loaded=""
for m in $MODULES; do
  grep -q "^$m " "$PROC_MODULES" 2>/dev/null && loaded="$loaded $m"
done
if [ -z "$loaded" ]; then
  echo "DVB-T driver: not loaded now."
  exit 0
fi
# rtl2832_sdr first: it uses rtl2832, and dvb_usb_rtl28xxu holds both.
failed=""
for m in $loaded; do
  modprobe -r "$m" 2>/dev/null || failed="$failed $m"
done
if [ -n "$failed" ]; then
  echo "DVB-T driver: could not unload:$failed (a dongle may be in use). Reboot before using the SDRs."
else
  echo "DVB-T driver: unloaded now:$loaded."
fi
exit 0
