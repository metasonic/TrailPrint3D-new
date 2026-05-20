#!/usr/bin/env bash
# Build all Docker images for the TrailPrint3D stack.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose build "$@"
