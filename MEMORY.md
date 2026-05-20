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
