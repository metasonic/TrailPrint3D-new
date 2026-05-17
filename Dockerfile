# ─────────────────────────────────────────────────────────────────
#  Stage 1 – Frontend build
# ─────────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─────────────────────────────────────────────────────────────────
#  Stage 2 – Base: Ubuntu + Blender 4.5 + system deps
# ─────────────────────────────────────────────────────────────────
FROM ubuntu:22.04 AS blender-base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget xz-utils ca-certificates \
        libxi6 libxxf86vm1 libxfixes3 libxrender1 \
        libgl1-mesa-glx libgles2-mesa libegl1-mesa \
        libglib2.0-0 libsm6 libxext6 \
        xvfb x11-utils \
        python3.11 python3-pip \
        curl \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Download and install Blender 4.5
ARG BLENDER_VERSION=4.5.0
ARG BLENDER_ARCHIVE=blender-${BLENDER_VERSION}-linux-x64
RUN wget -q "https://download.blender.org/release/Blender4.5/${BLENDER_ARCHIVE}.tar.xz" \
        -O /tmp/blender.tar.xz \
    && tar -xf /tmp/blender.tar.xz -C /opt/ \
    && mv /opt/${BLENDER_ARCHIVE} /opt/blender \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && rm /tmp/blender.tar.xz

# Install Python deps into Blender's bundled Python
RUN /opt/blender/${BLENDER_VERSION}/python/bin/python3.11 -m ensurepip --upgrade && \
    /opt/blender/${BLENDER_VERSION}/python/bin/python3.11 -m pip install --upgrade pip && \
    /opt/blender/${BLENDER_VERSION}/python/bin/python3.11 -m pip install requests

# Install the io_mesh_3mf (3MF) extension for Blender
# Run Blender once headlessly to trigger extension setup
RUN Xvfb :99 -screen 0 1280x720x24 & \
    sleep 2 && DISPLAY=:99 \
    blender --background --python-expr \
        "import bpy; bpy.ops.extensions.repo_refresh_all(); print('Blender init OK')" \
    || true

# ─────────────────────────────────────────────────────────────────
#  Stage 3 – App (FastAPI web server)
# ─────────────────────────────────────────────────────────────────
FROM blender-base AS app
WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY TrailPrint3D/ ./TrailPrint3D/
COPY blender/ ./blender/
COPY backend/ ./backend/

# Copy frontend build
COPY --from=frontend-build /build/dist ./frontend/dist

# Create data directories
RUN mkdir -p /data/uploads /data/outputs /data/cache /data/presets

ENV PYTHONPATH=/app
ENV TP3D_DATA_DIR=/data
ENV TP3D_UPLOAD_DIR=/data/uploads
ENV TP3D_OUTPUT_DIR=/data/outputs
ENV BLENDER_PATH=/usr/local/bin/blender
ENV BLENDER_ADDON_DIR=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# ─────────────────────────────────────────────────────────────────
#  Stage 4 – Worker (Celery + Blender headless)
# ─────────────────────────────────────────────────────────────────
FROM blender-base AS worker
WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY TrailPrint3D/ ./TrailPrint3D/
COPY blender/ ./blender/
COPY backend/ ./backend/

# Create data directories
RUN mkdir -p /data/uploads /data/outputs /data/cache /data/presets

ENV PYTHONPATH=/app
ENV TP3D_DATA_DIR=/data
ENV TP3D_UPLOAD_DIR=/data/uploads
ENV TP3D_OUTPUT_DIR=/data/outputs
ENV BLENDER_PATH=/usr/local/bin/blender
ENV BLENDER_ADDON_DIR=/app
ENV TP3D_HEADLESS=1

# Default command (overridden by docker-compose)
CMD ["celery", "-A", "backend.app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
