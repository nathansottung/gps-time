#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p .dev
export GTP_DEMO=1 GTP_PORT="${GTP_PORT:-8080}" GTP_BIND=127.0.0.1
export GTP_CONFIG="$ROOT/.dev/config.json"
export GTP_DASHBOARD_CONFIG="$ROOT/.dev/dashboard.json"
echo "GPS Time demo: http://127.0.0.1:${GTP_PORT}/"
python3 -m gps_time_pi.server
