#!/usr/bin/env bash
# Run the Python test suite. Phase 3: just import smoke + Pydantic validation.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run pytest -q "$@"
