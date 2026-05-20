# MEMORY.md

Decision log for the TrailPrint3D web app conversion. Every significant decision
is appended here with full reasoning. Read this file at the start of every
session before suggesting changes.

## Format

Each entry uses these fields:

- **Decided**: what was chosen
- **Why**: reasoning
- **Rejected**: alternatives considered
- **Rejected Why**: why they were discarded
- **Flagged By**: role of the agent making the decision
- **Confidence**: High / Medium / Low

---

## 2026-05-20 - Session 1: Project bootstrap

### Initial state

- **Decided**: Bootstrap project on branch `claude/analyze-trailprint3d-Ub11X`. Repository contains the upstream `TrailPrint3D/` Blender addon source and a real-world GPX (`Cluj_Eco_Trail.gpx`, ~2.3 MB).
- **Why**: This is the agreed development branch per the task brief. Both files are needed for analysis and integration testing.
- **Rejected**: Working on `main`; generating a synthetic test GPX from scratch.
- **Rejected Why**: Brief mandates a feature branch; a real GPX is already present and is more representative than a synthetic one.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Q1 - Standard integration test GPX

- **Decided**: Use `Cluj_Eco_Trail.gpx` (already in repo root, ~2.3 MB real-world track) as the single standard integration test fixture.
- **Why**: Real-world data, representative of typical user uploads, already present. No need to fabricate a synthetic track for Phase 1.
- **Rejected**: Adding a small synthetic GPX alongside; using only a synthetic GPX.
- **Rejected Why**: Avoid premature complexity (Rule 2). If the Cluj track proves too large/slow for unit tests during pipeline implementation, we can add a small synthetic one then.
- **Flagged By**: User
- **Confidence**: High

### Q2 - Visual design source

- **Decided**: Establish a Tailwind-based design token system directly in the codebase. Do not wait for Figma.
- **Why**: Unblocks frontend work immediately, no external dependency. Tokens (colors, spacing, typography) can be refined later if Figma arrives.
- **Rejected**: Wait for Figma specs; hybrid placeholder-then-refactor.
- **Rejected Why**: Waiting blocks Phase 5. Hybrid was not explicitly chosen and adds a refactor step.
- **Flagged By**: User
- **Confidence**: High

### Q3 - Job state persistence

- **Decided**: Ephemeral Redis-backed job state only. No PostgreSQL, no persistent job history database.
- **Why**: Matches the brief's "ephemeral by design" constraint. Simplest viable architecture (Rule 2). Can be revisited if persistence is explicitly requested later.
- **Rejected**: Adding PostgreSQL or SQLite for job history.
- **Rejected Why**: Out of scope for Phase 1; adds a service, migrations, and ORM complexity for no immediate user value.
- **Flagged By**: User
- **Confidence**: High

### Phase 1 - Repository analysis report

- **Decided**: Phase 1 analysis report accepted and committed at `docs/phase1_repo_analysis.md` (1,359 lines). It maps every operator and utility in the `TrailPrint3D/` Blender addon to a Python replacement strategy, classifies ~100 props.py fields as Phase 1 or Phase 2, and surfaces concrete risk flags (Manifold boolean robustness, Frenet-frame extrusion completeness, Overpass reliability, single-color-mode complexity).
- **Why**: Provides the file:line index needed for Phase 4 implementation without re-reading 15k LOC of addon source each session.
- **Rejected**: Re-reading the full addon source ad-hoc per task.
- **Rejected Why**: Wastes context; the report is a stable artifact.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Phase 1 - Scope corrections applied to the analysis report

The analysis agent proposed several extensions beyond the brief. The following corrections are **binding** for Phase 2 onward and override anything that conflicts in `docs/phase1_repo_analysis.md`:

- **Decided**: Pipeline package contains exactly six modules — `pipeline/terrain.py`, `pipeline/track.py`, `pipeline/frame.py`, `pipeline/assembly.py`, `pipeline/export.py`, `pipeline/generate.py`. No `config.py`, `elevation.py`, `track_extrusion.py`, `cache.py`, or `constants.py` inside `pipeline/`.
- **Why**: This is the structure the brief mandates and the simplest viable decomposition (Rule 2). Pydantic settings live in the FastAPI backend, not in the pipeline. DEM caching is a small helper inside `terrain.py`. Frenet-frame extrusion is `track.py`'s responsibility per the brief.
- **Rejected**: Agent's 10-module split.
- **Rejected Why**: Premature decomposition; nothing in Phase 1 requires the extra surface area.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: DEM acquisition uses **only** the `elevation` Python package (AWS Open Data SRTM 30m). No OpenTopoData, Open-Elevation, Terrain-Tiles tile fetcher, or OpenTopography backend.
- **Why**: The brief's permanent constraints name `elevation` explicitly. A multi-backend abstraction is scope creep.
- **Rejected**: Porting the addon's four-backend API layer.
- **Rejected Why**: Each extra backend = new failure modes, new env vars, new tests, no user value at MVP.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Coordinate projection is **local UTM zone** via `pyproj`, picked from the track centroid. Not Web Mercator (EPSG:3857).
- **Why**: Brief mandates UTM. UTM is locally accurate in meters (essential for physical-print scale); Web Mercator distorts area especially at high latitudes.
- **Rejected**: Web Mercator (used by the original addon per the analysis report).
- **Rejected Why**: Wrong tool for a model with real-world dimensions.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Preset save/load (CSV in the addon) is **Phase 2+ deferred**, not Phase 1.
- **Why**: The brief's Phase 1 MVP list does not include presets; settings arrive as JSON in each `/preview` and `/export` request.
- **Rejected**: Porting `TP3D_OT_save_preset` / `load_preset` / `delete_preset` in Phase 1.
- **Rejected Why**: Scope creep; not in the panel-exposed parameter list (terrain scale, track thickness, frame style, shape, bbox padding).
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Phase 1 `GenerateSettings` schema is minimal — the brief's five exposed parameters plus a small number of internal knobs needed by the pipeline (cross-section type, frame thickness). Will be locked in during Phase 2 design.
- **Why**: The agent's 42-field Phase 1 list mixes brief parameters with deferred features (`scalemode=coordinates`, `disable_3mf_export`, `cache_size`, `rescale_multiplier`, etc.). Brief requires ~5 exposed parameters.
- **Rejected**: Adopting the full 42-field schema verbatim.
- **Rejected Why**: Most fields configure addon-specific behavior we are not porting. We can grow the schema in later sessions if a parameter proves necessary.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Phase 1 - Open ambiguities for user to resolve before Phase 2

1. **"Frame style" parameter semantics.** The brief lists "frame style" and "shape" as separate Phase 1 parameters. `shape` is clearly the boundary (square/circle/hexagon). "Frame style" has no obvious 1:1 mapping in `props.py`; candidates are border thickness, border height/depth, or a flat-vs-raised-vs-beveled flag.
2. **Bounding box padding semantics and units.** Brief lists this as a Phase 1 parameter; addon has no clean equivalent. Open: is it a percentage of track extent, or absolute meters?
3. **Track cross-section.** Brief mentions "configurable cross-section (circular, rectangular)". Is the cross-section selectable in the Phase 1 UI, or fixed to circular for MVP with rectangular deferred?
4. **DEM cache strategy.** `ELEVATION_CACHE_DIR` env var is defined. Simplest: point the `elevation` package at this directory and rely on its built-in tile cache. Confirm this is acceptable vs. a custom cache layer.

These will be resolved in the next user exchange before Phase 2 design is finalized.

### Phase 2 design inputs - user resolutions for the four ambiguities

- **Decided (Q-frame-style)**: "Frame style" maps to a single float parameter `frame_thickness_mm`. The frame is the boundary polygon extruded vertically by this thickness; no separate border width.
- **Why**: Simplest viable interpretation; matches `trimesh.creation.extrude_polygon`; one number is enough for MVP.
- **Rejected**: Border-width + thickness pair; preset style enum (flat/raised/beveled).
- **Rejected Why**: Extra UI surface and code for a Phase 1 MVP that does not require them.
- **Flagged By**: User
- **Confidence**: High

- **Decided (Q-bbox-padding)**: Padding is expressed as a fraction of track extent — `bbox_padding_percent: float` in `[0.0, 1.0]`, default `0.1`. DEM bbox = track bbox grown by that fraction in each direction.
- **Why**: Scale-invariant across short loops and long routes. Single field.
- **Rejected**: Absolute meters; dual mode + value fields.
- **Rejected Why**: Absolute meters gives inconsistent visual padding across track sizes; dual-mode adds API surface and validation work.
- **Flagged By**: User
- **Confidence**: High

- **Decided (Q-track-cross-section)**: Phase 1 track is circular only. `track_thickness_mm` is the **diameter** of the tube. Rectangular cross-section is Phase 2.
- **Why**: One parameter matches the brief's "track thickness" panel item exactly. Rectangular adds two parameters (width + height) and more extrusion code for no MVP value.
- **Rejected**: Phase 1 selector for circle | rectangle.
- **Rejected Why**: Scope creep against the brief's single "track thickness" exposure.
- **Flagged By**: User
- **Confidence**: High
- **Note**: Treating `track_thickness_mm` as diameter is an interpretation. Will document in code and revisit if the user expected radius.

- **Decided (Q-dem-cache)**: A thin custom cache layer lives inside `pipeline/terrain.py` (not a separate module). It keys on `(min_lat, min_lon, max_lat, max_lon, resolution_m)` rounded to a stable precision (4 decimal degrees = ~11 m), stores GeoTIFFs under `ELEVATION_CACHE_DIR`, and reads them back on cache hits. The `elevation` package writes into the same directory so its tiles are reused.
- **Why**: User chose custom over relying on the `elevation` package's internal cache. Custom cache gives a single deterministic key per request and lets us see hits/misses for the "near-instant preview when DEM is cached" requirement in the brief.
- **Rejected**: Relying only on the `elevation` package's built-in tile cache.
- **Rejected Why**: Per user choice; also harder to assert cache hits in tests when control is delegated to an external package.
- **Flagged By**: User
- **Confidence**: Medium (the bbox-rounded key is sensible but only proven once the pipeline is implemented; will revisit if it misses obvious overlaps).

### Phase 2 - Pipeline design locked

- **Decided**: Pipeline public surface is defined in `docs/phase2_pipeline_design.md`. Six modules (`terrain`, `track`, `frame`, `assembly`, `export`, `generate`). `GenerateSettings` is a Pydantic model in `backend/app/models.py` with 5 user-facing fields and 4 internal defaults. `generate()` returns a `GenerateResult` with output path, duration, cache hit, and track stats. Manifold engine is the only boolean backend — failure raises, no silent fallback.
- **Why**: This is the smallest surface that satisfies the brief's Phase 1 MVP. Every signature has one obvious job; nothing speculative.
- **Rejected**: Re-validation inside pipeline functions; multi-engine boolean fallback chain; exposing internal subdivisions in the API but not the UI as a separate concept.
- **Rejected Why**: Pydantic at the API boundary is sufficient. A multi-engine fallback for booleans was tempting but hides real bugs — print safety beats apparent robustness here. Subdivisions are exposed so power users can override via the API; UI just uses the defaults.
- **Flagged By**: Integration Lead
- **Confidence**: High on the module split and orchestrator contract; Medium on the Frenet-frame approach (parallel-transport rotation-minimizing frame is the planned implementation but only validated in Phase 4 against a synthetic switchback fixture).

### Phase 2 - Open questions to resolve before Phase 3

None blocking. Phase 3 (FastAPI app + Celery wiring + `/health`) can proceed
using the locked schema. The remaining unknowns are implementation details
that surface during Phase 4.

### Phase 3 - Backend Core delivered and live-verified

- **Decided**: Single Poetry project at the repo root with two packages, `backend/` and `pipeline/`, sharing one virtualenv. `GenerateSettings` lives in `backend/app/models.py` and is imported by the pipeline (one direction only; pipeline never imports FastAPI or Celery).
- **Why**: Mono-project keeps imports clean, avoids relative-path hacks, and lets the Phase 8 Dockerfile build one image with two entry points (uvicorn vs celery worker). Splitting would have required either a shared models package (more surface) or duplication (worse).
- **Rejected**: Two separate Poetry projects; placing `GenerateSettings` in `pipeline/` and having `backend` import it.
- **Rejected Why**: The pipeline must not depend on FastAPI/Celery (so it stays CLI-testable in Phase 4). Putting the schema where the API boundary lives keeps validation centred at the boundary.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: API shape is multipart `file=` + form field `settings=<JSON>` (plus `format=` for `/export`). Pydantic validates the JSON string at request time and returns 422 on bad fields.
- **Why**: Standard REST pattern for "file + structured metadata". No base64 bloat, browsers handle it natively.
- **Rejected**: JSON body with base64-encoded GPX.
- **Rejected Why**: Larger payload, more client complexity, no benefit.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Job status mapping uses `task_track_started=True` and translates Celery states (PENDING/RECEIVED → pending, STARTED/RETRY → processing, SUCCESS → completed, FAILURE/REVOKED → failed). Unknown job IDs return pending (Celery cannot distinguish "never seen" from "queued"). Completion responses include `result_url=/files/{job_id}.{ext}`; failures include `error=str(exception)`.
- **Why**: Matches the brief's four-state contract with minimal logic. The PENDING-on-unknown behaviour is inherent to Celery and surfacing it as-is is simpler than fronting with a Redis-side tracking set.
- **Rejected**: Tracking job IDs in a Redis set on enqueue to distinguish unknown from pending.
- **Rejected Why**: Adds bookkeeping that would have to be kept in sync with Celery's own state, with no concrete UX benefit in Phase 1.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Five bash scripts under `scripts/`: `test.sh`, `lint.sh`, `dev-up.sh`, `dev-down.sh`, `curl-smoke.sh`. `dev-up` runs Redis + uvicorn + a solo-pool Celery worker in the background, writing PIDs to `/tmp/tp3d.pids` and logs to `.dev-logs/`.
- **Why**: Per Rule 8. Solo pool avoids fork-on-load issues during dev; in production the Docker worker can use the default prefork pool. The smoke script exercises `/health → POST /preview → poll /jobs/{id}` and accepts a `failed` terminal state in Phase 3 because the pipeline stub is intentional.
- **Rejected**: Running services in foreground tabs/tmux.
- **Rejected Why**: Not reproducible in CI or in agent sessions.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Test layout: `tests/test_models.py` (GenerateSettings validation), `tests/test_pipeline_stub.py` (verifies the pipeline import contract), `tests/test_api.py` (uses `fastapi.testclient`; the one job-status test that needs Celery is `@pytest.mark.skipif`-gated on Redis being reachable).
- **Why**: Unit-level coverage runs without infra; the Redis-dependent test runs both via the dev stack and in CI when Redis is up. The curl smoke script remains the authoritative end-to-end verification per the brief.
- **Rejected**: Mocking Celery for the job-status test.
- **Rejected Why**: A Celery mock proves nothing about the real backend-state mapping, which is the only thing worth testing here.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Live verification recorded — `/health` returns `{status:ok, redis:true, celery:true}`, `POST /preview` with `Cluj_Eco_Trail.gpx` returns a job id, and `GET /jobs/{id}` reports `failed` with the expected `NotImplementedError` message surfaced. 8/8 pytest tests pass, ruff clean, mypy strict clean.
- **Why**: Phase 3 acceptance criteria from the brief are met.
- **Rejected**: n/a
- **Flagged By**: Integration Lead
- **Confidence**: High

### Phase 4 - Pipeline implementation and live end-to-end pass

- **Decided**: Geometric assembly is `intersect(terrain, frame_clip_volume) → union(clipped_terrain, frame_base, track_tube)`. The frame's 2D shape (square/circle/hexagon) defines the model's XY footprint; the terrain is clipped to that outline by an intermediate boolean intersect; the visible frame base sits below the terrain at z ∈ [-frame_thickness_mm, 0]; the track tube hugs the clipped terrain surface.
- **Why**: Without the clip step, the `shape` parameter is meaningless — terrain corners would poke past circular/hexagonal frame outlines. The brief's "boolean union" instruction is the *final* combine; an intermediate clip is required to make the shape parameter visible.
- **Rejected**: Literal three-mesh union with no clip step; clipping with shapely 2D booleans then re-triangulating; computing a "shaped terrain" by clamping vertices outside the shape (would leave holes).
- **Rejected Why**: Literal union ignores shape. 2D clip + re-triangulation loses the elevation data on cut edges. Vertex clamping is not watertight.
- **Flagged By**: Integration Lead
- **Confidence**: Medium — geometrically defensible and produces visually correct output, but the user may want different semantics (e.g. frame as a raised border rather than a base). Worth a check-in after they look at the rendered GLB.

- **Decided**: Track points are cast onto the DEM surface (Z replaced by terrain Z at the same XY) before tube extrusion. GPX-recorded elevations are discarded for visualisation purposes.
- **Why**: Matches the original addon's `overwrite_path_elevation=True` default. GPX elevations are noisy (consumer GPS) and frequently disagree with the DEM by tens of meters.
- **Rejected**: Using GPX elevations directly.
- **Rejected Why**: Track would float above or sink into the terrain, breaking the visual.
- **Flagged By**: Integration Lead
- **Confidence**: High (matches addon behaviour and produces correct visual).

- **Decided**: Track tube uses `trimesh.creation.sweep_polygon` with a shapely circular cross-section. Hand-rolled rotation-minimizing-frame implementation was deleted.
- **Why**: First attempt (custom Frenet/parallel-transport frame + manual cap fan) produced a non-watertight mesh — cap winding was off and the final union failed. `sweep_polygon` handles framing, caps, and watertightness as one primitive.
- **Rejected**: Hand-rolled implementation; cylinder-per-segment + union (would be slow and produce surface artifacts at joints).
- **Rejected Why**: Reinventing a well-tested trimesh primitive when there's no MVP-level reason to.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Terrain mesh is a watertight box-with-heightmap-top, hand-stitched from a grid (top) + grid (bottom) + four side walls. Winding is fixed globally with `mesh.fix_normals()` after construction (one-shot reorient).
- **Why**: trimesh has no direct "heightmap to watertight prism" primitive in the installed version. Hand-stitching is simple and gives full control over subdivisions. `fix_normals` handles the global-winding ambiguity in a single line.
- **Rejected**: `trimesh.creation.extrude_triangulation` of a single top surface (gives a flat-bottom open mesh, not a closed box); manifold3d's `linear_extrude` (would require porting the heightmap into manifold's API, more surface).
- **Rejected Why**: Both alternatives add code without simplifying anything.
- **Flagged By**: Integration Lead
- **Confidence**: High for the construction; Medium-High for performance — at the largest export subdivisions the terrain has ~17k vertices, fine for the brief's 20-30 concurrent jobs / 8GB target.

- **Decided**: `subdivisions` field semantics: higher value → finer detail. Internally maps to a downsampling stride via `stride = max(1, 8 // subdivisions)`. Preview default 2 → stride 4; export default 4 → stride 2.
- **Why**: Field name suggests "more = better" which is the intuitive direction. Stride is the actual implementation detail.
- **Rejected**: Exposing stride directly; preview_subdivisions and export_subdivisions being equal (would defeat the preview-fast / export-fine distinction).
- **Rejected Why**: Stride is an implementation detail callers shouldn't have to reason about. Equal subdivisions kills the preview-mode purpose.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Manifold boolean engine is required (no fallback). `assembly.union()` and `assembly.intersect()` both check `manifold3d` import availability and verify the result `is_volume` before returning.
- **Why**: Brief mandates Manifold. A silent fallback to trimesh's other engines would let non-printable meshes through.
- **Rejected**: Multi-engine fallback (manifold → scad → blender). 
- **Rejected Why**: Hides real bugs; non-watertight meshes break slicers.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: System dependencies needed for the worker container: `gdal-bin` (for the `elevation` package's bbox-clip step which shells out to `gdal_translate`) and `libspatialindex-dev` (for `rtree`, used by trimesh's ray spatial index). Logged here so Phase 8 Dockerfile installs them.
- **Why**: Both surfaced as runtime errors during pipeline implementation. The `elevation` package's design uses GDAL CLI rather than the Python bindings.
- **Rejected**: Replacing the `elevation` package with direct tile downloads + rasterio stitching.
- **Rejected Why**: Brief mandates the `elevation` package by name. The GDAL/rtree system deps are standard apt-installable.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Live verification recorded — pipeline runs end-to-end on Cluj_Eco_Trail.gpx. Preview: 6.9 MB GLB in 2.76 s. Export: 21 MB STL in 3.28 s. Final mesh: 194 k verts, 388 k faces, watertight=True. HTTP route via FastAPI completes job pending → processing → completed in ~3 s, and `/files/{id}.glb` returns 200 with `Content-Type: model/gltf-binary`. 9/9 pytest tests (2 skip on cache state), ruff clean, mypy strict clean.
- **Why**: Phase 4 acceptance criteria from the brief are met.
- **Rejected**: n/a
- **Flagged By**: Integration Lead
- **Confidence**: High.

### Phase 5 - Frontend shell delivered (Astro 6 + React islands + Tailwind v4 + three.js)

- **Decided**: Frontend is a standalone Astro 6 project at `frontend/` (separate from the Python Poetry project at the repo root). Astro 6.3.6, @astrojs/node 10.1.1 in standalone mode, @astrojs/react 5.0.5, Tailwind v4 via @tailwindcss/vite, three.js 0.184, Vitest 4.1.7 + jsdom 29 for component tests, React 19.1. SSR is enabled (`output: "server"`) so the Node adapter hosts the app; the brief's `HOST=0.0.0.0` is set in both astro.config and the production start command.
- **Why**: Brief mandates Astro 6 + Node adapter standalone + Tailwind + Vitest + three.js. Latest stable across the board; Tailwind v4 is the version that ships the `@theme` directive used for design tokens.
- **Rejected**: Putting Astro inside the Python project; using Tailwind v3 (no `@theme`); @react-three/fiber wrapper.
- **Rejected Why**: Two languages, two package managers — cleaner to keep them separate. Tailwind v3 would force a postcss config and lose the `@theme` token block. r3f is an extra abstraction layer the brief did not ask for, and the canvas needs are simple enough that raw three.js fits in one file.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: State management is a single React Context (`AppState`) holding the uploaded GPX file, the current `GenerateSettings`, the active preview URL, the job status/error, and the export format. No Redux, no Zustand, no URL-state-sync. The same `GenerateSettings` type lives in `frontend/src/types/settings.ts`, hand-mirrored from `backend/app/models.py` (single point of drift; will be regenerated from OpenAPI if/when it becomes a problem).
- **Why**: Brief says "React hooks and context are sufficient". Hand-mirroring a 9-field interface is cheaper than wiring up an OpenAPI generator at this stage (Rule 2).
- **Rejected**: Zustand/Redux; OpenAPI codegen for types.
- **Rejected Why**: Premature; the schema rarely changes once locked.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Five components, one for each brief concern: `UploadForm` (drag-drop + file picker, .gpx filter), `SettingsPanel` (radio for shape, three sliders, one numeric field per Phase 5 UX questions), `PreviewCanvas` (three.js WebGL renderer + OrbitControls + GLTFLoader; reloads on URL change; disposes geometries on unmount), `DownloadPanel` (format picker + export button), `JobStatusBadge`. `AppShell.tsx` composes them under `AppStateProvider`. The Astro page (`pages/index.astro`) is a single `client:load` island hosting the shell.
- **Why**: Splitting along brief concerns; `client:load` because everything is interactive on load (no progressive-hydration win available for a single-page app this size).
- **Rejected**: Per-component islands (one for upload, one for canvas, etc.) with `client:visible` hydration.
- **Rejected Why**: Components share state via Context. Splitting them across islands would require duplicating Context per island or lifting state into Astro, both worse than one `client:load` block.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Tailwind v4 `@theme` block in `src/styles/global.css` defines the colour palette (canvas/surface/edge/ink/accent/success/warning/danger), font families, and corner radii. These are the in-code design tokens promised in Q2 (no Figma).
- **Why**: Tokens centralised, all components reference `var(--color-…)` so a future palette swap is one-file. Tailwind v4's `@theme` makes the token block first-class.
- **Rejected**: A `tailwind.config.ts` with extended theme (v3 style); per-component colour literals.
- **Rejected Why**: v3 style doesn't apply to Tailwind v4. Colour literals defeat the design-token decision.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Phase 5 wires the components together with **stub callbacks**, not real `fetch()` calls. `UploadForm.onUpload`, `SettingsPanel.onRegenerate`, `DownloadPanel.onExport` are all no-ops in `AppShell`. Phase 6 replaces them with `POST /api/v1/preview` + status polling at ~1 s intervals; Phase 7 adds the export flow.
- **Why**: Brief defines Phase 5 as the "frontend shell"; the integrations are Phase 6 and 7. Stubs let me ship Phase 5 cleanly without lifting backend coupling into the wrong phase.
- **Rejected**: Doing the API calls now.
- **Rejected Why**: Violates the "proceed strictly in this order" directive.
- **Flagged By**: Integration Lead
- **Confidence**: High

- **Decided**: Live verification recorded — `pnpm test` 8/8 passing (AppState init/update, UploadForm UI + .gpx filter, SettingsPanel defaults + slider updates), `pnpm check` (astro check) 0 errors / 0 warnings across 15 files, `pnpm build` produces a working standalone Node server, `HOST=0.0.0.0 node dist/server/entry.mjs` serves `GET /` with a full SSR-rendered page including all islands and Tailwind output.
- **Why**: Phase 5 acceptance criteria are met.
- **Rejected**: n/a
- **Flagged By**: Integration Lead
- **Confidence**: High

### Phase 6 - Preview integration wired and live-verified

- **Decided**: Frontend calls relative same-origin paths (`/api/v1/...`, `/files/...`). Astro's Vite dev server proxies both prefixes to `http://127.0.0.1:8000` (configured in `astro.config.mjs`). Production routing is deferred to Phase 8 (reverse proxy in Docker Compose).
- **Why**: Same-origin everywhere means no CORS middleware in the backend, no cross-origin cookies/auth concerns later, and the frontend code is identical in dev and prod. The dev-only Vite proxy mirrors what a Phase 8 reverse proxy will do.
- **Rejected**: Adding `CORSMiddleware` to FastAPI; baking a `PUBLIC_API_BASE_URL` env var into the frontend; serving the frontend bundle from FastAPI.
- **Rejected Why**: CORS introduces an attack surface and configuration burden we don't need. A separate API base URL splits dev and prod paths and complicates testing. Serving the frontend from FastAPI defeats the separate-container deploy in the brief.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: A single API client module at `frontend/src/api/client.ts` exposes `postPreview`, `postExport`, `getJob`, and `pollJob`. Polling cadence is 1 s (per the agreed simple-polling design). `pollJob` accepts an `AbortSignal`; the shell cancels any in-flight poll before starting a new one (no race between the previous completion and the new request).
- **Why**: One place to evolve the network layer (e.g. swap to SSE/WebSocket later). The signal-based cancellation is the standard web-platform idiom.
- **Rejected**: WebSocket / SSE for job updates; embedding fetch calls inline in components.
- **Rejected Why**: Brief implies polling; WS/SSE adds a server-side dependency without user-visible benefit at this size. Inline fetches scatter retry/cancellation logic.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: `AppShell` exposes one generator: `generatePreview(file)` is called from both `handleUpload` (after a drop) and `handleRegenerate` (after settings change). On upload the preview kicks off automatically with default settings — matching the brief: "preview uses default settings immediately after upload".
- **Why**: One code path, one place where state transitions and abort signalling live. The brief's "auto-generate on upload" behaviour falls out for free.
- **Rejected**: Asking the user to click a button after upload; making `handleUpload` do nothing until the user touches Regenerate.
- **Rejected Why**: Contradicts the brief.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: `scripts/dev-up.sh` now also starts the Astro dev server (background, logs to `.dev-logs/frontend.log`, PID tracked in `/tmp/tp3d.pids`). Pass `NO_FRONTEND=1` to skip it (the backend-only mode used by `curl-smoke.sh`).
- **Why**: Local end-to-end verification needs all four processes up. Single command, single teardown.
- **Rejected**: A second `scripts/dev-up-all.sh`; running the frontend manually in a foreground tab.
- **Rejected Why**: Two scripts to remember; manual setup is not reproducible.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Live verification recorded — booted the full stack via `scripts/dev-up.sh`, drove a real Chromium browser via Playwright to drop `Cluj_Eco_Trail.gpx` into the upload form, observed `POST /api/v1/preview` → 7 polls of `/jobs/{id}` → `GET /files/{id}.glb` all returning 200, with the terrain + hexagonal frame + red track visible in the canvas and the status badge transitioning pending → processing → "Ready". 14/14 vitest passing, astro check 0/0/0 across 17 files.
- **Why**: Phase 6 acceptance criteria are met.
- **Rejected**: n/a
- **Flagged By**: Integration Lead
- **Confidence**: High.

### Phase 7 - Export integration wired and live-verified

- **Decided**: Export uses the same enqueue → poll → terminal-status pattern as preview, but on `completed` triggers a browser download instead of setting the preview URL. Download is implemented with a synthetic `<a download href=resultUrl>` click that the browser sees as a normal same-origin download (no fetch + blob URL needed because `/files/...` is same-origin and serves the right Content-Type).
- **Why**: Same shape as preview, so the surrounding state machine (in-flight abort, status badge, error surface) is reused. The anchor-click idiom is the simplest correct browser primitive.
- **Rejected**: `window.open(result_url)`; `fetch + Blob + URL.createObjectURL`.
- **Rejected Why**: `window.open` may open in a new tab/popup-blocker. The fetch+blob path re-downloads the file into memory just to inject an artificial URL — pointless for a same-origin file.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Download filename is `${gpx-stem}.${format}` (e.g. `Cluj_Eco_Trail.stl`). The `<a download>` attribute hints the filename; the server's Content-Disposition is not set today (browsers honour the attribute for same-origin downloads).
- **Why**: Predictable and matches what a desktop slicer user expects.
- **Rejected**: Using the backend's `{job_id}.{format}` filename verbatim.
- **Rejected Why**: A UUID is opaque; the GPX stem is meaningful.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: A separate `exporting` boolean in `AppShell` tracks in-flight export jobs distinctly from preview jobs, so the Settings panel can stay disabled during export even though `jobStatus` is shared. The Regenerate/Export buttons are both gated by a combined `busy` flag.
- **Why**: Keeps the user from double-clicking Export or hitting Regenerate while an export is mid-flight (both would abort the in-flight poll and confuse the status badge).
- **Rejected**: Two parallel jobStatus fields (one preview, one export); allowing concurrent jobs.
- **Rejected Why**: One in-flight job at a time is the simplest correct model; the brief gives no concurrency requirement for the UI.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Live verification recorded — full stack via `scripts/dev-up.sh`; Playwright drove the browser through upload → preview-Ready → click Export → 6 polls → real browser download event captured with file `Cluj_Eco_Trail.stl` (21,427,184 bytes — byte-identical to the Phase 4 CLI export). Test suite: 15/15 vitest, astro check 0/0/0 across 18 files.
- **Why**: Phase 7 acceptance criteria are met.
- **Rejected**: n/a
- **Flagged By**: Integration Lead
- **Confidence**: High.

### Phase 8 - Docker packaging, nginx + brotli, full stack live

- **Decided**: Five services in `docker-compose.yml` (`redis`, `backend`, `worker`, `frontend`, `nginx`) plus an opt-in `flower` behind a Compose profile. Backend and worker share a single image (`trailprint3d-backend:0.1.0`) with the worker's `command` overridden to launch Celery; saves one image and avoids drift. Public port is a single `nginx` listener (default :8080, overridable via `TP3D_PORT`).
- **Why**: Brief mandates a Docker Compose stack with these services. Sharing the backend image keeps the worker's import graph identical to the API and proves "what the API can import, the worker can run".
- **Rejected**: Separate Dockerfiles per service; nginx-less stack with CORS on FastAPI; per-service port exposure.
- **Rejected Why**: Two near-identical backend images doubles surface area. CORS is a long tail of pitfalls when same-origin via a reverse proxy is essentially free. Multiple exposed ports complicates firewall rules.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: nginx is custom-built with `ngx_brotli` as dynamic modules. Multi-stage `docker/nginx.Dockerfile` compiles brotli's C library via CMake (it's a submodule of `ngx_brotli` and isn't pre-built), then compiles the nginx module against the official nginx 1.27.3 source, and ships only the `.so` files plus the runtime config into a clean `nginx:1.27.3` final image.
- **Why**: User chose nginx with brotli. Official nginx images don't ship brotli; building from source pins the version and keeps the production image small (~280 MB total). The `nginx.conf` enables brotli for `text/*`, JS, JSON, WASM, SVG, and `model/gltf+json`; gzip is the fallback. GLB binaries skip compression (already binary).
- **Rejected**: Community brotli images (drift / single-maintainer risk); building brotli statically into nginx (loses the ability to disable it).
- **Rejected Why**: Self-build keeps us in control of pins; dynamic modules are the modern nginx pattern.
- **Flagged By**: Integration Lead
- **Confidence**: High. Verified live: `curl -H 'Accept-Encoding: br' /` returns `Content-Encoding: br`.

- **Decided**: All three custom images use Debian-bookworm-slim bases (`python:3.11.10-slim-bookworm`, `node:22.22.3-bookworm-slim`, `nginx:1.27.3`) rather than `-alpine`. The frontend image grows to ~190 MB (vs ~50 MB alpine) but that's a one-time payment for build robustness.
- **Why**: Alpine's `apk` repos require pre-existing TLS trust to install `ca-certificates`, which is a chicken-and-egg behind TLS-inspecting corporate proxies. Debian's GPG-signed-over-HTTP apt sidesteps this entirely and is friendlier across deployment environments.
- **Rejected**: Alpine bases.
- **Rejected Why**: Repeated chicken-and-egg failures during sandbox build; not worth the size win.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: `docker/extra-cas/` is a drop-in directory each Dockerfile copies into `/usr/local/share/ca-certificates/extra/` before any network step, then runs `update-ca-certificates`. Empty in the committed tree (only `.gitkeep` + README), so production builds are a no-op; corporate / sandbox builds drop their proxy CA in and everything works.
- **Why**: Lets the same Dockerfile work in clean and proxy-intercepted environments without code-level differences. No bespoke build flags or compose overrides needed.
- **Rejected**: `--build-secret` flag; per-environment Dockerfile variants; baking sandbox CAs into the committed tree.
- **Rejected Why**: Secrets-flag adds a script-level coupling; variants split the build surface; baking CAs ties the image to a single environment.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Four shell wrappers under `scripts/` for the Docker workflow: `build.sh`, `up.sh`, `down.sh`, `logs.sh`. Each is a one-liner over `docker compose ...` so the surface matches the brief's example names; `up.sh` prints the URL.
- **Why**: Rule 8 — repeatable Docker commands belong in scripts.
- **Rejected**: A Makefile; a single multi-subcommand script.
- **Rejected Why**: Bash one-liners are clear and discoverable.
- **Flagged By**: Integration Lead
- **Confidence**: High.

- **Decided**: Live verification recorded — `scripts/build.sh` built all four images (backend ~384 MB, frontend ~192 MB, nginx ~72 MB; redis pulled from upstream). `scripts/up.sh` brought the five services up; all reported `running` within ~20 s. Through nginx on :8080: `GET /` returned 200 with `Content-Encoding: br`, `GET /api/v1/health` returned `{redis:true,celery:true}`, `POST /api/v1/preview` with `Cluj_Eco_Trail.gpx` enqueued a job, 8 polls of `/api/v1/jobs/{id}` reached `completed`, `GET /files/{id}.glb` returned 200 / model/gltf-binary / 6,981,224 bytes (byte-identical to the Phase 4 CLI preview output). Playwright then drove a real Chromium browser through the same flow against the Dockerized stack and rendered the model.
- **Why**: Phase 8 acceptance criteria are met. All 8 phases of the brief are complete.
- **Rejected**: n/a
- **Flagged By**: Integration Lead
- **Confidence**: High.
