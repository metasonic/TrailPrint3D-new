# ERRORS.md

Log of approaches that took more than 2 attempts to work. Check this before
suggesting an approach to a similar task.

## Format

Each entry uses these fields:

- **Attempted**: approach that failed
- **Failed Because**: root cause
- **What Worked Instead**: working approach
- **Note for Next Time**: guidance for future sessions
- **Flagged By**: role of the agent

---

## 2026-05-20 — Phase 8 follow-up: terrain rendered but track tube placed 50 km off-origin

- **Attempted**: Visual end-to-end verification across Phases 6, 7, 8 trusted "Status: Ready + GLB returned 200" as proof the preview rendered. The first user-side review showed the canvas containing only the grid helper — the model was loaded but invisible. Two subsequent regenerations failed to surface the issue because the bug lived in the GLB itself and the network/timing layers all looked healthy.
- **Failed Because**:
  1. `pipeline/track.py:build_track_tube` read `terrain_mesh.metadata["centre_x"]` / `["centre_y"]` to shift the track to the terrain's centre. Those keys are set to **0.0** by `pipeline/terrain.py:build_terrain_mesh` (the terrain's POST-translation centre, after it was already moved to the origin). The actual UTM centre lives under `"utm_centre"`. As a result, the track points kept their raw UTM offsets (~397 000 east, ~4 660 000 north) and were merely scaled by `xy_scale` — leaving the track tube extruded tens of kilometres from origin in model space. trimesh's boolean union with the terrain succeeded but produced a GLB whose bounding box extended to ~51 535 mm in Y; the camera in PreviewCanvas (at ~120 mm) could not possibly see anything but the grid.
  2. `frontend/src/components/PreviewCanvas.tsx`'s centring math applied `root.position.sub(centre)` before `root.scale.setScalar(factor)`. In three.js the world transform is `T(position) * S(scale)`, so position needs to be expressed in *scaled* units. The combination worked by accident when `factor=1` and broke silently otherwise.
  3. trimesh exports GLB with Z as the height axis (Z-up); three.js renders Y-up. Without an explicit rotation, the model stands on its edge.
- **What Worked Instead**:
  1. Switch `build_track_tube` to use `utm_centre` and apply the shift **before** the xy_scale multiplication — same order as the terrain mesh:
     ```python
     utm_centre_x, utm_centre_y = terrain_mesh.metadata.get("utm_centre", (0.0, 0.0))
     scaled[:, 0] = (scaled[:, 0] - utm_centre_x) * xy_scale
     scaled[:, 1] = (scaled[:, 1] - utm_centre_y) * xy_scale
     ```
  2. Wrap the loaded GLB in a `THREE.Group`, rotate the inner model −π/2 around X to convert Z-up → Y-up, then on the wrapper set `scale` first and compute `position` in scaled coordinates: `wrapper.position.set(-centre.x * factor, -box.min.y * factor, -centre.z * factor)`. The model now sits flat on the grid centred at the origin.
- **Note for Next Time**:
  - Never accept a "Ready" badge as visual confirmation. For any change to the pipeline geometry or the canvas, **inspect the GLB bbox** (`trimesh.load(...).bounds`) and **read the screenshot** to confirm the model is actually visible. A 200 OK on `/files/{id}.glb` proves the file landed, not that it's renderable in-frame.
  - When the terrain and the track are produced by separate steps that each apply translate+scale, write them as a single named transform (e.g. one `MeshSpace` class holding `utm_centre` + `xy_scale` + `z_scale`) so they cannot drift apart. Two callers reading two different metadata keys was a latent bug from day one.
  - trimesh ↔ three.js axis convention mismatch: bake the Z-up → Y-up rotation into the GLB export (option in `trimesh.exchange.gltf.export_glb`) rather than fixing it client-side, so any future consumer of the GLB (e.g. a desktop slicer preview) sees the same orientation.
- **Flagged By**: Integration Lead (after user feedback)
