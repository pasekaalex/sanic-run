"""Validate the reproducible SANIC Blender source assets.

Usage (Blender consumes arguments before ``--``)::

    blender --background blender/sanic-source.blend \
      --python blender/scripts/validate_assets.py -- character
    blender --background blender/world-source.blend \
      --python blender/scripts/validate_assets.py -- world
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


CHARACTER_OBJECTS = {
    "SANIC_Armature",
    "SANIC_BodySculpt",
    "SANIC_Head",
    "SANIC_Quills",
    "SANIC_Muzzle",
    "SANIC_Eyes",
    "SANIC_GloveShell.L",
    "SANIC_GloveShell.R",
    "SANIC_ShoeUpper.L",
    "SANIC_ShoeUpper.R",
    "SANIC_ShoeMidsole.L",
    "SANIC_ShoeMidsole.R",
    "SANIC_ShoeOutsole.L",
    "SANIC_ShoeOutsole.R",
    "SANIC_ShoeStrap.L",
    "SANIC_ShoeStrap.R",
}
CHARACTER_ACTIONS = {"Idle", "Run", "Jump", "Crash"}
CHARACTER_BONES = {
    "root", "hips", "spine", "spine_upper", "chest", "neck", "head",
    "clavicle.L", "clavicle.R",
    "upper_arm.L", "upper_arm.R", "upper_arm_twist.L", "upper_arm_twist.R",
    "lower_arm.L", "lower_arm.R", "lower_arm_twist.L", "lower_arm_twist.R",
    "hand.L", "hand.R", "thumb.L", "thumb.R",
    "finger_index.L", "finger_index.R", "finger_middle.L", "finger_middle.R",
    "finger_ring.L", "finger_ring.R", "finger_pinky.L", "finger_pinky.R",
    "upper_leg.L", "upper_leg.R", "upper_leg_twist.L", "upper_leg_twist.R",
    "lower_leg.L", "lower_leg.R", "lower_leg_twist.L", "lower_leg_twist.R",
    "foot.L", "foot.R", "toe.L", "toe.R",
    "quill_upper", "quill_mid", "quill_lower",
}
BLOCKY_SOURCE_OBJECTS = {
    "SANIC_Sole.L", "SANIC_Sole.R", "SANIC_Midsole.L", "SANIC_Midsole.R",
    "SANIC_Shoe.L", "SANIC_Shoe.R", "SANIC_ShoeToe.L", "SANIC_ShoeToe.R",
}
ACTION_FRAME_RANGES = {
    "Idle": (1, 60),
    "Run": (1, 21),
    "Jump": (1, 30),
    "Crash": (1, 42),
}
WORLD_OBJECTS = {
    "SANIC_Ring",
    "KIT_Tree_A",
    "KIT_Tree_B",
    "KIT_Grass",
    "KIT_Fern",
    "KIT_Rock",
    "KIT_Mushroom",
    "KIT_Log",
    "KIT_Candle",
    "KIT_FUD",
    "KIT_Gap",
    "KIT_Sign_Stimmy",
    "KIT_Sign_Trenches",
    "KIT_Sign_Coping",
    "KIT_Sign_Memes",
}
WORLD_EXPORT_COLLECTIONS = {"WORLD_RING_EXPORT", "WORLD_KIT_EXPORT"}


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def evaluated_triangle_count(objects: list[bpy.types.Object]) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return triangles


def validate_character() -> None:
    objects = set(bpy.data.objects.keys())
    missing_objects = CHARACTER_OBJECTS - objects
    missing_actions = CHARACTER_ACTIONS - set(bpy.data.actions.keys())
    assert not missing_objects, f"Missing objects: {sorted(missing_objects)}"
    assert not (BLOCKY_SOURCE_OBJECTS & objects), (
        f"Legacy box footwear remains: {sorted(BLOCKY_SOURCE_OBJECTS & objects)}"
    )
    assert not missing_actions, f"Missing actions: {sorted(missing_actions)}"

    body = bpy.data.objects["SANIC_BodySculpt"]
    assert body.get("sanic_base_license") == "CC0-1.0"
    assert body.get("sanic_base_source") == "Blender Studio Human Base Meshes v1.4.1"
    assert body.get("sanic_base_object") == "GEO-body_male_realistic"
    assert all(polygon.use_smooth for polygon in body.data.polygons)

    rig = bpy.data.objects["SANIC_Armature"]
    actual_bones = {bone.name for bone in rig.data.bones}
    missing_bones = CHARACTER_BONES - actual_bones
    assert not missing_bones, f"Missing deformation bones: {sorted(missing_bones)}"

    assert bpy.context.scene.render.fps == 30
    for name, expected_range in ACTION_FRAME_RANGES.items():
        action = bpy.data.actions[name]
        actual_range = tuple(int(value) for value in action.frame_range)
        assert actual_range == expected_range, (name, actual_range, expected_range)

    source = list(bpy.data.collections["SANIC_SOURCE_HIGH"].all_objects)
    web = list(bpy.data.collections["SANIC_WEB"].all_objects)
    source_triangles = evaluated_triangle_count(source)
    web_triangles = evaluated_triangle_count(web)
    assert 350_000 <= source_triangles <= 600_000, source_triangles
    assert 100_000 <= web_triangles <= 140_000, web_triangles

    glb_path = Path(bpy.data.filepath).parents[1] / "public/models/sanic-runner.glb"
    assert glb_path.is_file()
    assert 1_000_000 <= glb_path.stat().st_size < 5_000_000, glb_path.stat().st_size

    assert Path(bpy.data.filepath).name == "sanic-source.blend"
    print(
        {
            "mode": "character",
            "objects": len(bpy.data.objects),
            "actions": sorted(CHARACTER_ACTIONS),
            "source_triangles": source_triangles,
            "web_triangles": web_triangles,
            "glb_bytes": glb_path.stat().st_size,
        }
    )


def validate_world() -> None:
    missing_collections = WORLD_EXPORT_COLLECTIONS - set(bpy.data.collections.keys())
    assert not missing_collections, f"Missing export collections: {sorted(missing_collections)}"

    missing_objects = WORLD_OBJECTS - set(bpy.data.objects.keys())
    assert not missing_objects, f"Missing world objects: {sorted(missing_objects)}"

    suffixed_duplicates = {
        obj.name
        for obj in bpy.data.objects
        if any(obj.name.startswith(f"{required}.") for required in WORLD_OBJECTS)
    }
    assert not suffixed_duplicates, f"Suffixed duplicate world roots: {sorted(suffixed_duplicates)}"

    required = [bpy.data.objects[name] for name in sorted(WORLD_OBJECTS)]
    wrong_types = {obj.name: obj.type for obj in required if obj.type != "MESH"}
    assert not wrong_types, f"World roots must be Mesh objects: {wrong_types}"
    parented = sorted(obj.name for obj in required if obj.parent is not None)
    assert not parented, f"World roots must be unparented: {parented}"

    missing_uvs = sorted(obj.name for obj in required if not obj.data.uv_layers)
    assert not missing_uvs, f"World roots missing UV maps: {missing_uvs}"
    negative_scales = {
        obj.name: tuple(round(value, 6) for value in obj.scale)
        for obj in required
        if any(value < 0.0 for value in obj.scale)
    }
    assert not negative_scales, f"Negative world-root scales: {negative_scales}"
    unapplied_scales = {
        obj.name: tuple(round(value, 6) for value in obj.scale)
        for obj in required
        if any(abs(value - 1.0) > 1e-5 for value in obj.scale)
    }
    assert not unapplied_scales, f"World-root scales are not applied: {unapplied_scales}"

    exported: list[bpy.types.Object] = []
    for collection_name in sorted(WORLD_EXPORT_COLLECTIONS):
        exported.extend(bpy.data.collections[collection_name].all_objects)
    exported_unique = list({obj.name: obj for obj in exported}.values())
    exported_names = {obj.name for obj in exported_unique}
    assert exported_names == WORLD_OBJECTS, (
        f"Export collection contract mismatch; missing={sorted(WORLD_OBJECTS - exported_names)}, "
        f"extra={sorted(exported_names - WORLD_OBJECTS)}"
    )
    triangles = evaluated_triangle_count(exported_unique)
    assert triangles < 120_000, f"World export triangle count is {triangles}"
    assert Path(bpy.data.filepath).name == "world-source.blend"
    print(
        {
            "mode": "world",
            "objects": sorted(exported_names),
            "triangles": triangles,
        }
    )


def main() -> None:
    args = arguments_after_separator()
    assert len(args) == 1 and args[0] in {"character", "world"}, (
        "Expected exactly one validation mode after '--': character or world"
    )
    if args[0] == "character":
        validate_character()
    else:
        validate_world()


if __name__ == "__main__":
    main()
