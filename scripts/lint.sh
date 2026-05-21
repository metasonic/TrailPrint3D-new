#!/usr/bin/env bash
# Lint and type-check the Python source.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run ruff check backend pipeline tests
poetry run ruff format --check backend pipeline tests
poetry run mypy backend pipeline
