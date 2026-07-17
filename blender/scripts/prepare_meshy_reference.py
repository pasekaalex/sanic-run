"""Export a local, optimized, unrigged GLB for a guarded Meshy experiment.

The corrected Blender source is opened read-only in practice: this script never
saves a ``.blend`` file. Texture and material changes are made on in-memory
copies only.

Usage::

    blender --background --factory-startup --python-exit-code 1 \
      --python blender/scripts/prepare_meshy_reference.py -- \
      /path/to/corrected.blend \
      /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/meshy-input.glb
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


EXPORT_COLLECTION = "SANIC_CHARACTER_EXPORT"
EXCLUDED_COLLECTIONS = ("SANIC_RAW_PRIVATE", "SANIC_SPIN_EXPORT")
MAX_IMAGE_DIMENSION = 1_024
REFERENCE_ROOT = Path(
    "/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference"
).resolve()


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def assert_outside_repository(output_path: Path) -> None:
    reference_root = REFERENCE_ROOT.expanduser().resolve()
    absolute = Path(os.path.abspath(output_path.expanduser()))
    resolved = absolute.resolve()
    assert (
        absolute.is_relative_to(reference_root)
        and resolved.is_relative_to(reference_root)
    ), (
        "Meshy reference output must stay under the reference root: "
        f"{output_path}"
    )


def open_source(source_path: Path) -> None:
    assert source_path.is_file(), f"Corrected Blender source does not exist: {source_path}"
    assert source_path.suffix.lower() == ".blend", (
        f"Corrected Meshy source must be a .blend file: {source_path}"
    )
    result = bpy.ops.wm.open_mainfile(filepath=str(source_path))
    assert result == {"FINISHED"}, result


def collection_object_set(collection: bpy.types.Collection) -> set[bpy.types.Object]:
    return set(collection.all_objects)


def select_export_meshes() -> list[bpy.types.Object]:
    collection = bpy.data.collections.get(EXPORT_COLLECTION)
    assert collection is not None, (
        f"Corrected source is missing collection {EXPORT_COLLECTION}"
    )
    excluded_objects: set[bpy.types.Object] = set()
    for name in EXCLUDED_COLLECTIONS:
        excluded = bpy.data.collections.get(name)
        assert excluded is not None, f"Corrected source is missing collection {name}"
        excluded_objects.update(collection_object_set(excluded))

    collection_objects = collection_object_set(collection)
    export_objects = sorted(
        (obj for obj in collection_objects if obj.type == "MESH"),
        key=lambda obj: obj.name,
    )
    assert export_objects, f"{EXPORT_COLLECTION} contains no mesh objects"
    assert not (set(export_objects) & excluded_objects), (
        f"{EXPORT_COLLECTION} shares objects with an excluded collection"
    )
    assert not [
        obj for obj in collection_objects if obj.type == "ARMATURE"
    ], f"{EXPORT_COLLECTION} must be unrigged"
    assert not [
        modifier
        for obj in export_objects
        for modifier in obj.modifiers
        if modifier.type == "ARMATURE"
    ], f"{EXPORT_COLLECTION} meshes must not use armature modifiers"

    bpy.ops.object.select_all(action="DESELECT")
    for obj in export_objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = export_objects[0]
    selected = set(bpy.context.selected_objects)
    assert selected == set(export_objects), (
        f"Unexpected selected objects: {sorted(obj.name for obj in selected)}"
    )
    return export_objects


def target_image_size(image: bpy.types.Image) -> tuple[int, int]:
    width, height = int(image.size[0]), int(image.size[1])
    assert width > 0 and height > 0, f"Texture image {image.name} has no pixel data"
    scale = min(1.0, MAX_IMAGE_DIMENSION / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def copy_and_pack_textures(
    export_objects: list[bpy.types.Object],
) -> dict[str, tuple[int, int]]:
    material_copies: dict[bpy.types.Material, bpy.types.Material] = {}
    image_copies: dict[bpy.types.Image, bpy.types.Image] = {}

    for obj in export_objects:
        for slot in obj.material_slots:
            source_material = slot.material
            if source_material is None:
                continue
            material_copy = material_copies.get(source_material)
            if material_copy is None:
                material_copy = source_material.copy()
                material_copy.name = f"{source_material.name}_MeshyReference"
                material_copies[source_material] = material_copy
                if material_copy.node_tree is not None:
                    for node in material_copy.node_tree.nodes:
                        if node.type != "TEX_IMAGE" or node.image is None:
                            continue
                        source_image = node.image
                        image_copy = image_copies.get(source_image)
                        if image_copy is None:
                            image_copy = source_image.copy()
                            image_copy.name = f"{source_image.name}_MeshyReference"
                            width, height = target_image_size(source_image)
                            if tuple(image_copy.size) != (width, height):
                                image_copy.scale(width, height)
                            image_copy.pack()
                            image_copies[source_image] = image_copy
                        node.image = image_copy
            slot.material = material_copy

    assert image_copies, f"{EXPORT_COLLECTION} contains no image textures"
    dimensions = {
        image.name: (int(copy.size[0]), int(copy.size[1]))
        for image, copy in image_copies.items()
    }
    assert all(max(size) <= MAX_IMAGE_DIMENSION for size in dimensions.values())
    assert all(copy.packed_file is not None for copy in image_copies.values())
    return dimensions


def evaluated_triangle_count(objects: list[bpy.types.Object]) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return total


def dimensions(objects: list[bpy.types.Object]) -> Vector:
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        for corner in obj.bound_box
    ]
    minimum = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    maximum = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    return maximum - minimum


def export_selected(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_materials="EXPORT",
        export_tangents=True,
        export_yup=True,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
    )
    assert result == {"FINISHED"}, result
    assert output_path.is_file(), f"Meshy reference export was not created: {output_path}"


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 2, (
        "Expected exactly SOURCE_BLEND and OUTPUT_GLB arguments"
    )
    source_path = Path(arguments[0]).expanduser().resolve()
    output_argument = Path(arguments[1]).expanduser()
    assert_outside_repository(output_argument)
    output_path = output_argument.resolve()
    assert output_path.suffix.lower() == ".glb", (
        f"Meshy reference output must be a GLB: {output_path}"
    )
    assert source_path != output_path, "Meshy reference output cannot overwrite its source"
    open_source(source_path)
    export_objects = select_export_meshes()
    images = copy_and_pack_textures(export_objects)
    triangles = evaluated_triangle_count(export_objects)
    asset_dimensions = dimensions(export_objects)
    export_selected(output_path)

    print(
        "MESHY_REFERENCE_EXPORT="
        + json.dumps(
            {
                "path": str(output_path),
                "bytes": output_path.stat().st_size,
                "triangles": triangles,
                "dimensions": [round(value, 6) for value in asset_dimensions],
                "images": {
                    name: list(size) for name, size in sorted(images.items())
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
