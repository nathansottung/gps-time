#!/usr/bin/env bash
# Build the Pi bundle, upload it, verify it on the Pi, install. Stops at the
# first failure (review GPS-021): a failed build never uploads an old archive,
# and install.sh never runs on an archive whose SHA-256 doesn't match.
set -euo pipefail
if [[ $# -lt 1 ]]; then echo "usage: $0 <pi-host> [pi-user] [--use-demo-layout]" >&2; exit 2; fi
HOST="$1"; USER_NAME="${2:-pi}"; USE_LAYOUT="${3:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REMOTE="${USER_NAME}@${HOST}"
ARCHIVE="dist/gps-time-pi-deploy.tar.gz"
# Upload into a fresh directory in the remote user's home, not a fixed /tmp name.
REMOTE_DIR="gps-time-deploy"

if [[ "$USE_LAYOUT" == "--use-demo-layout" ]]; then python3 tools/promote_dashboard.py; fi
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
ssh ${TTY_OPT[@]+"${TTY_OPT[@]}"} "$REMOTE" "set -e; cd ~/$REMOTE_DIR \
  && echo '$SHA  gps-time-pi-deploy.tar.gz' | sha256sum -c - \
  && tar -xzf gps-time-pi-deploy.tar.gz \
  && cd gps-time && sudo bash install.sh"
echo "Open http://${HOST}/"
