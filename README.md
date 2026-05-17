# TrailPrint3D — Web Application

Convert any GPX or IGC trail file into a 3D-printable terrain mesh — all in a browser.  
Self-hosted, no cloud lock-in, export to STL / OBJ / 3MF.

> **Original Blender addon**: [TrailPrint3D.com](https://www.trailprint3d.com)

---

## Architecture

```
┌──────────────┐       POST /api/upload, /api/preview, /api/export
│  Astro 6     │ ──────────────────────────────────────────────────►
│  Three.js    │                                                    │
│  React island│ ◄── GLB (glTF binary for Three.js preview) ───────┤
└──────────────┘                                                    │
                                         ┌────────────────────────  ▼ ──────────────────────────┐
                                         │               FastAPI Backend                        │
                                         │                                                      │
                                         │  Quick Preview (pure Python, < 15 s)                 │
                                         │   gpx_parser → geo → elevation → trimesh → GLB       │
                                         │                                                      │
                                         │  Final Export (headless Blender, < 120 s)            │
                                         │   Celery → blender --background → STL / OBJ / 3MF   │
                                         └──────────────────────────────────────────────────────┘
```

**Two processing modes:**

| Mode | Trigger | Engine | Output | Target time |
|------|---------|--------|--------|-------------|
| Quick Preview | Settings change | Pure Python (numpy + trimesh) | GLB | < 15 s |
| Final Export | Export button | Headless Blender 4.5 | STL / OBJ / 3MF | < 120 s |

---

## Quick Start (Docker Compose)

```bash
git clone https://github.com/metasonic/trailprint3d-new
cd trailprint3d-new
cp .env.example .env
docker compose up --build
```

Open **http://localhost:3000** in your browser.

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_API_URL` | `http://localhost:8000` | Backend URL as seen by the browser |
| `REDIS_URL` | `redis://redis:6379/0` | Celery/job-queue broker |
| `OUTPUT_DIR` | `/app/data` | Uploaded files, previews, exports |
| `CACHE_DIR` | `/app/.cache` | Elevation tiles, OSM, elevation cache |
| `BLENDER_EXECUTABLE_PATH` | `/opt/blender/blender` | Path to Blender 4.5+ binary |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum GPX file size |
| `ELEVATION_DATA_SOURCE` | `TERRAIN-TILES` | Default elevation API (see below) |
| `TERRAIN_RESOLUTION` | `4` | Default `num_subdivisions` (1–8) |
| `OPENTOPODATA_URL` | `https://api.opentopodata.org/v1/` | Can point to self-hosted instance |
| `OPENTOPOGRAPHY_API_KEY` | _(empty)_ | Required only for OpenTopography API |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Can point to self-hosted Overpass |
| `CACHE_MAX_AGE_HOURS` | `720` | How long OSM/elevation cache is reused |

### Elevation API options

| Value | Speed | Coverage | Key required |
|-------|-------|----------|-------------|
| `TERRAIN-TILES` | ★★★ Fastest | Global | No |
| `OPENTOPODATA` | ★★ | Global (dataset-dependent) | No (rate limited) |
| `OPEN-ELEVATION` | ★★ | Global | No (rate limited) |
| `OPENTOPOGRAPHY` | ★★ | Global, high-res | Yes (free) |

---

## Development Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```bash
python -m pytest backend/tests/ -v
```

Start Celery worker (requires Redis):

```bash
celery -A backend.tasks.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload a GPX/IGC file; returns `file_id` + track stats |
| `POST` | `/api/preview` | Generate a GLB preview; returns URL |
| `GET` | `/api/preview/{filename}` | Serve the GLB binary |
| `POST` | `/api/export` | Queue a full export; returns `job_id` |
| `GET` | `/api/job/{job_id}` | Poll job status and progress |
| `GET` | `/api/download/{job_id}/{filename}` | Download the finished file |
| `GET` | `/health` | Health check |

---

## Supported Features

| Feature | Preview | Export |
|---------|---------|--------|
| GPX / IGC parsing | ✓ | ✓ |
| Terrain elevation (4 APIs) | ✓ | ✓ |
| Shape: Hex / Circle / Square / Octagon / Ellipse / Heart | ✓ | ✓ |
| Elevation scale | ✓ | ✓ |
| Trail extrusion | ✓ | ✓ |
| OSM water / forests / roads / buildings | — | ✓ |
| Frame / plate / text labels | — | ✓ |
| STL export | — | ✓ |
| OBJ export (with materials) | — | ✓ |
| 3MF export | — | ✓ |

---

## Data Attribution

- **Elevation**: [Terrain Tiles / Amazon](https://registry.opendata.aws/terrain-tiles/) · [OpenTopoData](https://www.opentopodata.org/) · [Open-Elevation](https://open-elevation.com/) · [OpenTopography](https://opentopography.org/)
- **OSM features**: © [OpenStreetMap](https://openstreetmap.org/copyright) contributors (ODbL)
- **3D generation**: [TrailPrint3D](https://github.com/EmGi96/TrailPrint3D) by EmGi (GPL-3.0)

Generated 3D models are **commercially usable** under the TrailPrint3D license.

[Slightly outdated Video Tutorial](https://www.youtube.com/watch?v=2NzwC3188HY&t=242s)

## Features

### Map Generation
- Import a GPX file and generate a 3D map around your trail
- Three generation modes: **Single Trail**, **Multi-Trail chain** *(Premium)*, **Terrain** *(Premium)*
- Terrain generation from custom map bounds (center + radius, two corner points, or a blank tile)
- Configurable shape: circle, square (with independent width/height), ellipse (with aspect ratio), hexagon, octagon, medal
- Elevation scaling, path thickness, and single-color-mode for clean single-material prints

### Terrain Elements
Automatically fetches and renders geographic data from OpenStreetMap:
- Water (ponds, small rivers, big rivers)
- Ocean
- Forests, Scree, Glaciers
- Farmland, Greenspaces
- City boundaries
- Buildings (3D, experimental)
- Roads (major, primary, and small streets)

### Post-Processing
- **Color Mountains** — assigns material zones by elevation threshold
- **Contour Lines** — adds printable contour line geometry
- **Magnet Holes** — drills holes for magnets (configurable diameter/depth)
- **Dovetail Cutouts** — adds dovetail joints for tiling maps
- **Bottom Mark** — engraves a mark on the bottom face
- **SVG / Text Import** — imports SVG outlines or custom text as 3D objects
- **Pin Placement** — places a pin at GPS coordinates; pin on city name *(Premium)*
- **Heightmap Import** *(Premium)* — imports a 2D image as a heightmap


### Export
- Export to **STL**, **OBJ**, and **3MF** (3mf is using the [3MF Addon by Clonephaze](https://github.com/Clonephaze/3MF-Blender-Add-on---Maintained))
- Configurable default export folder in addon preferences
- Optional auto-export after generation


## Requirements

- Blender **4.5** or newer (Version 5.1 recommended for best stability)
- Internet connection for elevation and map data APIs
- (Optional) OpenTopography API key — free at [portal.opentopography.org](https://portal.opentopography.org)
- (Optional) [3MF Addon by Clonephaze](https://github.com/Clonephaze/3MF-Blender-Add-on---Maintained) for 3MF export

## Installation

1. Download the latest release zip (or from https://trailprint3d.com).
2. In Blender, go to **Edit → Preferences → Add-ons → Install**.
3. Select the downloaded zip and enable **TrailPrint3D**.
4. If not visible, Press "N" on your Keyboard to open the Sidebar. Navigate to the
   TrailPrint3D Tab in the Sidebar

Video Tutorial for the Installation:
https://youtu.be/qfpxZbYOvvk


## Data Sources

| Data | Provider | Used for |
| Elevation (SRTM & others) | [OpenTopoData](https://www.opentopodata.org) | Terrain height |
| Elevation (SRTM/NASA) | [Open-Elevation](https://open-elevation.com) | Terrain height |
| Elevation tiles | [Terrain Tiles / Mapzen](https://registry.opendata.aws/terrain-tiles/) | Terrain height |
| Elevation (high-res datasets) | [OpenTopography](https://opentopography.org) | Terrain height (API key required) |
| Water, forests, roads, buildings, cities | [Overpass API](https://overpass-api.de) | Map elements |
| Geographic data | [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) | Underlying map data |

## License

Copyright (C) 2026 EmGi.
Released under the [GNU General Public License](https://www.gnu.org/licenses/gpl-3.0.html).
Models generated by this addon may be used commercially.
