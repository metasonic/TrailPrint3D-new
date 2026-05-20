#!/usr/bin/env bash
# Start all services in detached mode.
# Usage: scripts/up.sh [--build]

set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d "$@"

echo ""
echo "Services started:"
echo "  Frontend → http://localhost"
echo "  API      → http://localhost:8000/api/v1/health"
echo ""
echo "Logs: docker compose logs -f"
echo "Stop: docker compose down"
