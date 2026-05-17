# TrailPrint3D Web Application

This repository contains the web application version of the [TrailPrint3D](https://github.com/EmGi96/TrailPrint3D) Blender addon. It allows you to self-host a web service that takes GPX files and generates 3D printable miniature map models (STL, OBJ, 3MF) using headless Blender.

## Architecture

*   **Frontend**: Astro 6 + React + TailwindCSS + React Three Fiber.
*   **Backend**: FastAPI orchestrating Python background jobs.
*   **Queue**: RQ + Redis to handle heavy 3D rendering jobs.
*   **3D Engine**: Python `bpy==5.0.1` (Headless Blender) running natively.

## Prerequisites

*   Docker and Docker Compose

## Quick Start (Self-Hosted)

1.  Clone this repository.
2.  Start the multi-container stack:
    `docker-compose up -d --build`
3.  Open your browser to `http://localhost`.

## Configuration Environment Variables

You can configure the application by modifying the `docker-compose.yml` or creating a `.env` file.

### Backend Options
| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Connection string for the Redis task queue. |
| `UPLOAD_DIR` | `/data/uploads` | Path to the directory where user GPX uploads are stored. |
| `OUTPUT_DIR` | `/data/outputs` | Path to the directory where generated 3D meshes (GLB, STL, OBJ) are stored. |
| `ELEVATION_API_URL` | *(optional)* | URL to a self-hosted elevation API if you don't want to use the public default. |
| `OPENTOPOGRAPHY_KEY` | *(optional)* | API key for high-res OpenTopography data. |

### Frontend Options
| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | The URL of the FastAPI backend. Used by the browser to fetch data. |

## Data Persistence

The docker-compose configuration mounts two named volumes:
*   `redis_data`: Keeps your job queue states intact across restarts.
*   `app_data`: Stores the uploaded GPX files and generated 3D meshes. You may want to configure a cron job to clean up `/data/outputs` periodically if disk space is a concern.
