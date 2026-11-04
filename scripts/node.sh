#!/bin/bash
# SDR node mode: a second Pi carries the SDR load, and the timing Pi reads its feeds
# (docs/deploy/sdr-node.md). Run by install.sh, on either Pi:
#
# On the SDR node (the second Pi):
#   GTP_NODE=1 GTP_NODE_STATION=<station address>
#       chrony becomes a client of the station: one `server <station> prefer` in chrony's sources.d
#       (owner, 2026-11-04: no GNSS or PPS on the node; its timestamps are labelled ntp). The node's
#       rtl_tcp and readsb Beast (when installed with GTP_SDR=1) listen on the LAN for the station's
#       address only. The web SDR (GTP_WEBSDR=1) and the feeders (scripts/feeders.sh) may run here too.
#   GTP_NODE=0      undo: the chrony source and the drop-ins go; chrony reloads its sources
#
# On the station (the timing Pi):
#   GTP_SDR_NODE=<node address>
#       a network-only readsb pulls the node's Beast (port 30005) into /run/readsb/aircraft.json,
#       where reference-adsb reads it, from that address only; the station's own readsb is stopped
#       (they share /run/readsb). The Radio page links to the node's web SDR.
#   GTP_SDR_NODE=none   undo
#
# Addresses are IPv4 or IPv6 literals (systemd's address allow-lists take no names). Never touched:
# gpsd, the PPS line, and the station's chrony.
set -u
ROOT="${GTP_NODE_TEST_ROOT-}"            # tests only: a prefix for every path written
UNITS="$ROOT/etc/systemd/system"
SRC="$(cd "$(dirname "$0")/.." && pwd)/system"
NODE_ENV="$ROOT/etc/default/gps-time-node"
PEER_ENV="$ROOT/etc/default/gps-time-sdr-node"
CHRONY_SOURCES="$ROOT/etc/chrony/sources.d/gps-time-node.sources"
RTL_DROPIN="$UNITS/gps-time-rtl-tcp.service.d/gps-time-node.conf"
READSB_DROPIN="$UNITS/gps-time-readsb.service.d/gps-time-node.conf"
PEER_UNIT="$UNITS/gps-time-readsb-node.service"
MODULES_DROPIN="$UNITS/gps-time-modules.service.d/gps-time-sdr-node.conf"
WANT_NODE="${GTP_NODE-}"
WANT_PEER="${GTP_SDR_NODE-}"

say() { echo "SDR node: $*"; }
fail() { say "$*; nothing changed." >&2; exit 1; }

valid_ip() {
  local ip="$1"
  if [[ "$ip" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]]; then
    for o in "${BASH_REMATCH[@]:1}"; do [ "$o" -le 255 ] || return 1; done
    return 0
  fi
  [[ "$ip" =~ ^[0-9A-Fa-f:]{2,39}$ && "$ip" == *:* ]]
}

# fill <template> <out> <address>: the template with @ADDR@ replaced
fill() {
  install -d -m 0755 "$(dirname "$2")"
  sed "s/@ADDR@/$3/g" "$1" > "$2.tmp" && chmod 0644 "$2.tmp" && mv -f "$2.tmp" "$2"
}

if [ -z "$WANT_NODE" ] && [ -z "$WANT_PEER" ]; then
  if [ -f "$NODE_ENV" ]; then say "this Pi stays an SDR node (GTP_NODE is not set)."
  elif [ -f "$PEER_ENV" ]; then say "the station keeps reading the SDR node (GTP_SDR_NODE is not set)."
  else say "not set up. A second Pi as SDR node: docs/deploy/sdr-node.md"; fi
  exit 0
fi

# ── this Pi as an SDR node ───────────────────────────────────────────────────
case "$WANT_NODE" in
  "") ;;
  0|off|no|false)
    rm -f "$CHRONY_SOURCES" "$RTL_DROPIN" "$READSB_DROPIN" "$NODE_ENV"
    rmdir "$(dirname "$RTL_DROPIN")" "$(dirname "$READSB_DROPIN")" 2>/dev/null || true
    systemctl daemon-reload
    chronyc reload sources >/dev/null 2>&1 || true
    systemctl try-restart gps-time-rtl-tcp.service gps-time-readsb.service >/dev/null 2>&1 || true
    say "no longer an SDR node: the station's chrony source and the LAN drop-ins are removed." ;;
  1|on|yes|true)
    STATION="${GTP_NODE_STATION-}"
    [ -z "$STATION" ] && STATION="$(sed -n 's/^GTP_NODE_STATION=//p' "$NODE_ENV" 2>/dev/null | tail -n 1)"
    [ -n "$STATION" ] || fail "GTP_NODE_STATION (the station's address) is needed"
    valid_ip "$STATION" || fail "GTP_NODE_STATION='$STATION' must be an IPv4 or IPv6 address"
    echo "== SDR node: time from the station over NTP =="
    install -d -m 0755 "$(dirname "$NODE_ENV")" "$(dirname "$CHRONY_SOURCES")"
    { echo "# Written by gps-time-pi install.sh (scripts/node.sh): this Pi is an SDR node of the station."
      echo "GTP_NODE_STATION=$STATION"; } > "$NODE_ENV.tmp" && mv -f "$NODE_ENV.tmp" "$NODE_ENV"
    chmod 0644 "$NODE_ENV"
    { echo "# Written by gps-time-pi (scripts/node.sh): this SDR node keeps time from the station."
      echo "# No GNSS or PPS here; timestamps made on this Pi are labelled ntp."
      echo "server $STATION iburst minpoll 4 maxpoll 6 prefer"; } > "$CHRONY_SOURCES.tmp" && mv -f "$CHRONY_SOURCES.tmp" "$CHRONY_SOURCES"
    chmod 0644 "$CHRONY_SOURCES"
    if grep -Eq '^[[:space:]]*sourcedir[[:space:]]+/etc/chrony/sources\.d' "$ROOT/etc/chrony/chrony.conf" 2>/dev/null; then
      chronyc reload sources >/dev/null 2>&1 && say "chrony: the station ($STATION) added as its preferred source." \
        || say "chrony: the source file is written; chrony reads it at its next start."
    else
      say "chrony.conf has no 'sourcedir /etc/chrony/sources.d': add it, or the station won't be used as a source." >&2
    fi
    echo "== SDR node: feeds for the station only =="
    if [ -f "$UNITS/gps-time-rtl-tcp.service" ]; then
      fill "$SRC/gps-time-rtl-tcp-node.conf" "$RTL_DROPIN" "$STATION"
      say "rtl_tcp: listening on port 1234 for $STATION (and this Pi) only."
    fi
    if [ -f "$UNITS/gps-time-readsb.service" ]; then
      fill "$SRC/gps-time-readsb-node.conf" "$READSB_DROPIN" "$STATION"
      say "readsb: Beast on port 30005 for $STATION (and this Pi) only."
    fi
    systemctl daemon-reload
    systemctl try-restart gps-time-rtl-tcp.service gps-time-readsb.service >/dev/null 2>&1 || true ;;
  *) fail "GTP_NODE must be 1 or 0, not '$WANT_NODE'" ;;
esac

# ── the station reading an SDR node ──────────────────────────────────────────
case "$WANT_PEER" in
  "") ;;
  none|0|off)
    systemctl disable --now gps-time-readsb-node.service >/dev/null 2>&1 || true
    rm -f "$PEER_UNIT" "$PEER_ENV" "$MODULES_DROPIN"
    systemctl daemon-reload
    systemctl try-restart gps-time-readsb.service >/dev/null 2>&1 || true
    say "the station no longer reads an SDR node." ;;
  *)
    valid_ip "$WANT_PEER" || fail "GTP_SDR_NODE='$WANT_PEER' must be an IPv4 or IPv6 address (or none)"
    [ -f "$NODE_ENV" ] && fail "this Pi is itself an SDR node (GTP_NODE=1); GTP_SDR_NODE belongs on the station"
    echo "== SDR node: the station reads the node's Beast =="
    install -d -m 0755 "$(dirname "$PEER_ENV")"
    { echo "# Written by gps-time-pi install.sh (scripts/node.sh): the SDR node this station reads."
      echo "GTP_SDR_NODE=$WANT_PEER"; } > "$PEER_ENV.tmp" && mv -f "$PEER_ENV.tmp" "$PEER_ENV"
    chmod 0644 "$PEER_ENV"
    fill "$SRC/gps-time-readsb-node.service" "$PEER_UNIT" "$WANT_PEER"
    # The SDR modules (sdr-pps-marker's rtl_tcp) may reach the node too, and still nothing else.
    install -d -m 0755 "$(dirname "$MODULES_DROPIN")"
    printf '[Service]\n# Written by scripts/node.sh: the SDR modules may reach the SDR node (rtl_tcp on port 1234).\nIPAddressAllow=%s\n' "$WANT_PEER" > "$MODULES_DROPIN"
    chmod 0644 "$MODULES_DROPIN"
    systemctl daemon-reload
    systemctl try-restart gps-time-modules.service >/dev/null 2>&1 || true
    systemctl enable gps-time-readsb-node.service >/dev/null 2>&1 && systemctl restart gps-time-readsb-node.service \
      && say "reading the node's Beast from $WANT_PEER into /run/readsb (the station's own readsb stopped)." \
      || say "gps-time-readsb-node.service did not start (journalctl -u gps-time-readsb-node)." ;;
esac
exit 0
