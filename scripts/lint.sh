#!/usr/bin/env bash
# Run all linters and type checks.
# Usage: scripts/lint.sh

set -euo pipefail
REPO="$(dirname "$0")/.."
PASS=true

echo "=== Frontend: TypeScript check ==="
cd "$REPO/frontend"
if npm run check; then
    echo "  ✓ Frontend types OK"
else
    echo "  ✗ Frontend type errors"
    PASS=false
fi

echo ""
echo "=== Backend: ruff (if installed) ==="
cd "$REPO/backend"
if command -v ruff &>/dev/null; then
    if ruff check app/; then
        echo "  ✓ ruff OK"
    else
        echo "  ✗ ruff errors"
        PASS=false
    fi
else
    echo "  (ruff not installed — skipping)"
fi

echo ""
if $PASS; then
    echo "All checks passed."
else
    echo "One or more checks failed." >&2
    exit 1
fi
