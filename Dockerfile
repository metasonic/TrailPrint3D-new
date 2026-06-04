FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV DATA_DIR=/data
ENV RENDER_THREADS=2

# Install required system dependencies for headless Blender (bpy)
RUN apt-get update && apt-get install -y \
    libx11-6 \
    libxrender1 \
    libxxf86vm1 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libsm6 \
    libgl1 \
    libegl1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement list and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set up required directories
RUN mkdir -p /data/uploads /data/outputs /data/cache

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
