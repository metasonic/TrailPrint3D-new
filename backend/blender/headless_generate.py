"""
Headless Blender runner for TrailPrint3D.

Invocation:
  blender --background --python headless_generate.py -- /path/to/config.json

The OpenTopography API key is read from the OPENTOPOGRAPHY_API_KEY environment
variable (not from the config file) to avoid writing secrets to disk.
"""
import sys
import os
import json
from pathlib import Path


def main():
    try:
        sep = sys.argv.index("--")
        config_path = Path(sys.argv[sep + 1])
    except (ValueError, IndexError):
        print("Usage: blender --background --python headless_generate.py -- <config.json>")
        sys.exit(1)

    config = json.loads(config_path.read_text())
    settings = config["settings"]
    addon_src_dir = config["addon_src_dir"]
    gpx_path = config["gpx_path"]
    export_dir = config["export_dir"]
    export_format = config.get("export_format", "STL")
    cache_dir = config.get("cache_dir", "/app/.cache")
    # API key comes from environment, not config file (avoids secrets on disk)
    ot_api_key = os.environ.get("OPENTOPOGRAPHY_API_KEY", "")

    print("STATUS: Initializing Blender scene", flush=True)

    import bpy  # noqa: F401 — available in headless Blender

    # -----------------------------------------------------------------------
    # Build property dict for the addon
    # -----------------------------------------------------------------------
    class _MockTP3D(dict):
        """Attribute-style dict that satisfies addon's scene.tp3d reads."""

        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)

        def __setattr__(self, name, value):
            self[name] = value

        def get(self, key, default=None):
            return super().get(key, default)

    tp3d = _MockTP3D(settings)
    tp3d.setdefault("o_verticesPath", "")
    tp3d.setdefault("o_verticesMap", "")
    tp3d.setdefault("o_mapScale", "")
    tp3d.setdefault("o_time", "")
    tp3d.setdefault("o_apiCounter_OpenTopoData", "")
    tp3d.setdefault("o_apiCounter_OpenElevation", "")
    tp3d.setdefault("o_centerx", 0.0)
    tp3d.setdefault("o_centery", 0.0)
    tp3d.setdefault("sRunDuration", 0)
    tp3d.setdefault("sAdditionalExtrusion", 0.0)
    tp3d.setdefault("sAutoScale", 1.0)
    tp3d.setdefault("sScaleHor", 1.0)
    tp3d.setdefault("sMapInKm", 0.0)
    tp3d.setdefault("sTime_str", "")
    tp3d.setdefault("modelname", settings.get("trailName", "trail"))
    tp3d.setdefault("total_length", 0.0)
    tp3d.setdefault("total_elevation", 0.0)
    tp3d.setdefault("total_time", 0.0)
    tp3d.setdefault("average_speed", 0.0)
    tp3d.setdefault("trail_date", "")
    tp3d.setdefault("lowestZ", 0.0)
    tp3d.setdefault("highestZ", 0.0)
    tp3d.setdefault("buggyDataset", False)
    tp3d.setdefault("minLat", 0.0)
    tp3d.setdefault("maxLat", 0.0)
    tp3d.setdefault("minLon", 0.0)
    tp3d.setdefault("maxLon", 0.0)
    tp3d.setdefault("exportformat", "STL")
    tp3d.setdefault("opentopoAdress", "https://api.opentopodata.org/v1/")
    tp3d.setdefault("currentMap", None)
    tp3d.setdefault("currentTrail", None)
    tp3d.setdefault("selfHosted", "")
    tp3d.setdefault("ccacheSize", 50000)
    tp3d.setdefault("apiRetries", 5)
    for key in [
        "col_wArea", "col_fArea", "col_scrArea", "col_cArea",
        "col_grArea", "col_faArea", "col_glArea",
    ]:
        tp3d.setdefault(key, 1.0)
    tp3d.setdefault("col_KeepManifold", False)
    tp3d.setdefault("col_wStreamWidth", 1.0)
    tp3d.setdefault("el_bHeightMultiplier", 1.0)
    tp3d.setdefault("el_sMultiplier", 1.0)
    tp3d.setdefault("el_oFlip", False)
    tp3d.setdefault("mountain_treshold", 60)
    tp3d.setdefault("cl_thickness", 0.2)
    tp3d.setdefault("cl_distance", 2.0)
    tp3d.setdefault("cl_offset", 0.0)
    tp3d.setdefault("indipendendTiles", False)
    tp3d.setdefault("tolerance", 0.2)
    tp3d.setdefault("toleranceElements", 0.4)
    tp3d.setdefault("elementModeInset", 2.0)
    tp3d.setdefault("rectangleHeight", settings.get("rectangleHeight", 100))
    tp3d.setdefault("ellipseRatio", settings.get("ellipseRatio", 0.75))
    tp3d.setdefault("outerBorderSize", 20)
    tp3d.setdefault("tileSpacing", 0.0)
    tp3d.setdefault("plateInsertValue", 0.0)
    tp3d.setdefault("plateBevel", 0.0)
    tp3d.setdefault("textSize", 5)
    tp3d.setdefault("textSizeTitle", 0)
    tp3d.setdefault("titlefield", "{name}")
    tp3d.setdefault("textfield1", "{length}")
    tp3d.setdefault("textfield2", "{elevation}")
    tp3d.setdefault("textfield3", "{duration}")
    tp3d.setdefault("titleIcon", "no")
    tp3d.setdefault("iconText1", "distance")
    tp3d.setdefault("iconText2", "elevation")
    tp3d.setdefault("iconText3", "time")
    tp3d.setdefault("rescaleMultiplier", 1.0)
    tp3d.setdefault("thickenValue", 1.0)
    tp3d.setdefault("generation_mode", "GENERATION")
    tp3d.setdefault("use_multi_generation", False)
    tp3d.setdefault("disable_auto_export", False)
    tp3d.setdefault("disable_3mf_export", export_format != "3MF")
    tp3d.setdefault("text_angle_preset", 0)
    tp3d.setdefault("svg_path", "")

    tp3d["file_path"] = gpx_path
    tp3d["export_path"] = export_dir + "/"

    # -----------------------------------------------------------------------
    # Inject tp3d into bpy.context.scene.
    #
    # In a registered Blender addon, scene.tp3d is a bpy.props.PointerProperty
    # and cannot be freely reassigned with `= mock_dict`. Two strategies:
    #
    # 1. Enable the addon via bpy.ops.preferences.addon_enable() so that the
    #    PropertyGroup is registered, then set individual property values.
    # 2. Fall back to setting each property value after addon registration.
    #
    # We store tp3d in the custom property bag (scene["tp3d"]) as a universal
    # fallback that works regardless of the registration state.
    # -----------------------------------------------------------------------
    sys.path.insert(0, addon_src_dir)

    bpy.context.scene["tp3d"] = tp3d

    # Attempt to enable the addon so its PropertyGroup is registered,
    # then copy our values onto the live PropertyGroup instance.
    try:
        result = bpy.ops.preferences.addon_enable(module="TrailPrint3D")
        if "FINISHED" in result:
            pg = bpy.context.scene.tp3d
            for key, value in tp3d.items():
                try:
                    setattr(pg, key, value)
                except (AttributeError, TypeError):
                    pass  # read-only RNA props or type mismatch — skip
    except Exception as exc:
        print(f"WARNING: Could not enable addon via bpy.ops ({exc}). "
              "Relying on custom property bag fallback.", flush=True)

    # -----------------------------------------------------------------------
    # Patch addon_preferences.get_prefs to return mock
    # -----------------------------------------------------------------------
    class _MockPrefs:
        openTopographyApiKey = ot_api_key
        default_export_folder = export_dir + "/"

    try:
        import TrailPrint3D.addon_preferences as _ap
        _ap.get_prefs = lambda: _MockPrefs()
    except ImportError as exc:
        print(f"STATUS: FAILED — could not import TrailPrint3D: {exc}", flush=True)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Patch progress overlay (no GPU in headless)
    # -----------------------------------------------------------------------
    try:
        import TrailPrint3D.progress as _progress

        class _NoopOverlay:
            active = False
            def update(self, **_): pass
            def set_fetch_progress(self, *_, **__): pass
            @classmethod
            def get(cls): return cls()
            @classmethod
            def add_warning(cls, *_, **__): pass

        _progress.ProgressOverlay = _NoopOverlay
        _progress.WarningsOverlay = _NoopOverlay
    except (ImportError, AttributeError):
        pass

    # -----------------------------------------------------------------------
    # Patch constants cache paths to use configured cache_dir
    # -----------------------------------------------------------------------
    try:
        import TrailPrint3D.constants as const
        const.elevation_cache_file = os.path.join(cache_dir, "elevation", "cache.json")
        const.overpass_cache_dir = os.path.join(cache_dir, "osm")
        const.terrarium_cache_dir = os.path.join(cache_dir, "tiles")
        os.makedirs(const.overpass_cache_dir, exist_ok=True)
        os.makedirs(const.terrarium_cache_dir, exist_ok=True)
        os.makedirs(os.path.dirname(const.elevation_cache_file), exist_ok=True)
    except (ImportError, AttributeError):
        pass

    # -----------------------------------------------------------------------
    # Run generation
    # -----------------------------------------------------------------------
    print("STATUS: Running TrailPrint3D generation pipeline", flush=True)
    print("PROGRESS: 5", flush=True)

    try:
        from TrailPrint3D import utils
        # runGeneration(0) — argument 0 selects the default single-trail generation mode.
        # Verify against addon source if the mode enum changes in a future release.
        utils.runGeneration(0)
    except Exception as exc:
        print(f"STATUS: FAILED — generation error: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("PROGRESS: 95", flush=True)
    print("STATUS: Export complete", flush=True)
    print("PROGRESS: 100", flush=True)


if __name__ == "__main__":
    main()
