import bpy
import sys
import json
import os
import traceback

def setup_trailprint3d():
    addon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../TrailPrint3D"))
    if addon_dir not in sys.path:
        sys.path.append(os.path.dirname(addon_dir))

    import TrailPrint3D
    TrailPrint3D.register()

    prefs = bpy.context.preferences.addons.get('TrailPrint3D')
    if prefs and hasattr(prefs, 'preferences'):
        ot_key = os.getenv('OPENTOPOGRAPHY_KEY')
        if ot_key:
            prefs.preferences.opentopo_api_key = ot_key

def apply_settings(settings):
    try:
        if 'shape' in settings:
            bpy.context.scene.tp3d.shape = settings['shape'].capitalize()
        if 'colorMode' in settings:
            bpy.context.scene.tp3d.color_mountains = settings['colorMode']
        if 'roads' in settings:
            bpy.context.scene.tp3d.roads_enable = settings['roads']
    except Exception as e:
        print(f"Warning: Failed to apply some settings: {e}", file=sys.stderr)

def run_preview(job_id: str, gpx_path: str, output_path: str, settings_json: str):
    settings = json.loads(settings_json)
    try:
        setup_trailprint3d()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"status": "error", "error": f"Failed to setup addon: {str(e)}"}

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    try:
        bpy.context.scene.tp3d.gpx_file = gpx_path
        apply_settings(settings)

        bpy.ops.tp3d.run_generation()

        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
                mod.ratio = 0.2
                bpy.ops.object.modifier_apply(modifier="Decimate")

        bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLB')
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"status": "error", "error": f"Generation failed: {str(e)}"}

    return {"status": "success", "mesh_path": output_path}

def run_export(job_id: str, gpx_path: str, output_path: str, format: str, settings_json: str):
    settings = json.loads(settings_json)
    try:
        setup_trailprint3d()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"status": "error", "error": f"Failed to setup addon: {str(e)}"}

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    try:
        bpy.context.scene.tp3d.gpx_file = gpx_path
        apply_settings(settings)

        res = os.getenv('TERRAIN_RESOLUTION')
        if res:
             bpy.context.scene.tp3d.resolution = int(res)

        bpy.ops.tp3d.run_generation()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"status": "error", "error": f"Generation failed: {str(e)}"}

    try:
        if format == "stl":
            bpy.ops.export_mesh.stl(filepath=output_path)
        elif format == "obj":
            bpy.ops.wm.obj_export(filepath=output_path)
        elif format == "3mf":
            bpy.ops.export_mesh.three_mf(filepath=output_path)
    except Exception as e:
         traceback.print_exc(file=sys.stderr)
         return {"status": "error", "error": f"Export failed: {str(e)}"}

    return {"status": "success", "mesh_path": output_path}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("job_id")
    parser.add_argument("gpx_path")
    parser.add_argument("output_path")
    parser.add_argument("--format", default=None)
    parser.add_argument("--settings", default="{}")
    parser.add_argument("--result-file", required=True)

    # Handle the fact that blender might pass `--` before our args
    args_list = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(args_list)

    if args.command == "preview":
        res = run_preview(args.job_id, args.gpx_path, args.output_path, args.settings)
    elif args.command == "export":
        res = run_export(args.job_id, args.gpx_path, args.output_path, args.format, args.settings)
    else:
        res = {"status": "error", "error": "Unknown command"}

    with open(args.result_file, "w") as f:
        json.dump(res, f)
