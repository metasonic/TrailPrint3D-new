#!/usr/bin/env bash
# End-to-end smoke test for Phase 3: /health, POST /preview, GET /jobs/{id}.
#
# Phase 3 expectation: the pipeline stub raises NotImplementedError, so the
# enqueued job transitions pending → processing → failed. That is the correct
# Phase 3 demonstration — job plumbing works end-to-end; Phase 4 makes the
# job actually succeed.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="${BASE:-http://127.0.0.1:8000}"
GPX="${GPX:-Cluj_Eco_Trail.gpx}"

echo "[smoke] GET $BASE/api/v1/health"
curl -fsS "$BASE/api/v1/health" | tee /tmp/tp3d.health.json
echo

if ! grep -q '"redis":true' /tmp/tp3d.health.json; then
    echo "[smoke] redis is down — start it with scripts/dev-up.sh" >&2
    exit 1
fi
if ! grep -q '"celery":true' /tmp/tp3d.health.json; then
    echo "[smoke] celery worker is down — start it with scripts/dev-up.sh" >&2
    exit 1
fi

SETTINGS='{"shape":"hexagon","terrain_scale":1.0,"track_thickness_mm":1.2,"frame_thickness_mm":5.0,"bbox_padding_percent":0.1}'

echo "[smoke] POST $BASE/api/v1/preview (file=$GPX)"
RESP=$(curl -fsS -X POST "$BASE/api/v1/preview" \
    -F "file=@${GPX}" \
    -F "settings=${SETTINGS}")
echo "$RESP"
JOB_ID=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
echo "[smoke] enqueued job_id=$JOB_ID"

# Poll up to 15 times (~15s)
for i in $(seq 1 15); do
    STATUS_JSON=$(curl -fsS "$BASE/api/v1/jobs/$JOB_ID")
    STATUS=$(printf '%s' "$STATUS_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
    printf '[smoke] poll %d/15: status=%s\n' "$i" "$STATUS"
    if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
        echo "$STATUS_JSON"
        break
    fi
    sleep 1
done

if [[ "$STATUS" == "failed" ]]; then
    echo "[smoke] job failed (expected in Phase 3 — pipeline.generate is a stub)"
    echo "[smoke] OK"
    exit 0
fi
if [[ "$STATUS" == "completed" ]]; then
    echo "[smoke] job completed (unexpected in Phase 3 but not an error)"
    echo "[smoke] OK"
    exit 0
fi
echo "[smoke] job never reached terminal state" >&2
exit 1
