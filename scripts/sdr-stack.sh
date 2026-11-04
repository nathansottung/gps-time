#!/bin/bash
# Optional SDR stack for GPS Time's SDR modules (docs/deploy/sdr-stack.md).
#
# Off unless asked for. Run by install.sh:
#   GTP_SDR=1      install or update it
#   GTP_SDR=0      stop and remove the units this script installed (packages are kept)
#   (unset)        change nothing
#
# What GTP_SDR=1 installs, each on the loopback address only or with no network at all:
#   rtl-sdr (Debian)      rtl_tcp for sdr-pps-marker: gps-time-rtl-tcp.service, 127.0.0.1:1234
#   readsb (Debian)       1090 MHz ADS-B: gps-time-readsb.service, no network listeners;
#                         aircraft.json in /run/readsb (RAM) for reference-adsb
#   dump978-fa and        978 MHz UAT, built from FlightAware's source at a pinned commit:
#   skyaware978           gps-time-dump978.service (127.0.0.1:30978, :30979) and
#                         gps-time-skyaware978.service, aircraft.json in /run/skyaware978 (RAM)
#   a drop-in             gps-time-modules.service may reach 127.0.0.1 (rtl_tcp), nothing else
#
# Each role needs its own RTL-SDR, picked by its USB serial (set one with rtl_eeprom -s):
#   GTP_SDR_PPS_SERIAL    the dongle with the injected PPS (sdr-pps-marker)
#   GTP_SDR_1090_SERIAL   the 1090 MHz dongle
#   GTP_SDR_978_SERIAL    the 978 MHz dongle
# A role with no serial is installed but not enabled. Serials are kept in
# /etc/default/gps-time-sdr between runs; GTP_SDR_<ROLE>_SERIAL=none clears one.
#
# Never touched: gpsd, chrony, the PPS line and its overlay. No receiver position is given
# to any decoder, and nothing listens on an outside address.
set -u
ROOT="${GTP_SDR_TEST_ROOT-}"            # tests only: a prefix for every path written
UNITS="$ROOT/etc/systemd/system"
DROPIN="$UNITS/gps-time-modules.service.d/gps-time-sdr.conf"
ENVFILE="$ROOT/etc/default/gps-time-sdr"
LIB="$ROOT/usr/local/lib/gps-time-sdr"
SRC="$(cd "$(dirname "$0")/.." && pwd)/system"
OUR_UNITS="gps-time-rtl-tcp.service gps-time-readsb.service gps-time-dump978.service gps-time-skyaware978.service"
# dump978 v11.1 (github.com/flightaware/dump978); the commit is checked after the clone.
DUMP978_REPO="https://github.com/flightaware/dump978.git"
DUMP978_TAG="v11.1"
DUMP978_COMMIT="f40aa9a0d2d0a0067c0c628b44ba316f7049b8ce"
WANT="${GTP_SDR-}"

say() { echo "SDR stack: $*"; }

if [ -z "$WANT" ]; then
  if [ -f "$UNITS/gps-time-rtl-tcp.service" ] || [ -f "$ENVFILE" ]; then
    say "kept as it is (GTP_SDR is not set)."
  else
    say "not installed. To add it: sudo GTP_SDR=1 GTP_SDR_1090_SERIAL=... bash install.sh (docs/deploy/sdr-stack.md)"
  fi
  exit 0
fi

case "$WANT" in
  0|off|no|false)
    for u in $OUR_UNITS; do
      if [ -f "$UNITS/$u" ]; then
        systemctl disable --now "$u" >/dev/null 2>&1 || true
        rm -f "$UNITS/$u"
      fi
    done
    rm -f "$DROPIN"
    rmdir "$(dirname "$DROPIN")" 2>/dev/null || true
    systemctl daemon-reload
    say "units and the module drop-in removed. Packages, $ENVFILE and $LIB are kept."
    exit 0 ;;
  1|on|yes|true) ;;
  *) say "GTP_SDR must be 1 or 0, not '$WANT'; nothing changed." >&2; exit 1 ;;
esac

# Serials: from the environment, else what an earlier run kept. Letters, digits, - and _ only,
# since they reach the units' command lines.
old() { [ -f "$ENVFILE" ] && sed -n "s/^$1=\\([A-Za-z0-9_-]*\\)\$/\\1/p" "$ENVFILE" | tail -n 1; }
pick() {
  local name="$1" v
  v="${!name-}"
  [ -z "$v" ] && v="$(old "$name")"
  [ "$v" = none ] && v=""
  if [ -n "$v" ] && ! [[ "$v" =~ ^[A-Za-z0-9_-]{1,32}$ ]]; then
    say "$name='$v' is not a serial (letters, digits, - and _, at most 32); nothing changed." >&2
    exit 1
  fi
  printf '%s' "$v"
}
PPS_SERIAL="$(pick GTP_SDR_PPS_SERIAL)" || exit 1
S1090="$(pick GTP_SDR_1090_SERIAL)" || exit 1
S978="$(pick GTP_SDR_978_SERIAL)" || exit 1
for a in "$PPS_SERIAL:$S1090" "$PPS_SERIAL:$S978" "$S1090:$S978"; do
  x="${a%%:*}"; y="${a#*:}"
  if [ -n "$x" ] && [ "$x" = "$y" ]; then
    say "the same serial ($x) is given for two roles; each role needs its own RTL-SDR. Nothing changed." >&2
    exit 1
  fi
done

echo "== SDR stack: packages =="
# readsb's own service would start on install and take the first RTL-SDR it finds, which
# could be the PPS dongle. Mask it first, unless it was already installed and running for
# the owner: then it is left alone and its /run/readsb is used.
OWN_READSB=0
if dpkg -s readsb >/dev/null 2>&1; then
  if systemctl is-enabled --quiet readsb.service 2>/dev/null; then OWN_READSB=1; fi
else
  systemctl mask readsb.service >/dev/null 2>&1 || true
fi
apt-get install -y --no-install-recommends rtl-sdr readsb soapysdr-module-rtlsdr >/dev/null \
  || { say "apt-get could not install rtl-sdr, readsb and soapysdr-module-rtlsdr; nothing else changed." >&2; exit 1; }
# The DVB-T driver claims RTL-SDRs: our own blacklist file (kept when the stack is removed),
# and unloaded now if it's loaded.
bash "$(dirname "$0")/rtl-dvb-blacklist.sh" "$ROOT" || say "the DVB-T driver blacklist could not be written (see above)."

echo "== SDR stack: dump978-fa and skyaware978 ($DUMP978_TAG) =="
HAVE978=0
if [ -x "$LIB/dump978-fa" ] && [ -x "$LIB/skyaware978" ] && [ "$(cat "$LIB/dump978.commit" 2>/dev/null)" = "$DUMP978_COMMIT" ]; then
  say "dump978 $DUMP978_TAG already built."
  HAVE978=1
elif apt-get install -y --no-install-recommends git build-essential libboost-program-options-dev \
       libboost-regex-dev libboost-filesystem-dev libsoapysdr-dev >/dev/null; then
  BUILD="$(mktemp -d)"
  chown nobody "$BUILD" 2>/dev/null || true
  # Fetched and built as nobody, not root; only the two binaries are installed.
  as_nobody() { if [ "$(id -u)" = 0 ]; then runuser -u nobody -- "$@"; else "$@"; fi; }
  if as_nobody git clone --quiet --depth 1 --branch "$DUMP978_TAG" "$DUMP978_REPO" "$BUILD/dump978" \
     && [ "$(as_nobody git -C "$BUILD/dump978" rev-parse HEAD)" = "$DUMP978_COMMIT" ] \
     && as_nobody make -C "$BUILD/dump978" -j2 VERSION="$DUMP978_TAG" dump978-fa skyaware978 \
          CFLAGS="-O2 -g -Ilibs" \
          CXXFLAGS="-std=c++11 -Wno-psabi -O2 -g -Ilibs -DBOOST_ASIO_NO_DEPRECATED" >/dev/null; then
    install -d -m 0755 "$LIB"
    install -m 0755 "$BUILD/dump978/dump978-fa" "$BUILD/dump978/skyaware978" "$LIB/"
    echo "$DUMP978_COMMIT" > "$LIB/dump978.commit"
    HAVE978=1
    say "dump978 $DUMP978_TAG built and installed in $LIB."
  else
    say "dump978 $DUMP978_TAG could not be fetched, verified ($DUMP978_COMMIT) or built; 978 MHz stays off." >&2
  fi
  rm -rf "$BUILD"
else
  say "the build tools for dump978 could not be installed; 978 MHz stays off." >&2
fi

echo "== SDR stack: units (loopback only) =="
install -d -m 0755 "$(dirname "$ENVFILE")"
{
  echo "# Written by gps-time-pi install.sh (scripts/sdr-stack.sh): one RTL-SDR serial per role."
  echo "GTP_SDR_PPS_SERIAL=$PPS_SERIAL"
  echo "GTP_SDR_1090_SERIAL=$S1090"
  echo "GTP_SDR_978_SERIAL=$S978"
} > "$ENVFILE.tmp" && mv -f "$ENVFILE.tmp" "$ENVFILE"
chmod 0644 "$ENVFILE"
install -d -m 0755 "$UNITS" "$(dirname "$DROPIN")"
for u in $OUR_UNITS; do install -m 0644 "$SRC/$u" "$UNITS/$u"; done
install -m 0644 "$SRC/gps-time-modules-sdr.conf" "$DROPIN"
systemctl daemon-reload
# The drop-in applies at the next start; only a supervisor that is already running is restarted.
systemctl try-restart gps-time-modules.service >/dev/null 2>&1 || true

role() {   # role <unit...> -- <serial> <what>
  local units=() serial what
  while [ "$1" != "--" ]; do units+=("$1"); shift; done
  serial="$2"; what="$3"
  if [ -n "$serial" ]; then
    systemctl enable "${units[@]}" >/dev/null 2>&1 && systemctl restart "${units[@]}" \
      && say "$what on the RTL-SDR with serial $serial: enabled." \
      || say "$what: ${units[*]} did not start (journalctl -u ${units[0]})."
  else
    systemctl disable --now "${units[@]}" >/dev/null 2>&1 || true
    say "$what: installed, not enabled (no serial; see docs/deploy/sdr-stack.md)."
  fi
}
role gps-time-rtl-tcp.service -- "$PPS_SERIAL" "rtl_tcp (sdr-pps-marker)"
if [ "$OWN_READSB" = 1 ]; then
  systemctl disable --now gps-time-readsb.service >/dev/null 2>&1 || true
  say "1090 MHz: readsb.service was already enabled before this script; it is left as it is (its /run/readsb is used)."
else
  role gps-time-readsb.service -- "$S1090" "1090 MHz (readsb)"
fi
if [ "$HAVE978" = 1 ]; then
  role gps-time-dump978.service gps-time-skyaware978.service -- "$S978" "978 MHz (dump978-fa, skyaware978)"
else
  systemctl disable --now gps-time-dump978.service gps-time-skyaware978.service >/dev/null 2>&1 || true
fi
# The supervisor runs nothing while the experimental switch is off, so with the SDR stack asked
# for it is enabled: then turning a module on in Administration is all that's left.
systemctl enable gps-time-modules.service >/dev/null 2>&1 && systemctl start gps-time-modules.service   && say "gps-time-modules.service enabled; it runs no module until one is turned on in Administration."   || say "gps-time-modules.service could not be enabled (journalctl -u gps-time-modules)."
say "gps-time-modules.service may reach 127.0.0.1 ($DROPIN)."
exit 0
