"""
Headless Blender terrain generation script.

Invoked by the Celery worker as:
  blender --background --python scripts/generate_terrain.py -- \
    --gpx   /path/to/track.gpx         \
    --settings /path/to/settings.json  \
    --output   /path/to/output.glb     \
    --mode  preview                    \
    --format glb

Progress lines printed to stdout: {"progress": N, "phase": "..."}
Any error causes a non-zero exit.
"""

import sys
import os
import json
import argparse
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Parse CLI args (everything after the "--" separator Blender uses)
# ---------------------------------------------------------------------------
if "--" in sys.argv:
    _argv = sys.argv[sys.argv.index("--") + 1:]
else:
    _argv = sys.argv[1:]

parser = argparse.ArgumentParser(prog="generate_terrain.py")
parser.add_argument("--gpx",      required=True, help="Path to .gpx file")
parser.add_argument("--settings", required=True, help="Path to settings JSON")
parser.add_argument("--output",   required=True, help="Path for output file")
parser.add_argument("--mode",     required=True, choices=["preview", "export"])
parser.add_argument("--format",   required=True, dest="fmt",
                    help="Output format: glb | stl | obj | 3mf")
args = parser.parse_args(_argv)

output_path = Path(args.output)
job_dir     = output_path.parent
cache_root  = job_dir / ".cache"
cache_root.mkdir(parents=True, exist_ok=True)
(cache_root / "terrarium").mkdir(exist_ok=True)
(cache_root / "overpass").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# 2. Progress reporter — printed to stdout so the Celery task can parse it
# ---------------------------------------------------------------------------
def _emit(progress: int, phase: str) -> None:
    print(json.dumps({"progress": progress, "phase": phase}), flush=True)

_emit(5, "Initializing")

# ---------------------------------------------------------------------------
# 3. Stub the TrailPrint3D progress module BEFORE any addon import.
#    progress.py imports gpu / blf / gpu_extras.batch at module level; those
#    modules exist in Blender but GPU drawing is not available in --background
#    mode and we don't want any GUI windows.
# ---------------------------------------------------------------------------
class _StubProgress:
    """No-op drop-in for ProgressOverlay / SubprocessProgress."""

    @classmethod
    def get(cls):
        return cls()

    def start(self): pass

    def update(self, percent=0.0, phase="", message="", **kwargs):
        _emit(max(5, min(95, int(percent * 100))), phase)

    def add_completed_step(self, *a): pass

    def finish(self):
        _emit(95, "Finishing")

    def is_cancel_requested(self):
        return False


class _StubWarnings:
    """No-op drop-in for WarningsOverlay."""

    @classmethod
    def clear(cls): pass

    @classmethod
    def add_warning(cls, *a, **kw): pass


_progress_stub = types.ModuleType("TrailPrint3D.progress")
_progress_stub.ProgressOverlay    = _StubProgress
_progress_stub.SubprocessProgress = _StubProgress
_progress_stub.WarningsOverlay    = _StubWarnings
sys.modules["TrailPrint3D.progress"] = _progress_stub

# ---------------------------------------------------------------------------
# 4. Locate the addon and add repo root to sys.path
# ---------------------------------------------------------------------------
_script_dir = Path(__file__).resolve().parent   # …/scripts/
_repo_root  = _script_dir.parent                # …/TrailPrint3D-new/
sys.path.insert(0, str(_repo_root))

# Stub map_picker early — it may not ship with the free version
if "TrailPrint3D.map_picker" not in sys.modules:
    sys.modules["TrailPrint3D.map_picker"] = types.ModuleType("TrailPrint3D.map_picker")

# ---------------------------------------------------------------------------
# 5. Load the addon (but NOT via register() — we bootstrap manually)
#    Importing TrailPrint3D triggers __init__.py which loads submodules.
#    The progress stub (step 3) prevents gpu/blf crashes.
# ---------------------------------------------------------------------------
import bpy  # type: ignore  — available because we're running inside Blender

# Importing the package runs __init__.py, which loads all submodules.
# It does NOT call register(), so no Blender classes are registered yet.
import TrailPrint3D                          # noqa: E402 — must come after path setup
import TrailPrint3D.constants   as _const
import TrailPrint3D.utils       as _utils
import TrailPrint3D.utils.scene as _scene

# ---------------------------------------------------------------------------
# 6. Redirect cache directories to the job-local cache folder
# ---------------------------------------------------------------------------
_const.cache_dir            = str(cache_root)
_const.elevation_cache_file = str(cache_root / "elevation_cache.json")
_const.terrarium_cache_dir  = str(cache_root / "terrarium")
_const.overpass_cache_dir   = str(cache_root / "overpass")
_const.counter_file         = str(cache_root / "api_counter.json")
_const.preset_dir           = str(cache_root / "presets")
(cache_root / "presets").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# 7. Stub show_message_box and zoom_camera_to_selected in all namespaces
#    that export them.  Deferred imports (`from .scene import fn`) look up
#    the module attribute at call time, so patching the module is sufficient.
# ---------------------------------------------------------------------------
def _headless_message_box(message="", title="", icon="ERROR"):
    print(f"[TP3D] {icon}: {message}", file=sys.stderr)

def _safe_zoom(obj):
    """No-op: camera zoom is meaningless in headless mode."""
    pass  # bpy.context.screen is None in --background

_scene.show_message_box       = _headless_message_box
_scene.zoom_camera_to_selected = _safe_zoom

# Also patch the re-exported names in the utils package namespace
# (io_gpx does `from . import show_message_box` which resolves via utils)
_utils.show_message_box        = _headless_message_box
_utils.zoom_camera_to_selected = _safe_zoom

# ---------------------------------------------------------------------------
# 8. Stub addon_preferences.get_prefs
#    Called unconditionally in _rg_validate_inputs for the OT API key and
#    the default export folder fallback.
# ---------------------------------------------------------------------------
import TrailPrint3D.addon_preferences as _addon_prefs

class _FakePrefs:
    openTopographyApiKey  = ""
    default_export_folder = str(job_dir) + os.sep

_addon_prefs.get_prefs = lambda: _FakePrefs()

# ---------------------------------------------------------------------------
# 9. Register only the classes we actually need
# ---------------------------------------------------------------------------
from TrailPrint3D import props as _props

bpy.utils.register_class(_addon_prefs.TP3D_AddonPreferences)
bpy.utils.register_class(_props.TP3D_PG_properties)
bpy.types.Scene.tp3d = bpy.props.PointerProperty(type=_props.TP3D_PG_properties)

# ---------------------------------------------------------------------------
# 10. Load generation settings from the JSON file written by the route handler
# ---------------------------------------------------------------------------
with open(args.settings) as _f:
    _settings = json.load(_f)

# ---------------------------------------------------------------------------
# 11. Map snake_case API field names → camelCase Blender property names
# ---------------------------------------------------------------------------
_ELEVATION_API_MAP = {
    "mapzen":           "TERRAIN-TILES",
    "terrain-tiles":    "TERRAIN-TILES",
    "opentopodata":     "OPENTOPODATA",
    "open-elevation":   "OPEN-ELEVATION",
    "opentopography":   "OPENTOPOGRAPHY",
}

_ELEMENT_MODE_MAP = {
    "paint":         "PAINT",
    "single_color":  "SINGLECOLORMODE_REMESH",
    "separate":      "SEPARATE",
}

_SHAPE_MAP = {
    "hexagon": "HEXAGON",
    "square":  "SQUARE",
    "circle":  "CIRCLE",
}

_FIELD_MAP = {
    # (snake_case API key): (blender_prop_name, python_type)
    "obj_size":             ("objSize",              int),
    "num_subdivisions":     ("num_subdivisions",     int),
    "scale_elevation":      ("scaleElevation",       float),
    "path_thickness":       ("pathThickness",        float),
    "shape_rotation":       ("shapeRotation",        int),
    "single_color_mode":    ("singleColorMode",      bool),
    "min_thickness":        ("minThickness",         float),
    "outer_border_size":    ("outerBorderSize",      int),
    "plate_thickness":      ("plateThickness",       float),
    "plate_insert":         ("plateInsertValue",     float),
    "fixed_elevation_scale":("fixedElevationScale",  bool),
    "x_terrain_offset":     ("xTerrainOffset",       float),
    "y_terrain_offset":     ("yTerrainOffset",       float),
    "water_ponds":          ("col_wPondsActive",     bool),
    "water_small_rivers":   ("col_wSmallRiversActive", bool),
    "water_big_rivers":     ("col_wBigRiversActive", bool),
    "forests":              ("col_fActive",          bool),
    "buildings":            ("el_bActive",           bool),
    "roads_major":          ("el_sBigActive",        bool),
    "roads_medium":         ("el_sMedActive",        bool),
    "roads_minor":          ("el_sSmallActive",      bool),
    "city_boundaries":      ("col_cActive",          bool),
    "greenspace":           ("col_grActive",         bool),
}

tp3d = bpy.context.scene.tp3d
tp3d.file_path          = args.gpx
tp3d.export_path        = str(job_dir) + os.sep
tp3d.disable_auto_export = True

# Shape
_raw_shape = _settings.get("shape", "hexagon")
tp3d.shape = _SHAPE_MAP.get(str(_raw_shape).lower(), "HEXAGON")

# Elevation API
_raw_api = _settings.get("elevation_api", "mapzen")
tp3d.api  = _ELEVATION_API_MAP.get(str(_raw_api).lower(), "TERRAIN-TILES")

# OpenTopo dataset
if "opentopo_dataset" in _settings:
    tp3d.openTopographyDataset = str(_settings["opentopo_dataset"]).upper()

# Element mode
_raw_em = _settings.get("element_mode", "paint")
tp3d.elementMode = _ELEMENT_MODE_MAP.get(str(_raw_em).lower(), "PAINT")

# Scalar / bool fields
for _snake, (_prop, _typ) in _FIELD_MAP.items():
    if _snake in _settings:
        setattr(tp3d, _prop, _typ(_settings[_snake]))

# ---------------------------------------------------------------------------
# 12. Run the generation pipeline
# ---------------------------------------------------------------------------
_emit(10, "Starting generation")

from TrailPrint3D.utils.generation import runGeneration  # noqa: E402

runGeneration(0)   # 0 = standard single-GPX generation

_emit(90, "Exporting result")

# ---------------------------------------------------------------------------
# 13. Export the result
# ---------------------------------------------------------------------------
# Collect all non-default generated objects (mesh, curve, text)
_generated = [
    o for o in bpy.data.objects
    if o.type in ("MESH", "CURVE", "FONT", "SURFACE")
]

if not _generated:
    print("ERROR: generation produced no objects", file=sys.stderr)
    sys.exit(1)

bpy.ops.object.select_all(action="DESELECT")
for _o in _generated:
    _o.select_set(True)
bpy.context.view_layer.objects.active = _generated[0]

_fmt = args.fmt.lower()
_out = str(output_path)

if _fmt == "glb":
    bpy.ops.export_scene.gltf(
        filepath=_out,
        export_format="GLB",
        export_selected=True,
        export_apply=True,
    )
elif _fmt == "stl":
    bpy.ops.wm.stl_export(
        filepath=_out,
        export_selected_objects=True,
    )
elif _fmt == "obj":
    bpy.ops.wm.obj_export(
        filepath=_out,
        export_selected_objects=True,
        export_triangulated_mesh=True,
        apply_modifiers=True,
        forward_axis="Y",
        up_axis="Z",
    )
elif _fmt == "3mf":
    try:
        bpy.ops.export_scene.three_mf_export(filepath=_out)
    except AttributeError:
        # 3MF extension not installed — fall back to STL with correct path
        _stl_out = str(output_path.with_suffix(".stl"))
        bpy.ops.wm.stl_export(filepath=_stl_out, export_selected_objects=True)
        _out = _stl_out
else:
    print(f"ERROR: unknown format '{_fmt}'", file=sys.stderr)
    sys.exit(1)

if not Path(_out).exists():
    print(f"ERROR: export did not produce '{_out}'", file=sys.stderr)
    sys.exit(1)

_emit(100, "Done")
print(f"[TP3D] output: {_out}", flush=True)
