#!/usr/bin/env bash
# Stop the processes started by scripts/dev-up.sh.
set -euo pipefail
if [[ ! -f /tmp/tp3d.pids ]]; then
    echo "[dev-down] no /tmp/tp3d.pids; nothing to stop"
    exit 0
fi
while read -r name pid; do
    if kill -0 "$pid" 2>/dev/null; then
        echo "[dev-down] stopping $name ($pid)"
        kill "$pid" 2>/dev/null || true
    fi
done < /tmp/tp3d.pids
rm -f /tmp/tp3d.pids
