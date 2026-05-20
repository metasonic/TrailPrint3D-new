# Build context: repo root (needed so COPY can reach scripts/ and TrailPrint3D/)
# Same image for both `api` and `worker` services; CMD differs in compose.

FROM python:3.11-slim

LABEL org.opencontainers.image.description="TrailPrint3D API + Celery worker"

# ── System deps required by Blender (headless) ───────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
        libegl1 libxkbcommon0 libxi6 \
        curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Blender (TrailPrint3D requires >= 4.5.0) ─────────────────────────────────
ARG BLENDER_VERSION=4.5.0
ARG BLENDER_MAJOR=4.5
RUN curl -fL \
      "https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
      | tar -xJ -C /opt \
    && ln -sf "/opt/blender-${BLENDER_VERSION}-linux-x64/blender" /usr/local/bin/blender \
    && blender --version

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app/backend

COPY backend/pyproject.toml backend/poetry.lock ./

RUN pip install --no-cache-dir "poetry==2.3.3" \
    && poetry config virtualenvs.create false \
    && poetry install --only=main --no-interaction --no-ansi \
    && pip uninstall -y poetry

# ── Application code ──────────────────────────────────────────────────────────
COPY backend/app/ ./app/

# Blender script and TrailPrint3D addon (used by the Celery worker)
COPY scripts/ /app/scripts/
COPY TrailPrint3D/ /app/TrailPrint3D/

RUN mkdir -p /app/output

# ── Runtime config ────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    OUTPUT_DIR=/app/output \
    BLENDER_EXECUTABLE=/usr/local/bin/blender \
    BLENDER_SCRIPT_PATH=/app/scripts/generate_terrain.py

EXPOSE 8000

# API default; override to `celery -A app.celery_app worker ...` for the worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
