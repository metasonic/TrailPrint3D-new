#!/bin/sh
set -e

# Ensure writable directories exist on mounted volumes (runs as root before privilege drop).
mkdir -p \
    /app/data/uploads \
    /app/data/preview \
    /app/data/exports \
    /app/data/jobs \
    /app/.cache/elevation \
    /app/.cache/tiles \
    /app/.cache/osm

# Fix ownership so appuser can write even if the Docker volume was created by root
chown -R appuser:appuser /app/data /app/.cache 2>/dev/null || true

# Drop privileges and exec the container command
exec gosu appuser "$@"
