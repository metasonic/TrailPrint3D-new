# TrailPrint3D Architecture & Audit Document

## 1. Audit Summary
The current TrailPrint3D addon heavily relies on `bpy` (Blender's Python API) and specifically `bpy.ops` (Blender operators). The core functionality involves complex 3D geometry manipulation:
- Creating custom objects (planes, bezier curves).
- Extensive use of Modifiers (Array, Solidify, Boolean, Displace) to shape the map elements.
- Extrusions and Boolean operations (intersect, difference) for creating boundaries and paths.
- Applying text meshes and materials.

Given the deeply embedded use of `bpy.ops` and the reliance on Blender's robust modifier stack, replacing this with pure Python geometry libraries (Option B) would be extremely time-consuming and error-prone, likely failing to reach 100% feature parity. Therefore, we must choose **Option A (Headless Blender)**.

## 2. Decision: Option A (Headless Blender)
We will run `bpy` (Blender as a Python module) in headless mode inside a Docker container.
- **Engine**: Python 3.11 with `bpy==5.0.1` installed as a module.
- **Architecture**: A FastAPI application will receive web requests, queue them, and execute the blender scripting using the existing (but refactored) logic.
- **Advantages**: Perfect feature parity, full access to Blender modifiers and exports.
- **Challenges**: Cold start and image size are mitigated by building a streamlined docker image with necessary X11 dependencies.

## 3. Environment Variable Schema
The application requires several configuration points managed by environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ELEVATION_API_KEY` | OpenTopography API Key (if needed) | `""` |
| `DATA_DIR` | Directory for storing cache, inputs, and outputs | `/data` |
| `MAX_UPLOAD_MB` | Maximum size for GPX uploads | `10` |
| `RENDER_THREADS` | Concurrency limit for background bpy workers | `2` |
| `PORT` | Web server port | `8000` |
| `OPENTOPODATA_URL` | URL for OpenTopoData API (self-hosted option) | `""` |

## 4. API Contract

The system will expose the following REST endpoints via FastAPI:

### `POST /upload`
- **Request**: `multipart/form-data` with file field `gpx_file`.
- **Response**: JSON containing an `id` for the uploaded session.

### `POST /preview`
- **Request**: JSON specifying `id` and base settings (shape, scale, etc.).
- **Response**: Returns a fast, lower-resolution JSON/Mesh preview, or initiates a background task returning a tracking ID.

### `POST /generate`
- **Request**: JSON specifying `id` and full generation settings (base shape, frame, coloring, multi-color segmentation).
- **Response**: JSON containing a `job_id`.

### `GET /download/{job_id}`
- **Request**: Path param `job_id` and query param `format` (stl, obj, 3mf).
- **Response**: A file download of the generated 3D map.

### `GET /formats`
- **Request**: None.
- **Response**: JSON list of supported formats `["stl", "obj", "3mf"]`.
