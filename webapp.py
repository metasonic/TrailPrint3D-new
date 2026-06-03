import bpy
import os
import tempfile
import zipfile
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
import glob
import sys
import contextlib
import threading

app = FastAPI()

# Global lock for Blender operations
blender_lock = threading.Lock()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>TrailPrint3D Generator</title>
    <style>
        body { font-family: sans-serif; margin: 40px; }
        form { max-width: 500px; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="file"], select, input[type="number"], input[type="checkbox"] { width: 100%; padding: 8px; margin-bottom: 10px; box-sizing: border-box; }
        input[type="checkbox"] { width: auto; }
        input[type="submit"] { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #45a049; }
        .checkbox-group { display: flex; align-items: center; }
        .checkbox-group input { margin-right: 10px; margin-bottom: 0; }
    </style>
</head>
<body>
    <h2>TrailPrint3D Generator</h2>
    <form action="/generate" enctype="multipart/form-data" method="post">
        <div class="form-group">
            <label>GPX File:</label>
            <input type="file" name="gpx_file" required accept=".gpx">
        </div>

        <div class="form-group">
            <label>Shape:</label>
            <select name="shape">
                <option value="HEXAGON">Hexagon</option>
                <option value="SQUARE">Rectangle</option>
                <option value="CIRCLE">Circle</option>
            </select>
        </div>

        <div class="form-group">
            <label>Size (mm):</label>
            <input type="number" name="size" value="100" min="10" max="500">
        </div>

        <div class="form-group">
            <label>Elevation Scale Multiplier:</label>
            <input type="number" name="scaleElevation" value="1.0" step="0.1" min="0.1" max="10.0">
        </div>

        <div class="form-group">
            <label>Path Thickness (mm):</label>
            <input type="number" name="pathThickness" value="1.2" step="0.1" min="0.1" max="5.0">
        </div>

        <div class="form-group checkbox-group">
            <input type="checkbox" name="singleColorMode" id="singleColorMode" value="true">
            <label for="singleColorMode" style="display:inline">Single Color Mode (for non-multicolor printers)</label>
        </div>

        <div class="form-group checkbox-group">
            <input type="checkbox" name="water" id="water" value="true">
            <label for="water" style="display:inline">Include Water Features</label>
        </div>

        <div class="form-group checkbox-group">
            <input type="checkbox" name="roads" id="roads" value="true">
            <label for="roads" style="display:inline">Include Roads</label>
        </div>

        <input type="submit" value="Generate 3D Map">
    </form>
</body>
</html>
"""

def setup_blender():
    try:
        sys.path.append(os.path.dirname(__file__))
        import TrailPrint3D
        TrailPrint3D.register()
        print("Blender addon enabled successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error loading addon: {e}")

setup_blender()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return html_content

def cleanup_temp_dir(dir_path: str):
    import shutil
    shutil.rmtree(dir_path, ignore_errors=True)

@app.post("/generate")
async def generate_map(
    background_tasks: BackgroundTasks,
    gpx_file: UploadFile = File(...),
    shape: str = Form("HEXAGON"),
    size: int = Form(100),
    scaleElevation: float = Form(1.0),
    pathThickness: float = Form(1.2),
    singleColorMode: bool = Form(False),
    water: bool = Form(False),
    roads: bool = Form(False)
):
    temp_dir = tempfile.mkdtemp()
    # Ensure the temp_dir is cleaned up after the response is sent
    background_tasks.add_task(cleanup_temp_dir, temp_dir)

    # Sanitize filename
    safe_filename = os.path.basename(gpx_file.filename) if gpx_file.filename else "upload.gpx"
    gpx_path = os.path.join(temp_dir, safe_filename)
    with open(gpx_path, "wb") as f:
        f.write(await gpx_file.read())

    export_path = os.path.join(temp_dir, "export/")
    os.makedirs(export_path, exist_ok=True)

    # Acquire lock for thread-safe Blender operations
    with blender_lock:
        # Clear the scene for fresh start
        bpy.ops.wm.read_factory_settings(use_empty=True)

        if not hasattr(bpy.context.scene, "tp3d"):
            import TrailPrint3D
            try:
                TrailPrint3D.unregister()
            except:
                pass
            TrailPrint3D.register()

        # Set all properties
        bpy.context.scene.tp3d.file_path = gpx_path
        bpy.context.scene.tp3d.export_path = export_path
        bpy.context.scene.tp3d.shape = shape
        bpy.context.scene.tp3d.objSize = size
        bpy.context.scene.tp3d.scaleElevation = scaleElevation
        bpy.context.scene.tp3d.pathThickness = pathThickness
        bpy.context.scene.tp3d.singleColorMode = singleColorMode

        # Terrain elements
        if water:
            bpy.context.scene.tp3d.col_wPondsActive = True
            bpy.context.scene.tp3d.col_wSmallRiversActive = True
            bpy.context.scene.tp3d.col_wBigRiversActive = True

        if roads:
            bpy.context.scene.tp3d.el_sBigActive = True
            bpy.context.scene.tp3d.el_sMedActive = True
            bpy.context.scene.tp3d.el_sSmallActive = True

        bpy.context.scene.tp3d.disable_auto_export = True

        import TrailPrint3D.addon_preferences as prefs
        class MockPrefs:
            openTopographyApiKey = ""
            default_export_folder = export_path
        def get_prefs_mock():
            return MockPrefs()

        prefs.get_prefs = get_prefs_mock
        import TrailPrint3D.utils.generation as gen
        gen.addon_preferences.get_prefs = get_prefs_mock

        import TrailPrint3D.export as exp
        import TrailPrint3D.utils as utils

        # Delete default objects just in case
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        try:
            utils.runGeneration(0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

        # Manually export the newly created objects
        objects = bpy.context.scene.objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            if obj.type in ['MESH', 'CURVE']:
                # Curve can't be exported as STL directly without conversion, but utils might have converted it.
                # Just to be safe, convert to mesh first if needed
                if obj.type == 'CURVE':
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    bpy.ops.object.convert(target='MESH')

                obj.select_set(True)
                filepath = os.path.join(export_path, f"{obj.name}.stl")
                try:
                    bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True)
                except Exception as e:
                    print(f"Failed to export {obj.name}: {e}")
                obj.select_set(False)

    # Outside the lock, zip and return the files
    files = glob.glob(os.path.join(export_path, "*.stl"))
    if not files:
        objects = [o.name for o in bpy.data.objects]
        return {"error": "No files exported", "objects": objects}

    zip_path = os.path.join(temp_dir, "map.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))

    return FileResponse(zip_path, media_type="application/zip", filename=f"{shape}_Map.zip")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
