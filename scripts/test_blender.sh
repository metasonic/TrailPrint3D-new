#!/usr/bin/env bash
# test_blender.sh — smoke-test the headless Blender pipeline
#
# Usage:
#   scripts/test_blender.sh [--blender /path/to/blender]
#
# Requires BLENDER env var or --blender flag pointing to the Blender executable.
# Exits 0 on success, non-zero on failure.

set -euo pipefail

BLENDER="${BLENDER:-blender}"
FIXTURE_GPX="$(dirname "$0")/../TrailPrint3D/fixtures/Cluj_Eco_Trail.gpx"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --blender) BLENDER="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if ! command -v "$BLENDER" &>/dev/null; then
    echo "ERROR: blender not found at '$BLENDER'" >&2
    echo "Set BLENDER env var or pass --blender /path/to/blender" >&2
    exit 1
fi

if [[ ! -f "$FIXTURE_GPX" ]]; then
    echo "ERROR: fixture GPX not found: $FIXTURE_GPX" >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

SETTINGS_FILE="$WORKDIR/settings.json"
OUTPUT_FILE="$WORKDIR/output.glb"

cat > "$SETTINGS_FILE" <<'JSON'
{
  "obj_size": 80,
  "num_subdivisions": 2,
  "shape": "hexagon",
  "elevation_api": "mapzen",
  "water_ponds": false,
  "water_small_rivers": false,
  "water_big_rivers": false,
  "forests": false,
  "buildings": false,
  "roads_major": false,
  "roads_medium": false,
  "roads_minor": false,
  "city_boundaries": false,
  "greenspace": false
}
JSON

echo "=== Running headless Blender generation ==="
echo "GPX:    $FIXTURE_GPX"
echo "Output: $OUTPUT_FILE"
echo ""

"$BLENDER" --background --python "$(dirname "$0")/generate_terrain.py" -- \
    --gpx      "$FIXTURE_GPX" \
    --settings "$SETTINGS_FILE" \
    --output   "$OUTPUT_FILE" \
    --mode     preview \
    --format   glb

if [[ ! -f "$OUTPUT_FILE" ]]; then
    echo "FAIL: output file was not created" >&2
    exit 1
fi

SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || stat -f%z "$OUTPUT_FILE")
if [[ "$SIZE" -lt 1024 ]]; then
    echo "FAIL: output file is suspiciously small ($SIZE bytes)" >&2
    exit 1
fi

echo ""
echo "PASS: $OUTPUT_FILE ($SIZE bytes)"
