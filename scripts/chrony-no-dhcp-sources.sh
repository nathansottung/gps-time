#!/bin/bash
# Stops chrony from using NTP servers handed out by DHCP.
#
# Debian's chrony.conf has `sourcedir /run/chrony-dhcp`. When the router's DHCP
# names this station as the LAN's NTP server (option 42), the station receives
# that too and chrony polls the station's own address. After a PPS loss it can
# select that source and follow itself. This comments the line out; every other
# source (refclocks, pool/server lines, /etc/chrony/sources.d) is left alone.
#
# Run by install.sh, which restarts chrony afterwards. Idempotent. The file as
# it was before the first change is kept next to it as <file>.before-gps-time-pi.
# Usage: chrony-no-dhcp-sources.sh [/etc/chrony/chrony.conf]
# GTP_KEEP_DHCP_NTP=1 leaves the file untouched.
CONF="${1:-/etc/chrony/chrony.conf}"
PATTERN='^[[:space:]]*sourcedir[[:space:]]+/run/chrony-dhcp/?([[:space:]].*)?$'

if [ -n "${GTP_KEEP_DHCP_NTP:-}" ] && [ "${GTP_KEEP_DHCP_NTP}" != "0" ]; then
  echo "GTP_KEEP_DHCP_NTP is set: $CONF is left as it is. chrony may poll this station's own address."
  exit 0
fi
if [ ! -f "$CONF" ]; then
  echo "$CONF not found; nothing changed." >&2
  exit 1
fi
if ! grep -Eq "$PATTERN" "$CONF"; then
  echo "chrony is not using NTP servers from DHCP ($CONF has no active 'sourcedir /run/chrony-dhcp'); nothing changed."
  exit 0
fi
[ -e "$CONF.before-gps-time-pi" ] || cp -p "$CONF" "$CONF.before-gps-time-pi" || exit 1
# The result is checked before it replaces the content; cat (not mv) keeps the
# file's owner and mode.
sed -E "s|$PATTERN|# & # disabled by gps-time-pi: the station must not poll itself|" "$CONF" > "$CONF.gtp-tmp" \
  && cat "$CONF.gtp-tmp" > "$CONF" && rm -f "$CONF.gtp-tmp" || { rm -f "$CONF.gtp-tmp"; exit 1; }
echo "Disabled 'sourcedir /run/chrony-dhcp' in $CONF (original kept as $CONF.before-gps-time-pi)."
echo "chrony no longer takes NTP servers from DHCP. To undo: remove the leading '# ' from that line and restart chrony."
