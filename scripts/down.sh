#!/usr/bin/env bash
# Stop the TrailPrint3D stack. Pass -v to also drop the named volumes.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down "$@"
