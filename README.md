# TrailPrint3D Web Application

This project converts the TrailPrint3D Blender Plugin into a standalone headless Python web application. It runs a web server inside a Docker container, taking a GPX file and map configuration as input, generating a 3D printable map via headless Blender (`bpy`), and returning a ZIP file with the generated STLs.

## Features Exposed
- **GPX Upload:** Accepts GPX tracks.
- **Map Shape:** Hexagon, Square, Circle.
- **Map Size & Thickness:** Configure the 3D model footprint.
- **Single Color Mode:** Optimizes output for single extruder printers by applying booleans on overlapping features.
- **Geographical Data:** Includes options for water features and roads (OpenStreetMap data fetched dynamically).
- **Scale Configurations:** Adjustable vertical elevation scale multiplier.

## Running the Web App locally

First install `uv` (Fast Python package installer).

```bash
uv venv --python 3.11
source .venv/bin/activate
uv sync
uv run python webapp.py
```

Then visit `http://localhost:8000` in your web browser.

## Running with Docker

```bash
docker build -t trailprint3d .
docker run -p 8000:8000 trailprint3d
```
