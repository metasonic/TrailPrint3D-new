#!/usr/bin/env bash
# Build the Astro app for production. Output: frontend/dist/.
set -euo pipefail
cd "$(dirname "$0")/.."/frontend
pnpm build "$@"
