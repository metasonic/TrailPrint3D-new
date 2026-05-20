# syntax=docker/dockerfile:1.7
#
# Backend + Worker image. Both services share this image; the compose file
# overrides `command` for the worker. System deps: gdal-bin (the elevation
# Python package shells out to gdal_translate) and libspatialindex (rtree,
# used by trimesh's ray spatial index) — logged in MEMORY.md Phase 4.

FROM python:3.11.10-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libspatialindex-dev \
        gdal-bin \
        libgdal-dev \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Optional: trust additional CAs (corporate TLS-inspecting proxies, etc).
# Empty docker/extra-cas/ is a no-op; see docker/extra-cas/README.md.
COPY docker/extra-cas/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root


FROM python:3.11.10-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libspatialindex-c6 \
        ca-certificates \
        make \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

COPY docker/extra-cas/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY backend ./backend
COPY pipeline ./pipeline

RUN mkdir -p /app/output /app/elevation_cache \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Backend default; worker overrides via compose.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
