"""Mesh export dispatch. STL, OBJ, 3MF, GLB via trimesh.exchange."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import trimesh

ExportFormat = Literal["stl", "obj", "3mf", "glb"]

_FILE_TYPES: dict[str, str] = {
    "stl": "stl",
    "obj": "obj",
    "3mf": "3mf",
    "glb": "glb",
}


def export_mesh(mesh: trimesh.Trimesh, path: Path, fmt: ExportFormat) -> None:
    """Write `mesh` to `path` in the requested format. Parent dir is created."""
    if fmt not in _FILE_TYPES:
        raise ValueError(f"unsupported export format: {fmt!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(file_obj=str(path), file_type=_FILE_TYPES[fmt])
