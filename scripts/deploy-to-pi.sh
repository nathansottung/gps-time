#!/usr/bin/env bash
# Build the Pi bundle, upload it, verify it on the Pi, install. Stops at the
# first failure (review GPS-021): a failed build never uploads an old archive,
# and install.sh never runs on an archive whose SHA-256 doesn't match.
set -euo pipefail
if [[ $# -lt 1 ]]; then echo "usage: $0 <pi-host> [pi-user]" >&2; exit 2; fi
HOST="$1"; USER_NAME="${2:-pi}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REMOTE="${USER_NAME}@${HOST}"
ARCHIVE="dist/gps-time-pi-deploy.tar.gz"
# Upload into a fresh directory in the remote user's home, not a fixed /tmp name.
REMOTE_DIR="gps-time-deploy"

# install.sh's optional flags (docs/deploy/sdr-stack.md, websdr.md; the chrony steps), taken from
# this shell's environment and passed to `sudo env ... bash install.sh` on the Pi:
#   GTP_WEBSDR=1 bash scripts/deploy-to-pi.sh <pi-host> <pi-user>
# Only these names are passed (tests/test_deploy_scripts.py keeps the list in step with install.sh).
# Values reach a remote shell, so they are checked first: letters, digits, space and . _ : , / -
# only. A bad value stops the deploy before anything is built or uploaded.
INSTALL_FLAGS=(GTP_INDEPENDENT_REFS GTP_KEEP_DHCP_NTP GTP_SDR GTP_SDR_1090_SERIAL GTP_SDR_978_SERIAL GTP_SDR_PPS_SERIAL GTP_WEBSDR GTP_WEBSDR_MAX_HOURS GTP_WEBSDR_PORT GTP_WEBSDR_SERIAL)
FLAG_VALUE='^[A-Za-z0-9 ._:,/-]{1,200}$'
ASSIGN=""
for name in "${INSTALL_FLAGS[@]}"; do
  value="${!name-}"
  [ -z "$value" ] && continue
  if ! [[ "$value" =~ $FLAG_VALUE ]]; then
    echo "$name has characters an install flag can't have (letters, digits, space and . _ : , / - only); deploy stopped, nothing built or uploaded." >&2
    exit 2
  fi
  ASSIGN+=" $name='$value'"
done
IGNORED=""
for name in $(compgen -e | grep '^GTP_' || true); do
  [ "$name" = GTP_DEPLOY_TTY ] && continue
  case " ${INSTALL_FLAGS[*]} " in *" $name "*) ;; *) IGNORED+=" $name" ;; esac
done
[ -n "$IGNORED" ] && echo "Not passed to install.sh (not install flags):$IGNORED"
INSTALL="sudo bash install.sh"
if [ -n "$ASSIGN" ]; then
  INSTALL="sudo env${ASSIGN} bash install.sh"
  echo "Install flags passed to the Pi:$ASSIGN"
fi

rm -f "$ARCHIVE"
# The bundle ships the built web UI (/app/). Build it from this checkout;
# build_bundles.py refuses a web/dist built from another version.
(cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run build)
python3 tools/build_bundles.py
[[ -s "$ARCHIVE" ]] || { echo "build did not produce $ARCHIVE" >&2; exit 1; }
if command -v sha256sum >/dev/null; then SHA="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
else SHA="$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')"; fi   # macOS
echo "Built $ARCHIVE (SHA-256 $SHA)"

ssh "$REMOTE" "rm -rf ~/$REMOTE_DIR && mkdir -m 0700 ~/$REMOTE_DIR"
scp "$ARCHIVE" "${REMOTE}:${REMOTE_DIR}/gps-time-pi-deploy.tar.gz"

# A remote terminal only when this script itself runs in one: sudo can then
# prompt, and install.sh shows the admin token on the terminal only, so
# redirected output never captures it. Without one, sudo must not need a password.
TTY_OPT=()
if [ -t 0 ] && [ -t 1 ]; then TTY_OPT=(-t); fi
# GTP_DEPLOY_TTY=1 or 0 overrides the detection (the tests use it).
case "${GTP_DEPLOY_TTY:-}" in 1) TTY_OPT=(-t) ;; 0) TTY_OPT=() ;; esac
ssh ${TTY_OPT[@]+"${TTY_OPT[@]}"} "$REMOTE" "set -e; cd ~/$REMOTE_DIR \
  && echo '$SHA  gps-time-pi-deploy.tar.gz' | sha256sum -c - \
  && tar -xzf gps-time-pi-deploy.tar.gz \
  && cd gps-time && $INSTALL"
echo "Open http://${HOST}/"
