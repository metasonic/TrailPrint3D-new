"""Boolean assembly via the Manifold engine.

Manifold is required (the brief mandates it). If `manifold3d` is not importable
or the boolean op produces a non-manifold result, this module raises rather
than silently falling back — print safety beats apparent robustness.
"""

from __future__ import annotations

import trimesh


def _check_manifold_available() -> None:
    try:
        import manifold3d  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "manifold3d is not installed; install it (poetry install) before running the pipeline"
        ) from exc


def intersect(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """a ∩ b using the Manifold engine."""
    _check_manifold_available()
    result = trimesh.boolean.intersection([a, b], engine="manifold")
    if not isinstance(result, trimesh.Trimesh) or result.is_empty:
        raise RuntimeError("boolean intersection produced an empty mesh")
    return result


def union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Union of N meshes via the Manifold engine. Raises if the result is non-manifold."""
    _check_manifold_available()
    if not meshes:
        raise ValueError("union() needs at least one mesh")
    if len(meshes) == 1:
        return meshes[0]
    result = trimesh.boolean.union(meshes, engine="manifold")
    if not isinstance(result, trimesh.Trimesh) or result.is_empty:
        raise RuntimeError("boolean union produced an empty mesh")
    if not result.is_volume:
        raise RuntimeError("boolean union produced a non-manifold mesh; refusing to ship")
    return result
