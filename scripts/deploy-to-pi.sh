#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then echo "usage: $0 <pi-host> [pi-user] [--use-demo-layout]" >&2; exit 2; fi
HOST="$1"; USER_NAME="${2:-pi}"; USE_LAYOUT="${3:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "$USE_LAYOUT" == "--use-demo-layout" ]]; then python3 tools/promote_dashboard.py; fi
python3 tools/build_bundles.py
scp dist/gps-time-pi-deploy.tar.gz "${USER_NAME}@${HOST}:/tmp/gps-time-pi-deploy.tar.gz"
# A remote terminal only when this script itself runs in one: install.sh shows
# the admin token on the terminal only, so redirected output never captures it.
TTY_OPT=""
if [ -t 0 ] && [ -t 1 ]; then TTY_OPT="-t"; fi
ssh $TTY_OPT "${USER_NAME}@${HOST}" 'rm -rf ~/gps-time-deploy && mkdir -p ~/gps-time-deploy && tar -xzf /tmp/gps-time-pi-deploy.tar.gz -C ~/gps-time-deploy && cd ~/gps-time-deploy/gps-time && sudo bash install.sh'
echo "Open http://${HOST}/"
