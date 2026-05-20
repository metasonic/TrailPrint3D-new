# MEMORY.md — TrailPrint3D Web Conversion

## Project Overview
Converting the TrailPrint3D Blender addon into a self-hosted web application.
- Frontend: Astro 6, TypeScript, Tailwind CSS, Three.js
- Backend: FastAPI, Python 3.11+, Celery + Redis
- Export Engine: Headless Blender via subprocess
- Deployment: Docker Compose

---

## Session Log

### Session 1 — 2026-05-20

**Repository confirmed present**: `/home/user/TrailPrint3D-new`
- Addon source: `TrailPrint3D/`
- Test GPX fixture available: `Cluj_Eco_Trail.gpx`
- MEMORY.md and ERRORS.md created this session.

**Mandatory Q&A — answered 2026-05-20**

| # | Question | Answer |
|---|----------|--------|
| Q1 | Preview engine | Headless Blender (same pipeline for preview + export, 5–15s latency accepted) |
| Q2 | Test fixture | Use `Cluj_Eco_Trail.gpx` already in repo |
| Q3 | UI design approach | Tailwind design tokens defined in code (no Figma dependency) |
| Q4 | Job state persistence | Ephemeral Redis-backed Celery results; loss on Redis restart accepted |

---

### Decision — Preview Engine (2026-05-20)
- **Decided**: Use headless Blender for both preview and export jobs.
- **Why**: Guarantees visual parity between preview and final export. Simplest single pipeline.
- **Rejected**: Custom Python preview engine.
- **Rejected Why**: Faster but risks visual mismatch with Blender-exported model; adds maintenance burden of a second renderer.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — Test GPX Fixture (2026-05-20)
- **Decided**: `Cluj_Eco_Trail.gpx` (present in repo root) is the standard integration test fixture.
- **Why**: Already available, no additional setup.
- **Rejected**: User-supplied fixture.
- **Rejected Why**: Not needed; existing file is sufficient.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — UI Design Approach (2026-05-20)
- **Decided**: Define Tailwind design tokens (colors, spacing, type scale) directly in `tailwind.config` and build UI iteratively.
- **Why**: No external tooling dependency, unblocks Phase 5 immediately.
- **Rejected**: Wait for Figma specifications.
- **Rejected Why**: Blocks Phase 5 with no concrete ETA for designer deliverables.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — Job State Persistence (2026-05-20)
- **Decided**: Ephemeral Redis-backed Celery results only; no database for job history.
- **Why**: Simpler stack, fewer services, matches project constraint of ephemeral-by-design storage.
- **Rejected**: SQLite or PostgreSQL for persistent job history.
- **Rejected Why**: Not requested; adds complexity without confirmed requirement.
- **Flagged By**: Integration Lead
- **Confidence**: High

---

---

## Phase 1 Analysis — Repository Map (2026-05-20)

### File inventory

| File | Role | Headless viable? | Notes |
|------|------|-----------------|-------|
| `TrailPrint3D/__init__.py` | Addon registration, startup hooks | Not needed | Use individual modules directly |
| `TrailPrint3D/props.py` | All 60+ user-adjustable scene properties | Replaceable | Values injected from JSON settings dict |
| `TrailPrint3D/operators.py` | Blender operator wrappers | Not needed | Operators call `utils.*` functions; call those directly |
| `TrailPrint3D/panels.py` | GUI panel layouts | Not needed | Web UI replaces this |
| `TrailPrint3D/export.py` | STL/OBJ/3MF export, 3MF thumbnail | Partial | Export fns headless ✓; `customThumbnail()` **GUI-only** — skip |
| `TrailPrint3D/utils/io_gpx.py` | GPX/IGC parsing | ✓ Yes | Uses stdlib xml.etree only; one `bpy.context` write to remove |
| `TrailPrint3D/utils/elevation.py` | AWS Terrarium tiles, OpenTopoData, OpenTopography | ✓ Yes | All HTTP via `requests`; reads `bpy.context.scene.tp3d.*` for settings |
| `TrailPrint3D/utils/geo.py` | Mercator projection, haversine, scale | ✓ Yes | Pure math; reads scale vars from scene props |
| `TrailPrint3D/utils/generation.py` | `runGeneration()` master orchestrator | ✓ With guards | See blocker list below |
| `TrailPrint3D/utils/terrain.py` | `coloring_main()`, ocean, contour lines | ✓ With guards | Boolean ops work headlessly |
| `TrailPrint3D/utils/osm.py` | Overpass API, buildings, roads | ✓ Yes | Pure HTTP + bmesh |
| `TrailPrint3D/utils/mesh_ops.py` | bmesh booleans, raycasting, normal ops | ✓ Yes | No GUI dependency |
| `TrailPrint3D/utils/primitives.py` | Hexagon/circle/rectangle mesh creation | ✓ Yes | Pure bmesh |
| `TrailPrint3D/utils/scene.py` | Camera zoom, object cleanup, message boxes | Partial | `zoom_camera_to_selected()` / `show_message_box()` **GUI-only** — guard |
| `TrailPrint3D/utils/geo.py` | Coordinate conversion, scale math | ✓ Yes | |
| `TrailPrint3D/utils/presets.py` | CSV preset load/save | Not needed | |
| `TrailPrint3D/utils/metadata.py` | Custom property tags on objects | ✓ Yes | Useful for identifying objects post-generation |
| `TrailPrint3D/utils/text_objects.py` | HexagonOuterText, InnerText, etc. | Optional | Only needed for text-shape modes |
| `TrailPrint3D/constants.py` | Size thresholds, cache paths | ✓ Yes | Cache paths need redirecting to `OUTPUT_DIR` |
| `TrailPrint3D/progress.py` | GUI progress overlay (HTML web panel) | Not needed | Stub out; logging replaces it |
| `TrailPrint3D/addon_preferences.py` | Blender preferences UI | Not needed | API keys pass via env vars |

---

### Headless blockers and mitigations

| Blocker | Location | Mitigation |
|---------|----------|-----------|
| `bpy.context.screen.areas` iteration (shading switch, view3d) | `generation.py:1204`, `terrain.py:469` | Wrap in `try/except AttributeError` — cosmetic only |
| `zoom_camera_to_selected()` calls | `generation.py` multiple | Wrap in `try/except` — cosmetic only |
| `_progress.ProgressOverlay.get().start()` / `.update()` | `generation.py` throughout | Replace with a no-op stub class injected before script run |
| `addon_preferences.get_prefs()` (default export folder, API key) | `generation.py`, `elevation.py` | Stub `get_prefs()` to return an object with values from env vars |
| `customThumbnail()` | `export.py:240` | Skip entirely — not needed for web preview |
| `bpy.ops.render.opengl()` | `export.py:295` | Skipped (part of `customThumbnail`) |
| `bpy.utils.user_resource('CONFIG')` in `constants.py` | `constants.py` | Override cache dir to `OUTPUT_DIR/cache` before importing |
| `bpy.context.scene.tp3d.*` property reads everywhere | All util modules | Inject a minimal `tp3d` property group from JSON settings before calling any util |

---

### Settings exposed to the web UI (from props.py)

**Core generation**
- `shape`: HEXAGON, SQUARE, CIRCLE (free tier); OCTAGON, ELLIPSE, HEART (premium — skip for now)
- `objSize`: int, 5–10000 mm (default 100)
- `num_subdivisions`: int, 1–10 (default 4; preview will use 3)
- `scaleElevation`: float, 0–10000 (default 1)
- `pathThickness`: float, 0.1–5 mm (default 1.2)
- `minThickness`: float, 0.5–1000 mm (default 2)
- `shapeRotation`: int, -360–360 (default 0)
- `fixedElevationScale`: bool (default False)
- `overwritePathElevation`: bool (default True)

**Elevation source**
- `api`: TERRAIN-TILES (default), OPENTOPODATA, OPEN-ELEVATION, OPENTOPOGRAPHY
- `dataset`: aster30m (default for opentopodata), mapzen (terrain-tiles default)

**Map offset**
- `xTerrainOffset`: float (default 0)
- `yTerrainOffset`: float (default 0)

**Elements (OSM overlays)**
- `col_wPondsActive`, `col_wSmallRiversActive`, `col_wBigRiversActive`: bool (water)
- `col_fActive`: bool (forests)
- `col_cActive`: bool (city boundaries)
- `col_grActive`: bool (greenspace)
- `el_bActive`: bool (buildings)
- `el_sBigActive`, `el_sMedActive`, `el_sSmallActive`: bool (roads)

**Single color mode**
- `singleColorMode`: bool (for single-extrusion printers)
- `elementMode`: PAINT (default), SINGLECOLORMODE_REMESH, SEPARATE

---

### Key architectural finding: headless viability

**Verdict: HIGH confidence the full pipeline runs in `blender --background --python`.** Blender 4.x supports all mesh/modifier operations headlessly. The only GUI-bound code is the viewport shading switch, camera zoom, and 3MF thumbnail render — none of which affect the geometry or output files. All network I/O (Terrarium tiles, OSM Overpass) uses Python `requests` and runs independently of the Blender window.

**Approach for `scripts/generate_terrain.py`**:
1. Accept CLI args: `--gpx <path>`, `--settings <json_path>`, `--output <path>`, `--mode preview|export`, `--format stl|obj|3mf|glb`
2. Before importing any addon module, monkey-patch `constants.py` to redirect cache dirs to `$OUTPUT_DIR/cache`
3. Stub out `ProgressOverlay`, `WarningsOverlay`, `addon_preferences.get_prefs()`, all `screen.areas` calls
4. Load settings JSON and assign all props to `bpy.context.scene.tp3d`
5. Call `runGeneration(0)` (type 0 = single GPX file + trail)
6. After generation, export: glTF/GLB for preview (`bpy.ops.export_scene.gltf()`), or STL/OBJ/3MF for export
7. Print progress as JSON lines to stdout for the Celery task to parse

---

### Decision — Generate terrain script strategy (2026-05-20)
- **Decided**: Monkey-patch constants + stub GUI dependencies, then call `runGeneration(0)` directly inside headless Blender. Do not rewrite the pipeline from scratch.
- **Why**: Minimizes code duplication; guarantees parity with the addon's output; lower risk.
- **Rejected**: Full rewrite of terrain generation in pure Python outside Blender.
- **Rejected Why**: Enormous scope, high visual-mismatch risk, defeats purpose of using Blender.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — Preview settings (2026-05-20)
- **Decided**: Preview mode uses `num_subdivisions=3`, disables all OSM elements (water, forest, city, buildings, roads), exports glTF binary (`.glb`). Full-res export uses user settings.
- **Why**: Eliminates OSM API latency and reduces vertex count for fast Three.js rendering. User can enable elements for final export.
- **Rejected**: Identical settings for preview and export.
- **Rejected Why**: OSM fetch adds 10–60s per element; preview doesn't benefit from it.
- **Flagged By**: Integration Lead
- **Confidence**: High

---

## Phase 2 — API Contract (2026-05-20)

**Spec file**: `docs/openapi.yaml` (OpenAPI 3.1.0)

### Endpoints defined

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/preview` | Upload GPX + settings → returns `{job_id}`. Celery task generates GLB. |
| POST | `/api/v1/export` | Upload GPX + settings + format → returns `{job_id}`. Celery task generates STL/OBJ/3MF. |
| GET | `/api/v1/jobs/{job_id}` | Returns `{status, progress, result_url, error}`. |
| GET | `/api/v1/health` | Returns `{status, api, redis, celery}`. |

### Settings schema (`GenerationSettings`) — field→addon mapping

| API field | addon prop | Type | Default |
|-----------|-----------|------|---------|
| `shape` | `shape` | enum HEXAGON/SQUARE/CIRCLE | HEXAGON |
| `obj_size` | `objSize` | int 5–10000 | 100 |
| `rectangle_height` | `rectangleHeight` | int 5–10000 | 100 |
| `shape_rotation` | `shapeRotation` | int -360–360 | 0 |
| `num_subdivisions` | `num_subdivisions` | int 1–10 | 4 (preview: 3) |
| `scale_elevation` | `scaleElevation` | float 0–10000 | 1.0 |
| `fixed_elevation_scale` | `fixedElevationScale` | bool | false |
| `min_thickness` | `minThickness` | float 0.5–1000 | 2.0 |
| `overwrite_path_elevation` | `overwritePathElevation` | bool | true |
| `x_terrain_offset` | `xTerrainOffset` | float | 0.0 |
| `y_terrain_offset` | `yTerrainOffset` | float | 0.0 |
| `path_thickness` | `pathThickness` | float 0.1–5 | 1.2 |
| `elevation_api` | `api` | enum TERRAIN-TILES/OPENTOPODATA/OPEN-ELEVATION | TERRAIN-TILES |
| `opentopodata_dataset` | `dataset` | enum | aster30m |
| `water_ponds` | `col_wPondsActive` | bool | false |
| `water_small_rivers` | `col_wSmallRiversActive` | bool | false |
| `water_big_rivers` | `col_wBigRiversActive` | bool | false |
| `river_width` | `col_wStreamWidth` | float 0.1–10 | 1.0 |
| `forests` | `col_fActive` | bool | false |
| `city_boundaries` | `col_cActive` | bool | false |
| `greenspace` | `col_grActive` | bool | false |
| `buildings` | `el_bActive` | bool | false |
| `building_height_multiplier` | `el_bHeightMultiplier` | float 0.01–10 | 1.0 |
| `roads_major` | `el_sBigActive` | bool | false |
| `roads_medium` | `el_sMedActive` | bool | false |
| `roads_minor` | `el_sSmallActive` | bool | false |
| `street_width_multiplier` | `el_sMultiplier` | float | 1.0 |
| `element_mode` | `elementMode` | enum PAINT/SINGLECOLORMODE_REMESH/SEPARATE | PAINT |
| `single_color_mode` | `singleColorMode` | bool | false |

### Job status machine

```
pending → processing → completed
                    ↘ failed
```

Progress values mapped to Blender pipeline phases:
- 0–5%: pending / queued
- 5–15%: GPX parse + validation
- 15–35%: elevation fetch (Terrarium tiles)
- 35–65%: terrain mesh generation + displacement
- 65–75%: trail curve creation
- 75–85%: OSM element fetches (export only)
- 85–95%: boolean operations + finalize
- 95–100%: file export

### Decision — API field naming (2026-05-20)
- **Decided**: Use snake_case for all API fields, differing from the addon's camelCase prop names. A mapping table in MEMORY.md bridges the two.
- **Why**: REST API convention; consistent with FastAPI/Pydantic defaults.
- **Rejected**: Match the addon's camelCase names exactly.
- **Rejected Why**: Inconsistent with Python API conventions; would confuse frontend developers.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — Settings transport (2026-05-20)
- **Decided**: Settings sent as a JSON string field (`settings`) inside the multipart form alongside the file upload. Not a separate JSON body endpoint.
- **Why**: A single multipart request carries both the binary GPX file and structured settings in one HTTP round-trip. Matches how browser `FormData` naturally works.
- **Rejected**: Two separate endpoints (upload file first, then POST settings with a file reference).
- **Rejected Why**: Adds a round-trip and a temporary file-reference step with no benefit.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — File serving (2026-05-20)
- **Decided**: Generated files served as static files at `/files/{job_id}/{filename}` from the OUTPUT_DIR volume. FastAPI mounts this as a `StaticFiles` handler.
- **Why**: Simplest zero-overhead file serving; no streaming proxy needed.
- **Rejected**: Serve files through a FastAPI streaming endpoint.
- **Rejected Why**: Unnecessary complexity; static file serving is sufficient and faster.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — Preview forces num_subdivisions=3 (logged from Phase 1) (2026-05-20)
- **Decided**: The backend overrides `num_subdivisions` to 3 and disables all OSM element flags when mode=preview, regardless of what the client sends.
- **Why**: Keeps preview latency under 15s; OSM elements are irrelevant for geometry preview.
- **Flagged By**: Integration Lead
- **Confidence**: High

---

## Phase 3 — Backend Core (2026-05-20)

**Test result**: 15/15 passing (`pytest backend/tests/`)

### Files created

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Poetry config; fastapi, uvicorn, celery[redis], pydantic-settings, aiofiles, redis |
| `backend/app/config.py` | `Settings(BaseSettings)` — all 10 env vars validated at startup |
| `backend/app/models.py` | Pydantic models: `GenerationSettings`, `JobAccepted`, `JobStatus`, `HealthStatus` |
| `backend/app/celery_app.py` | Celery instance, Redis broker/backend, task tracking config |
| `backend/app/tasks.py` | `generate_preview` + `generate_export` tasks; invoke Blender subprocess, parse JSON progress lines |
| `backend/app/main.py` | FastAPI app with lifespan (OUTPUT_DIR mkdir), `/files` static mount, route registration |
| `backend/app/routes/preview.py` | `POST /api/v1/preview` — validates file, enforces preview overrides, enqueues task |
| `backend/app/routes/export.py` | `POST /api/v1/export` — validates file + format, enqueues task |
| `backend/app/routes/jobs.py` | `GET /api/v1/jobs/{job_id}` — maps Celery states to JobStatus |
| `backend/app/routes/health.py` | `GET /api/v1/health` — pings Redis + Celery inspect |
| `backend/tests/conftest.py` | AsyncClient fixture, minimal GPX fixture |
| `backend/tests/test_health.py` | 3 health-check tests (ok, redis-down, no-workers) |
| `backend/tests/test_jobs.py` | 12 tests: preview/export validation, job status state machine |

### Blender–Celery progress protocol
The Blender script must emit lines matching `{"progress": N, "phase": "..."}` to stdout.
`tasks.py` reads these line-by-line and calls `self.update_state(state="PROGRESS", meta=...)`.

### Bug fixed during tests
`jobs.py` originally deferred `from app.config import settings` inside the function body,
making it invisible to `patch("app.routes.jobs.settings")`. Moved to module-level import.
Logged in ERRORS.md.

### Decision — Task ID equals Job ID (2026-05-20)
- **Decided**: `apply_async(task_id=job_id)` where `job_id` is the UUID generated in the route.
- **Why**: Single identifier for the entire job lifecycle; frontend polls one URL with one ID.
- **Rejected**: Let Celery auto-generate the task ID and store a separate mapping.
- **Rejected Why**: Unnecessary indirection; no persistent store to hold the mapping.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Decision — Job-exists check via filesystem (2026-05-20)
- **Decided**: The job status endpoint distinguishes "unknown job" from "queued but not started" by checking whether `OUTPUT_DIR/{job_id}/` exists (created by the route handler at enqueue time).
- **Why**: Celery returns `PENDING` for both states; filesystem presence is the only reliable discriminator without a DB.
- **Flagged By**: Integration Lead
- **Confidence**: High

---

## Phase 4 — Blender Script (2026-05-20)

### Files created / modified

| File | Change |
|------|--------|
| `scripts/generate_terrain.py` | New — headless Blender pipeline script |
| `scripts/test_blender.sh` | New — smoke-test helper (requires Blender installed) |
| `TrailPrint3D/utils/generation.py` | Guard: `if bpy.context.screen:` around viewport shading loop (line ~1204) |
| `TrailPrint3D/utils/terrain.py` | Guard: `if bpy.context.screen:` around viewport shading loop (line ~469) |
| `TrailPrint3D/utils/scene.py` | Guard: `if not bpy.context.screen: return` in `zoom_camera_to_selected` |

### Headless bootstrap sequence in `generate_terrain.py`

1. Parse `--gpx`, `--settings`, `--output`, `--mode`, `--format` from argv after `--`
2. Create `job_dir/.cache/{terrarium,overpass}` directories
3. Stub `sys.modules["TrailPrint3D.progress"]` with `_StubProgress`/`_StubWarnings` before any import
4. Add repo root to `sys.path`; stub `map_picker` module
5. `import TrailPrint3D` (runs `__init__.py`; progress stub is already in sys.modules)
6. Patch `TrailPrint3D.constants` cache dirs to point to `job_dir/.cache/`
7. Patch `_scene.show_message_box` and `_scene.zoom_camera_to_selected` (and mirror patches on `_utils` namespace)
8. Patch `addon_preferences.get_prefs` to return `_FakePrefs(openTopographyApiKey="", default_export_folder=job_dir/)`
9. Register `TP3D_AddonPreferences` + `TP3D_PG_properties`; bind `bpy.types.Scene.tp3d`
10. Load settings JSON → map snake_case → camelCase Blender props
11. Set `tp3d.file_path = gpx`, `tp3d.export_path = job_dir`, `tp3d.disable_auto_export = True`
12. `from TrailPrint3D.utils.generation import runGeneration; runGeneration(0)`
13. Collect generated mesh/curve/font objects, select all, export via `bpy.ops.*`

### Format → export op mapping

| format | operator |
|--------|----------|
| `glb`  | `bpy.ops.export_scene.gltf(format="GLB", export_selected=True, export_apply=True)` |
| `stl`  | `bpy.ops.wm.stl_export(export_selected_objects=True)` |
| `obj`  | `bpy.ops.wm.obj_export(export_selected_objects=True, export_triangulated_mesh=True)` |
| `3mf`  | `bpy.ops.export_scene.three_mf_export()` with STL fallback if not installed |

### Progress scale
Script emits: 5 (init) → 10 (start gen) → 5–95 (passthrough from ProgressOverlay.update) → 90 (pre-export) → 100 (done)

---

## Phase 5 — Frontend Shell (2026-05-20)

**Build result**: 1 page built, 0 TypeScript errors.

### Stack
- Astro 6.3.5 (static output)
- Tailwind CSS v4.3 via `@tailwindcss/vite` (no tailwind.config.js — tokens in `@theme` block)
- Three.js 0.184.0 (type stubs installed; wired in Phase 6)
- Dev proxy: `/api` and `/files` → `http://localhost:8000`

### Files created

| File | Purpose |
|------|---------|
| `frontend/package.json` | Astro + Tailwind v4 + Three.js dependencies |
| `frontend/astro.config.mjs` | `@tailwindcss/vite` plugin, dev proxy |
| `frontend/tsconfig.json` | Extends `astro/tsconfigs/strict` |
| `frontend/src/env.d.ts` | Astro type reference |
| `frontend/src/styles/global.css` | `@import "tailwindcss"` + `@theme` design tokens |
| `frontend/src/layouts/Layout.astro` | HTML shell, imports global CSS |
| `frontend/src/pages/index.astro` | 2-column layout: 320px panel + fill canvas |
| `frontend/src/components/SettingsPanel.astro` | Full settings form (all 25 API fields + export) |
| `frontend/src/components/Canvas3D.astro` | `<canvas id="canvas-3d">` + placeholder overlay + progress/error UI |
| `frontend/public/favicon.svg` | Trail-themed SVG favicon |

### Design tokens (`@theme`)
- `--color-trail-orange: #f97316` — primary accent / CTA buttons
- `--color-surface-base: #0a0f1a` — page background (deep navy)
- `--color-surface-panel: #111827` — settings sidebar background
- `--color-surface-raised: #1f2937` — card / secondary button
- `--color-surface-input: #1a2232` — form inputs

### `window.__tp3d` API (exposed by Canvas3D.astro, consumed in Phase 6)
```typescript
showProgress(phase: string, pct: number): void
hideProgress(): void
showError(msg: string): void        // auto-dismisses after 6s
showPlaceholder(show: boolean): void
```

### Decision — Tailwind v4 vs v3 (2026-05-20)
- **Decided**: Use Tailwind v4 with the `@tailwindcss/vite` plugin; design tokens in `@theme` block in global.css.
- **Why**: v4 is current (released alongside Astro 6); avoids deprecated `@astrojs/tailwind` path; no separate config file needed.
- **Rejected**: Tailwind v3 + `@astrojs/tailwind`.
- **Rejected Why**: v3 is legacy; `@astrojs/tailwind` v6 still bundles v3 internally and would pin us to an older API.
- **Flagged By**: Integration Lead
- **Confidence**: High

---

## Phase Completion Tracker

- [x] Phase 1: Repository Analysis
- [x] Phase 2: API Contract
- [x] Phase 3: Backend Core
- [x] Phase 4: Blender Script
- [x] Phase 5: Frontend Shell
- [ ] Phase 6: Preview Integration
- [ ] Phase 7: Export Integration
- [ ] Phase 8: Docker Packaging
