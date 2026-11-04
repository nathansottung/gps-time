#!/bin/bash
# Optional web SDR for the station: OpenWebRX+ behind a LAN gate with an optional login
# (docs/deploy/websdr.md).
#
# Off unless asked for. Run by install.sh:
#   GTP_WEBSDR=1      install or update it
#   GTP_WEBSDR=0      remove the units, the drop-ins and the OpenWebRX+ port setting (packages kept)
#   (unset)           change nothing
#
# Settings, kept in /etc/default/gps-time-websdr between runs:
#   GTP_WEBSDR_SERIAL     the RTL-SDR it uses; default: the 1090 MHz dongle (GTP_SDR_1090_SERIAL).
#                         Never the PPS or the 978 MHz dongle.
#   GTP_WEBSDR_PORT       the LAN port of the password gate (default 8073)
#   GTP_WEBSDR_MAX_HOURS  a session ends by itself after this many hours (default 4, 1 to 24)
#   GTP_WEBSDR_AUTH       1: the gate asks for a login; 0 (the default): LAN only, no login
#   GTP_WEBSDR_REMEMBER_DAYS  how long "Remember this browser" lasts (default 30, 1 to 365)
#   GTP_WEBSDR_HF         HF profiles: off (default; 24 MHz and up only), direct (direct sampling,
#                         the Q branch: NESDR SMArt v5, RTL-SDR Blog V3), native (a dongle with its
#                         own HF path, e.g. RTL-SDR Blog V4)
#
# What GTP_WEBSDR=1 does:
#   - adds the OpenWebRX+ apt repository (luarvique.github.io/ppa) for bookworm or trixie, after
#     checking its signing key's fingerprint, and installs the openwebrx package with its own
#     openwebrx.service masked (it would take the first dongle it finds on port 8073);
#   - installs the decoders' helpers (direwolf, wsjtx, aprs-symbols, csdr-skimmer: APRS, packet,
#     FT8, FT4, WSPR, CW and RTTY skimmers; SSTV, fax, CW and RTTY decoders are built in) and the
#     band bookmarks (/etc/openwebrx/bookmarks.d/gps-time-decoders.json);
#   - points OpenWebRX+ at 127.0.0.1:8074 (conf.d), pins its RTL-SDR to the serial, and sets the
#     station's band profiles (system/openwebrx-gps-time-profiles.json);
#   - installs gps-time-websdr.service (OpenWebRX+, loopback only, no outside host),
#     gps-time-websdr-gate.service (the gate on the LAN port, private ranges only, a login if
#     GTP_WEBSDR_AUTH=1), and gps-time-websdr-signout.service (signs out every browser).
#     Neither is enabled at boot: the web SDR is started from the Radio page (anyone on the LAN,
#     no admin token) or with systemctl.
#     While it runs, readsb is stopped (Conflicts=); websdr-handoff starts it again afterwards.
#
# Never touched: gpsd, chrony, the PPS line and its overlay. No receiver position is given.
set -u
ROOT="${GTP_WEBSDR_TEST_ROOT-}"            # tests only: a prefix for every path written
UNITS="$ROOT/etc/systemd/system"
DROPIN="$UNITS/gps-time-websdr.service.d/gps-time-max.conf"
ENVFILE="$ROOT/etc/default/gps-time-websdr"
SDR_ENV="$ROOT/etc/default/gps-time-sdr"
PWDIR="$ROOT/etc/gps-time-websdr"
OWRX_CONF="$ROOT/etc/openwebrx/openwebrx.conf.d/gps-time.conf"
OWRX_DATA="$ROOT/var/lib/openwebrx"
LIB="$ROOT/usr/local/lib/gps-time-sdr"
KEYRING="$ROOT/usr/share/keyrings/gps-time-openwebrx-plus.gpg"
SOURCES="$ROOT/etc/apt/sources.list.d/gps-time-openwebrx-plus.list"
OS_RELEASE="${GTP_WEBSDR_OS_RELEASE:-/etc/os-release}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/system"
OUR_UNITS="gps-time-websdr.service gps-time-websdr-gate.service gps-time-websdr-signout.service"
REPO="https://luarvique.github.io/ppa"
# Marat Fayzullin (luarvique), the OpenWebRX+ maintainer: checked 2026-11-04.
KEY_FPR="82B2AC14962B3C75FAC97206B64EADD5CB69C981"
PY="${GTP_WEBSDR_PYTHON:-python3}"
WANT="${GTP_WEBSDR-}"

say() { echo "Web SDR: $*"; }

if [ -z "$WANT" ]; then
  if [ -f "$UNITS/gps-time-websdr.service" ]; then
    say "kept as it is (GTP_WEBSDR is not set)."
  else
    say "not installed. To add it: sudo GTP_WEBSDR=1 bash install.sh (docs/deploy/websdr.md)"
  fi
  exit 0
fi

case "$WANT" in
  0|off|no|false)
    for u in $OUR_UNITS; do
      if [ -f "$UNITS/$u" ]; then
        systemctl stop "$u" >/dev/null 2>&1 || true
        rm -f "$UNITS/$u"
      fi
    done
    rm -f "$DROPIN" "$OWRX_CONF" "$LIB/websdr-handoff" "$UNITS/gps-time-airband-fetch.service" \
      "$ROOT/etc/openwebrx/bookmarks.d/gps-time-airband.json" "$ROOT/etc/openwebrx/bookmarks.d/gps-time-decoders.json"
    rmdir "$(dirname "$DROPIN")" 2>/dev/null || true
    systemctl daemon-reload
    say "units, drop-in and the OpenWebRX+ port setting removed. Packages, the repository, $ENVFILE and the password are kept."
    exit 0 ;;
  1|on|yes|true) ;;
  *) say "GTP_WEBSDR must be 1 or 0, not '$WANT'; nothing changed." >&2; exit 1 ;;
esac

kv() { [ -f "$1" ] && sed -n "s/^$2=\\([A-Za-z0-9_.-]*\\)\$/\\1/p" "$1" | tail -n 1; }
fail() { say "$*; nothing changed." >&2; exit 1; }

SERIAL="${GTP_WEBSDR_SERIAL-}"
[ -z "$SERIAL" ] && SERIAL="$(kv "$ENVFILE" GTP_WEBSDR_SERIAL)"
[ -z "$SERIAL" ] && SERIAL="$(kv "$SDR_ENV" GTP_SDR_1090_SERIAL)"
PORT="${GTP_WEBSDR_PORT-}"; [ -z "$PORT" ] && PORT="$(kv "$ENVFILE" GTP_WEBSDR_PORT)"; [ -z "$PORT" ] && PORT=8073
HOURS="${GTP_WEBSDR_MAX_HOURS-}"; [ -z "$HOURS" ] && HOURS="$(kv "$ENVFILE" GTP_WEBSDR_MAX_HOURS)"; [ -z "$HOURS" ] && HOURS=4
AUTH="${GTP_WEBSDR_AUTH-}"; [ -z "$AUTH" ] && AUTH="$(kv "$ENVFILE" GTP_WEBSDR_AUTH)"; [ -z "$AUTH" ] && AUTH=0
DAYS="${GTP_WEBSDR_REMEMBER_DAYS-}"; [ -z "$DAYS" ] && DAYS="$(kv "$ENVFILE" GTP_WEBSDR_REMEMBER_DAYS)"; [ -z "$DAYS" ] && DAYS=30
HF="${GTP_WEBSDR_HF-}"; [ -z "$HF" ] && HF="$(kv "$ENVFILE" GTP_WEBSDR_HF)"; [ -z "$HF" ] && HF=off

[ -n "$SERIAL" ] || fail "no RTL-SDR serial: set GTP_WEBSDR_SERIAL, or GTP_SDR_1090_SERIAL with GTP_SDR=1"
[[ "$SERIAL" =~ ^[A-Za-z0-9_-]{1,32}$ ]] || fail "GTP_WEBSDR_SERIAL='$SERIAL' is not a serial (letters, digits, - and _, at most 32)"
for role in GTP_SDR_PPS_SERIAL GTP_SDR_978_SERIAL; do
  if [ "$(kv "$SDR_ENV" "$role")" = "$SERIAL" ]; then
    fail "$SERIAL is the dongle for $role; the web SDR may share only the 1090 MHz dongle (or one with no role)"
  fi
done
# The owner's limit: at most 3 RTL-SDRs by serial on a Pi 4, counting the SDR stack's roles when
# it's installed. Sharing the 1090 MHz dongle adds none.
. "$(dirname "$0")/dongle-roles.sh"
SDR_SERIALS=""
if [ -f "$UNITS/gps-time-rtl-tcp.service" ]; then
  SDR_SERIALS="$(dongle_saved "$SDR_ENV" GTP_SDR_PPS_SERIAL) $(dongle_saved "$SDR_ENV" GTP_SDR_1090_SERIAL) $(dongle_saved "$SDR_ENV" GTP_SDR_978_SERIAL)"
fi
# shellcheck disable=SC2086  # the saved serials are letters, digits, - and _ only
dongle_check "$ROOT" "$SERIAL" $SDR_SERIALS >/dev/null || fail "the web SDR's dongle would be one too many (see above)"
[[ "$PORT" =~ ^[0-9]{4,5}$ ]] && [ "$PORT" -ge 1024 ] && [ "$PORT" -le 65535 ] && [ "$PORT" != 8074 ] \
  || fail "GTP_WEBSDR_PORT='$PORT' must be 1024 to 65535 and not 8074 (OpenWebRX+ itself)"
[[ "$HOURS" =~ ^[0-9]{1,2}$ ]] && [ "$HOURS" -ge 1 ] && [ "$HOURS" -le 24 ] \
  || fail "GTP_WEBSDR_MAX_HOURS='$HOURS' must be a whole number of hours, 1 to 24"
case "$AUTH" in
  1|on|yes|true) AUTH=1 ;;
  0|off|no|false) AUTH=0 ;;
  *) fail "GTP_WEBSDR_AUTH='$AUTH' must be 1 (login on) or 0 (off)" ;;
esac
[[ "$DAYS" =~ ^[0-9]{1,3}$ ]] && [ "$DAYS" -ge 1 ] && [ "$DAYS" -le 365 ] \
  || fail "GTP_WEBSDR_REMEMBER_DAYS='$DAYS' must be a whole number of days, 1 to 365"
case "$HF" in
  off|direct|native) ;;
  *) fail "GTP_WEBSDR_HF='$HF' must be off, direct or native" ;;
esac

CODENAME="$(sed -n 's/^VERSION_CODENAME=//p' "$OS_RELEASE" 2>/dev/null | tr -d '"' | head -n 1)"
case "$CODENAME" in
  bookworm|trixie) ;;
  *) fail "OpenWebRX+ packages exist for Debian bookworm and trixie, not '${CODENAME:-unknown}'" ;;
esac

# An OpenWebRX the owner runs already is left alone.
if dpkg -s openwebrx >/dev/null 2>&1 && systemctl is-enabled --quiet openwebrx.service 2>/dev/null; then
  fail "openwebrx.service is already installed and enabled by its owner; it is left as it is"
fi

echo "== Web SDR: OpenWebRX+ repository ($CODENAME) =="
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL --max-time 60 "$REPO/openwebrx-plus.gpg" -o "$TMP/key" \
  || fail "the OpenWebRX+ signing key could not be downloaded"
GOT="$(gpg --show-keys --with-colons "$TMP/key" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
[ "$GOT" = "$KEY_FPR" ] || fail "the OpenWebRX+ signing key's fingerprint is '${GOT:-none}', not $KEY_FPR"
install -d -m 0755 "$(dirname "$KEYRING")" "$(dirname "$SOURCES")"
gpg --yes --dearmor -o "$KEYRING.tmp" "$TMP/key" && chmod 0644 "$KEYRING.tmp" && mv -f "$KEYRING.tmp" "$KEYRING" \
  || fail "the signing key could not be written"
echo "deb [signed-by=/usr/share/keyrings/gps-time-openwebrx-plus.gpg] $REPO/$CODENAME ./" > "$SOURCES"

echo "== Web SDR: packages =="
# The package's own unit would start at install on port 8073 with the first dongle it finds.
if ! dpkg -s openwebrx >/dev/null 2>&1; then
  systemctl mask openwebrx.service >/dev/null 2>&1 || true
fi
if ! { apt-get update >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y openwebrx >/dev/null; }; then
  rm -f "$SOURCES"
  say "apt-get could not install openwebrx; the repository entry was taken out again. Nothing else changed." >&2
  exit 1
fi
systemctl mask openwebrx.service >/dev/null 2>&1 || true
# The decoders' helpers, named so they are there even where apt skips Recommends. SSTV, fax, CW
# and RTTY decoders are built into OpenWebRX+ (python3-csdr). A failure here keeps the web SDR.
DECODERS="direwolf wsjtx aprs-symbols csdr-skimmer"
# shellcheck disable=SC2086  # fixed package names
if DEBIAN_FRONTEND=noninteractive apt-get install -y $DECODERS >/dev/null; then
  say "decoders' helpers installed ($DECODERS)."
else
  say "the decoders' helpers ($DECODERS) could not all be installed; FT8, FT4, WSPR, APRS, packet and the skimmers may be missing." >&2
fi
# The DVB-T driver claims RTL-SDRs: our own blacklist file (kept when the web SDR is removed),
# and unloaded now if it's loaded. openwebrx may not pull in rtl-sdr's own blacklist.
bash "$(dirname "$0")/rtl-dvb-blacklist.sh" "$ROOT" || say "the DVB-T driver blacklist could not be written (see above)."

echo "== Web SDR: OpenWebRX+ settings =="
install -d -m 0755 "$(dirname "$OWRX_CONF")"
install -m 0644 "$SRC/openwebrx-gps-time.conf" "$OWRX_CONF"
install -d -m 0755 "$OWRX_DATA"
# Pin every RTL-SDR device in OpenWebRX+'s settings to the serial and set the station's band
# profiles (system/openwebrx-gps-time-profiles.json). A new settings file gets one RTL-SDR with
# the base VHF/UHF profiles; an existing one is kept (a copy is left beside it). On every RTL-SDR
# the station's own profiles (keys gtp-*) are replaced: 10 m, 6 m and 2 m digital always, the HF
# ones only with GTP_WEBSDR_HF=direct or native. The owner's own profiles are never touched.
"$PY" - "$OWRX_DATA/settings.json" "$SERIAL" "$SRC/openwebrx-gps-time-profiles.json" "$HF" <<'PYEOF'   || { say "OpenWebRX+'s settings.json could not be read or updated; the package is installed, the units are not." >&2; exit 1; }
import copy, json, os, shutil, sys
path, serial, profiles_path, hf = sys.argv[1:5]
with open(profiles_path, encoding="utf-8") as f:
    prof = json.load(f)
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    shutil.copy2(path, path + ".gps-time-prev")
else:
    doc = {"version": 8, "sdrs": {"rtlsdr": {
        "name": "RTL-SDR", "type": "rtl_sdr", "rf_gain": 29, "direct_sampling": 0,
        "profiles": copy.deepcopy(prof["base"])}}}
ours = dict(prof["managed"])
if hf in ("direct", "native"):
    for key, p in prof["hf"].items():
        ours[key] = {**p, "direct_sampling": 2 if hf == "direct" else 0}
sdrs = doc.get("sdrs") if isinstance(doc.get("sdrs"), dict) else {}
n = 0
for dev in sdrs.values():
    if isinstance(dev, dict) and dev.get("type") == "rtl_sdr":
        dev["device"] = serial
        profiles = dev.get("profiles") if isinstance(dev.get("profiles"), dict) else {}
        profiles = {k: v for k, v in profiles.items() if not k.startswith("gtp-")}
        profiles.update(copy.deepcopy(ours))
        dev["profiles"] = profiles
        n += 1
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=4)
os.replace(tmp, path)
print(f"Web SDR: {n} RTL-SDR device(s) in OpenWebRX+ set to serial {serial}; "
      f"{len(ours)} station band profiles (HF: {hf}).")
PYEOF
chown -R openwebrx:openwebrx "$OWRX_DATA" 2>/dev/null || true

echo "== Web SDR: units (OpenWebRX+ on the loopback, the gate on the LAN) =="
install -d -m 0755 "$(dirname "$ENVFILE")" "$LIB"
{
  echo "# Written by gps-time-pi install.sh (scripts/websdr.sh)."
  echo "GTP_WEBSDR_SERIAL=$SERIAL"
  echo "GTP_WEBSDR_PORT=$PORT"
  echo "GTP_WEBSDR_MAX_HOURS=$HOURS"
  echo "GTP_WEBSDR_AUTH=$AUTH"
  echo "GTP_WEBSDR_REMEMBER_DAYS=$DAYS"
  echo "GTP_WEBSDR_HF=$HF"
} > "$ENVFILE.tmp" && mv -f "$ENVFILE.tmp" "$ENVFILE"
chmod 0644 "$ENVFILE"
install -d -m 0700 "$PWDIR"
if [ ! -f "$PWDIR/password" ]; then
  # The gate reads this as a credential; with no password line in it, it answers 503 to everything.
  (umask 077; echo "# No password yet: sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.websdr_gate passwd" > "$PWDIR/password")
fi
if [ ! -s "$PWDIR/cookie-key" ]; then
  # Signs "Remember this browser" cookies; a new one (websdr_gate signout-all) signs every browser out.
  KEY="$("$PY" -c 'import secrets; print(secrets.token_hex(32))')" || fail "no cookie key could be made"
  (umask 077; printf '# The web SDR cookie key (gps_time_pi/websdr_gate.py).\n%s\n' "$KEY" > "$PWDIR/cookie-key")
fi
install -m 0755 "$SRC/websdr-handoff" "$LIB/websdr-handoff"
install -d -m 0755 "$UNITS" "$(dirname "$DROPIN")"
for u in $OUR_UNITS; do install -m 0644 "$SRC/$u" "$UNITS/$u"; done
# Airband bookmarks (FAA NASR, refreshed only on the owner's "Refresh now"): the oneshot unit, and
# OpenWebRX+'s bookmarks.d linked to the file it writes beside config.json.
install -m 0644 "$SRC/gps-time-airband-fetch.service" "$UNITS/gps-time-airband-fetch.service"
install -d -m 0755 "$ROOT/etc/openwebrx/bookmarks.d"
ln -sfn /opt/gps-time-pi/airband-openwebrx.json "$ROOT/etc/openwebrx/bookmarks.d/gps-time-airband.json"
# The decoders' band bookmarks: fixed, published frequencies; nothing about the station's location.
install -m 0644 "$SRC/openwebrx-gps-time-decoders.json" "$ROOT/etc/openwebrx/bookmarks.d/gps-time-decoders.json"
printf '[Service]\n# Written by scripts/websdr.sh: a session ends by itself after GTP_WEBSDR_MAX_HOURS.\nRuntimeMaxSec=%sh\n' "$HOURS" > "$DROPIN"
systemctl daemon-reload
# Never enabled at boot; a running web SDR picks up the new settings at its next start.
systemctl disable gps-time-websdr.service gps-time-websdr-gate.service >/dev/null 2>&1 || true
say "installed, not running. RTL-SDR $SERIAL, LAN port $PORT, sessions end after $HOURS h, HF profiles: $HF."
if [ "$AUTH" = 0 ]; then
  say "login off: anyone on the LAN can listen (GTP_WEBSDR_AUTH=1 turns the login on)."
elif grep -q '^[^#]' "$PWDIR/password" 2>/dev/null; then
  say "login on, a password is set; \"Remember this browser\" lasts $DAYS days."
else
  say "login on, but no password yet; until one is set the gate refuses everything. Set it with:"
  say "  sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.websdr_gate passwd"
fi
say "start it from the Radio page (anyone on the LAN, no token) or: sudo systemctl start gps-time-websdr"
exit 0
