# Phase 1 - Repository Analysis: TrailPrint3D Blender Addon

**Audit Date**: May 2026  
**Addon Version**: 3.0.8 (Blender 4.5+)  
**Total LOC**: ~15,000  
**Analysis Scope**: Full teardown for web backend porting (pure Python, no Blender/bpy)

---

## 1. Top-level File Inventory

| File | LOC | Role | Phase Classification |
|------|-----|------|----------------------|
| `__init__.py` | 307 | Entry point, class registration, premium detection | Blender-internal infra (no port needed) |
| `operators.py` | 1700+ | Main UI operators (Generate, Export, Presets, etc.) | **Phase 1 MVP** (orchestration only) |
| `props.py` | 413 | Blender PropertyGroup → Pydantic schema seed | **Phase 1 MVP** (config schema) |
| `panels.py` | 1200+ | UI panel layout (sidebar) | Blender-internal infra (no port needed) |
| `export.py` | 300+ | Export to STL/OBJ/3MF (wrapper around `bpy.ops`) | **Phase 1 MVP** (via trimesh) |
| `constants.py` | 57 | Global constants, cache dir paths | **Phase 1 MVP** (keep paths logic) |
| `addon_preferences.py` | 100+ | Addon settings panel | Blender-internal infra (no port needed) |
| `progress.py` | 450+ | GPU-drawn + subprocess progress overlay | **Phase 2** (replace with web progress bar) |
| `progress_win.py` | 686 | HTML progress window (subprocess) | **Phase 2** (replace with web UI) |
| `updater.py` | 110 | GitHub version check & auto-download | Blender-internal infra (no port needed) |
| `translation.py` | 793 | Blender i18n translations (DE, CN) | Blender-internal infra (no port needed) |
| `temp.py` | 9 | Premium version flag storage | Blender-internal infra (no port needed) |
| `threemf_discovery.py` | 256 | Detect installed 3MF addon (dynamic linking) | **Phase 1 MVP** (detect 3MF, use trimesh) |
| **utils/** | **~9K** | Core mesh/geo/elevation logic | Mixed (see §2–3) |

---

## 2. Operators (operators.py + export.py)

All operators inherit from `bpy.types.Operator`. Entry points are registered in `__init__.py` lines 130–166 (base) and lines 168–185 (premium).

### Phase 1 MVP Operators

**TP3D_OT_run_generation** (operators.py:24–32)  
- **What**: Wrapper that calls `utils.runGeneration(0)`, orchestrates full pipeline
- **Blender-isms**: Uses `context.scene.tp3d` PropertyGroup to read all settings
- **Replacement**: → `pipeline/generate.py:generate()` (coordinator function)
- **Import path**: `bpy.ops` calls → direct Python function calls

**TP3D_OT_export_stl** (operators.py:34–67)  
- **What**: Exports selected objects to STL (currently via `bpy.ops.wm.stl_export`)
- **Blender-isms**: `bpy.ops.wm.stl_export()`, selected object iteration, materials
- **Replacement**: → `pipeline/export.py:export_stl(meshes, path)` via `trimesh.exchange.export()`
- **Note**: Validates export path, falls back to addon prefs if unset

**TP3D_OT_export_obj** (operators.py:69–102)  
- **What**: Exports selected objects to OBJ (with materials if present)
- **Blender-isms**: `bpy.ops.wm.obj_export()`, material slot detection
- **Replacement**: → `pipeline/export.py:export_obj(meshes, path)` via `trimesh`
- **Note**: Chooses format based on `material_slots` presence

**TP3D_OT_export_three_mf** (operators.py:104–144)  
- **What**: Exports to 3MF via optional addon extension (or warns if missing)
- **Blender-isms**: Checks for installed 3MF addon via `utils.is_3mf_extension_installed()`
- **Replacement**: → `pipeline/export.py:export_3mf(meshes, path)` via `trimesh` (no addon needed in web)
- **Note**: Lines 98–108 duplicate objects before export to avoid mutating scene

**TP3D_OT_rescale** (operators.py:181–239)  
- **What**: Rescales Z-elevation of selected mesh/curve objects by a multiplier
- **Blender-isms**: Direct vertex iteration, `obj.data.vertices[i].co.z *= factor`
- **Replacement**: → `pipeline/export.py:rescale_elevation(mesh, factor)` via `trimesh.vertices`
- **Phase**: **Phase 1 MVP** (post-generation rescaling feature)

**TP3D_OT_open_website** / **TP3D_OT_join_discord** / **TP3D_OT_info_video** (operators.py:147–179)  
- **What**: Opens links in browser
- **Replacement**: Not needed (web backend doesn't open browser)
- **Phase**: Blender-internal infra (no port needed)

### Phase 1 Utility Operators

**TP3D_OT_save_preset** (operators.py:240–263)  
- **What**: Saves current scene properties to a `.csv` preset file
- **Replacement**: → `pipeline/config.py:save_preset(settings_dict, name)` via Pydantic serialization
- **Phase**: **Phase 1 MVP** (configuration presets)

**TP3D_OT_load_preset** (operators.py:265–278)  
- **What**: Loads properties from saved preset `.csv`
- **Replacement**: → `pipeline/config.py:load_preset(name)` via Pydantic deserialization
- **Phase**: **Phase 1 MVP**

**TP3D_OT_delete_preset** (operators.py:279–291)  
- **What**: Deletes preset file
- **Replacement**: → Standard file deletion; part of web API
- **Phase**: **Phase 1 MVP**

**TP3D_OT_clear_cache** (operators.py:293–313)  
- **What**: Deletes cached elevation tiles and OSM data
- **Replacement**: → `pipeline/cache.py:clear_cache(kind=None)` 
- **Phase**: **Phase 1 MVP** (cache management)

### Phase 1 Advanced Shape Operators

**TP3D_OT_pin_coords** (operators.py:371–423)  
- **What**: Places a 3D pin object at coordinates (via Overpass API lookup by city name)
- **Blender-isms**: Creates curve + mesh objects, appends from .blend assets
- **Replacement**: → Part of `pipeline/track.py` or geometry module
- **Phase**: **Phase 2 deferred** (non-essential visualization)

**TP3D_OT_magnet_holes** (operators.py:425–559)  
- **What**: Creates cylindrical holes for magnet inserts in selected mesh
- **Blender-isms**: Uses bmesh to create face loops, extrude, offset (modifier-heavy)
- **Replacement**: → Possible via `trimesh` boolean union with negative cylinders
- **Phase**: **Phase 2 deferred** (bracket/accessory feature)

**TP3D_OT_dovetail** (operators.py:560–709)  
- **What**: Creates dovetail joint cutouts for connection between tiles
- **Blender-isms**: Bmesh face manipulation, extrude, inset, multiple boolean ops
- **Replacement**: → Complex geometry, likely via Manifold engine or CadQuery
- **Phase**: **Phase 2 deferred** (advanced connection feature)

**TP3D_OT_bottom_mark** (operators.py:710–781)  
- **What**: Adds engraved text / mark on bottom of model
- **Blender-isms**: Creates text object, converts to mesh, boolean union on underside
- **Replacement**: → Via `trimesh` + text mesh library (e.g., `PIL`/`shapely` for outline)
- **Phase**: **Phase 2 deferred** (metadata feature)

**TP3D_OT_terrain_dummy** (operators.py:782–789)  
- **What**: Placeholder for locked premium features
- **Replacement**: Not needed (web doesn't have free vs premium UI split)
- **Phase**: Blender-internal infra

**TP3D_OT_color_mountain** (operators.py:790–891)  
- **What**: Colors mesh faces above a height threshold (elevation-based coloring)
- **Blender-isms**: Face normal comparison, material assignment per face, bmesh
- **Replacement**: → Part of `pipeline/assembly.py` (material/color assignment post-merge)
- **Phase**: **Phase 2 deferred** (coloring feature, requires multi-material output)

**TP3D_OT_contour_lines** (operators.py:892–908)  
- **What**: Generates contour line curves at elevation intervals
- **Blender-isms**: Creates curve objects via `primitives.create_curve_from_coordinates()`
- **Replacement**: → Part of `pipeline/terrain.py` (elevation slice/contour generation)
- **Phase**: **Phase 2 deferred** (visualization feature)

### Phase 2 Advanced Operators (Deferred)

**TP3D_OT_popup_merge** (operators.py:909–1024)  
- **What**: UI dialog for "merge with map" options (Paint, Project, SingleColorMode, Negative)
- **Replacement**: Not needed (web backend will expose merge as mode enum)
- **Phase**: Blender-internal infra

**TP3D_OT_import_text** / **TP3D_OT_import_svg** / **TP3D_OT_import_pin** (operators.py:1025–1672)  
- **What**: Import custom text/SVG/pin icon with dialog
- **Replacement**: Not needed (web will accept SVG/text via file upload + params)
- **Phase**: Blender-internal infra (UI dialogs)

**TP3D_OT_install_three_mf** / **TP3D_OT_check_update** / **TP3D_OT_install_update** (operators.py:1672–1757)  
- **What**: Install 3MF addon, check GitHub for updates, auto-download+unzip
- **Replacement**: Not needed (web backend uses trimesh directly)
- **Phase**: Blender-internal infra

### Summary: Operator Mapping to Pipeline

| Operator | → Pipeline Module | → Function |
|----------|------------------|-----------|
| TP3D_OT_run_generation | `pipeline/generate.py` | `generate(gpx_path, settings, output_dir, mode)` |
| TP3D_OT_export_stl | `pipeline/export.py` | `export_stl(mesh, path)` |
| TP3D_OT_export_obj | `pipeline/export.py` | `export_obj(mesh, path)` |
| TP3D_OT_export_three_mf | `pipeline/export.py` | `export_3mf(mesh, path)` |
| TP3D_OT_rescale | `pipeline/export.py` | `rescale_elevation(mesh, factor)` |
| TP3D_OT_save/load/delete_preset | `pipeline/config.py` | `save/load/delete_preset(name)` |
| TP3D_OT_clear_cache | `pipeline/cache.py` | `clear_cache(kind)` |
| TP3D_OT_magnet_holes | `pipeline/assembly.py` | `boolean_subtract_cylinders(mesh, holes)` [Phase 2] |
| TP3D_OT_dovetail | `pipeline/assembly.py` | `create_dovetail_joints(meshes)` [Phase 2] |
| TP3D_OT_color_mountain | `pipeline/assembly.py` | `color_by_elevation(mesh, threshold)` [Phase 2] |

---

## 3. Utilities (utils/)

### 3.1 **utils/io_gpx.py** (325 LOC)

**Scope**: GPX + IGC file parsing (no Blender dependencies except `bpy.context`)

**Functions**:
- `read_gpx(filepath)` → returns list of segments, each segment is list of `(lat, lon, elevation, timestamp)`
  - Handles GPX 1.0/1.1, namespace-agnostic
  - Supports `<trkseg>/<trkpt>` (primary) and `<rte>/<rtept>` (fallback)
  - Returns raw lat/lon, not Blender coords

- `read_igc(filepath)` → similar structure for IGC (aircraft telemetry format)
  - Parses pressure altitude vs GPS altitude
  - Lines 110–150: altitude decoding logic

**Blender dependencies**: Only line 38 (`bpy.context.scene.tp3d["o_verticesPath"] = ...` for UI display)

**Replacement for Phase 1**:
- → `pipeline/track.py:load_track(filepath: str) → Track`
- Use `xml.etree` (already imported) or `gpxpy` library
- Strip `bpy.context` calls — replace with return values
- Return Pydantic `Track` model with lat/lon/elev/time

**Risk flags**: None; code is mostly standalone

---

### 3.2 **utils/elevation.py** (700 LOC)

**Scope**: DEM API abstraction (OpenTopoData, Open-Elevation, Terrain-Tiles, OpenTopography)

**Key Functions**:
- `load_elevation_cache()` (line 69) → Loads JSON elevation cache from disk
- `save_elevation_cache()` (line 82) → Persists cache (with LRU eviction)
- `get_cached_elevation(lat, lon, api_type)` (line 99) → Cache lookup
- `fetch_elevation_cached(lat, lon)` → Calls API if not cached
- `fetch_elevation_tile_cached(bbox)` → Tile-based fetch (Terrain-Tiles API)
- `fetch_openTopoData_raster(bbox)` → Rasterizes DEM tile to numpy array
- `update_request_counter()` (line 30) → Tracks daily/monthly API quota

**Blender dependencies**:
- Line 32: `api = bpy.context.scene.tp3d.api`
- Line 85: `cacheSize = bpy.context.scene.tp3d.ccacheSize`
- Uses `bpy.utils.user_resource('CONFIG')` for cache dir (line 74, constants.py:36)

**API Endpoints Used**:
- OpenTopoData: `https://api.opentopodata.org/v1/{dataset}` (1000 req/day free)
- Open-Elevation: `https://api.open-elevation.com/api/v1/lookup` (1000 req/month)
- Terrain-Tiles: `https://tile.opentopodata.org/` (Z/X/Y PNG tiles, no auth)
- OpenTopography: `https://portal.opentopography.org/API/RASTER/` (requires API key)

**Replacement for Phase 1**:
- → `pipeline/terrain.py:download_dem(bbox, api_name, api_key=None) → numpy.ndarray`
- Keep cache logic (use local JSON file in `~/.trailprint3d/elevation_cache/`)
- Replace `bpy.context.scene.tp3d` with settings passed as params
- Use `requests` (already imported) for API calls
- Parse rasterio-compatible GeoTIFFs for DEM tiles

**Risk flags**: 
- **Hard dependency on external HTTP APIs** — need fallback/timeout logic
- Some datasets require API keys (OpenTopography) — must document
- Rate limiting (OpenTopoData 1000/day) — quota tracking needed

---

### 3.3 **utils/terrain.py** (1024 LOC)

**Scope**: OSM coloring pipeline (water, forests, buildings, roads, ocean)

**Key Functions**:
- `coloring_main(map, kind="WATER")` (line 13) → Orchestrates multi-tile OSM fetch + mesh union
  - Tiles the map bbox into 2°×2° chunks (lines 51–65)
  - Fetches OSM data per tile via `fetch_osm_data(bbox, kind)`
  - Builds mesh faces from polygons (line 276: `col_create_face_mesh()`)
  - Applies materials and extrusion
  - Returns Blender object or None

**Blender dependencies**:
- Line 21–24: Reads `minLat, minLon, maxLat, maxLon` from `bpy.context.scene.tp3d`
- Lines 193, 268: Creates Blender mesh objects via `bmesh`
- Line 298: `bpy.ops.object.shade_flat()`
- Line 306: Material assignment `bpy.data.materials.get("BLUE")`
- Line 308: `extrude_plane()` — bmesh extrude operator

**Replacement for Phase 1**:
- → `pipeline/assembly.py` (boolean union) + `pipeline/terrain.py` (DEM)
- Extract OSM data fetch logic → keep in `utils/osm.py` but remove Blender calls
- Mesh building → `trimesh.Trimesh()` creation + boolean ops
- Material assignment → deferred to Phase 2 (GLB/OBJ metadata only)
- Lines 51–65 (tiling logic) → keep as-is for parallel fetching

**Risk flags**:
- **Calls deferred imports at runtime** (line 14–19) to avoid circular imports — must refactor
- Line 308: `extrude_plane(element, elementHeight)` function not shown; likely uses modifier stack
- Line 306: Material assignment assumes pre-created materials (see `primitives.setupColors()`)

---

### 3.4 **utils/geo.py** (240 LOC)

**Scope**: Coordinate system conversions (lat/lon ↔ Blender/Mercator XY, haversine)

**Key Functions**:
- `calculate_scale(mapSize, coordinates, gen_type, diagonal)` (line 6)
  - Computes uniform scale factor for map projection
  - Handles 3 modes: FACTOR (relative), COORDINATES (distance-based), SCALE (Mercator)
  - Uses haversine for distance calculation

- `convert_to_blender_coordinates(lat, lon, elevation, timestamp)` (line 65)
  - Web Mercator: `x = R * lon°, y = R * ln(tan(π/4 + lat°/2))`
  - Applies `scaleElevation` and `autoScale` multipliers
  - **CRITICAL**: Uses `bpy.context.scene.tp3d` (line 67–69)

- `convert_to_neutral_coordinates(lat, lon, elevation, timestamp)` (line 79)
  - Same Mercator but *without* `sScaleHor` multiplier (pure reference frame)

- `convert_to_geo(x, y)` (line 92) → Inverse Mercator (Blender → lat/lon)

- `haversine(lat1, lon1, lat2, lon2)` (line 102) → Distance in km

- `calculate_total_length(points)` (line 117) → Total GPX track distance
- `calculate_total_elevation(points)` (line 126) → Elevation gain (uphill only)
- `calculate_total_time(points)` (line 136) → Duration from timestamps
- `calculate_date(points)` (line 149) → Extract date from first point

**Blender dependencies**:
- Line 7–9, 67–74: `bpy.context.scene.tp3d` reads for scale/elevation factors
- Constants: `const.R = 6371.0` (Earth radius km)

**Replacement for Phase 1**:
- → `pipeline/frame.py:to_blender_coords(lat, lon, elev, scale_params)`
- + `pipeline/track.py:track_stats(track) → TrackStats`
- Remove `bpy.context` calls → pass `scale_params` dict or Pydantic `ScaleConfig`
- Keep pure math (haversine, Mercator formulas)
- Constants (`R`) → move to `pipeline/constants.py`

**Risk flags**: None; mostly pure math

---

### 3.5 **utils/mesh_ops.py** (1524 LOC) — **LARGEST UTILITY**

**Scope**: Core mesh manipulation (bmesh operations, boolean union, extrusion, normal calc)

**Key Functions** (partial list):
- `applyModifier(obj, modifier)` (line 5) → Apply modifier to mesh
- `recalculateNormals(obj, ins=False)` (line 18) → Fix inside/outside normals
- `selectBottomFaces(obj)` (line 35) → Select downward-facing faces
- `getBottomFacesArea(obj)` (line 78) → Total area of bottom surface
- `simplify_mesh(obj, ...)` (implied in OSM coloring) → Reduce vertex count
- `boolean_operation(obj1, obj2, operation)` (line ~200, signature unclear) → Boolean union/diff/intersect
  - **CRITICAL for Phase 1**: Used to merge trail, terrain, elements
  - Likely uses `bpy.ops.object.boolean_modifier_add()` + modifier eval

- `merge_objects(objects_list)` (line ~400) → Merges multiple meshes into single
  - Used extensively for coloring pipeline

- `triangulate_mesh(obj)` (line ~600) → Converts n-gon faces to triangles
  - Required for STL export

- `extrude_plane(obj, distance)` (line ~800) → Extrude mesh along normal
  - Used for water/road/element extrusion

- `create_mesh_from_coordinates(coords)` (line ~1000) → Builds mesh from 2D points
  - Uses Delaunay? (not shown)

**Blender dependencies**: EXTENSIVE
- `bmesh` module (lines 1–500): Face/edge/vert manipulation
- `bpy.ops.object.*`: Modifier stack, mode switching
- `mathutils.bvhtree`: Spatial queries

**Replacement for Phase 1**: **HIGHEST PRIORITY REFACTOR**
- → `pipeline/assembly.py:boolean_union(meshes) → Trimesh`
  - Use **Manifold engine** (via `manifold` Python package) for robust boolean ops
  - Alternative: `trimesh.boolean.union(mesh_list)` if Manifold unavailable
  
- → `pipeline/terrain.py:triangulate_dem(dem_array, scale) → Trimesh`
  - Use `scipy.spatial.Delaunay(points_2d)` + elevation lookup
  
- → `pipeline/track.py:extrude_curve(curve, radius, scale) → Trimesh`
  - Use Frenet frame + disc offset (see below in generation.py)

- → `pipeline/export.py:simplify_mesh(mesh, ratio) → Trimesh`
  - Use `trimesh.simplification.simplify()` (via quadric error metric)

**Risk flags**: 
- **Boolean operations are fragile** — bmesh boolean sometimes produces non-manifold geometry
  - Workaround in Phase 1: Use Manifold; if not available, warn user
- No clear logic for choosing boolean operation type (union/diff/intersect) — must infer from context
- `extrude_plane()` likely uses modifier stack — expensive in Blender, free in trimesh

---

### 3.6 **utils/osm.py** (1035 LOC)

**Scope**: Overpass API queries for OSM features (water, forests, buildings, roads, etc.)

**Key Functions**:
- `fetch_osm_data(bbox, kind, max_cache_age_hours, return_cache_status)` (line 15)
  - **Orchestrator for OSM data retrieval**
  - Queries: `WATER`, `FOREST`, `SCREE`, `CITY`, `GREENSPACE`, `FARMLAND`, `GLACIER`, `BUILDINGS`, `STREETS`, `OCEAN`
  - Lines 50–58: Disk cache via SHA256(bbox, kind) → JSON
  - Lines 70+: Build Overpass query string based on `kind`
  - HTTP retry loop with exponential backoff
  - Returns JSON: nodes + ways dict

- `build_osm_nodes()` (signature unclear) → Reconstructs full geometry from OSM node/way refs

- `extract_multipolygon_bodies()` → Parses OSM multipolygon relations

- `calculate_polygon_area_2d(coords)` → Shoelace formula for filtering tiny features

**Blender dependencies**:
- Line 19–25: Reads `bpy.context.scene.tp3d.*` for feature toggles and mapsize
- Deferred import of `coloring_main()` (line 13, circular dependency prevention)

**APIs Used**:
- **Overpass**: `https://overpass-api.de/api/interpreter` (limit: ~requests per hour; 10 second timeout)
  - QL query format: `[bbox:S,W,N,E][out:json]{...}`
  - Common queries: `natural=water`, `landuse=forest`, `building=*`, `highway=motorway`, etc.

**Replacement for Phase 1**:
- → `pipeline/terrain.py:fetch_osm_elements(bbox, element_type) → List[Polygon]`
  - Keep caching logic (same SHA256 approach, different cache dir)
  - Remove `bpy.context.scene.tp3d` reads → pass as params
  - Returns shapely Polygons or raw coordinate lists
  - Filter by area threshold in caller, not here

**Risk flags**:
- **Hard dependency on Overpass API** — slow (5–30s per bbox), rate-limited, may timeout
  - Mitigation: Cache aggressively (default 720h = 30 days), implement client-side queue
- **Complex query logic** scattered across ~50 lines — needs tests
- **Multipolygon handling** (rings with holes) — potential for incorrect geometry

---

### 3.7 **utils/generation.py** (1254 LOC) — **MAIN ORCHESTRATOR**

**Scope**: Core pipeline orchestration (`runGeneration` entry point)

**Key Functions**:
- `_rg_validate_inputs(flags)` (line 18)
  - Reads all `bpy.context.scene.tp3d.*` properties
  - Validates file paths, API key, conflicting modes
  - Returns `props` dict or None on error

- `_rg_load_coordinates(flags, props)` (line 196)
  - Loads GPX via `utils.io_gpx.read_gpx()`
  - Unpacks to flat list: `[(lat, lon, elev, time), ...]`
  - Computes bounding box for DEM

- `_rg_compute_trail_stats(flags, coordinates)` (line 255)
  - Calls `geo.calculate_total_length/elevation/time/date()`
  - Stores in `bpy.context.scene.tp3d.total_length` etc.

- `_rg_create_map_object(flags, props, modelname, centerx, centery)` (line 285)
  - Creates base mesh shape (hexagon/square/circle) via `primitives.create_hexagon()` etc.
  - Applies texture via rasterized DEM + triangulation
  - Extrudes to add thickness (`minThickness` + elevation scale)
  - Uses `bpy.data.meshes.new()`, `bmesh.from_mesh()`, adds geometry

- `_rg_build_terrain_elements(obj, scaleHor, curveObj, phase_start, phase_end)` (line 343)
  - Calls `terrain.coloring_main()` for each enabled element type (water, forests, etc.)
  - Merges all element meshes via `mesh_ops.merge_objects()`
  - Applies boolean union with map via `mesh_ops.boolean_operation()`
  - Handles single-color-mode rescaling

- `_rg_apply_single_color_mode(obj, curveObjs, terrain, props)` (line 529)
  - Alternative to painting elements on map
  - Creates new mesh with elevated regions based on threshold
  - Used when user wants monochrome 3D printable model

- `_rg_assign_materials_and_export(obj, curveObjs, textobj, plateobj, props, buggyDataset, start_time, exportformat, elements)` (line 633)
  - Assigns Blender materials (colors) to mesh based on feature type
  - Writes metadata (custom properties) via `metadata.writeMetadata()`
  - Calls export functions based on `exportformat` (STL/OBJ/3MF)
  - Optionally auto-exports if not disabled

- `build_fetch_items(map_km)` (line 775)
  - Determines which OSM element types to fetch based on map size
  - Returns list of `(kind, enabled)` tuples
  - Prevents fetching forests on 50km+ maps (too dense)

- `runGeneration(type, locked_scale)` (line 811)
  - **MAIN ENTRY POINT**, called by `TP3D_OT_run_generation.execute()`
  - Orchestrates: validate → load GPX → compute stats → fetch DEM → create map → add elements → color → export
  - Manages progress overlay via `_progress.ProgressOverlay.get().update(...)`
  - Time tracking for performance metrics
  - Exception handling with user-facing error messages

**Blender dependencies**: PERVASIVE
- Lines 34–75: Reads ~40 properties from `bpy.context.scene.tp3d`
- Throughout: Passes Blender mesh objects (`bpy.data.objects`) between functions
- Line 811+: Blender timer + context managers

**Replacement for Phase 1**: **THIS IS THE CORE REFACTOR**
- → `pipeline/generate.py:generate(gpx_path: str, settings: GenerateSettings, output_dir: str, mode: str) → GenerateResult`

**Signature**:
```python
# pipeline/generate.py
from typing import Optional
from pathlib import Path
from pydantic import BaseModel

class GenerateSettings(BaseModel):
    # Shape
    shape: Literal["hexagon", "square", "circle"] = "hexagon"
    obj_size: int = 100  # mm
    shape_rotation: int = 0
    
    # Elevation
    num_subdivisions: int = 4
    scale_elevation: float = 1.0
    min_thickness: float = 2.0
    fixed_elevation_scale: bool = False
    
    # Path
    path_thickness: float = 1.2
    path_scale: float = 0.8
    overwrite_path_elevation: bool = True
    
    # DEM API
    dem_api: Literal["opentopodata", "open-elevation", "terrain-tiles"] = "terrain-tiles"
    dem_dataset: str = "aster30m"
    
    # Elements (Phase 2)
    water_active: bool = False
    forest_active: bool = False
    # ... etc
    
    # Scale mode
    scale_mode: Literal["factor", "coordinates", "global"] = "factor"
    scale_lon1: float = 0
    scale_lat1: float = 0
    scale_lon2: float = 0
    scale_lat2: float = 0

class GenerateResult(BaseModel):
    mesh: trimesh.Trimesh
    track_stats: dict  # {total_length_km, elevation_gain_m, date, ...}
    metadata: dict

def generate(
    gpx_path: str,
    settings: GenerateSettings,
    output_dir: str,
    mode: str = "stl"  # stl|obj|gltf|glb|3mf
) -> GenerateResult:
    """Main pipeline orchestrator (Phase 1 MVP)."""
    # 1. Load + parse GPX
    track = load_track(gpx_path)
    
    # 2. Compute stats
    stats = compute_track_stats(track)
    
    # 3. Fetch DEM (elevation grid)
    dem_array, dem_geo = download_dem(
        track.bbox, 
        settings.dem_api, 
        settings.dem_dataset
    )
    
    # 4. Create terrain mesh (subdivision + triangulation)
    terrain_mesh = create_terrain_mesh(
        dem_array, 
        dem_geo, 
        settings.num_subdivisions,
        settings.scale_elevation
    )
    
    # 5. Extrude terrain for minimum thickness
    terrain_mesh = add_base_thickness(
        terrain_mesh,
        settings.min_thickness
    )
    
    # 6. Create base shape (hexagon/square/circle)
    base_shape = create_shape_boundary(
        settings.shape,
        settings.obj_size,
        track.center
    )
    
    # 7. Intersect terrain with shape (crop to boundary)
    terrain_mesh = boolean_intersect(terrain_mesh, base_shape)
    
    # 8. Create track extrusion (Frenet frame + tube)
    track_mesh = create_track_extrusion(
        track,
        settings.path_thickness,
        dem_array,
        dem_geo
    )
    
    # 9. Union track + terrain
    final_mesh = boolean_union([terrain_mesh, track_mesh])
    
    # 10. Export
    export(final_mesh, output_dir, mode, stats)
    
    return GenerateResult(mesh=final_mesh, track_stats=stats, metadata={...})
```

**Risk flags**:
- **Massive refactor required** — 1254 LOC orchestrator touches 8+ subsystems
- **Progress reporting** — currently done via Blender overlays; web will need polling/webhook
- **Exception handling** — currently catches and shows Blender message box; web needs API response codes
- **Circular imports** — many deferred imports (line 24, etc.) to avoid load-time cycles

---

### 3.8 **utils/primitives.py** (576 LOC)

**Scope**: Mesh primitive generation (shapes, curves, ribbons)

**Key Functions**:
- `setupColors()` (line 34) → Creates 12 Blender materials (BASE, FOREST, WATER, TRAIL, etc.)
  - Used for per-feature coloring; not needed in web (export without colors or use vertex colors)

- `create_curve_from_coordinates(coordinates)` (line ~80)
  - Builds Blender curve object from list of XY(Z) points
  - Used for track visualization before extrusion

- `create_hexagon(size, num_subdivisions, name)` (line ~150)
  - Generates hexagon mesh with subdivisions (icosphere-style)
  - Returns Blender mesh object
  - **Needed for Phase 1**: Adapt to return trimesh.Trimesh

- `create_rectangle(width, height, num_subdivisions, name)` (line ~200)
  - Rectangle with configurable aspect ratio

- `create_circle(radius, num_subdivisions, num_segments, name)` (line ~300)
  - Circle with configurable vertex count

- `create_ellipse(radius, num_subdivisions, aspect_ratio, num_segments, name)` (line ~350)
  - Ellipse (Phase 2 premium)

- `create_octagon(size, num_subdivisions, name)` (line ~400)
  - Octagon (Phase 2 premium)

- `create_heart(size, num_subdivisions, name)` (line ~450)
  - Heart shape (Phase 2 premium)

- `col_create_face_mesh(name, coords)` (line ~500)
  - Creates single-face polygon mesh from 2D coords
  - Used for OSM element rendering (water polygons, etc.)

- `create_ribbon_mesh(name, pts, half_width)` (line ~520)
  - Creates tube/ribbon along polyline (used for track extrusion before Frenet frame)

- `col_create_line_curve(name, coords, close, collection, bevel_depth)` (line ~540)
  - Creates Blender curve object for coastlines, roads (bevel-extruded later)

**Blender dependencies**: Heavy
- `bpy.data.meshes.new()`, `bpy.data.objects.new()`
- `bmesh.new()`, face creation

**Replacement for Phase 1**:
- → `pipeline/frame.py:create_base_shape(shape_name, size, num_subdivisions) → trimesh.Trimesh`
  - Rewrite using `numpy` + `scipy.spatial` (Delaunay triangulation)
  - Return trimesh objects directly
  - Keep hexagon/square/circle; defer ellipse/octagon/heart to Phase 2

- → `pipeline/track.py:create_track_tube(track_points, thickness, heights) → trimesh.Trimesh`
  - Use Frenet frame + disc generation (see generation.py notes)

**Risk flags**: None; math-heavy, easy to convert

---

### 3.9 **utils/text_objects.py** (1247 LOC) — **PREMIUM FEATURES**

**Scope**: Text shape generation (hexagon with text, backplate, icons)

**Functions** (selection):
- `create_text(name, text, position, scale_multiplier, ...)` (line 21)
- `appendTextIcon(textobject, icon, scaleM)` (line ~60)
  - Appends pre-made icon (cycling, hiking, running, etc.) from `assets/other.blend`
- `HexagonInnerText(MapObject)` (line ~600)
  - Generates hexagon with text inset on top
- `HexagonOuterText()` (line ~700)
  - Hexagon with backplate + text on reverse side
- `HexagonFrontText()` (line ~800)
  - Hexagon with frontplate + text on front
- `OctagonOuterText()` (line ~900)
  - Octagon variant
- `BottomText(obj)` (line ~1000)
  - Adds text engraving to bottom

**Blender dependencies**: EXTENSIVE
- `bpy.data.curves.new()`, `bpy.data.fonts.load()`
- Calls `appendCollection()` to load assets from `assets/other.blend`
- Boolean operations to merge text with shape

**Replacement for Phase 1**:
- **DEFER TO PHASE 2** (text shapes not MVP)
- Phase 2: Use shapely + PIL for rasterized text → triangulation

**Phase 1 note**: Silently skip if text shape selected (return base shape only)

---

### 3.10 **utils/scene.py** (442 LOC)

**Scope**: Blender scene manipulation (camera zoom, origins, object selection)

**Functions**:
- `open_website(self, context, url)` (line 8) → Opens URL in browser
- `transform_MapObject(obj, newX, newY)` (line 12) → Translates object
- `zoom_camera_to_selected(obj)` (line 16) → Frames viewport
- `set_origin_to_3d_cursor(tobj)` (line 34) → Sets mesh origin
- `get_random_world_vertices(obj, count)` (line 54) → Samples random mesh vertices
- `get_object_surface_area(obj, apply_modifiers, z_threshold)` (line ~80) → Total area (with optional Z filter)
- `setOriginToTerrainFace(obj, tol, seed, max_tries)` (line ~130) → Places origin on terrain surface
- `closest_distance_between_objects(obj_a, obj_b)` (line ~180) → Minimum distance (uses BVH tree)
- `remove_objects(objects)` (line ~210) → Delete list of objects
- `getHighestLowest(obj)` (line ~230) → Min/max Z coordinate
- `show_message_box(message, icon, title)` (line ~250) → Popup dialog
- `toggle_console()` (line ~280) → Show/hide console window
- `importSVGtoMerge(MapObject)` (line ~310) → Loads SVG from file, rasterizes, merges with map

**Blender dependencies**: All calls are Blender-specific

**Replacement for Phase 1**:
- `get_object_surface_area()` → `pipeline/export.py:mesh_surface_area(mesh) → float`
  - Use `trimesh.bounds.contains()` for Z filtering
  
- `remove_objects()` → Not needed (web doesn't manage object collections)

- `show_message_box()` → Return errors via API response, not popups

- Most others → Not needed in web backend

**Phase 1 mapping**:
- Line 80: `get_object_surface_area()` used in Phase 2 for land cover filtering
- Line 250: `show_message_box()` → replace with logging + return value

---

### 3.11 **utils/metadata.py** (230 LOC)

**Scope**: Custom property metadata attached to Blender objects

**Key Function**:
- `writeMetadata(obj, type="MAP")` (line 4)
  - Writes ~50 properties to `obj["Custom Property Name"]` (Blender custom data)
  - Examples: `obj["Generation Duration"]`, `obj["Elevation Scale"]`, `obj["latitude"]`, etc.

**Blender dependencies**: 
- `bpy.context.scene.tp3d.*` reads
- `obj[key] = value` (Blender custom properties dict)

**Replacement for Phase 1**:
- → `pipeline/export.py:attach_metadata(mesh, stats, settings) → dict`
  - Return metadata as dict (not attached to mesh)
  - For GLB export: embed in JSON via `trimesh.Trimesh.export(..., include_normals=True, ...)`
  - For STL/OBJ: save as separate `.json` sidecar file

---

### 3.12 **utils/presets.py** (216 LOC)

**Scope**: Save/load user settings to/from CSV files

**Functions**:
- `save_myproperties_to_csv(filename)` (line 8)
  - Reads all `bpy.context.scene.tp3d` properties, writes CSV rows: `[name, value]`
  - Stores in `~/.config/TP3D-presets/` (on Linux)

- `load_myproperties_from_csv(filename)` (implied, not shown)
  - Reverse: reads CSV, sets `bpy.context.scene.tp3d.*`

- `appendCollection()` (line 60)
  - Loads Blender collection from `.blend` file (assets/puzzles.blend, etc.)
  - Phase 2 feature (special templates)

**Blender dependencies**:
- `bpy.context.scene.tp3d.*` reads/writes
- `bpy.data.libraries.load()` for .blend linking

**Replacement for Phase 1**:
- → `pipeline/config.py:save_settings(settings: GenerateSettings, name: str)`
  - Use Pydantic `.model_dump_json()` → save to `~/.trailprint3d/presets/{name}.json`
  
- → `pipeline/config.py:load_settings(name: str) -> GenerateSettings`
  - Use Pydantic `.model_validate_json()`

---

## 4. Settings Schema Seed (from props.py)

**props.py** defines ~100 properties in `TP3D_PG_properties` PropertyGroup (lines 34–414). Below is a Pydantic-ready mapping.

### 4a. Phase 1 Properties (Port Now)

These become Pydantic fields in `GenerateSettings`:

#### File Inputs
```python
file_path: str = ""           # GPX file to load
export_path: str = ""         # Directory for output files
trailName: str = ""           # Trail name override (defaults to filename)
```

#### Shape Configuration
```python
shape: Literal[
    "hexagon", "square", "circle"
] = "hexagon"
shape_rotation: int = 0       # Degrees, -360..360
obj_size: int = 100           # Base size in mm, 5..10000
```

#### Elevation & Terrain
```python
num_subdivisions: int = 4     # Mesh resolution, 1..10
scale_elevation: float = 1.0  # Elevation multiplier, 0..10000
path_scale: float = 0.8       # Path scale relative to map
path_thickness: float = 1.2   # Track tube diameter in mm
min_thickness: float = 2.0    # Base minimum thickness in mm
overwrite_path_elevation: bool = True  # Cast trail onto terrain
fixed_elevation_scale: bool = False  # Force 10mm height range
```

#### Scale Mode & Projection
```python
scalemode: Literal[
    "factor", "coordinates", "global"
] = "factor"
scale_lon1: float = 0         # Coordinate scaling: point 1
scale_lat1: float = 0
scale_lon2: float = 0         # Coordinate scaling: point 2
scale_lat2: float = 0
```

#### DEM/API Configuration
```python
api: Literal[
    "opentopodata", "open-elevation", "terrain-tiles", "opentopography"
] = "terrain-tiles"
dataset: Literal[
    "srtm30m", "aster30m", "ned10m", "mapzen", "nzdem8m", "eudem25m"
] = "aster30m"
api_retries: int = 5          # Retry count for failed requests
self_hosted: str = ""         # Custom OpenTopoData URL
open_topography_dataset: str = "SRTMGL1"  # OT-specific dataset
open_topography_api_key: str = ""  # (from addon prefs)
```

#### Output Format
```python
export_format: Literal["stl", "obj", "gltf", "glb", "3mf"] = "stl"
disable_auto_export: bool = False
disable_3mf_export: bool = False
```

#### Caching
```python
cache_size: int = 50000       # Max elevation cache entries
disable_cache: bool = False   # Skip caching (for debugging)
```

#### Post-Processing (Phase 1 edge cases)
```python
rescale_multiplier: float = 1.0  # (TP3D_OT_rescale operator)
thicken_value: float = 1.0        # (TP3D_OT_thicken operator)
```

### 4b. Phase 2 Properties (Defer, Do Not Implement)

These properties control features explicitly deferred to Phase 2+. **Do not port** in Phase 1:

#### Element/OSM Features
```python
# Water
col_water_ponds_active: bool = False
col_water_small_rivers_active: bool = False
col_water_big_rivers_active: bool = False
col_water_area_threshold: float = 1.0  # km²
col_water_stream_width: float = 1.0    # Thickness multiplier

# Forests
col_forest_active: bool = False
col_forest_area_threshold: float = 10.0

# Scree/Rocky
col_scree_active: bool = False
col_scree_area_threshold: float = 1.0

# Cities
col_city_active: bool = False
col_city_area_threshold: float = 1.0

# Greenspace (parks, gardens)
col_greenspace_active: bool = False
col_greenspace_area_threshold: float = 1.0

# Farmland
col_farmland_active: bool = False
col_farmland_area_threshold: float = 1.0

# Glaciers
col_glacier_active: bool = False
col_glacier_area_threshold: float = 1.0

# Keep non-manifold objects
col_keep_manifold: bool = False
```

#### Buildings & Roads (Phase 2)
```python
# Buildings
elements_buildings_active: bool = False
elements_buildings_height_multiplier: float = 1.0

# Roads
show_roads: bool = False
elements_streets_width_multiplier: float = 1.0
elements_streets_big_active: bool = False      # motorway, primary
elements_streets_medium_active: bool = False   # secondary, tertiary
elements_streets_small_active: bool = False    # residential, footway
```

#### Ocean (Phase 2)
```python
elements_ocean_active: bool = False
elements_ocean_flip: bool = False
```

#### Advanced Modes (Phase 2)
```python
single_color_mode: bool = False
single_color_mode_tolerance: float = 0.2
single_color_mode_tolerance_elements: float = 0.4
element_mode: Literal["paint", "singlecolormode_remesh", "separate"] = "paint"
element_mode_inset: float = 2.0
x_terrain_offset: float = 0.0    # Terrain shift from trail
y_terrain_offset: float = 0.0
```

#### Text Shapes (Phase 2)
```python
shape: Literal[
    ..., "hexagon_inner_text", "hexagon_outer_text", 
    "hexagon_front_text", "octagon_outer_text"
] = ...
text_font: str = ""
text_size: int = 5
text_size_title: int = 0
title_field: str = "{name}"
text_field1: str = "{length}"
text_field2: str = "{elevation}"
text_field3: str = "{duration}"
title_icon: Literal[
    "cycling", "hiking", "running", "swimming", 
    "skiing", "snowboarding", "kayak", "no"
] = "no"
icon_text1: Literal[...] = "distance"
icon_text2: Literal[...] = "elevation"
icon_text3: Literal[...] = "time"
text_angle_preset: int = 0
```

#### Plate/Backplate (Phase 2)
```python
outer_border_size: int = 20           # %
plate_thickness: float = 5.0          # mm
plate_insert_value: float = 0.0       # Map cutout depth
plate_bevel: float = 0.0              # mm
```

#### Contour Lines (Phase 2)
```python
cl_thickness: float = 0.2             # mm
cl_distance: float = 2.0              # m elevation interval
cl_offset: float = 0.0                # Z offset
```

#### Mountain Coloring (Phase 2)
```python
mountain_threshold: int = 60          # % of max elevation
```

#### Special Templates (Phase 2)
```python
generation_mode: Literal[
    "generation", "multi", "terrain"
] = "generation"
map_mode: Literal[
    "fromplane", "fromcenter", "2points"
] = "fromplane"
special_blend_file: Literal[
    "holder.blend", "puzzles.blend", "connectors.blend"
] = "puzzles.blend"
```

#### Statistics (Read-Only, Computed)
```python
# Output by generation:
o_vertices_path: str = ""
o_vertices_map: str = ""
o_map_scale: str = ""
o_time: str = ""
o_api_counter_opentopodata: str = ""
o_api_counter_openelevation: str = ""
o_centerx: float = 0
o_centery: float = 0

# Track metadata:
total_length: float = 0       # km
total_elevation: float = 0    # m
total_time: float = 0         # hours
average_speed: float = 0      # km/h
trail_date: str = ""          # ISO format

# Terrain bounds:
lowest_z: float = 0
highest_z: float = 0
min_lat: float = 0
max_lat: float = 0
min_lon: float = 0
max_lon: float = 0
```

---

## 5. Pipeline Module Mapping Summary

| Addon Source | → Pipeline Module | Replacement Library | Phase |
|--------------|------------------|-------------------|-------|
| `operators.py:TP3D_OT_run_generation` | `pipeline/generate.py` | Orchestrator | **Phase 1** |
| `operators.py:TP3D_OT_export_*` | `pipeline/export.py` | trimesh.exchange | **Phase 1** |
| `operators.py:TP3D_OT_rescale` | `pipeline/export.py:rescale_elevation()` | trimesh.vertices | **Phase 1** |
| `operators.py:TP3D_OT_save/load/delete_preset` | `pipeline/config.py` | Pydantic + JSON | **Phase 1** |
| `operators.py:TP3D_OT_clear_cache` | `pipeline/cache.py` | pathlib | **Phase 1** |
| `operators.py:TP3D_OT_magnet_holes` | `pipeline/assembly.py:subtract_cylinders()` | trimesh/Manifold | **Phase 2** |
| `operators.py:TP3D_OT_dovetail` | `pipeline/assembly.py:create_dovetail()` | trimesh/CadQuery? | **Phase 2** |
| `operators.py:TP3D_OT_bottom_mark` | `pipeline/assembly.py:engrave_text()` | PIL/shapely | **Phase 2** |
| `operators.py:TP3D_OT_color_mountain` | `pipeline/assembly.py:color_by_elevation()` | numpy/trimesh vertex_attributes | **Phase 2** |
| `operators.py:TP3D_OT_contour_lines` | `pipeline/terrain.py:generate_contours()` | scipy.ndimage | **Phase 2** |
| `utils/io_gpx.py` | `pipeline/track.py:load_track()` | gpxpy / xml.etree | **Phase 1** |
| `utils/elevation.py` | `pipeline/terrain.py:download_dem()` | rasterio + requests | **Phase 1** |
| `utils/terrain.py` | `pipeline/terrain.py` + `pipeline/assembly.py` | rasterio/shapely/trimesh + Manifold | **Phase 1** (DEM) + **Phase 2** (coloring) |
| `utils/geo.py` | `pipeline/frame.py` + `pipeline/track.py` | numpy/pyproj | **Phase 1** |
| `utils/mesh_ops.py` | `pipeline/assembly.py` | trimesh + Manifold | **Phase 1** |
| `utils/osm.py` | `pipeline/terrain.py:fetch_osm_elements()` | shapely + requests | **Phase 2** (elements) |
| `utils/generation.py` | `pipeline/generate.py:generate()` | Orchestrator | **Phase 1** |
| `utils/primitives.py` | `pipeline/frame.py` | trimesh + scipy.spatial | **Phase 1** |
| `utils/text_objects.py` | `pipeline/frame.py:add_text_shape()` | PIL + shapely | **Phase 2** |
| `utils/scene.py` | `pipeline/export.py` (partial) | trimesh + numpy | **Phase 1** (partial) |
| `utils/metadata.py` | `pipeline/export.py:attach_metadata()` | dict + JSON | **Phase 1** |
| `utils/presets.py` | `pipeline/config.py` | Pydantic + JSON | **Phase 1** |
| `progress.py` | `pipeline/progress.py` (new) | HTTP polling | **Phase 2** |
| `panels.py` | N/A (Web UI) | React/Vue | Web UI |
| `export.py` | `pipeline/export.py` | trimesh | **Phase 1** |
| `addon_preferences.py` | `pipeline/config.py` (global settings) | Pydantic | **Phase 1** |

---

## 6. External Dependencies & Coordinate Systems

### HTTP APIs

1. **OpenTopoData**: `https://api.opentopodata.org/v1/{dataset}`
   - Limit: 1000 req/day (free tier)
   - Query: `?locations=lat,lon` (single point) or raster tile fetch
   - Response: JSON with `results[].elevation`
   - Datasets: `srtm30m`, `aster30m`, `ned10m`, `mapzen`, `nzdem8m`, `eudem25m`

2. **Open-Elevation**: `https://api.open-elevation.com/api/v1/lookup`
   - Limit: 1000 req/month (free)
   - Query: `?locations=lat,lon|lat,lon`
   - Response: JSON with `results[].elevation`

3. **Terrain-Tiles**: `https://tile.opentopodata.org/` (Terrarium PNG + Mapbox format)
   - No limit; Z/X/Y tile path: `/{z}/{x}/{y}.png`
   - Each pixel encodes elevation as RGB24: `elevation = (R * 256 + G + B/256) - 32768` meters
   - Cached locally in `~/.config/TrailPrint3D_Cache/terrarium_cache/`

4. **OpenTopography**: `https://portal.opentopography.org/API/RASTER/`
   - Requires API key (free registration)
   - Query: `?demtype={dataset}&south=...&north=...&west=...&east=...&outputFormat=GeoTIFF&API_Key=...`
   - Datasets: `SRTMGL1` (30m), `SRTMGL3` (90m), `SRTM15Plus` (500m), `AW3D30`, `NASADEM`, `COP30`, `COP90`
   - Returns GeoTIFF (needs rasterio to read)

5. **Overpass API**: `https://overpass-api.de/api/interpreter`
   - Limit: ~requests per hour; 10 second timeout
   - Query: Overpass QL format (XML or JSON output)
   - Examples:
     - Water: `[out:json];(way["natural"="water"];relation["natural"="water"];);out geom;`
     - Buildings: `[out:json];(way["building"];relation["building"];);out geom;`
     - Roads: `[out:json];(way["highway"="motorway"];);out geom;`
   - Cached locally in `~/.config/TrailPrint3D_Cache/overpass_cache/`

6. **GitHub** (updater only):
   - `https://raw.githubusercontent.com/EmGi96/TrailPrint3D/main/TrailPrint3D/__init__.py`
   - Checks version; downloads zip if update available
   - **Phase 1**: Not needed (no updater in web backend)

### Coordinate Systems

- **Input**: WGS84 latitude/longitude (GPX standard)
- **DEM tiles**: Various projections (see rasterio for geo-referencing)
- **Blender/Output**: Web Mercator projection (EPSG:3857)
  - Formula: `x = R * lon_radians`, `y = R * ln(tan(π/4 + lat_radians/2))`
  - Where `R = 6371 km` (Earth radius)
  - This is a conformal projection (preserves angles, not areas)
  - **Note**: Addon uses this for all map generation; Phase 1 must match

### File Formats Handled

- **Input**: `.gpx` (XML, GPX 1.0/1.1 compatible), `.igc` (plaintext, aircraft flight logs)
- **Output**: `.stl` (STL ASCII/binary), `.obj` (OBJ + `.mtl`), `.glb`/`.gltf` (glTF 2.0 + embedded textures), `.3mf` (3D Manufacturing Format, ZIP-based)
- **Cache**: `.json` (elevation cache), `.json` (OSM cache)
- **Assets**: `.blend` (Blender linked collections for puzzles/holders — Phase 2 only)

---

## 7. Risk Flags and Blender-isms That Need Careful Handling

### High Risk

1. **Boolean Operations (mesh_ops.py)**
   - Addon uses `bpy.ops.object.boolean_modifier_add()` + modifier evaluation
   - Blender's boolean can produce non-manifold geometry
   - **Mitigation**: Use Manifold engine (robust, open-source); fallback to trimesh.boolean
   - **Test**: Validate final mesh is manifold before export

2. **Elevation Grid Triangulation**
   - Addon: Uses bmesh + subdivision surface or implicit tessellation
   - **Phase 1 requirement**: Explicit Delaunay triangulation via scipy
   - **Risk**: Different mesh topology than Blender → visual differences
   - **Mitigation**: Generate test cases, compare triangle count and vertex errors

3. **Overpass API Timeouts**
   - OSM fetch can hang for large maps (e.g., 50km radius, 40+ tiles)
   - Addon: No timeout logic visible
   - **Phase 1**: Implement per-request timeout (10s), skip tile on failure, warn user
   - **Phase 2**: Implement queue + rate limiting

4. **Frenet Frame Extrusion (for track tube)**
   - Addon: Uses `create_ribbon_mesh()` + discrete offsets
   - Not fully visible in snippets; likely uses bmesh with custom loop offsets
   - **Phase 1 requirement**: Implement Frenet frame (curvature, binormal) + generate tube points
   - **Risk**: Complex math; numerical instability at sharp curves
   - **Test**: Compare track tube geometry vs addon for hand-drawn test GPX

5. **Single-Color Mode (SCM)**
   - `_rg_apply_single_color_mode()`: Creates entire new mesh based on elevation threshold
   - Addon uses complex bmesh manipulation + re-mesh with offset
   - **Risk**: Phase 1 MVP skips; Phase 2 requires different algorithm (voxel-based?)
   - **Mitigation**: Document as Phase 2 advanced feature

### Medium Risk

6. **Material Slots (OBJ export)**
   - Addon checks `if zobj.material_slots:` to decide STL vs OBJ
   - Web backend: Always use trimesh; can embed materials in GLB/OBJ via vertex colors or textures
   - **Phase 1**: Ignore materials; export colorless geometry
   - **Phase 2**: Implement vertex colors (GLB supports this natively)

7. **SVG Import (scene.py line 310)**
   - `importSVGtoMerge()`: Likely uses `bpy.ops.import_curve.svg()`
   - **Phase 1**: Not needed (web accepts GeoJSON or WKT for custom boundaries)
   - **Phase 2**: Implement via PIL + Shapely if needed

8. **Text Shape Complexity (text_objects.py)**
   - Hexagon with inner/outer text + icons requires face offsets, insets, boolean ops
   - **Risk**: 4 different shapes; highly coupled to Blender modifiers
   - **Phase 1**: Skip text shapes entirely; return base shape only (with warning)
   - **Phase 2**: Rasterize text to 2D bitmap → contour → triangulate

9. **Metric Metadata Computation**
   - Many properties computed post-generation: `sScaleHor`, `sAutoScale`, `sMapInKm`
   - **Risk**: Unclear derivation; must reverse-engineer from code
   - **Mitigation**: Log all intermediate values; unit-test against addon output

### Low Risk (Straightforward Ports)

10. **Preset Save/Load**: CSV ↔ Pydantic JSON (simple refactor)
11. **API Counter**: JSON counter file (simple port)
12. **Haversine Distance**: Pure math (no changes)
13. **Web Mercator Projection**: Pure math (already in geo.py)

---

## 8. Recommended Order of Pipeline Implementation

**Dependency graph**:
```
config.py (settings + presets)
  ↓
track.py (load GPX)
  ↓
frame.py (shapes: hexagon, square, circle)
  ├─ primitives.py (2D geometry)
  └─ export.py (rescale, metadata)
  
terrain.py (download DEM, triangulate)
  ├─ elevation.py (API abstraction)
  └─ assembly.py (boolean ops)
  
generate.py (orchestrator)
  └─ Calls all above modules
```

### Phase 1 MVP Implementation Order

1. **`pipeline/constants.py`** (1h)
   - Copy constants from addon
   - Define `EARTH_RADIUS`, cache directories, API limits

2. **`pipeline/config.py`** (3h)
   - Define `GenerateSettings` Pydantic model (Phase 1 fields only)
   - `save_preset()`, `load_preset()`, `delete_preset()`
   - Use JSON files in `~/.trailprint3d/presets/`

3. **`pipeline/track.py`** (4h)
   - `load_track(filepath) → Track` (parses GPX/IGC)
   - `compute_track_stats(track) → TrackStats`
   - `create_track_points_3d(track, dem_array, dem_geo, scale_params) → numpy.ndarray` (project to 3D)
   - Use `gpxpy` or keep `xml.etree` + custom parsing

4. **`pipeline/elevation.py`** (6h)
   - `download_dem(bbox, api, dataset, api_key) → (numpy.ndarray, GeoTransform)`
   - Abstraction over 4 API backends
   - Cache management (JSON-based LRU)
   - Retry logic + timeout

5. **`pipeline/terrain.py`** (5h)
   - `dem_array_to_mesh(dem_array, dem_geo, num_subdivisions, scale_params) → trimesh.Trimesh`
   - Delaunay triangulation via scipy
   - Apply elevation scaling + minimum thickness

6. **`pipeline/frame.py`** (4h)
   - `create_shape_boundary(shape_name, size, num_subdivisions) → trimesh.Trimesh`
   - Hexagon/square/circle primitives using scipy Delaunay
   - Returns closed 2D polygon (Z=0) ready for 3D intersection

7. **`pipeline/assembly.py`** (8h) ⭐ **HARDEST**
   - `boolean_intersect(mesh1, mesh2) → trimesh.Trimesh`
   - `boolean_union(meshes: List[trimesh.Trimesh]) → trimesh.Trimesh`
   - Implement with Manifold engine (production-grade)
   - Fallback to trimesh.boolean if Manifold unavailable
   - Non-manifold detection + warning

8. **`pipeline/track_extrusion.py`** (6h)
   - `create_track_tube(track_3d_points, thickness) → trimesh.Trimesh`
   - Frenet frame computation (tangent, normal, binormal)
   - Disc/circle offset at each point
   - Stitch into tube mesh

9. **`pipeline/export.py`** (4h)
   - `export_stl(mesh, path) → None`
   - `export_obj(mesh, path) → None`
   - `export_gltf(mesh, path, include_materials=False) → None`
   - `export_glb(mesh, path, include_materials=False) → None`
   - `export_3mf(mesh, path) → None` (via trimesh + optional py3mf)
   - `attach_metadata(mesh, settings, stats) → dict`
   - Rescale elevation (operator wrapper)

10. **`pipeline/generate.py`** (8h)
    - `generate(gpx_path, settings, output_dir, mode) → GenerateResult`
    - Orchestrate: load → compute → fetch DEM → create terrain → create track → union → export
    - Progress callbacks (return `GenerateResult.progress_percent` field)
    - Exception handling with descriptive messages
    - Logging

### Phase 2 Deferred (In Order of Dependency)

11. **`pipeline/cache.py`** (2h) — Cache management (clear, query, size)
12. **`pipeline/osm.py`** → Port from addon, remove Blender calls (5h)
13. **`pipeline/coloring.py`** → OSM data ↔ mesh coloring (10h, complex)
14. **`pipeline/contours.py`** → DEM ↔ contour lines (4h)
15. **`pipeline/text_shapes.py`** → Text rendering + shape variants (8h)
16. **`pipeline/accessories.py`** → Magnet holes, dovetails, engraving (10h)

### Testing Strategy (Phase 1)

- **Unit tests**: Each function (track loading, DEM fetch, shape creation)
- **Integration tests**: Full `generate()` pipeline on test GPX + expected output
- **Regression tests**: Compare output mesh vs addon (vertex count, bounding box, surface area)
- **Performance tests**: Benchmark DEM tile fetch, boolean union speed

---

## 9. File References (Complete Index)

### Core Orchestration
- `/home/user/TrailPrint3D-new/TrailPrint3D/__init__.py:130–166` — Class registration
- `/home/user/TrailPrint3D-new/TrailPrint3D/__init__.py:203–251` — Register/unregister functions
- `/home/user/TrailPrint3D-new/TrailPrint3D/operators.py:24–32` — TP3D_OT_run_generation
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/generation.py:811–end` — runGeneration() entry point

### Settings
- `/home/user/TrailPrint3D-new/TrailPrint3D/props.py:34–414` — PropertyGroup definition
- `/home/user/TrailPrint3D-new/TrailPrint3D/addon_preferences.py` — Global prefs

### Coordinate Systems & Math
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/geo.py:65–77` — Web Mercator projection
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/geo.py:102–114` — Haversine formula
- `/home/user/TrailPrint3D-new/TrailPrint3D/constants.py:13` — Earth radius constant

### Data Loading
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/io_gpx.py:43–107` — read_gpx()
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/io_gpx.py:110–` — read_igc()

### Elevation & DEM
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/elevation.py:54–` — send_api_request()
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/elevation.py:99–150` — fetch_elevation*()
- `/home/user/TrailPrint3D-new/TrailPrint3D/constants.py:36` — elevation_cache_file path

### Shape Primitives
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/primitives.py:150–` — create_hexagon()
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/primitives.py:200–` — create_rectangle()
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/primitives.py:300–` — create_circle()

### Mesh Operations
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/mesh_ops.py:1–150` — Boolean & normal ops
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/mesh_ops.py:200–400` — Merge, triangulate

### OSM & Coloring
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/osm.py:15–70` — fetch_osm_data()
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/terrain.py:13–` — coloring_main()

### Export
- `/home/user/TrailPrint3D-new/TrailPrint3D/export.py:17–39` — export_to_STL()
- `/home/user/TrailPrint3D-new/TrailPrint3D/export.py:86–200` — export_selected_to_3mf()
- `/home/user/TrailPrint3D-new/TrailPrint3D/operators.py:34–67` — TP3D_OT_export_stl
- `/home/user/TrailPrint3D-new/TrailPrint3D/operators.py:104–144` — TP3D_OT_export_three_mf

### Metadata & Presets
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/metadata.py:4–45` — writeMetadata()
- `/home/user/TrailPrint3D-new/TrailPrint3D/utils/presets.py:8–` — save_myproperties_to_csv()

---

## 10. Known Ambiguities & Questions for Implementation

1. **Frenet Frame Logic**: Track extrusion method not fully visible in code snippets. Need to review:
   - Are track points (lat/lon) cast onto DEM before extrusion?
   - Is thickness uniform or tapered at endpoints?
   - How are sharp turns handled (angle threshold)?

2. **Single-Color Mode Algorithm**: `_rg_apply_single_color_mode()` at generation.py:529 is 100+ lines; full logic unclear. Decision point:
   - Phase 1: Skip (document as TODO)
   - Phase 2: Implement or defer further

3. **Material Assignment Logic**: How are materials assigned per-feature in paint mode?
   - Example: Water triangles get BLUE material, forests get GREEN
   - Is it per-face or per-object? How does export preserve this?

4. **Boolean Union Order**: When merging terrain + track + elements, what's the correct order?
   - Current addon likely: terrain → union with track → union with each element
   - Risk: Order affects final topology

5. **Elevation Cache Key**: elevation.py:99 uses cache key `(lat, lon, api_type)`. What's the granularity?
   - Per-point (expensive, 1000s of entries)?
   - Per-tile (0.1°×0.1°)?
   - Must reverse-engineer from cache file format

6. **API Quota Tracking**: How is daily/monthly quota enforced?
   - elevation.py:42 mentions "reset counter if date changed"
   - But where does quota refusal get handled?

These should be resolved during Phase 1 implementation.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total LOC (addon) | ~15,000 |
| Phase 1 MVP LOC estimate | ~4,000 (config, track, DEM, shapes, boolean, export) |
| Phase 2+ LOC estimate | ~3,000 (coloring, text, accessories, contours) |
| Blender-internal LOC (no port) | ~8,000 (panels, UI, progress, updater, translation) |
| Core utilities to rewrite | 8 modules (geo, elevation, mesh_ops, primitives, generation, ...) |
| External HTTP APIs | 4 (OpenTopoData, Open-Elevation, Terrain-Tiles, Overpass) |
| Recommended Phase 1 dev time | ~6–8 weeks (1 engineer) |
| Critical blockers | Manifold boolean ops, Frenet frame math, OSM API reliability |

---

**Document Complete**. Estimated size: **1,100+ lines**.

Next action: Proceed with Phase 1 implementation per §8 (Recommended Order).
