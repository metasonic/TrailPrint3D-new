"""headless_script.py — Entry-point for TrailPrint3D running inside Blender headlessly.

Invocation (from the Celery worker / subprocess):

    blender --background --python /path/to/blender/headless_script.py -- \\
        --job-id <job_id>

Required environment variables:
    TP3D_JOB_DIR      — directory where outputs (STL, GLB, etc.) are written
    TP3D_PARAMS_FILE  — path to a JSON file containing GenerationParams fields
                        plus a 'gpx_file_path' key
    TP3D_ADDON_DIR    — *parent* directory of the TrailPrint3D package
                        (i.e. the dir that contains the TrailPrint3D/ folder)

Optional environment variables:
    TP3D_HEADLESS     — set to '1' automatically by this script before importing
                        any addon modules
    TP3D_DATA_DIR     — base directory for cache/presets (replaces bpy CONFIG path)
    TP3D_OUTPUT_DIR   — default export folder returned by addon_preferences
    TP3D_OPENTOPOGRAPHY_KEY — OpenTopography API key
    TP3D_JOB_ID       — job ID used to check for cancellation in Redis
    REDIS_URL         — Redis connection URL (default: redis://localhost:6379/0)

Progress is emitted as newline-delimited JSON to stdout:
    {"type": "progress", "percent": 0.5, "phase": "...", "message": "..."}
    {"type": "step", "step": "..."}
    {"type": "warning", "message": "...", "level": "warn"}
    {"type": "error", "message": "..."}
"""

import sys
import os
import json


# ---------------------------------------------------------------------------
# 1. Parse arguments that appear after the '--' Blender separator
# ---------------------------------------------------------------------------

def _parse_args():
    """Return a dict of parsed CLI arguments from after the '--' separator."""
    args = {}
    try:
        sep = sys.argv.index('--')
        tail = sys.argv[sep + 1:]
    except ValueError:
        tail = []

    i = 0
    while i < len(tail):
        token = tail[i]
        if token == '--job-id' and i + 1 < len(tail):
            args['job_id'] = tail[i + 1]
            i += 2
        else:
            i += 1
    return args


cli_args = _parse_args()
job_id = cli_args.get('job_id', os.environ.get('TP3D_JOB_ID', ''))

# Propagate job-id into env so the cancel-check in _HeadlessOverlay can use it
if job_id:
    os.environ['TP3D_JOB_ID'] = job_id

# ---------------------------------------------------------------------------
# 2. Activate headless mode BEFORE importing any TrailPrint3D modules
# ---------------------------------------------------------------------------

os.environ['TP3D_HEADLESS'] = '1'

# ---------------------------------------------------------------------------
# 3. Read required environment variables
# ---------------------------------------------------------------------------

job_dir        = os.environ.get('TP3D_JOB_DIR', '')
params_file    = os.environ.get('TP3D_PARAMS_FILE', '')
addon_dir      = os.environ.get('TP3D_ADDON_DIR', '')

if not job_dir:
    print(json.dumps({'type': 'error', 'message': 'TP3D_JOB_DIR env var is not set'}),
          flush=True)
    sys.exit(1)

if not params_file:
    print(json.dumps({'type': 'error', 'message': 'TP3D_PARAMS_FILE env var is not set'}),
          flush=True)
    sys.exit(1)

if not addon_dir:
    print(json.dumps({'type': 'error',
                      'message': 'TP3D_ADDON_DIR env var is not set'}),
          flush=True)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 4. Extend sys.path so TrailPrint3D package (and context_shim) are importable
# ---------------------------------------------------------------------------

# TP3D_ADDON_DIR is the *parent* of the TrailPrint3D package directory
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

# Add the blender/ script directory itself so context_shim is importable
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# ---------------------------------------------------------------------------
# 5. Load and validate params
# ---------------------------------------------------------------------------

try:
    with open(params_file, 'r', encoding='utf-8') as fh:
        params = json.load(fh)
except Exception as exc:
    print(json.dumps({'type': 'error',
                      'message': f'Failed to read params file: {exc}'}),
          flush=True)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 5b. Ensure cache/preset directories exist (normally done by addon register)
# ---------------------------------------------------------------------------

try:
    from TrailPrint3D.constants import _ensure_dirs  # type: ignore
    _ensure_dirs()
except Exception as exc:
    print(json.dumps({'type': 'warning',
                      'message': f'Could not create cache dirs: {exc}',
                      'level': 'warn'}),
          flush=True)

# ---------------------------------------------------------------------------
# 5c. Resolve font path for Docker/Linux environments
# ---------------------------------------------------------------------------

# If textFont is empty and we're on Linux, try common system font paths so
# text-plate shapes don't silently fail bpy.data.fonts.load("").
if not params.get('textFont'):
    _linux_fonts = [
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    ]
    for _fp in _linux_fonts:
        if os.path.isfile(_fp):
            params['textFont'] = _fp
            break

# 5d. Inject self-hosted OpenTopoData URL from env if not in params
if not params.get('selfHosted') and os.environ.get('TP3D_OPENTOPODATA_SELF_HOSTED'):
    params['selfHosted'] = os.environ['TP3D_OPENTOPODATA_SELF_HOSTED']

# ---------------------------------------------------------------------------
# 6. bpy is available — set up a clean default scene
# ---------------------------------------------------------------------------

try:
    import bpy  # noqa: E402  (bpy is only available inside Blender)

    # Start from a clean slate
    bpy.ops.wm.read_factory_settings(use_empty=True)

except Exception as exc:
    print(json.dumps({'type': 'error',
                      'message': f'Blender scene initialisation failed: {exc}'}),
          flush=True)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 7. Register the TrailPrint3D PropertyGroup and populate from params
# ---------------------------------------------------------------------------

try:
    from TrailPrint3D.props import TP3D_PG_properties  # type: ignore

    # Register the PropertyGroup so bpy.context.scene.tp3d is a proper
    # Blender PropertyGroup (needed for any bpy operators that still check
    # types, and for EnumProperty default-value resolution).
    try:
        bpy.utils.register_class(TP3D_PG_properties)
    except ValueError:
        pass  # already registered

    bpy.types.Scene.tp3d = bpy.props.PointerProperty(type=TP3D_PG_properties)

    # Now populate the PropertyGroup from the params dict.
    # setattr silently ignores unknown keys on a PropertyGroup.
    tp3d_pg = bpy.context.scene.tp3d
    for key, value in params.items():
        try:
            setattr(tp3d_pg, key, value)
        except Exception:
            # Some properties may be read-only or type-incompatible at this
            # stage; skip them silently — they'll be read via .get() which
            # falls through to the PropertyGroup default.
            pass

except Exception as exc:
    print(json.dumps({'type': 'error',
                      'message': f'PropertyGroup registration failed: {exc}'}),
          flush=True)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 8. Set critical path properties
# ---------------------------------------------------------------------------

# export_path must end with a slash so Blender treats it as a directory
bpy.context.scene.tp3d.export_path = job_dir.rstrip('/') + '/'

gpx_file_path = params.get('gpx_file_path', '')
if gpx_file_path:
    bpy.context.scene.tp3d.file_path = gpx_file_path

# Reflect generation_mode from params (default: GENERATION)
generation_mode = params.get('generation_mode', 'GENERATION')
try:
    bpy.context.scene.tp3d.generation_mode = generation_mode
except Exception:
    pass

# ---------------------------------------------------------------------------
# 9. Run the generation pipeline
# ---------------------------------------------------------------------------

# Map generation_mode string → runGeneration(type) integer:
#   'GENERATION' → 0  (single GPX file)
#   'MULTI'      → 1  (chain directory)
#   'TERRAIN'    → 2  (no GPX, use coordinates / jmap)
_MODE_MAP = {
    'GENERATION': 0,
    'MULTI':      1,
    'TERRAIN':    2,
}
run_type = _MODE_MAP.get(generation_mode, 0)

try:
    from TrailPrint3D.utils.generation import runGeneration  # type: ignore

    print(json.dumps({'type': 'progress', 'percent': 0.0,
                      'phase': 'Starting generation',
                      'message': f'mode={generation_mode}'}),
          flush=True)

    runGeneration(run_type)

    # runGeneration returns None on both success and failure; check for output
    # files as the reliable indicator that the pipeline completed.
    import glob
    output_files = []
    for _pat in ('*.stl', '*.obj', '*.3mf'):
        output_files.extend(glob.glob(os.path.join(job_dir, _pat)))

    if not output_files:
        print(json.dumps({'type': 'error',
                          'message': 'Generation produced no output files — '
                                     'check GPX path, export path, and settings. '
                                     'See log output above for details.'}),
              flush=True)
        sys.exit(1)

except SystemExit:
    # runGeneration may call sys.exit on cancellation — treat as error
    raise
except Exception as exc:
    import traceback
    tb = traceback.format_exc()
    print(json.dumps({'type': 'error',
                      'message': f'Generation failed: {exc}',
                      'traceback': tb}),
          flush=True)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 10. Export GLB preview for the Three.js browser viewer
# ---------------------------------------------------------------------------

try:
    from TrailPrint3D.export import export_to_glb  # type: ignore
    glb_path = os.path.join(job_dir, 'preview.glb')
    export_to_glb(glb_path)
    print(json.dumps({'type': 'step', 'step': f'GLB preview exported to {glb_path}'}),
          flush=True)

except Exception as exc:
    # GLB export failure is non-fatal — the STL/3MF files are the primary output
    print(json.dumps({'type': 'warning',
                      'message': f'GLB preview export failed: {exc}',
                      'level': 'warn'}),
          flush=True)

# ---------------------------------------------------------------------------
# 11. Signal completion
# ---------------------------------------------------------------------------

print(json.dumps({'type': 'progress', 'percent': 1.0,
                  'phase': 'Complete', 'message': 'Generation complete'}),
      flush=True)
