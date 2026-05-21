#!/usr/bin/env bash
# Tail logs from one or all services.
# Usage: scripts/logs.sh                  # all services
#        scripts/logs.sh backend worker   # specific services
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose logs -f --tail=200 "$@"
