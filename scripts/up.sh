#!/usr/bin/env bash
# Start the full TrailPrint3D stack. Pass --build to rebuild images first.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d "$@"
echo
echo "Stack is up."
echo "  UI:        http://localhost:${TP3D_PORT:-8080}/"
echo "  API:       http://localhost:${TP3D_PORT:-8080}/api/v1/health"
echo "  Logs:      scripts/logs.sh"
echo "  Stop:      scripts/down.sh"
