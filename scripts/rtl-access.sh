#!/bin/bash
# RTL-SDRs to the plugdev group, read and write (sourced or run by sdr-stack.sh and websdr.sh).
#   bash scripts/rtl-access.sh <root> <system dir>
# Every SDR unit of the station (readsb, dump978-fa, rtl_tcp, OpenWebRX+) runs with
# SupplementaryGroups=plugdev, and libusb needs the dongle's node in /dev/bus/usb open to it.
# Debian's own rule (60-librtlsdr0.rules) is applied only when a dongle is plugged in, so a dongle
# plugged in before the package was installed keeps root-only access: the trigger applies the rule
# to those now. It changes access only, never the kernel driver. Kept when the SDR units are removed.
ROOT="${1-}"
SRC="${2:?system dir}"
RULE="$ROOT/etc/udev/rules.d/61-gps-time-rtl-sdr.rules"
install -d -m 0755 "$(dirname "$RULE")"
install -m 0644 "$SRC/61-gps-time-rtl-sdr.rules" "$RULE"
getent group plugdev >/dev/null 2>&1 || groupadd --system plugdev 2>/dev/null \
  || { echo "RTL-SDR access: there is no plugdev group and it could not be made; the SDR units won't open a dongle." >&2; exit 1; }
if udevadm control --reload-rules >/dev/null 2>&1 \
  && udevadm trigger --subsystem-match=usb --attr-match=idVendor=0bda >/dev/null 2>&1; then
  udevadm settle --timeout=10 >/dev/null 2>&1 || true
  echo "RTL-SDR access: RTL2832U dongles are given to plugdev (read and write), applied to the ones plugged in now."
else
  echo "RTL-SDR access: udev could not apply the rule now; unplug and replug the dongles, or reboot." >&2
  exit 1
fi
exit 0
