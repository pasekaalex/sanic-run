"""Validate a local GLB before it is considered for a Meshy rigging task.

Usage::

    blender --background --factory-startup --python-exit-code 1 \
      --python blender/scripts/validate_meshy_reference.py -- /path/to/input.glb
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1_024
MAX_TRIANGLES = 300_000
MINIMUM_HEIGHT = 1.55
MAXIMUM_HEIGHT = 1.85
MAXIMUM_FOOT_OFFSET = 0.002
FACE_SIDE_MAXIMUM_Y = -0.20
MIRROR_TOLERANCE = 0.03
FACE_PAIRS = (
    ("SANIC_Face_Eyelid.L", "SANIC_Face_Eyelid.R"),
    ("SANIC_Face_Brow.L", "SANIC_Face_Brow.R"),
)


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def import_glb(path: Path) -> None:
    assert path.is_file(), f"Meshy reference does not exist: {path}"
    assert path.suffix.lower() == ".glb", f"Meshy reference must be a GLB: {path}"
    size = path.stat().st_size
    assert size <= MAX_FILE_BYTES, (
        f"Meshy reference exceeds {MAX_FILE_BYTES} bytes: {size}"
    )
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(path))
    assert result == {"FINISHED"}, result


def visible_meshes() -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render and not obj.hide_viewport
    ]


def textured_meshes(
    objects: list[bpy.types.Object],
) -> list[bpy.types.Object]:
    textured: list[bpy.types.Object] = []
    for obj in objects:
        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None or material.node_tree is None:
                continue
            if any(
                node.type == "TEX_IMAGE" and node.image is not None
                for node in material.node_tree.nodes
            ):
                textured.append(obj)
                break
    return textured


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


def world_bounds(
    objects: list[bpy.types.Object],
) -> tuple[Vector, Vector]:
    assert objects, "Meshy reference contains no visible mesh objects"
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


def mesh_centroid(obj: bpy.types.Object) -> Vector:
    assert obj.data.vertices, f"{obj.name} contains no vertices"
    return sum(
        (obj.matrix_world @ vertex.co for vertex in obj.data.vertices),
        Vector(),
    ) / len(obj.data.vertices)


def referenced_images(
    objects: list[bpy.types.Object],
) -> list[bpy.types.Image]:
    images: list[bpy.types.Image] = []
    seen: set[int] = set()
    for obj in objects:
        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None or material.node_tree is None:
                continue
            for node in material.node_tree.nodes:
                if node.type != "TEX_IMAGE" or node.image is None:
                    continue
                identity = id(node.image)
                if identity in seen:
                    continue
                seen.add(identity)
                images.append(node.image)
    return images


def image_dimensions(
    objects: list[bpy.types.Object] | None = None,
) -> dict[str, tuple[int, int]]:
    images = referenced_images(visible_meshes() if objects is None else objects)
    assert images, "Meshy reference contains no visible textured mesh objects"
    packed: dict[str, tuple[int, int]] = {}
    for image in images:
        assert image.packed_file is not None, (
            f"Referenced image {image.name} must be embedded/packed"
        )
        dimensions = (int(image.size[0]), int(image.size[1]))
        assert max(dimensions) <= MAX_IMAGE_DIMENSION, (
            f"Referenced image {image.name} exceeds "
            f"{MAX_IMAGE_DIMENSION}px: {dimensions}"
        )
        packed[image.name] = dimensions
    return packed


def validate(path: Path) -> dict[str, object]:
    import_glb(path)
    armatures = [
        obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"
    ]
    assert len(armatures) == 0, (
        f"Meshy reference must contain exactly zero armatures, got {len(armatures)}"
    )

    meshes = visible_meshes()
    assert meshes, "Meshy reference contains no visible mesh objects"
    images = image_dimensions(meshes)

    triangles = evaluated_triangle_count(meshes)
    assert triangles < MAX_TRIANGLES, (
        f"Meshy reference must contain fewer than {MAX_TRIANGLES} triangles: "
        f"{triangles}"
    )

    minimum, maximum = world_bounds(meshes)
    dimensions = maximum - minimum
    assert MINIMUM_HEIGHT <= dimensions.z <= MAXIMUM_HEIGHT, (
        f"Meshy reference height must be {MINIMUM_HEIGHT}-{MAXIMUM_HEIGHT} m: "
        f"{dimensions.z:.6f}"
    )
    assert abs(minimum.z) <= MAXIMUM_FOOT_OFFSET, (
        f"Meshy reference feet must sit near Z=0: {minimum.z:.6f}"
    )

    face_centroids: dict[str, Vector] = {}
    for left_name, right_name in FACE_PAIRS:
        for name in (left_name, right_name):
            obj = bpy.data.objects.get(name)
            assert obj is not None and obj.type == "MESH", (
                f"Meshy reference is missing semantic face mesh {name}"
            )
            centroid = mesh_centroid(obj)
            assert centroid.y < FACE_SIDE_MAXIMUM_Y, (
                f"{name} must remain on the Blender -Y face side: "
                f"{centroid.y:.6f}"
            )
            face_centroids[name] = centroid

        left = face_centroids[left_name]
        right = face_centroids[right_name]
        assert abs(left.x + right.x) <= MIRROR_TOLERANCE, (
            f"{left_name}/{right_name} X centroids are not mirrored: "
            f"{left.x:.6f}, {right.x:.6f}"
        )
        assert abs(left.y - right.y) <= MIRROR_TOLERANCE, (
            f"{left_name}/{right_name} Y centroids do not match: "
            f"{left.y:.6f}, {right.y:.6f}"
        )

    return {
        "bytes": path.stat().st_size,
        "triangles": triangles,
        "dimensions": [round(value, 6) for value in dimensions],
        "minimum": [round(value, 6) for value in minimum],
        "images": {name: list(size) for name, size in sorted(images.items())},
        "face_centroids": {
            name: [round(value, 6) for value in centroid]
            for name, centroid in sorted(face_centroids.items())
        },
    }


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 1, "Expected exactly one Meshy reference GLB path"
    path = Path(arguments[0]).expanduser().resolve()
    report = validate(path)
    print(f"MESHY_REFERENCE_REPORT={json.dumps(report, sort_keys=True)}")
    print("MESHY_REFERENCE_VALIDATION=PASS")


if __name__ == "__main__":
    main()
