# ── Stage 1: download Blender ──────────────────────────────────────────────
FROM python:3.12-slim AS blender-fetcher

RUN apt-get update && apt-get install -y --no-install-recommends wget xz-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG BLENDER_VERSION=4.5.0
ARG BLENDER_ARCH=linux-x64
# SHA256 of blender-4.5.0-linux-x64.tar.xz — update when upgrading Blender.
# Verify: sha256sum blender-<version>-linux-x64.tar.xz
ARG BLENDER_SHA256=""

RUN wget -q "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-${BLENDER_ARCH}.tar.xz" \
    -O /tmp/blender.tar.xz \
    && if [ -n "${BLENDER_SHA256}" ]; then \
         echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - || exit 1; \
       fi \
    && mkdir -p /opt/blender \
    && tar -xf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
    && rm /tmp/blender.tar.xz

# Install TrailPrint3D addon into Blender's extension path
COPY TrailPrint3D /opt/blender/4.5/extensions/user_default/TrailPrint3D

# ── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM python:3.12-slim

# System deps for headless Blender (OpenGL stub, X11-xcb)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libx11-xcb1 \
    libxi6 \
    libxxf86vm1 \
    libxfixes3 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=blender-fetcher /opt/blender /opt/blender
ENV PATH="/opt/blender:${PATH}"

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY TrailPrint3D/ ./TrailPrint3D/

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED="1"

# Run as non-root for security
RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
