FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libx11-6 \
    libxrender1 \
    libxxf86vm1 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libsm6 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (using a recent version)
COPY --from=ghcr.io/astral-sh/uv:0.5.24 /uv /bin/uv

# Set up the application
WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
RUN uv venv --python 3.11
RUN uv sync --frozen --no-install-project

# Copy the actual app code
COPY TrailPrint3D/ ./TrailPrint3D/
COPY webapp.py .

EXPOSE 8000

CMD ["uv", "run", "python", "webapp.py"]
