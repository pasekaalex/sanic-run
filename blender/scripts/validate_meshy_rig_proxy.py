"""Validate the detector-friendly A-pose proxy before a Meshy rig request."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TRIANGLES = 50_000
MIN_TRIANGLES = 5_000
EXPECTED_HEIGHT = 1.7
HEIGHT_TOLERANCE = 0.005
FOOT_TOLERANCE = 0.002
MAXIMUM_WIDTH = 1.75
MAXIMUM_DEPTH = 0.50
REQUIRED_PARTS = {
    "Proxy_Head",
    "Proxy_Torso",
    "Proxy_Pelvis",
    "Proxy_Nose",
    "Proxy_UpperArm.L",
    "Proxy_UpperArm.R",
    "Proxy_LowerArm.L",
    "Proxy_LowerArm.R",
    "Proxy_Hand.L",
    "Proxy_Hand.R",
    "Proxy_UpperLeg.L",
    "Proxy_UpperLeg.R",
    "Proxy_LowerLeg.L",
    "Proxy_LowerLeg.R",
    "Proxy_Foot.L",
    "Proxy_Foot.R",
}


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def world_bounds(
    objects: list[bpy.types.Object],
) -> tuple[Vector, Vector]:
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


def centroid(obj: bpy.types.Object) -> Vector:
    return sum(
        (obj.matrix_world @ vertex.co for vertex in obj.data.vertices),
        Vector(),
    ) / len(obj.data.vertices)


def triangle_count(objects: list[bpy.types.Object]) -> int:
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


def embedded_images(objects: list[bpy.types.Object]) -> dict[str, list[int]]:
    images: dict[str, list[int]] = {}
    for obj in objects:
        assert obj.material_slots, f"{obj.name} has no material"
        for slot in obj.material_slots:
            material = slot.material
            assert material is not None and material.node_tree is not None, (
                f"{obj.name} has an invalid material"
            )
            texture_nodes = [
                node
                for node in material.node_tree.nodes
                if node.type == "TEX_IMAGE" and node.image is not None
            ]
            assert texture_nodes, f"{obj.name} is not image textured"
            for node in texture_nodes:
                image = node.image
                assert image is not None and image.packed_file is not None, (
                    f"{obj.name} texture is not embedded"
                )
                images[image.name] = [int(image.size[0]), int(image.size[1])]
    return images


def validate(path: Path) -> dict[str, object]:
    assert path.is_file(), f"Meshy proxy GLB does not exist: {path}"
    assert path.suffix.lower() == ".glb", f"Meshy proxy must be GLB: {path}"
    assert path.stat().st_size <= MAX_FILE_BYTES, (
        f"Meshy proxy exceeds {MAX_FILE_BYTES} bytes"
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(path))
    assert result == {"FINISHED"}, result

    armatures = [
        obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"
    ]
    assert not armatures, "Meshy pose-estimation proxy must be unrigged"
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render
    ]
    names = {obj.name for obj in meshes}
    missing = REQUIRED_PARTS - names
    assert not missing, f"Meshy proxy is missing parts: {sorted(missing)}"

    minimum, maximum = world_bounds(meshes)
    dimensions = maximum - minimum
    assert abs(dimensions.z - EXPECTED_HEIGHT) <= HEIGHT_TOLERANCE, (
        f"Meshy proxy height is not {EXPECTED_HEIGHT}m: {dimensions.z:.6f}"
    )
    assert abs(minimum.z) <= FOOT_TOLERANCE, (
        f"Meshy proxy feet are not grounded: {minimum.z:.6f}"
    )
    assert dimensions.x <= MAXIMUM_WIDTH, (
        f"Meshy proxy is too wide: {dimensions.x:.6f}"
    )
    assert dimensions.y <= MAXIMUM_DEPTH, (
        f"Meshy proxy is too deep: {dimensions.y:.6f}"
    )

    triangles = triangle_count(meshes)
    assert MIN_TRIANGLES <= triangles < MAX_TRIANGLES, (
        f"Meshy proxy triangle count is unsuitable: {triangles}"
    )
    images = embedded_images(meshes)

    nose = centroid(bpy.data.objects["Proxy_Nose"])
    head = centroid(bpy.data.objects["Proxy_Head"])
    assert nose.y < head.y - 0.08, (
        "Meshy proxy nose must unambiguously mark Blender -Y / glTF +Z front"
    )

    for left_name, right_name in (
        ("Proxy_Hand.L", "Proxy_Hand.R"),
        ("Proxy_Foot.L", "Proxy_Foot.R"),
        ("Proxy_UpperArm.L", "Proxy_UpperArm.R"),
        ("Proxy_LowerLeg.L", "Proxy_LowerLeg.R"),
    ):
        left = centroid(bpy.data.objects[left_name])
        right = centroid(bpy.data.objects[right_name])
        assert abs(left.x + right.x) <= 0.005
        assert abs(left.y - right.y) <= 0.005
        assert abs(left.z - right.z) <= 0.005

    hand = centroid(bpy.data.objects["Proxy_Hand.R"])
    shoulder = centroid(bpy.data.objects["Proxy_Shoulder.R"])
    assert hand.x - shoulder.x >= 0.50, "A-pose arms are not clearly separated"
    assert shoulder.z - hand.z >= 0.15, "A-pose arms are not angled downward"

    return {
        "bytes": path.stat().st_size,
        "triangles": triangles,
        "meshes": len(meshes),
        "images": images,
        "minimum": [round(value, 6) for value in minimum],
        "dimensions": [round(value, 6) for value in dimensions],
        "nose": [round(value, 6) for value in nose],
    }


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 1, "Expected exactly one proxy GLB path"
    report = validate(Path(arguments[0]).expanduser().resolve())
    print(f"MESHY_PROXY_REPORT={json.dumps(report, sort_keys=True)}")
    print("MESHY_PROXY_VALIDATION=PASS")


if __name__ == "__main__":
    main()
