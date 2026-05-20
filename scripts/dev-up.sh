#!/usr/bin/env bash
# Boot Redis + FastAPI + Celery worker locally for ad-hoc curl testing.
# All three run as background processes; PIDs go in /tmp/tp3d.pids.
# Use scripts/dev-down.sh to stop them.
set -euo pipefail
cd "$(dirname "$0")/.."

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export OUTPUT_DIR="${OUTPUT_DIR:-$PWD/.dev-output}"
export ELEVATION_CACHE_DIR="${ELEVATION_CACHE_DIR:-$PWD/.dev-elevation-cache}"
mkdir -p "$OUTPUT_DIR" "$ELEVATION_CACHE_DIR" .dev-logs

: > /tmp/tp3d.pids

echo "[dev-up] starting redis-server on 127.0.0.1:6379"
redis-server --port 6379 --bind 127.0.0.1 --daemonize no \
    --logfile "$PWD/.dev-logs/redis.log" >/dev/null 2>&1 &
echo "redis $!" >> /tmp/tp3d.pids
sleep 0.5

echo "[dev-up] starting FastAPI on 127.0.0.1:8000"
poetry run uvicorn backend.app.main:app \
    --host 127.0.0.1 --port 8000 --log-level info \
    >".dev-logs/backend.log" 2>&1 &
echo "backend $!" >> /tmp/tp3d.pids

echo "[dev-up] starting Celery worker (solo pool, 1 process)"
poetry run celery -A backend.app.celery_app.celery_app worker \
    --loglevel=info --pool=solo \
    >".dev-logs/worker.log" 2>&1 &
echo "worker $!" >> /tmp/tp3d.pids

sleep 1
echo "[dev-up] done. Logs in .dev-logs/. Stop with scripts/dev-down.sh"
