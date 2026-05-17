"""context_shim.py — Drop-in replacement for bpy.context.scene.tp3d.

The generation code reads hundreds of attributes from the scene's
PropertyGroup.  This shim exposes the same interface (attribute access,
dict-style .get(), item access) so the headless script can populate it
from a plain params dict and pass it into the pipeline unchanged.
"""


class TP3DContext:
    """Drop-in replacement for bpy.context.scene.tp3d.

    Supports dict-style .get(key, default), attribute access, and item access.
    All reads return from the internal _data dict; missing keys return None.
    """

    def __init__(self, params: dict):
        object.__setattr__(self, '_data', dict(params))

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return self._data.get(name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value

    def get(self, name, default=None):
        return self._data.get(name, default)

    def __getitem__(self, key):
        return self._data.get(key)

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data
