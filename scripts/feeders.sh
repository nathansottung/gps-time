#!/bin/bash
# Opt-in ADS-B feeders (docs/deploy/feeders.md). Run by install.sh:
#   GTP_FEEDERS=1               install feeder support: Beast on 127.0.0.1:30005 from readsb, and a
#                               feeder unit per aggregator, none running until turned on in
#                               Administration (admin token and a typed confirmation)
#   GTP_FEEDERS_PIAWARE=1       also FlightAware's PiAware, from FlightAware's apt repository
#   GTP_FEEDERS_CUSTOM=host:port  also one aggregator of the owner's own ("custom")
#   GTP_FEEDERS=0               stop and remove the feeder units and drop-ins (packages, UUIDs kept)
#   (unset)                     change nothing
#
# Needs the SDR stack's readsb (GTP_SDR=1 with a 1090 MHz serial). readsb itself still reaches no
# outside host; only the feeder units and PiAware do. No feeder is given the station's position.
# PiAware is set to read 127.0.0.1:30005, never gpsd, with no automatic updates and MLAT off
# (MLAT is a separate opt-in in Administration, refused in hidden privacy mode).
set -u
ROOT="${GTP_FEEDERS_TEST_ROOT-}"            # tests only: a prefix for every path written
UNITS="$ROOT/etc/systemd/system"
CONF="$ROOT/etc/gps-time-feeders"
FLAGS="$ROOT/opt/gps-time-pi/feeders"
LIB="$ROOT/usr/local/lib/gps-time-sdr"
READSB_DROPIN="$UNITS/gps-time-readsb.service.d/gps-time-feed.conf"
PIAWARE_DROPIN="$UNITS/piaware.service.d/gps-time.conf"
KEYRING="$ROOT/usr/share/keyrings/gps-time-flightaware.gpg"
SOURCES="$ROOT/etc/apt/sources.list.d/gps-time-flightaware.list"
OS_RELEASE="${GTP_FEEDERS_OS_RELEASE:-/etc/os-release}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/system"
FA_REPO="https://apt.svc.flightaware.com/piaware/release"
# FlightAware ADS-B repository signing key (signs the trixie and bookworm releases): checked 2026-11-04.
FA_KEY_FPR="56B6684E138929F4E7CF014BC3B2A470AAD5A173"
# The built-in aggregators: name host port (all take beast_reduce_plus_out on 30004).
CATALOG="adsbfi feed.adsb.fi 30004
airplaneslive feed.airplanes.live 30004
adsbexchange feed1.adsbexchange.com 30004"
WANT="${GTP_FEEDERS-}"

say() { echo "Feeders: $*"; }
fail() { say "$*; nothing changed." >&2; exit 1; }

if [ -z "$WANT" ]; then
  if [ -f "$UNITS/gps-time-feed@.service" ]; then say "kept as they are (GTP_FEEDERS is not set)."
  else say "not installed. To add them: sudo GTP_FEEDERS=1 bash install.sh (docs/deploy/feeders.md)"; fi
  exit 0
fi

case "$WANT" in
  0|off|no|false)
    for f in "$CONF"/*.conf; do
      [ -e "$f" ] || continue
      n="$(basename "$f" .conf)"
      systemctl disable --now "gps-time-feed@$n.service" >/dev/null 2>&1 || true
    done
    rm -f "$UNITS/gps-time-feed@.service" "$READSB_DROPIN" "$PIAWARE_DROPIN" "$LIB/piaware-settings" "$FLAGS"/*.on "$FLAGS"/*.mlat
    rmdir "$(dirname "$READSB_DROPIN")" "$(dirname "$PIAWARE_DROPIN")" 2>/dev/null || true
    systemctl disable --now piaware.service >/dev/null 2>&1 || true
    systemctl daemon-reload
    systemctl try-restart gps-time-readsb.service >/dev/null 2>&1 || true
    say "feeder units, drop-ins and the owner's on-switches removed; readsb is back to no network. Packages, $CONF (the feeder UUIDs) and the FlightAware repository are kept."
    exit 0 ;;
  1|on|yes|true) ;;
  *) fail "GTP_FEEDERS must be 1 or 0, not '$WANT'" ;;
esac

[ -f "$UNITS/gps-time-readsb.service" ] || fail "the feeders read readsb, and gps-time-readsb.service isn't installed (GTP_SDR=1 with GTP_SDR_1090_SERIAL)"
CUSTOM="${GTP_FEEDERS_CUSTOM-}"
if [ -n "$CUSTOM" ]; then
  [[ "$CUSTOM" =~ ^[A-Za-z0-9.-]{1,253}:[0-9]{1,5}$ ]] || fail "GTP_FEEDERS_CUSTOM='$CUSTOM' must be host:port"
  CATALOG="$CATALOG
custom ${CUSTOM%:*} ${CUSTOM##*:}"
fi
PIAWARE="${GTP_FEEDERS_PIAWARE-}"
case "$PIAWARE" in ""|0|1) ;; *) fail "GTP_FEEDERS_PIAWARE must be 1 or 0, not '$PIAWARE'" ;; esac

echo "== Feeders: readsb's Beast output on 127.0.0.1:30005 =="
install -d -m 0755 "$(dirname "$READSB_DROPIN")" "$UNITS" "$LIB"
install -m 0644 "$SRC/gps-time-readsb-feed.conf" "$READSB_DROPIN"
install -m 0644 "$SRC/gps-time-feed@.service" "$UNITS/gps-time-feed@.service"
install -d -m 0755 "$CONF"
install -d -m 0750 "$FLAGS"
chown gps-time:gps-time "$FLAGS" 2>/dev/null || true

echo "== Feeders: aggregators (installed, off until turned on in Administration) =="
printf '%s\n' "$CATALOG" | while read -r name host port; do
  [ -n "$name" ] || continue
  {
    echo "# Written by scripts/feeders.sh: where gps-time-feed@$name sends readsb's Beast output."
    echo "FEED_HOST=$host"
    echo "FEED_PORT=$port"
  } > "$CONF/$name.conf.tmp" && chmod 0644 "$CONF/$name.conf.tmp" && mv -f "$CONF/$name.conf.tmp" "$CONF/$name.conf"
  # A random feeder UUID per aggregator, made once and kept: it identifies this station's feed there.
  if [ ! -s "$CONF/$name.uuid" ]; then
    u="$(cat /proc/sys/kernel/random/uuid 2>/dev/null)"
    if ! [[ "$u" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
      h="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
      u="${h:0:8}-${h:8:4}-4${h:13:3}-a${h:17:3}-${h:20:12}"
    fi
    [[ "$u" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || { say "$name: could not make a feeder UUID." >&2; continue; }
    echo "$u" > "$CONF/$name.uuid"
    chmod 0644 "$CONF/$name.uuid"
  fi
  say "$name: $host:$port, installed."
done
systemctl daemon-reload
for f in "$CONF"/*.conf; do
  [ -e "$f" ] || continue
  # Enabled so the owner's choice survives a reboot; ConditionPathExists keeps it from running
  # until Administration writes $FLAGS/<name>.on.
  systemctl enable "gps-time-feed@$(basename "$f" .conf).service" >/dev/null 2>&1 || true
done
systemctl try-restart gps-time-readsb.service >/dev/null 2>&1 || true

if [ "$PIAWARE" = 1 ]; then
  echo "== Feeders: PiAware (FlightAware) =="
  CODENAME="$(sed -n 's/^VERSION_CODENAME=//p' "$OS_RELEASE" 2>/dev/null | tr -d '"' | head -n 1)"
  case "$CODENAME" in bookworm|trixie) ;; *) say "PiAware: no FlightAware packages for '${CODENAME:-unknown}'; PiAware skipped." >&2; CODENAME="" ;; esac
  if [ -n "$CODENAME" ]; then
    ARCH="$(dpkg --print-architecture 2>/dev/null || echo arm64)"
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    ok=1
    curl -fsSL --max-time 60 "$FA_REPO/dists/$CODENAME/piaware/binary-$ARCH/Packages" -o "$TMP/Packages" || ok=0
    FILE="$(awk '/^Package: flightaware-apt-repository$/{p=1} p&&/^Filename:/{print $2; exit}' "$TMP/Packages" 2>/dev/null)"
    SUM="$(awk '/^Package: flightaware-apt-repository$/{p=1} p&&/^SHA256:/{print $2; exit}' "$TMP/Packages" 2>/dev/null)"
    [ "$ok" = 1 ] && [ -n "$FILE" ] && curl -fsSL --max-time 60 "$FA_REPO/$FILE" -o "$TMP/repo.deb" || ok=0
    [ "$ok" = 1 ] && [ "$(sha256sum "$TMP/repo.deb" | awk '{print $1}')" = "$SUM" ] || ok=0
    [ "$ok" = 1 ] && dpkg-deb -x "$TMP/repo.deb" "$TMP/x" || ok=0
    RING="$TMP/x/usr/share/keyrings/flightaware-archive-keyring.gpg"
    [ "$ok" = 1 ] && gpg --show-keys --with-colons "$RING" 2>/dev/null | awk -F: '$1 == "fpr" {print $10}' | grep -qx "$FA_KEY_FPR" || ok=0
    if [ "$ok" = 1 ]; then
      install -d -m 0755 "$(dirname "$KEYRING")" "$(dirname "$SOURCES")"
      install -m 0644 "$RING" "$KEYRING"
      echo "deb [signed-by=/usr/share/keyrings/gps-time-flightaware.gpg] $FA_REPO $CODENAME piaware" > "$SOURCES"
      # PiAware's own unit would start at install with its defaults, which read gpsd (the station's
      # exact position) and send it. Masked first; dump1090-fa (a decoder of its own) never runs.
      systemctl mask piaware.service dump1090-fa.service >/dev/null 2>&1 || true
      if apt-get update >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends piaware >/dev/null; then
        install -d -m 0755 "$(dirname "$PIAWARE_DROPIN")"
        install -m 0644 "$SRC/piaware-gps-time.conf" "$PIAWARE_DROPIN"
        install -m 0755 "$SRC/piaware-settings" "$LIB/piaware-settings"
        systemctl unmask piaware.service >/dev/null 2>&1 || true
        systemctl daemon-reload
        systemctl enable piaware.service >/dev/null 2>&1 || true
        say "PiAware: installed, off until turned on in Administration (use-gpsd no, MLAT off)."
      else
        rm -f "$SOURCES"
        say "PiAware: apt-get could not install piaware; the repository entry was taken out again." >&2
      fi
    else
      say "PiAware: FlightAware's repository key could not be fetched or isn't $FA_KEY_FPR; PiAware skipped." >&2
    fi
  fi
fi
say "installed. Turn a feeder on in Administration -> Feeders (admin token and a typed confirmation)."
exit 0
