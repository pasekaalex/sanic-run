"""Validate corrected Meshy SANIC handoff assets.

Usage::

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_correction.py -- \
      character /path/to/SANIC-meshy6-v1-corrected.glb

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_correction.py -- \
      spin-ball /path/to/SANIC-spin-ball-v1.glb

    blender --background /path/to/SANIC-meshy6-v1-corrected.blend \
      --python blender/scripts/validate_meshy_correction.py -- source
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


EXPECTED_CORRECTED = {
    "SANIC_BodyBase",
    "SANIC_Glove.L",
    "SANIC_Glove.R",
    "SANIC_Face_Eyelid.L",
    "SANIC_Face_Eyelid.R",
    "SANIC_Face_Brow.L",
    "SANIC_Face_Brow.R",
}
EXPECTED_SPIN = {"SANIC_SpinBall"}
EXPORT_COLLECTIONS = {"SANIC_CHARACTER_EXPORT", "SANIC_SPIN_EXPORT"}
RAW_COLLECTION = "SANIC_RAW_PRIVATE"


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def renderable_meshes() -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render
    ]


def renderable_bounds(
    objects: list[bpy.types.Object],
) -> tuple[Vector, Vector]:
    assert objects, "Asset contains no renderable mesh objects"
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        for corner in obj.bound_box
    ]
    return (
        Vector(
            (
                min(point.x for point in points),
                min(point.y for point in points),
                min(point.z for point in points),
            )
        ),
        Vector(
            (
                max(point.x for point in points),
                max(point.y for point in points),
                max(point.z for point in points),
            )
        ),
    )


def triangle_count(objects: list[bpy.types.Object]) -> int:
    total = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return total


def find_layer_collection(
    root: bpy.types.LayerCollection,
    name: str,
) -> bpy.types.LayerCollection | None:
    if root.collection.name == name:
        return root
    for child in root.children:
        match = find_layer_collection(child, name)
        if match is not None:
            return match
    return None


def reset_and_import(asset_path: Path) -> None:
    if not asset_path.is_file():
        raise FileNotFoundError(
            f"SANIC correction input does not exist: {asset_path}"
        )
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(asset_path))
    assert result == {"FINISHED"}, result


def validate_character(asset_path: Path) -> dict[str, object]:
    reset_and_import(asset_path)
    objects = renderable_meshes()
    names = {obj.name for obj in objects}
    missing = EXPECTED_CORRECTED - names
    assert not missing, f"Corrected character is missing objects: {sorted(missing)}"
    assert not [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"], (
        "Static correction export must not contain an armature"
    )
    assert not bpy.data.actions, "Static correction export must not contain actions"

    minimum, maximum = renderable_bounds(objects)
    dimensions = maximum - minimum
    triangles = triangle_count(objects)
    assert 1.68 <= dimensions.z <= 1.72, (
        f"Corrected character height must be 1.70 m, got {dimensions.z:.6f}"
    )
    assert abs(minimum.z) <= 0.002, (
        f"Corrected character feet must sit on Z=0, got {minimum.z:.6f}"
    )
    assert triangles < 180_000, (
        f"Corrected character exceeds 180000 triangles: {triangles}"
    )
    for side in ("L", "R"):
        glove = bpy.data.objects[f"SANIC_Glove.{side}"]
        assert len(glove.data.polygons) >= 500, (
            f"SANIC_Glove.{side} lacks modeled digit detail"
        )

    body = bpy.data.objects["SANIC_BodyBase"]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body_tree = BVHTree.FromObject(body, depsgraph)
    assert body_tree is not None
    for name in sorted(EXPECTED_CORRECTED):
        if not name.startswith("SANIC_Face_"):
            continue
        overlay = bpy.data.objects[name]
        center = sum(
            (overlay.matrix_world @ Vector(corner) for corner in overlay.bound_box),
            Vector(),
        ) / 8.0
        nearest = body_tree.find_nearest(center)
        assert nearest is not None
        distance = nearest[3]
        assert distance <= 0.018, (
            f"{name} floats {distance:.6f} m from the face surface"
        )

    return {
        "mode": "character",
        "objects": len(objects),
        "triangles": triangles,
        "minimum": [round(value, 6) for value in minimum],
        "maximum": [round(value, 6) for value in maximum],
        "dimensions": [round(value, 6) for value in dimensions],
    }


def validate_spin_ball(asset_path: Path) -> dict[str, object]:
    reset_and_import(asset_path)
    objects = renderable_meshes()
    names = {obj.name for obj in objects}
    missing = EXPECTED_SPIN - names
    assert not missing, f"Spin-ball export is missing objects: {sorted(missing)}"
    assert names == EXPECTED_SPIN, (
        f"Spin-ball export must contain one joined root, got {sorted(names)}"
    )
    minimum, maximum = renderable_bounds(objects)
    dimensions = maximum - minimum
    maximum_dimension = max(dimensions)
    triangles = triangle_count(objects)
    assert 0.72 <= maximum_dimension <= 0.85, (
        f"Spin-ball maximum dimension must be 0.72-0.85 m, got {maximum_dimension:.6f}"
    )
    assert triangles <= 8_000, f"Spin-ball exceeds 8000 triangles: {triangles}"
    assert len(objects[0].data.materials) <= 3, (
        f"Spin-ball must use at most three materials, got {len(objects[0].data.materials)}"
    )
    return {
        "mode": "spin-ball",
        "objects": len(objects),
        "triangles": triangles,
        "minimum": [round(value, 6) for value in minimum],
        "maximum": [round(value, 6) for value in maximum],
        "dimensions": [round(value, 6) for value in dimensions],
    }


def validate_source() -> dict[str, object]:
    collection_names = set(bpy.data.collections.keys())
    missing = EXPORT_COLLECTIONS - collection_names
    assert not missing, f"Corrected source is missing collections: {sorted(missing)}"
    assert RAW_COLLECTION in collection_names, (
        f"Corrected source is missing private collection {RAW_COLLECTION}"
    )
    raw_layer = find_layer_collection(
        bpy.context.view_layer.layer_collection,
        RAW_COLLECTION,
    )
    assert raw_layer is not None, f"Could not find view-layer entry for {RAW_COLLECTION}"
    assert raw_layer.exclude, f"{RAW_COLLECTION} must be excluded from the active view layer"
    character_names = {
        obj.name for obj in bpy.data.collections["SANIC_CHARACTER_EXPORT"].objects
    }
    spin_names = {
        obj.name for obj in bpy.data.collections["SANIC_SPIN_EXPORT"].objects
    }
    assert EXPECTED_CORRECTED <= character_names, (
        f"Character collection is missing {sorted(EXPECTED_CORRECTED - character_names)}"
    )
    assert EXPECTED_SPIN <= spin_names, (
        f"Spin collection is missing {sorted(EXPECTED_SPIN - spin_names)}"
    )
    return {
        "mode": "source",
        "character_objects": len(character_names),
        "spin_objects": len(spin_names),
        "raw_objects": len(bpy.data.collections[RAW_COLLECTION].objects),
    }


def main() -> None:
    arguments = arguments_after_separator()
    assert arguments, "Expected validation mode: source, character, or spin-ball"
    mode = arguments[0]
    if mode == "source":
        assert len(arguments) == 1, "source mode reads the already-open Blender file"
        report = validate_source()
    else:
        assert len(arguments) == 2, f"{mode} mode requires one asset path"
        asset_path = Path(arguments[1]).expanduser().resolve()
        if mode == "character":
            report = validate_character(asset_path)
        elif mode == "spin-ball":
            report = validate_spin_ball(asset_path)
        else:
            raise ValueError(f"Unknown SANIC correction validation mode: {mode}")
    print(f"SANIC_CORRECTION_REPORT={json.dumps(report, sort_keys=True)}")
    print("SANIC_CORRECTION_VALIDATION=PASS")


if __name__ == "__main__":
    main()
