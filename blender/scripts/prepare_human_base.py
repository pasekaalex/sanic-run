"""Isolate the verified Blender Studio CC0 male body for SANIC builds.

Usage (Blender consumes arguments before ``--``)::

    blender --background --python-exit-code 1 \
      --python blender/scripts/prepare_human_base.py -- SOURCE.blend OUTPUT.blend
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


SOURCE_OBJECT = "GEO-body_male_realistic"
OUTPUT_OBJECT = "SANIC_CC0_MaleBase"
BASE_PROPERTIES = {
    "sanic_base_license": "CC0-1.0",
    "sanic_base_source": "Blender Studio Human Base Meshes v1.4.1",
    "sanic_base_object": SOURCE_OBJECT,
}


def normalized(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def reset_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for candidate in list(bpy.data.collections):
        bpy.data.collections.remove(candidate)


def append_verified_body(source_path: Path) -> bpy.types.Object:
    with bpy.data.libraries.load(str(source_path), link=False) as (source, target):
        source_objects = list(source.objects)
        matches = [
            name for name in source_objects if normalized(name) == "geobodymalerealistic"
        ]
        assert len(matches) == 1, f"Expected one realistic male body, found {matches}"
        target.objects = matches

    body = target.objects[0]
    assert body is not None and body.type == "MESH", body
    source_collection = bpy.data.collections.new("SANIC_CC0_SOURCE")
    bpy.context.scene.collection.children.link(source_collection)
    source_collection.objects.link(body)
    return body


def trim_body(body: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body

    # The asset-browser collection lays the source out beside its peers.  The
    # mesh itself is centered, so discard that library-display offset before
    # applying the remaining object transforms.
    body.location = (0.0, 0.0, 0.0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    body.name = OUTPUT_OBJECT
    body.data.name = f"{OUTPUT_OBJECT}_Mesh"
    body.animation_data_clear()
    body.data.materials.clear()

    for key in list(body.keys()):
        del body[key]
    for key, value in BASE_PROPERTIES.items():
        body[key] = value

    multires = [modifier for modifier in body.modifiers if modifier.type == "MULTIRES"]
    assert len(multires) == 1, f"Expected one Multires modifier, found {multires}"
    assert multires[0].total_levels >= 2, multires[0].total_levels

    for candidate in list(bpy.data.objects):
        if candidate != body:
            bpy.data.objects.remove(candidate, do_unlink=True)
    bpy.ops.outliner.orphans_purge(
        do_local_ids=True,
        do_linked_ids=True,
        do_recursive=True,
    )


def main() -> None:
    args = arguments_after_separator()
    assert len(args) == 2, "Expected SOURCE.blend and OUTPUT.blend after '--'"
    source_path = Path(args[0]).expanduser().resolve()
    output_path = Path(args[1]).expanduser().resolve()
    assert source_path.is_file(), source_path
    assert source_path.suffix == ".blend", source_path
    assert output_path.suffix == ".blend", output_path
    assert source_path != output_path, "Source and output paths must differ"

    reset_scene()
    body = append_verified_body(source_path)
    trim_body(body)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), check_existing=False)

    mesh_objects = [obj.name for obj in bpy.data.objects if obj.type == "MESH"]
    modifier = next(item for item in body.modifiers if item.type == "MULTIRES")
    print(
        "SANIC_CC0_BASE_PREPARED",
        {
            "output": str(output_path),
            "mesh_objects": mesh_objects,
            "vertices": len(body.data.vertices),
            "polygons": len(body.data.polygons),
            "multires_total_levels": modifier.total_levels,
        },
    )


if __name__ == "__main__":
    main()
