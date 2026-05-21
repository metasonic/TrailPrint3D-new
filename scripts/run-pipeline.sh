#!/usr/bin/env bash
# Phase 4 CLI runner: invoke pipeline.generate.generate() directly on a GPX file.
# Usage: scripts/run-pipeline.sh <gpx> [glb|stl|obj|3mf] [preview|export]
set -euo pipefail
cd "$(dirname "$0")/.."

GPX="${1:-Cluj_Eco_Trail.gpx}"
FMT="${2:-glb}"
MODE="${3:-preview}"
OUT="${OUT:-$PWD/.dev-output/cli-$MODE.$FMT}"

export OUTPUT_DIR="${OUTPUT_DIR:-$PWD/.dev-output}"
export ELEVATION_CACHE_DIR="${ELEVATION_CACHE_DIR:-$PWD/.dev-elevation-cache}"
mkdir -p "$OUTPUT_DIR" "$ELEVATION_CACHE_DIR"

poetry run python -c "
import logging, sys
from pathlib import Path
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
from backend.app.models import GenerateSettings
from pipeline.generate import generate

settings = GenerateSettings()
result = generate(
    gpx_path=Path('${GPX}'),
    settings=settings,
    output_path=Path('${OUT}'),
    mode='${MODE}',
    export_format='${FMT}',
)
print('OK')
print(result.model_dump_json(indent=2))
"
