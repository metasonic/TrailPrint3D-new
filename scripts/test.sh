#!/usr/bin/env bash
# Run the backend test suite.
# Usage: scripts/test.sh [pytest args]

set -euo pipefail
cd "$(dirname "$0")/../backend"

echo "=== Backend tests ==="
python -m pytest "$@"
