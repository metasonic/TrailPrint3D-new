#!/usr/bin/env bash
# Run the Astro dev server (frontend). Listens on 0.0.0.0:4321.
set -euo pipefail
cd "$(dirname "$0")/.."/frontend
pnpm dev "$@"
