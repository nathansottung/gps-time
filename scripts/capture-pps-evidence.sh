#!/bin/bash
# capture-pps-evidence.sh — read-only snapshot of the PPS timing chain, for a timing incident.
#
# Run it BEFORE rebooting, so the evidence of the fault is kept:
#   bash /opt/gps-time-pi/scripts/capture-pps-evidence.sh            # as the normal user
#   sudo bash /opt/gps-time-pi/scripts/capture-pps-evidence.sh       # adds ppstest and dmesg
#
# Saves one archive, pps-evidence-<UTC time>.tar.gz, in /tmp (or --out DIR):
#   meta.txt         when, kernel, privacy mode, what was skipped
#   pps-devices.txt  /dev/pps* listing
#   pps-sysfs.txt    /sys/class/pps state, plus a few assert samples one second apart
#   ppstest.txt      a short ppstest per device (root only; skipped otherwise)
#   chrony.txt       chronyc -n tracking, sources, sourcestats, activity
#   kernel.txt       this boot's kernel messages about PPS, GPIO, serial ports and voltage
#   config.txt       the chrony, gpsd, boot and module lines that set up the timing chain
#   services.txt     state and restart counts of gpsd, chrony and gps-time-pi
#   gpsd.json        a few seconds of gpsd output, position removed (see below)
#
# Read-only: it changes no configuration, service or clock, and writes only a
# temporary directory and the archive. It never calls sudo itself.
#
# Privacy: gpsd output goes through gps_time_pi/gpsd_redact.py, which removes the
# position in every privacy mode (and satellite azimuth/elevation in hidden mode).
# --include-position keeps what the station's privacy mode shows on screen.
# Without python3 the gpsd output is left out. No hostname, client addresses or
# chrony `allow` lines are collected.

set -u
umask 077

OUT_DIR=${TMPDIR:-/tmp}
INCLUDE_POSITION=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT_DIR=${2:?--out needs a directory}; shift 2 ;;
    --include-position) INCLUDE_POSITION=1; shift ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done
[ -d "$OUT_DIR" ] && [ -w "$OUT_DIR" ] || { echo "cannot write to $OUT_DIR" >&2; exit 2; }

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
REDACT="$ROOT/gps_time_pi/gpsd_redact.py"
CONFIG=${GTP_CONFIG:-/opt/gps-time-pi/config.json}
# Overridable roots, so the tests can use a fake system tree.
SYS=${GTP_SYSFS_ROOT:-/sys}
DEV=${GTP_DEV_ROOT:-/dev}
ETC=${GTP_ETC_ROOT:-/etc}
BOOT=${GTP_BOOT_ROOT:-/boot}
SAMPLES=${GTP_PPS_SAMPLES:-5}
GPSD_SECONDS=${GTP_GPSD_SECONDS:-5}

stamp=$(date -u +%Y%m%dT%H%M%SZ)
name="pps-evidence-$stamp"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
d="$work/$name"
mkdir "$d"
skipped=""

# run FILE SECONDS CMD...: the command line, its output and its exit status.
run() {
  local f=$1 t=$2; shift 2
  {
    echo "\$ $*"
    if command -v "$1" >/dev/null 2>&1; then
      timeout "$t" "$@" 2>&1
      echo "[exit $?]"
    else
      echo "[$1 not installed]"
    fi
    echo
  } >> "$d/$f"
}

# show FILE...: each readable file's contents, prefixed by its name.
show() {
  local f
  for f in "$@"; do
    [ -r "$f" ] || continue
    printf '%s: %s\n' "${f##*/}" "$(tr -d '\0' < "$f" 2>/dev/null)"
  done
}

is_root=0
[ "$(id -u)" = 0 ] && is_root=1

mode=hidden
if command -v python3 >/dev/null 2>&1 && [ -r "$REDACT" ]; then
  mode=$(python3 -I "$REDACT" --config "$CONFIG" 2>/dev/null || echo hidden)
fi

# --- PPS devices and sysfs ---------------------------------------------------
{
  echo "\$ ls -l $DEV/pps*"
  ls -l "$DEV"/pps* 2>&1
} > "$d/pps-devices.txt"

ppsdirs=$(ls -d "$SYS"/class/pps/pps* 2>/dev/null)
{
  if [ -z "$ppsdirs" ]; then
    echo "no PPS devices under $SYS/class/pps"
  fi
  for p in $ppsdirs; do
    echo "== ${p##*/}"
    show "$p/name" "$p/path" "$p/mode" "$p/echo" "$p/assert" "$p/clear"
    echo
  done
  if [ -n "$ppsdirs" ]; then
    echo "== assert samples, ~1 s apart (system time, device, assert as seconds.nanoseconds#sequence)"
    i=0
    while [ "$i" -lt "$SAMPLES" ]; do
      for p in $ppsdirs; do
        printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)" "${p##*/}" "$(cat "$p/assert" 2>/dev/null)"
      done
      i=$((i + 1))
      [ "$i" -lt "$SAMPLES" ] && sleep 1
    done
  fi
} > "$d/pps-sysfs.txt"

: > "$d/ppstest.txt"
if [ "$is_root" = 1 ]; then
  for p in $ppsdirs; do run ppstest.txt 6 ppstest "$DEV/${p##*/}"; done
else
  echo "skipped: ppstest needs root (run the script with sudo to include it)" > "$d/ppstest.txt"
  skipped="$skipped ppstest"
fi

# --- chrony (monitoring reports over UDP: no root needed; -n: no DNS lookups) ---
: > "$d/chrony.txt"
for r in tracking "sources -v" "sourcestats -v" activity; do
  # shellcheck disable=SC2086  # the report name is split on purpose
  run chrony.txt 10 chronyc -n $r
done

# --- kernel messages from this boot ------------------------------------------
pattern='pps|gpio|uart|tty(AMA|S|USB|ACM)|serial|under-?voltage|throttl'
{
  if command -v journalctl >/dev/null 2>&1 && journalctl -k -b -q --no-pager -n 1 >/dev/null 2>&1; then
    echo "\$ journalctl -k -b | grep -iE '$pattern' | tail -n 300"
    journalctl -k -b -q --no-pager -o short-iso 2>/dev/null | grep -iE "$pattern" | tail -n 300
  elif dmesg >/dev/null 2>&1; then
    echo "\$ dmesg | grep -iE '$pattern' | tail -n 300"
    dmesg 2>/dev/null | grep -iE "$pattern" | tail -n 300
  else
    echo "skipped: kernel messages need the adm or systemd-journal group, or root"
  fi
} > "$d/kernel.txt"
grep -q '^skipped' "$d/kernel.txt" && skipped="$skipped kernel"

# --- configuration lines -----------------------------------------------------
{
  echo "== chrony (refclock, sources and clock-steering lines; no allow/deny lines)"
  grep -HnE '^[[:space:]]*(refclock|server|pool|peer|makestep|rtcsync|leapsectz|leapseclist|maxupdateskew|maxdistance|hwtimestamp|lock_all|sched_priority|confdir|sourcedir|include)\b' \
    "$ETC"/chrony/chrony.conf "$ETC"/chrony/conf.d/*.conf "$ETC"/chrony/sources.d/*.sources 2>/dev/null
  echo
  echo "== gpsd"
  grep -HnE '^[[:space:]]*(DEVICES|GPSD_OPTIONS|USBAUTO|START_DAEMON)=' "$ETC"/default/gpsd 2>/dev/null
  echo
  echo "== boot (PPS, GPIO and UART lines)"
  grep -HnE 'pps|gpio|uart|serial|dtoverlay|core_freq|force_turbo' \
    "$BOOT"/firmware/config.txt "$BOOT"/config.txt 2>/dev/null
  for c in "$BOOT"/firmware/cmdline.txt "$BOOT"/cmdline.txt; do
    [ -r "$c" ] && printf '%s: %s\n' "$c" "$(grep -oE '(console|kgdboc)=[^ ]*|nohz[^ ]*|isolcpus=[^ ]*' "$c" | tr '\n' ' ')"
  done
  echo
  echo "== kernel modules"
  grep -HnE 'pps' "$ETC"/modules "$ETC"/modules-load.d/*.conf 2>/dev/null
} > "$d/config.txt"

# --- services ----------------------------------------------------------------
: > "$d/services.txt"
for u in gpsd.socket gpsd.service chrony.service gps-time-pi.service gps-time-pi-chrony-clients.service; do
  run services.txt 10 systemctl show --no-pager \
    -p Id,LoadState,ActiveState,SubState,Result,NRestarts,ActiveEnterTimestamp,ExecMainStatus "$u"
done

# --- gpsd output, position removed ------------------------------------------
if command -v python3 >/dev/null 2>&1 && [ -r "$REDACT" ] && command -v gpspipe >/dev/null 2>&1; then
  pos_arg=()
  [ "$INCLUDE_POSITION" = 1 ] && pos_arg=(--include-position)
  timeout "$((GPSD_SECONDS + 2))" gpspipe -w -x "$GPSD_SECONDS" 2>/dev/null \
    | python3 -I "$REDACT" --mode "$mode" "${pos_arg[@]}" > "$d/gpsd.json" 2> "$d/gpsd-note.txt"
else
  echo "skipped: needs gpspipe and python3 (the output is not kept unredacted)" > "$d/gpsd-note.txt"
  skipped="$skipped gpsd"
fi

# --- meta, then the archive --------------------------------------------------
{
  echo "captured (UTC): $stamp"
  echo "script: capture-pps-evidence.sh"
  [ -r "$ROOT/gps_time_pi/VERSION" ] && echo "gps-time version: $(cat "$ROOT/gps_time_pi/VERSION")"
  echo "kernel: $(uname -srm)"
  echo "uptime since: $(uptime -s 2>/dev/null || echo unknown)"
  echo "run as root: $([ "$is_root" = 1 ] && echo yes || echo no)"
  echo "location privacy mode: $mode"
  echo "position in gpsd output: $([ "$INCLUDE_POSITION" = 1 ] && echo "as the privacy mode allows" || echo removed)"
  echo "skipped:${skipped:- nothing}"
} > "$d/meta.txt"

archive="$OUT_DIR/$name.tar.gz"
tar -czf "$archive" -C "$work" "$name" || { echo "could not write $archive" >&2; exit 1; }
echo "$archive"
