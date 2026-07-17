"""Validate the rigged and animated Meshy SANIC handoff.

Usage::

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_rig.py -- glb /path/to/runner.glb

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_rig.py -- source /path/to/runner.blend
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


EXPECTED_BONES = {
    "root",
    "hips",
    "spine",
    "chest",
    "neck",
    "head",
    "shoulder.L",
    "upper_arm.L",
    "lower_arm.L",
    "hand.L",
    "shoulder.R",
    "upper_arm.R",
    "lower_arm.R",
    "hand.R",
    "upper_leg.L",
    "lower_leg.L",
    "foot.L",
    "toe.L",
    "upper_leg.R",
    "lower_leg.R",
    "foot.R",
    "toe.R",
}
EXPECTED_ACTION_RANGES = {
    "Idle": (1, 60),
    "Run": (1, 24),
    "Jump": (1, 30),
    "Crash": (1, 36),
}
EXPECTED_ACTION_RANGES_V2 = {
    **EXPECTED_ACTION_RANGES,
    "Run": (1, 17),
}
RIGGED_COLLECTION = "SANIC_RIGGED_EXPORT"


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def ensure_input(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"SANIC rig input does not exist: {path}")


def mesh_objects() -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        # Blender's glTF importer creates a local-only Icosphere custom shape
        # for joints. It is not a node in the GLB and must not count as game
        # geometry, bounds, triangles, or skin weights.
        and all(collection.name != "glTF_not_exported" for collection in obj.users_collection)
    ]


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    assert objects, "Rigged SANIC contains no mesh objects"
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


def weight_metrics(objects: list[bpy.types.Object]) -> dict[str, object]:
    unweighted = 0
    denormalized = 0
    over_influenced = 0
    maximum_influences = 0
    weighted_vertices = 0
    for obj in objects:
        group_names = {group.index: group.name for group in obj.vertex_groups}
        for vertex in obj.data.vertices:
            influences = [
                membership.weight
                for membership in vertex.groups
                if membership.group in group_names and membership.weight > 1e-5
            ]
            if not influences:
                unweighted += 1
                continue
            weighted_vertices += 1
            maximum_influences = max(maximum_influences, len(influences))
            if len(influences) > 4:
                over_influenced += 1
            if abs(sum(influences) - 1.0) > 0.01:
                denormalized += 1
    return {
        "weighted_vertices": weighted_vertices,
        "unweighted": unweighted,
        "denormalized": denormalized,
        "over_influenced": over_influenced,
        "maximum_influences": maximum_influences,
    }


def action_ranges() -> dict[str, tuple[int, int]]:
    return {
        action.name: (
            int(round(action.frame_range[0])),
            int(round(action.frame_range[1])),
        )
        for action in bpy.data.actions
        if action.name in EXPECTED_ACTION_RANGES
    }


def validate_run_cycle(
    rig: bpy.types.Object,
    end_frame: int,
    passing_samples: tuple[tuple[int, str], tuple[int, str]],
    minimum_hand_travel: float,
) -> dict[str, float]:
    action = bpy.data.actions.get("Run")
    assert action is not None
    rig.animation_data_create()
    rig.animation_data.action = action
    scene = bpy.context.scene
    maximum_root_x = 0.0
    maximum_root_y = 0.0
    first_rotations: dict[str, tuple[float, float, float, float]] = {}
    final_rotations: dict[str, tuple[float, float, float, float]] = {}
    minimum_ground_clearance = float("inf")
    left_hand_forward_positions: list[float] = []
    right_hand_forward_positions: list[float] = []
    passing_knee_heights: list[float] = []
    for frame in range(1, end_frame + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        root = rig.pose.bones["root"]
        rest_head = rig.matrix_world @ rig.data.bones["root"].head_local
        posed_head = rig.matrix_world @ root.head
        displacement = posed_head - rest_head
        maximum_root_x = max(maximum_root_x, abs(displacement.x))
        maximum_root_y = max(maximum_root_y, abs(displacement.y))
        left_hand_forward_positions.append(rig.pose.bones["hand.L"].head.y)
        right_hand_forward_positions.append(rig.pose.bones["hand.R"].head.y)
        for passing_frame, recovery_side in passing_samples:
            if frame == passing_frame:
                passing_knee_heights.append(
                    rig.pose.bones[f"lower_leg.{recovery_side}"].head.z
                )
        for obj in mesh_objects():
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            minimum_ground_clearance = min(
                minimum_ground_clearance,
                min(
                    (evaluated.matrix_world @ Vector(corner)).z
                    for corner in evaluated.bound_box
                ),
            )
        if frame in {1, end_frame}:
            destination = first_rotations if frame == 1 else final_rotations
            for bone in rig.pose.bones:
                quaternion = bone.rotation_quaternion.normalized()
                destination[bone.name] = tuple(quaternion)
    assert maximum_root_x <= 0.002, (
        f"Run root drifts laterally by {maximum_root_x:.6f} m"
    )
    assert maximum_root_y <= 0.002, (
        f"Run root drifts forward by {maximum_root_y:.6f} m"
    )
    largest_cycle_error = 0.0
    for name in EXPECTED_BONES:
        first = first_rotations[name]
        final = final_rotations[name]
        direct = max(abs(first[index] - final[index]) for index in range(4))
        negated = max(abs(first[index] + final[index]) for index in range(4))
        largest_cycle_error = max(largest_cycle_error, min(direct, negated))
    assert largest_cycle_error <= 1e-4, (
        f"Run first/final pose mismatch is {largest_cycle_error:.8f}"
    )
    assert minimum_ground_clearance >= -0.002, (
        f"Run feet penetrate the ground by {-minimum_ground_clearance:.6f} m"
    )
    hand_travel = min(
        max(left_hand_forward_positions) - min(left_hand_forward_positions),
        max(right_hand_forward_positions) - min(right_hand_forward_positions),
    )
    assert hand_travel >= minimum_hand_travel, (
        f"Run hand travel is too weak: {hand_travel:.6f} m"
    )
    minimum_passing_knee_height = min(passing_knee_heights)
    assert minimum_passing_knee_height >= 0.46, (
        f"Run passing knee is too low: {minimum_passing_knee_height:.6f} m"
    )
    rig.animation_data.action = None
    return {
        "maximum_root_x": maximum_root_x,
        "maximum_root_y": maximum_root_y,
        "cycle_error": largest_cycle_error,
        "minimum_ground_clearance": minimum_ground_clearance,
        "hand_travel": hand_travel,
        "minimum_passing_knee_height": minimum_passing_knee_height,
    }


def validate_common(mode: str) -> dict[str, object]:
    meshes = mesh_objects()
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(armatures) == 1, f"Expected one armature, got {[obj.name for obj in armatures]}"
    rig = armatures[0]
    bones = set(rig.data.bones.keys())
    missing_bones = EXPECTED_BONES - bones
    assert not missing_bones, f"Rig is missing bones: {sorted(missing_bones)}"

    # Blender's glTF importer assigns the final imported action to the rig.
    # Three.js does not autoplay a clip, so measure the same neutral bind pose
    # the game initially renders rather than an arbitrary Crash frame.
    rig.animation_data_create()
    rig.animation_data.action = None
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()

    rig_version = int(rig.get("sanic_rig_version", 1))
    expected_ranges = (
        EXPECTED_ACTION_RANGES_V2
        if rig_version in {2, 3}
        else EXPECTED_ACTION_RANGES
    )
    if rig_version == 3:
        assert rig.get("sanic_run_variant") == "v3-run", (
            "SANIC rig version 3 must use sanic_run_variant='v3-run'"
        )
    ranges = action_ranges()
    assert ranges == expected_ranges, (
        f"Action ranges differ: expected {expected_ranges}, got {ranges}"
    )
    minimum, maximum = world_bounds(meshes)
    dimensions = maximum - minimum
    assert 1.68 <= dimensions.z <= 1.72, (
        f"Rigged character height must be 1.70 m, got {dimensions.z:.6f}"
    )
    assert abs(minimum.z) <= 0.002, (
        f"Rigged character feet must sit on Z=0, got {minimum.z:.6f}"
    )
    triangles = triangle_count(meshes)
    assert triangles < 150_000, f"Rigged character exceeds 150000 triangles: {triangles}"
    weights = weight_metrics(meshes)
    assert weights["unweighted"] == 0, weights
    assert weights["denormalized"] == 0, weights
    assert weights["over_influenced"] == 0, weights
    assert weights["maximum_influences"] <= 4, weights

    oversized_images = {
        image.name: tuple(image.size)
        for image in bpy.data.images
        if image.size[0] > 1024 or image.size[1] > 1024
    }
    assert not oversized_images, f"Web textures exceed 1024: {oversized_images}"
    run = validate_run_cycle(
        rig,
        end_frame=expected_ranges["Run"][1],
        passing_samples=((5, "R"), (13, "L")) if rig_version >= 2 else ((4, "R"), (16, "L")),
        minimum_hand_travel=0.28 if rig_version >= 2 else 0.36,
    )
    return {
        "mode": mode,
        "meshes": len(meshes),
        "triangles": triangles,
        "bones": len(bones),
        "rig_version": rig_version,
        "actions": ranges,
        "dimensions": [round(value, 6) for value in dimensions],
        "minimum": [round(value, 6) for value in minimum],
        "weights": weights,
        "run": {key: round(value, 8) for key, value in run.items()},
        "images": {image.name: tuple(image.size) for image in bpy.data.images},
    }


def validate_source(path: Path) -> dict[str, object]:
    ensure_input(path)
    bpy.ops.wm.open_mainfile(filepath=str(path))
    assert RIGGED_COLLECTION in bpy.data.collections, (
        f"Rigged source is missing collection {RIGGED_COLLECTION}"
    )
    rig = bpy.data.objects.get("SANIC_Armature")
    assert rig is not None and rig.type == "ARMATURE"
    for obj in bpy.data.collections[RIGGED_COLLECTION].objects:
        if obj.type != "MESH":
            continue
        modifiers = [modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"]
        assert len(modifiers) == 1 and modifiers[0].object == rig, (
            f"{obj.name} must have one SANIC armature modifier"
        )
    return validate_common("source")


def validate_glb(path: Path) -> dict[str, object]:
    ensure_input(path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(path))
    assert result == {"FINISHED"}, result
    return validate_common("glb")


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 2, "Expected mode and asset path"
    mode = arguments[0]
    path = Path(arguments[1]).expanduser().resolve()
    if mode == "glb":
        report = validate_glb(path)
    elif mode == "source":
        report = validate_source(path)
    else:
        raise ValueError(f"Unknown SANIC rig validation mode: {mode}")
    print(f"SANIC_RIG_REPORT={json.dumps(report, sort_keys=True)}")
    print("SANIC_RIG_VALIDATION=PASS")


if __name__ == "__main__":
    main()
