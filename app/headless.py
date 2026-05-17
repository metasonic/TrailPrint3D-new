import bpy
import sys
import os

# Ensure TrailPrint3D is loadable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import TrailPrint3D
from TrailPrint3D import utils, export, addon_preferences


class DummyPrefs:
    default_export_folder = ""
    openTopographyApiKey = ""

def mock_get_prefs():
    return DummyPrefs()

addon_preferences.get_prefs = mock_get_prefs


def init_blender_env():
    # Clear existing scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Register the addon to create the tp3d property group
    try:
        TrailPrint3D.register()
    except ValueError:
        pass # Already registered

def inject_config(config: dict):
    # Set properties dynamically on the scene's tp3d prop group
    tp3d = bpy.context.scene.tp3d
    for key, value in config.items():
        try:
            setattr(tp3d, key, value)
        except AttributeError:
            pass # Ignore read-only or invalid props

    # CRITICAL FIX: The addon derives the final object name (and therefore export filename) from 'trailName' if it is empty.
    # We must explicitly set it to our intended modelname so previews get _preview.stl suffix.
    tp3d.trailName = config.get('modelname', 'output')

def perform_generation(config_dict: dict, export_dir: str):
    init_blender_env()
    inject_config(config_dict)

    tp3d = bpy.context.scene.tp3d
    tp3d.export_path = export_dir

    # Ensure a default export dir is set in preferences so validation passes
    addon_preferences.get_prefs().default_export_folder = export_dir

    # Let's bypass UI warnings and invoke generation directly
    # TrailPrint3D uses utils.generation.runGeneration(0)
    # For headless, we can call it directly
    from TrailPrint3D.utils.generation import runGeneration

    try:
        runGeneration(0)
    except Exception as e:
        print(f"Generation failed: {e}")
        raise e
