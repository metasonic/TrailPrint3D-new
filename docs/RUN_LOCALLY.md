# TrailPrint3D Web Application - Local Setup & Resource Guide

This guide details how to run the TrailPrint3D self-hosted web application on your local machine and the hardware resources required to reliably generate 3D models.

## Resource Requirements

Generating 3D printable files from GPX tracks using headless Blender (`bpy`) is computationally demanding.

*   **Memory (RAM - Most Critical):** A minimum of **2GB RAM** is required for the background worker to process standard tracks. For high-resolution terrains or long, multi-day GPX tracks, a single job might spike to 3GB or 4GB. If you scale to multiple concurrent workers, you will need to multiply this requirement.
*   **CPU:** Mesh processing algorithms (Booleans, Decimation) are heavily reliant on single-core performance. A faster CPU will reduce generation time.
*   **Storage:** Generated output files (`.stl`, `.obj`, `.glb`) range from 5MB to 100MB+. Ensure you have sufficient disk space. An SSD is highly recommended to speed up large file writes and elevation data caching.
*   **Network:** The generation pipeline requires an active internet connection to fetch real-world elevation (DEM) and feature (OpenStreetMap) data based on the uploaded GPX coordinates.

**Recommended Baseline Server (Self-Hosted):** 2 vCPUs, 4GB RAM, 20GB SSD.

---

## How to Run Locally

You have two options for running the application locally: using Docker (Recommended) or Bare-Metal (for development).

### Method 1: Docker (Recommended)
Because headless Blender requires specific system graphics libraries (`libgl1`, `libx11`, etc.), Docker is the easiest and most reliable way to run the application on any operating system.

**Prerequisites:**
*   Docker and Docker Compose installed.

**Steps:**
1. Open your terminal in the root of the project.
2. Build and start the multi-container stack:
   `docker-compose up -d --build`
3. Open your browser and navigate to `http://localhost`.

*To stop the application later, run `docker-compose down`.*

### Method 2: Bare-Metal (For Development)
If you want to run the stack natively to make live code changes, you will need to run the services individually.

**Prerequisites:**
*   Python 3.11 (Required for `bpy==4.2.0`)
*   Node.js 20+
*   Redis server running locally on port 6379
*   *(Linux only)* System graphics libraries: `sudo apt install libgl1 libxi6 libxrender1 libxkbcommon0 libsm6`

**1. Start the Backend API**
Open a terminal, navigate to the `backend` folder:
```bash
cd backend
# Create a virtual environment using uv (or standard venv)
uv venv --python 3.11
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the dependencies
uv pip install -e . loguru python-multipart

# Start the FastAPI server
uvicorn trailprint3d_backend.main:app --reload
```
*The API will be available at `http://localhost:8000`*

**2. Start the Background Worker**
Open a **second** terminal, navigate to the `backend` folder, and activate the same environment:
```bash
cd backend
source .venv/bin/activate
python -m trailprint3d_backend.worker
```

**3. Start the Frontend**
Open a **third** terminal, navigate to the `frontend` folder:
```bash
cd frontend
npm install
npm run dev &
```
*The UI will be available at `http://localhost:4321` (check the terminal output for the exact port).*
