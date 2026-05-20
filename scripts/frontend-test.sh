#!/usr/bin/env bash
# Run frontend tests (Vitest) + Astro type check.
set -euo pipefail
cd "$(dirname "$0")/.."/frontend
pnpm test "$@"
pnpm check
