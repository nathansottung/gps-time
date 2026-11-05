#!/bin/bash
# Optional SDR stack for GPS Time's SDR modules (docs/deploy/sdr-stack.md).
#
# Off unless asked for. Run by install.sh:
#   GTP_SDR=1      install or update it
#   GTP_SDR=0      stop and remove the units this script installed (packages are kept)
#   (unset)        change nothing
#   check          (first argument) check the settings only and change nothing: install.sh runs this
#                  in its preflight, so a bad or missing serial stops the install before anything changes
#
# What GTP_SDR=1 installs, each on the loopback address only or with no network at all:
#   rtl-sdr (Debian)      rtl_tcp for sdr-pps-marker: gps-time-rtl-tcp.service, 127.0.0.1:1234
#   readsb (wiedehopf)    1090 MHz ADS-B, built from source at a pinned tag with RTL-SDR support
#                         (make RTLSDR=yes) into /usr/local/bin/readsb: Debian 13's readsb package has
#                         none (rc.8). gps-time-readsb.service, no network listeners; aircraft.json in
#                         /run/readsb (RAM) for reference-adsb
#   dump978-fa and        978 MHz UAT, built from FlightAware's source at a pinned commit:
#   skyaware978           gps-time-dump978.service (127.0.0.1:30978, :30979) and
#                         gps-time-skyaware978.service, aircraft.json in /run/skyaware978 (RAM)
#   a drop-in             gps-time-modules.service may reach 127.0.0.1 (rtl_tcp), nothing else
#   tar1090 (wiedehopf)   the live aircraft map, on by default with the 1090 MHz role: a static page
#                         from a pinned commit, in /usr/local/share/gps-time-tar1090/html, served by
#                         the web service at /tar1090/ (no listener of its own). GTP_TAR1090=0: off
#   skyaware978's page    the 978 MHz map from the same dump978 commit, in
#                         /usr/local/share/gps-time-skyaware978/html, served at /skyaware978/
#   a udev rule           RTL2832U dongles to plugdev (scripts/rtl-access.sh), which every SDR unit is in
#
# Each role needs its own RTL-SDR, picked by its USB serial (set one with rtl_eeprom -s, e.g. 1090 and
# 978; docs/deploy/sdr-stack.md -> "Two dongles"):
#   GTP_SDR_PPS_SERIAL    the dongle with the injected PPS (sdr-pps-marker)
#   GTP_SDR_1090_SERIAL   the 1090 MHz dongle: required with GTP_SDR=1 (none: no 1090 MHz role)
#   GTP_SDR_978_SERIAL    the 978 MHz dongle (off without one)
# A role with no serial is installed but not enabled. Serials are kept in
# /etc/default/gps-time-sdr between runs; GTP_SDR_<ROLE>_SERIAL=none clears one. With one dongle,
# it is the 1090 MHz one and 978 MHz stays off.
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
# tar1090 and its aircraft database (github.com/wiedehopf), fetched by commit and checked.
TAR1090_REPO="https://github.com/wiedehopf/tar1090.git"
TAR1090_COMMIT="5d59b1ba2c5e30eb23f1161940367b7767f10ad5"     # 3.14.1825, 2026-10-26
TAR1090_DB_REPO="https://github.com/wiedehopf/tar1090-db.git"
TAR1090_DB_COMMIT="2ab834a65f2fbde9457823e88682cd46954b8bc1"  # 2026-11-02
TAR1090_HTML="$ROOT/usr/local/share/gps-time-tar1090/html"
SKY_HTML="$ROOT/usr/local/share/gps-time-skyaware978/html"
# readsb v3.16.21 (github.com/wiedehopf/readsb), 2026-11-01; the commit is checked after the clone.
READSB_REPO="https://github.com/wiedehopf/readsb.git"
READSB_TAG="v3.16.21"
READSB_COMMIT="321931802d89f1695a38f6dfb0a64ba5c1211be4"
READSB_BIN="$ROOT/usr/local/bin/readsb"
# dump978 v11.1 (github.com/flightaware/dump978); the commit is checked after the clone.
DUMP978_REPO="https://github.com/flightaware/dump978.git"
DUMP978_TAG="v11.1"
DUMP978_COMMIT="f40aa9a0d2d0a0067c0c628b44ba316f7049b8ce"
WANT="${GTP_SDR-}"
CHECK_ONLY=0
[ "${1-}" = check ] && CHECK_ONLY=1
# How long the check after the install waits for the decoders to write their first file.
WAIT_S="${GTP_SDR_WAIT_S:-10}"

say() { echo "SDR stack: $*"; }

if [ -z "$WANT" ]; then
  [ "$CHECK_ONLY" = 1 ] && exit 0
  if [ -f "$UNITS/gps-time-rtl-tcp.service" ] || [ -f "$ENVFILE" ]; then
    say "kept as it is (GTP_SDR is not set)."
  else
    say "not installed. To add it: sudo GTP_SDR=1 GTP_SDR_1090_SERIAL=... bash install.sh (docs/deploy/sdr-stack.md)"
  fi
  exit 0
fi

case "$WANT" in
  0|off|no|false)
    [ "$CHECK_ONLY" = 1 ] && exit 0
    for u in $OUR_UNITS; do
      if [ -f "$UNITS/$u" ]; then
        systemctl disable --now "$u" >/dev/null 2>&1 || true
        rm -f "$UNITS/$u"
      fi
    done
    rm -f "$DROPIN"
    rmdir "$(dirname "$DROPIN")" 2>/dev/null || true
    rm -rf "$(dirname "$TAR1090_HTML")" "$(dirname "$SKY_HTML")"
    systemctl daemon-reload
    say "units, the module drop-in and the aircraft maps removed. Packages, $ENVFILE and $LIB are kept."
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
. "$(dirname "$0")/dongle-roles.sh"
. "$(dirname "$0")/sdr-decoders.sh"
ON_USB="$(dongle_serials "$ROOT" | tr '\n' ' ' | sed 's/ $//')"
NUSB="$(dongle_serials "$ROOT" | wc -l | tr -d ' ')"
# The 1090 MHz serial is required: readsb started with an empty one has "--device" and nothing
# after it, exits 1 and restarts for ever (rc.7 on the owner's Pi), and the aircraft map isn't
# installed. "none" says there is no 1090 MHz role on purpose; it's kept as "none".
RAW1090="${GTP_SDR_1090_SERIAL-}"; [ -z "$RAW1090" ] && RAW1090="$(old GTP_SDR_1090_SERIAL)"
if [ -z "$RAW1090" ]; then
  say "GTP_SDR_1090_SERIAL is empty, here and in $ENVFILE. readsb can't start without the 1090 MHz dongle's serial, and the aircraft map comes with it." >&2
  say "  RTL-SDRs on USB now: ${ON_USB:-none found}. Set GTP_SDR_1090_SERIAL to the 1090 MHz one (rtl_test -t lists them too)," >&2
  say "  or GTP_SDR_1090_SERIAL=none for no 1090 MHz role. Nothing changed." >&2
  exit 1
fi
SAVE1090="$S1090"; [ "$RAW1090" = none ] && SAVE1090=none
TAR1090="${GTP_TAR1090-}"; [ -z "$TAR1090" ] && TAR1090="$(old GTP_TAR1090)"; [ -z "$TAR1090" ] && TAR1090=1
case "$TAR1090" in
  1|on|yes|true) TAR1090=1 ;;
  0|off|no|false) TAR1090=0 ;;
  *) say "GTP_TAR1090='$TAR1090' must be 1 (the aircraft map, the default) or 0; nothing changed." >&2; exit 1 ;;
esac
for a in "$PPS_SERIAL:$S1090" "$PPS_SERIAL:$S978" "$S1090:$S978"; do
  x="${a%%:*}"; y="${a#*:}"
  if [ -n "$x" ] && [ "$x" = "$y" ]; then
    say "the same serial ($x) is given for two roles; each role needs its own RTL-SDR. Nothing changed." >&2
    exit 1
  fi
done
# The owner's limit: at most 3 RTL-SDRs by serial on a Pi 4, the web SDR's dongle included when
# it's installed (it may share the 1090 MHz or the 978 MHz one).
WEB_SERIAL=""
[ -f "$UNITS/gps-time-websdr.service" ] && WEB_SERIAL="$(dongle_saved "$ROOT/etc/default/gps-time-websdr" GTP_WEBSDR_SERIAL)"
dongle_check "$ROOT" "$PPS_SERIAL" "$S1090" "$S978" "$WEB_SERIAL" || { say "nothing changed." >&2; exit 1; }
# Warnings only (a dongle may be unplugged while installing): a serial no dongle has, and a serial
# that rtl-sdr's device search could read as an index once two dongles are plugged in.
say "RTL-SDRs on USB now: ${ON_USB:-none}."
for pair in "1090 MHz:$S1090" "978 MHz:$S978" "PPS markers:$PPS_SERIAL"; do
  what="${pair%%:*}"; s="${pair#*:}"
  [ -n "$s" ] || continue
  if ! dongle_serials "$ROOT" | grep -qxF "$s"; then
    say "warning: no RTL-SDR on USB has serial $s ($what); its service will not start until one does."
  elif [ "$(dongle_serials "$ROOT" | grep -cxF "$s")" -gt 1 ]; then
    say "warning: $(dongle_serials "$ROOT" | grep -cxF "$s") RTL-SDRs have serial $s ($what); give each its own with rtl_eeprom (docs/deploy/sdr-stack.md -> Two dongles)."
  fi
  if dongle_index_like "$s" "$NUSB"; then
    say "warning: serial $s ($what) could be read as device index $((10#$s)) with $NUSB RTL-SDRs plugged in (rtl_tcp, rtl_test -d). Unique serials such as 1090 and 978 avoid it (rtl_eeprom -s)."
  fi
done
# The decoders as they are now: a report only, since the install below builds readsb and adds the driver.
if [ "$CHECK_ONLY" = 1 ]; then
  if decoder_readsb_rtlsdr "$READSB_BIN"; then
    say "readsb in /usr/local/bin has RTL-SDR support."
  elif [ -n "$S1090" ]; then
    say "readsb with RTL-SDR support isn't installed yet; the install builds readsb $READSB_TAG (make RTLSDR=yes)."
  fi
  if [ -n "$S978" ] && ! decoder_soapy_rtlsdr "$ROOT"; then
    say "SoapySDR's RTL-SDR driver isn't installed yet; the install adds soapysdr-module-rtlsdr for dump978-fa."
  fi
fi
[ "$CHECK_ONLY" = 1 ] && { say "settings checked: 1090 MHz ${S1090:-none}, 978 MHz ${S978:-none}, PPS markers ${PPS_SERIAL:-none}."; exit 0; }

echo "== SDR stack: packages =="
# Debian's readsb package isn't installed any more (Debian 13 builds it without RTL-SDR support);
# one installed by rc.8 or earlier is left in place. Its readsb.service is masked so it can't take
# the first RTL-SDR it finds, which could be the PPS dongle, unless it was already enabled for the
# owner before this script: then it is left alone and its /run/readsb is used.
OWN_READSB=0
if dpkg -s readsb >/dev/null 2>&1 && systemctl is-enabled --quiet readsb.service 2>/dev/null; then
  OWN_READSB=1
else
  systemctl mask readsb.service >/dev/null 2>&1 || true
fi
apt-get install -y --no-install-recommends rtl-sdr soapysdr-module-rtlsdr >/dev/null \
  || { say "apt-get could not install rtl-sdr and soapysdr-module-rtlsdr; nothing else changed." >&2; exit 1; }
# The DVB-T driver claims RTL-SDRs: our own blacklist file (kept when the stack is removed),
# and unloaded now if it's loaded.
bash "$(dirname "$0")/rtl-dvb-blacklist.sh" "$ROOT" || say "the DVB-T driver blacklist could not be written (see above)."
# The dongles to plugdev: readsb, dump978-fa and rtl_tcp run with SupplementaryGroups=plugdev.
# Before rc.8 only the web SDR installed this rule.
bash "$(dirname "$0")/rtl-access.sh" "$ROOT" "$SRC" || say "the RTL-SDR access rule could not be applied (see above)."

as_nobody() { if [ "$(id -u)" = 0 ]; then runuser -u nobody -- "$@"; else "$@"; fi; }
CHECK_FAILED=0

echo "== SDR stack: readsb $READSB_TAG with RTL-SDR support =="
# Built whenever the stack is installed: the 1090 MHz role, the feeders and node mode all run it.
HAVE1090=0
if [ -x "$READSB_BIN" ] && [ "$(cat "$LIB/readsb.commit" 2>/dev/null)" = "$READSB_COMMIT" ] && decoder_readsb_rtlsdr "$READSB_BIN"; then
  say "readsb $READSB_TAG already built (RTL-SDR support checked)."
  HAVE1090=1
elif apt-get install -y --no-install-recommends git build-essential pkg-config libncurses-dev zlib1g-dev \
       libzstd-dev librtlsdr-dev libusb-1.0-0-dev >/dev/null; then
  RB="$(mktemp -d)"
  chown nobody "$RB" 2>/dev/null || true
  # Fetched and built as nobody, not root; only the readsb binary is installed.
  if as_nobody git clone --quiet --depth 1 --branch "$READSB_TAG" "$READSB_REPO" "$RB/readsb" \
     && [ "$(as_nobody git -C "$RB/readsb" rev-parse HEAD)" = "$READSB_COMMIT" ] \
     && as_nobody make -C "$RB/readsb" -j2 RTLSDR=yes readsb >/dev/null; then
    if decoder_readsb_rtlsdr "$RB/readsb/readsb"; then
      install -d -m 0755 "$(dirname "$READSB_BIN")" "$LIB"
      install -m 0755 "$RB/readsb/readsb" "$READSB_BIN.new" && mv -f "$READSB_BIN.new" "$READSB_BIN"
      echo "$READSB_COMMIT" > "$LIB/readsb.commit"
      HAVE1090=1
      say "readsb $READSB_TAG built with RTL-SDR support and installed as /usr/local/bin/readsb."
    else
      say "readsb $READSB_TAG was built, but it refuses --device-type rtlsdr (no RTL-SDR support); not installed." >&2
    fi
  else
    say "readsb $READSB_TAG could not be fetched, verified ($READSB_COMMIT) or built." >&2
  fi
  rm -rf "$RB"
else
  say "the build tools for readsb could not be installed." >&2
fi
if [ "$HAVE1090" = 0 ] && [ -n "$S1090" ] && [ "$OWN_READSB" = 0 ]; then
  CHECK_FAILED=1
  say "CHECK FAILED: no readsb with RTL-SDR support, so 1090 MHz stays off. Debian's /usr/bin/readsb has none (\"Unknown device type:rtlsdr\"). See above; docs/deploy/sdr-stack.md -> Check it." >&2
fi

echo "== SDR stack: SoapySDR's RTL-SDR driver (dump978-fa) =="
SOAPY_OK=0
if decoder_soapy_rtlsdr "$ROOT"; then
  SOAPY_OK=1
  say "SoapySDR's RTL-SDR driver is installed (librtlsdrSupport.so)."
elif [ -n "$S978" ]; then
  CHECK_FAILED=1
  say "CHECK FAILED: SoapySDR's RTL-SDR driver (librtlsdrSupport.so, package soapysdr-module-rtlsdr) isn't installed; dump978-fa can't open a dongle, so 978 MHz stays off." >&2
else
  say "SoapySDR's RTL-SDR driver isn't installed (needed only for 978 MHz)."
fi

echo "== SDR stack: dump978-fa and skyaware978 ($DUMP978_TAG) =="
HAVE978=0
if [ -x "$LIB/dump978-fa" ] && [ -x "$LIB/skyaware978" ] && [ "$(cat "$LIB/dump978.commit" 2>/dev/null)" = "$DUMP978_COMMIT" ] \
   && { [ -f "$SKY_HTML/index.html" ] || [ -f "$LIB/skyaware978.nopage" ]; }; then
  say "dump978 $DUMP978_TAG already built."
  HAVE978=1
elif apt-get install -y --no-install-recommends git build-essential libboost-program-options-dev \
       libboost-regex-dev libboost-filesystem-dev libsoapysdr-dev >/dev/null; then
  BUILD="$(mktemp -d)"
  chown nobody "$BUILD" 2>/dev/null || true
  # Fetched and built as nobody, not root; only the two binaries are installed.
  if as_nobody git clone --quiet --depth 1 --branch "$DUMP978_TAG" "$DUMP978_REPO" "$BUILD/dump978" \
     && [ "$(as_nobody git -C "$BUILD/dump978" rev-parse HEAD)" = "$DUMP978_COMMIT" ] \
     && as_nobody make -C "$BUILD/dump978" -j2 VERSION="$DUMP978_TAG" dump978-fa skyaware978 \
          CFLAGS="-O2 -g -Ilibs" \
          CXXFLAGS="-std=c++11 -Wno-psabi -O2 -g -Ilibs -DBOOST_ASIO_NO_DEPRECATED" >/dev/null; then
    install -d -m 0755 "$LIB"
    install -m 0755 "$BUILD/dump978/dump978-fa" "$BUILD/dump978/skyaware978" "$LIB/"
    # skyaware978's own map page, from the same commit; the station serves it at /skyaware978/.
    rm -f "$LIB/skyaware978.nopage"
    if [ -f "$BUILD/dump978/skyaware/index.html" ]; then
      rm -rf "$SKY_HTML.new" && install -d -m 0755 "$SKY_HTML.new" \
        && cp -r "$BUILD/dump978/skyaware/." "$SKY_HTML.new/" && chmod -R a+rX,go-w "$SKY_HTML.new" \
        && rm -rf "$SKY_HTML" && mv "$SKY_HTML.new" "$SKY_HTML" \
        && say "skyaware978's map page installed; the station serves it at /skyaware978/."
    else
      touch "$LIB/skyaware978.nopage"
      say "dump978 $DUMP978_TAG has no skyaware/ page; /skyaware978/ stays empty (the 978 MHz data still feeds the modules)."
    fi
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

echo "== SDR stack: aircraft map (tar1090) =="
if [ "$TAR1090" = 0 ]; then
  rm -rf "$(dirname "$TAR1090_HTML")"
  say "aircraft map off (GTP_TAR1090=0)."
elif [ -z "$S1090" ] && [ "$OWN_READSB" = 0 ]; then
  say "aircraft map: needs the 1090 MHz role (GTP_SDR_1090_SERIAL); not installed."
elif [ -f "$TAR1090_HTML/index.html" ] && [ "$(cat "$(dirname "$TAR1090_HTML")/commit" 2>/dev/null)" = "$TAR1090_COMMIT $TAR1090_DB_COMMIT" ]; then
  say "aircraft map: tar1090 ${TAR1090_COMMIT:0:7} already installed."
elif apt-get install -y --no-install-recommends git >/dev/null; then
  TB="$(mktemp -d)"
  chown nobody "$TB" 2>/dev/null || true
  # Fetched as nobody, by commit (not a branch), each checked; only the page's files are kept.
  fetch_commit() {   # fetch_commit <repo> <commit> <dir>
    as_nobody git init --quiet "$3" && as_nobody git -C "$3" fetch --quiet --depth 1 "$1" "$2" \
      && as_nobody git -C "$3" checkout --quiet FETCH_HEAD && [ "$(as_nobody git -C "$3" rev-parse HEAD)" = "$2" ]
  }
  if fetch_commit "$TAR1090_REPO" "$TAR1090_COMMIT" "$TB/tar1090" && fetch_commit "$TAR1090_DB_REPO" "$TAR1090_DB_COMMIT" "$TB/db" \
     && [ -f "$TB/tar1090/html/index.html" ] && [ -d "$TB/db/db" ]; then
    DBV="${TAR1090_DB_COMMIT:0:7}"
    STAGE="$(dirname "$TAR1090_HTML")/html.new"
    rm -rf "$STAGE" && install -d -m 0755 "$STAGE"
    cp -r "$TB/tar1090/html/." "$STAGE/" && cp -r "$TB/db/db" "$STAGE/db-$DBV"
    sed -i "s/let databaseFolder = .*;/let databaseFolder = \"db-$DBV\";/" "$STAGE/index.html"
    sed -i "s/id=\"webinterface_version\">/&(${TAR1090_COMMIT:0:7})/" "$STAGE/index.html"
    printf '{ "tar1090Version": "%s", "databaseVersion": "%s" }\n' "${TAR1090_COMMIT:0:7}" "$DBV" > "$STAGE/version.json"
    cp "$TB/tar1090/LICENSE" "$STAGE/LICENSE.txt" 2>/dev/null || true
    chmod -R a+rX,go-w "$STAGE"
    rm -rf "$TAR1090_HTML" && mv "$STAGE" "$TAR1090_HTML"
    echo "$TAR1090_COMMIT $TAR1090_DB_COMMIT" > "$(dirname "$TAR1090_HTML")/commit"
    say "aircraft map: tar1090 ${TAR1090_COMMIT:0:7} installed; the station serves it at /tar1090/."
  else
    say "aircraft map: tar1090 could not be fetched or verified ($TAR1090_COMMIT, db $TAR1090_DB_COMMIT); not installed." >&2
  fi
  rm -rf "$TB"
else
  say "aircraft map: git could not be installed; not installed." >&2
fi

echo "== SDR stack: units (loopback only) =="
install -d -m 0755 "$(dirname "$ENVFILE")"
{
  echo "# Written by gps-time-pi install.sh (scripts/sdr-stack.sh): one RTL-SDR serial per role."
  echo "GTP_SDR_PPS_SERIAL=$PPS_SERIAL"
  echo "GTP_SDR_1090_SERIAL=$SAVE1090"
  echo "GTP_SDR_978_SERIAL=$S978"
  echo "GTP_TAR1090=$TAR1090"
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
    systemctl reset-failed "${units[@]}" >/dev/null 2>&1 || true
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
elif [ "$HAVE1090" = 1 ]; then
  role gps-time-readsb.service -- "$S1090" "1090 MHz (readsb)"
else
  systemctl disable --now gps-time-readsb.service >/dev/null 2>&1 || true
fi
[ "$SOAPY_OK" = 1 ] || HAVE978=0
if [ "$HAVE978" = 1 ]; then
  role gps-time-dump978.service gps-time-skyaware978.service -- "$S978" "978 MHz (dump978-fa, skyaware978)"
else
  systemctl disable --now gps-time-dump978.service gps-time-skyaware978.service >/dev/null 2>&1 || true
fi
# The check that would have caught rc.7's crash loop: after WAIT_S seconds, is each enabled decoder
# active, and has it written its aircraft.json? A report, never a change; exit 3 tells install.sh.
web_has() {   # web_has <serial>: the web SDR is running on that dongle (so its decoder is paused)
  [ -n "$1" ] && [ "$WEB_SERIAL" = "$1" ] && systemctl is-active --quiet gps-time-websdr.service 2>/dev/null
}
CHECKS=""
[ "$OWN_READSB" = 0 ] && [ "$HAVE1090" = 1 ] && [ -n "$S1090" ] && CHECKS="$CHECKS gps-time-readsb.service:/run/readsb/aircraft.json:$S1090"
[ "$HAVE978" = 1 ] && [ -n "$S978" ] && CHECKS="$CHECKS gps-time-skyaware978.service:/run/skyaware978/aircraft.json:$S978"
if [ -n "$CHECKS" ]; then
  echo "== SDR stack: check after ${WAIT_S} s =="
  sleep "$WAIT_S"
  for c in $CHECKS; do
    u="${c%%:*}"; rest="${c#*:}"; json="${rest%%:*}"; serial="${rest#*:}"
    [ "$u" = gps-time-skyaware978.service ] && units_for="gps-time-dump978.service $u" || units_for="$u"
    if web_has "$serial"; then
      say "check: $units_for paused: the web SDR has dongle $serial; it comes back when the web SDR stops."
      continue
    fi
    for x in $units_for; do
      state="$(systemctl is-active "$x" 2>/dev/null)"; state="${state:-unknown}"
      if [ "$state" = active ]; then
        say "check: $x is active (dongle $serial)."
      else
        CHECK_FAILED=1
        say "CHECK FAILED: $x is $state, not active (dongle $serial). Its last lines:" >&2
        journalctl -u "$x" -n 12 --no-pager 2>/dev/null | sed 's/^/    /' >&2 || true
      fi
    done
    if [ -f "$ROOT$json" ]; then
      say "check: $json exists."
    else
      CHECK_FAILED=1
      say "CHECK FAILED: $json does not exist after ${WAIT_S} s." >&2
    fi
  done
fi

# The supervisor runs nothing while the experimental switch is off, so with the SDR stack asked
# for it is enabled: then turning a module on in Administration is all that's left.
systemctl enable gps-time-modules.service >/dev/null 2>&1 && systemctl start gps-time-modules.service   && say "gps-time-modules.service enabled; it runs no module until one is turned on in Administration."   || say "gps-time-modules.service could not be enabled (journalctl -u gps-time-modules)."
say "gps-time-modules.service may reach 127.0.0.1 ($DROPIN)."
if [ "$CHECK_FAILED" = 1 ]; then
  say "installed, but a decoder isn't running (see CHECK FAILED above; docs/deploy/sdr-stack.md -> Check it)." >&2
  exit 3
fi
exit 0
