#!/usr/bin/env bash
# Build all Docker images.
# Usage: scripts/build.sh [--no-cache] [extra docker compose build args]

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Building TrailPrint3D Docker images ==="
docker compose build "$@"
echo ""
echo "Build complete. Run scripts/up.sh to start services."
