"""Retarget Meshy's raw 644 sprint onto the authoritative SANIC armature.

The source animation is sampled as world-space joint direction deltas.  No
Meshy bone-local rotations, mesh, skin weights, or root travel are copied.

Usage:
    blender --background --factory-startup --python-exit-code 1 \
      --python blender/scripts/retarget_meshy_sprint_v4.py -- \
      SOURCE_BLEND RAW_ANIMATION_GLB OUTPUT_BLEND OUTPUT_GLB
"""

from __future__ import annotations

import json
import math
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import retarget_meshy_sprint_v4_spec as spec  # noqa: E402


AUTHORITATIVE_SOURCE = Path(
    "/home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend"
).resolve()
RAW_ANIMATION = Path(
    "/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/"
    "proxy-v1-sprint-644/animation.glb"
).resolve()
OUTPUT_ROOT = Path("/home/alex/Downloads/SANIC-Meshy-v4").resolve()
FORWARD = Vector((0.0, -1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
FLIGHT_HEIGHTS = {
    4: 0.010,
    5: 0.032,
    6: 0.010,
    12: 0.010,
    13: 0.032,
    14: 0.010,
}
GROUND_HEIGHT = 0.002
ROOT_BASE_OFFSET = -0.028
STANCE_SIDE_BY_FRAME = {
    1: "L",
    2: "L",
    3: "L",
    7: "R",
    8: "R",
    9: "R",
    10: "R",
    11: "R",
    15: "L",
    16: "L",
}


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def existing_path(argument: str, suffix: str) -> Path:
    path = Path(argument).expanduser().resolve()
    assert path.is_file(), f"Missing input: {path}"
    assert path.suffix.lower() == suffix, path
    return path


def safe_output_path(argument: str, suffix: str) -> Path:
    absolute = Path(os.path.abspath(Path(argument).expanduser()))
    resolved = absolute.resolve()
    assert absolute.is_relative_to(OUTPUT_ROOT), absolute
    assert resolved.is_relative_to(OUTPUT_ROOT), resolved
    assert resolved.suffix.lower() == suffix, resolved
    return resolved


def one_target_rig() -> bpy.types.Object:
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(rigs) == 1, [obj.name for obj in rigs]
    rig = rigs[0]
    required = set(spec.SOURCE_TO_TARGET_BONES.values()) | {
        "root",
        "toe.L",
        "toe.R",
    }
    missing = required - set(rig.data.bones.keys())
    assert not missing, sorted(missing)
    return rig


def snapshot_data_blocks() -> dict[str, set[object]]:
    return {
        "objects": set(bpy.data.objects),
        "collections": set(bpy.data.collections),
        "meshes": set(bpy.data.meshes),
        "armatures": set(bpy.data.armatures),
        "materials": set(bpy.data.materials),
        "images": set(bpy.data.images),
        "cameras": set(bpy.data.cameras),
        "lights": set(bpy.data.lights),
        "actions": set(bpy.data.actions),
    }


def mute_nla(rig: bpy.types.Object) -> None:
    rig.animation_data_create()
    for track in rig.animation_data.nla_tracks:
        track.mute = True


def source_head(
    rig: bpy.types.Object,
    name: str,
    *,
    rest: bool,
) -> Vector:
    if rest:
        return rig.matrix_world @ rig.data.bones[name].head_local
    return rig.matrix_world @ rig.pose.bones[name].head


def target_rest_direction(rig: bpy.types.Object, name: str) -> Vector:
    bone = rig.data.bones[name]
    return (
        rig.matrix_world.to_3x3() @ (bone.tail_local - bone.head_local)
    ).normalized()


def source_direction(
    rig: bpy.types.Object,
    start: str,
    end: str,
    *,
    rest: bool,
) -> Vector:
    return (
        source_head(rig, end, rest=rest)
        - source_head(rig, start, rest=rest)
    ).normalized()


def direction_from_world_rest_delta(
    source_rig: bpy.types.Object,
    target_rig: bpy.types.Object,
    target_name: str,
    source_start: str,
    source_end: str,
) -> Vector:
    rest_source = source_direction(
        source_rig,
        source_start,
        source_end,
        rest=True,
    )
    animated_source = source_direction(
        source_rig,
        source_start,
        source_end,
        rest=False,
    )
    world_delta = rest_source.rotation_difference(animated_source)
    return (world_delta @ target_rest_direction(target_rig, target_name)).normalized()


def damp_lateral(direction: Vector) -> Vector:
    return Vector(
        spec.damp_lateral_direction(tuple(direction))
    ).normalized()


def perpendicular_hint(direction: Vector, candidate: Vector) -> Vector:
    tangent = candidate - direction * candidate.dot(direction)
    if tangent.length <= 1e-7:
        for hint in (FORWARD, UP, Vector((1.0, 0.0, 0.0))):
            tangent = hint - direction * hint.dot(direction)
            if tangent.length > 1e-7:
                break
    assert tangent.length > 1e-7
    return tangent.normalized()


def clamp_elbow_directions(upper: Vector, lower: Vector) -> tuple[Vector, Vector]:
    upper = upper.normalized()
    lower = lower.normalized()
    reverse_upper = -upper
    angle = math.degrees(reverse_upper.angle(lower))
    # Keep a small numerical margin inside the public 75..105 degree contract.
    target = min(104.5, max(75.5, spec.clamp_elbow_angle_degrees(angle)))
    tangent = perpendicular_hint(reverse_upper, lower)
    radians = math.radians(target)
    guarded = reverse_upper * math.cos(radians) + tangent * math.sin(radians)
    return upper, guarded.normalized()


def guard_knee_directions(upper: Vector, lower: Vector) -> tuple[Vector, Vector]:
    upper = upper.normalized()
    lower = lower.normalized()
    flexion = math.degrees(upper.angle(lower))
    target = max(15.5, spec.ensure_knee_flex_degrees(flexion))
    if abs(target - flexion) <= 1e-6:
        return upper, lower
    tangent = perpendicular_hint(upper, lower)
    radians = math.radians(target)
    guarded = upper * math.cos(radians) + tangent * math.sin(radians)
    return upper, guarded.normalized()


def world_to_armature(rig: bpy.types.Object, direction: Vector) -> Vector:
    return (
        rig.matrix_world.inverted_safe().to_3x3() @ direction
    ).normalized()


def reset_pose(rig: bpy.types.Object) -> None:
    for bone in rig.pose.bones:
        bone.rotation_mode = "QUATERNION"
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def aim_bone_world(
    rig: bpy.types.Object,
    name: str,
    desired_world_direction: Vector,
) -> None:
    bone = rig.pose.bones[name]
    current = (bone.tail - bone.head).normalized()
    desired = world_to_armature(rig, desired_world_direction)
    swing = current.rotation_difference(desired)
    pivot = bone.head.copy()
    bone.matrix = (
        Matrix.Translation(pivot)
        @ swing.to_matrix().to_4x4()
        @ Matrix.Translation(-pivot)
        @ bone.matrix
    )
    bpy.context.view_layer.update()


def set_root_vertical_offset(rig: bpy.types.Object, offset: float) -> None:
    root = rig.pose.bones["root"]
    desired_world = rig.matrix_world @ rig.data.bones["root"].head_local
    desired_world.x = 0.0
    desired_world.y = 0.0
    desired_world.z += offset
    desired_armature = rig.matrix_world.inverted_safe() @ desired_world
    matrix = root.matrix.copy()
    matrix.translation = desired_armature
    root.matrix = matrix
    bpy.context.view_layer.update()


def torso_world_direction(source_rig: bpy.types.Object) -> tuple[Vector, float]:
    hips = source_head(source_rig, "Hips", rest=False)
    neck = source_head(source_rig, "neck", rest=False)
    source = (neck - hips).normalized()
    source_lean = math.degrees(math.atan2(source.dot(FORWARD), source.dot(UP)))
    target_lean = spec.target_torso_lean_degrees(source_lean)
    lean = math.radians(target_lean)
    direction = Vector(
        (
            source.x * spec.LATERAL_DIRECTION_DAMPING,
            -math.sin(lean),
            math.cos(lean),
        )
    ).normalized()
    return direction, target_lean


def retarget_directions(
    source_rig: bpy.types.Object,
    target_rig: bpy.types.Object,
) -> tuple[dict[str, Vector], float]:
    directions: dict[str, Vector] = {}
    torso, lean = torso_world_direction(source_rig)
    torso_lateral = torso.x
    for name, factor in (
        ("hips", 0.12),
        ("spine", 0.58),
        ("chest", 1.0),
        ("neck", 0.34),
        ("head", 0.16),
    ):
        angle = math.radians(lean * factor)
        directions[name] = Vector(
            (torso_lateral * factor, -math.sin(angle), math.cos(angle))
        ).normalized()

    for side, source_side in (("R", "Left"), ("L", "Right")):
        shoulder_source_start, shoulder_source_end = (
            spec.SHOULDER_DELTA_JOINTS[side]
        )
        shoulder_name = f"shoulder.{side}"
        raw_shoulder = direction_from_world_rest_delta(
            source_rig,
            target_rig,
            shoulder_name,
            shoulder_source_start,
            shoulder_source_end,
        )
        directions[shoulder_name] = target_rest_direction(
            target_rig,
            shoulder_name,
        ).lerp(
            raw_shoulder,
            spec.SHOULDER_RETARGET_DAMPING,
        ).normalized()

        upper_arm = damp_lateral(
            direction_from_world_rest_delta(
                source_rig,
                target_rig,
                f"upper_arm.{side}",
                f"{source_side}Arm",
                f"{source_side}ForeArm",
            )
        )
        lower_arm = damp_lateral(
            direction_from_world_rest_delta(
                source_rig,
                target_rig,
                f"lower_arm.{side}",
                f"{source_side}ForeArm",
                f"{source_side}Hand",
            )
        )
        upper_arm, lower_arm = clamp_elbow_directions(upper_arm, lower_arm)
        directions[f"upper_arm.{side}"] = upper_arm
        directions[f"lower_arm.{side}"] = lower_arm
        directions[f"hand.{side}"] = lower_arm

        upper_leg = damp_lateral(
            direction_from_world_rest_delta(
                source_rig,
                target_rig,
                f"upper_leg.{side}",
                f"{source_side}UpLeg",
                f"{source_side}Leg",
            )
        )
        lower_leg = damp_lateral(
            direction_from_world_rest_delta(
                source_rig,
                target_rig,
                f"lower_leg.{side}",
                f"{source_side}Leg",
                f"{source_side}Foot",
            )
        )
        upper_leg, lower_leg = guard_knee_directions(upper_leg, lower_leg)
        directions[f"upper_leg.{side}"] = upper_leg
        directions[f"lower_leg.{side}"] = lower_leg

        source_foot_start = f"{source_side}Foot"
        source_toe = f"{source_side}ToeBase"
        foot = direction_from_world_rest_delta(
            source_rig,
            target_rig,
            f"foot.{side}",
            source_foot_start,
            source_toe,
        )
        rest_source = source_direction(
            source_rig,
            source_foot_start,
            source_toe,
            rest=True,
        )
        animated_source = source_direction(
            source_rig,
            source_foot_start,
            source_toe,
            rest=False,
        )
        foot_delta = rest_source.rotation_difference(animated_source)
        toe = (
            foot_delta @ target_rest_direction(target_rig, f"toe.{side}")
        ).normalized()
        directions[f"foot.{side}"] = Vector(
            spec.guard_foot_direction(tuple(foot))
        )
        directions[f"toe.{side}"] = Vector(
            spec.guard_foot_direction(tuple(toe))
        )
    return directions, lean


def target_character_meshes(rig: bpy.types.Object) -> list[bpy.types.Object]:
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and any(
            modifier.type == "ARMATURE" and modifier.object == rig
            for modifier in obj.modifiers
        )
    ]
    assert meshes, "Target rig has no skinned character meshes"
    return meshes


def shoe_partitions(
    meshes: list[bpy.types.Object],
) -> dict[str, list[tuple[bpy.types.Object, list[int]]]]:
    result: dict[str, list[tuple[bpy.types.Object, list[int]]]] = {
        "L": [],
        "R": [],
    }
    for side in ("L", "R"):
        names = {f"foot.{side}", f"toe.{side}"}
        for obj in meshes:
            group_indices = {
                group.index for group in obj.vertex_groups if group.name in names
            }
            selected = [
                vertex.index
                for vertex in obj.data.vertices
                if any(
                    membership.group in group_indices and membership.weight > 1e-4
                    for membership in vertex.groups
                )
            ]
            if selected:
                result[side].append((obj, selected))
        assert result[side], f"Missing target shoe weights for {side}"
    return result


def shoe_minimum_z(
    partitions: dict[str, list[tuple[bpy.types.Object, list[int]]]],
    side: str,
) -> float:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    minimum = float("inf")
    for obj, indices in partitions[side]:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            minimum = min(
                minimum,
                *(
                    (evaluated.matrix_world @ mesh.vertices[index].co).z
                    for index in indices
                ),
            )
        finally:
            evaluated.to_mesh_clear()
    assert math.isfinite(minimum)
    return minimum


def solve_target_pose(
    source_rig: bpy.types.Object,
    target_rig: bpy.types.Object,
    root_bounce: float,
) -> tuple[float, dict[str, Vector]]:
    reset_pose(target_rig)
    set_root_vertical_offset(target_rig, root_bounce)
    directions, lean = retarget_directions(source_rig, target_rig)
    for name in ("hips", "spine", "chest", "neck", "head"):
        aim_bone_world(target_rig, name, directions[name])
    for side in ("L", "R"):
        for part in spec.ARM_RETARGET_ORDER:
            aim_bone_world(target_rig, f"{part}.{side}", directions[f"{part}.{side}"])
        for part in ("upper_leg", "lower_leg", "foot", "toe"):
            aim_bone_world(target_rig, f"{part}.{side}", directions[f"{part}.{side}"])
    return lean, directions


def solve_leg_to_shoe_height(
    rig: bpy.types.Object,
    directions: dict[str, Vector],
    partitions: dict[str, list[tuple[bpy.types.Object, list[int]]]],
    side: str,
    desired_shoe_z: float,
) -> None:
    """Move one sole vertically with IK while keeping the raw bend plane."""

    hip = rig.matrix_world @ rig.pose.bones[f"upper_leg.{side}"].head
    raw_knee = rig.matrix_world @ rig.pose.bones[f"lower_leg.{side}"].head
    raw_ankle = rig.matrix_world @ rig.pose.bones[f"foot.{side}"].head
    current_shoe_z = shoe_minimum_z(partitions, side)
    sole_from_ankle_z = current_shoe_z - raw_ankle.z
    desired_ankle_z = desired_shoe_z - sole_from_ankle_z

    upper_length = rig.data.bones[f"upper_leg.{side}"].length
    lower_length = rig.data.bones[f"lower_leg.{side}"].length
    minimum_flex = math.radians(15.5)
    maximum_reach = math.sqrt(
        upper_length * upper_length
        + lower_length * lower_length
        + 2.0 * upper_length * lower_length * math.cos(minimum_flex)
    )
    vertical = desired_ankle_z - hip.z
    assert abs(vertical) < maximum_reach, (
        side,
        hip.z,
        desired_ankle_z,
        maximum_reach,
    )
    horizontal = Vector(
        (raw_ankle.x - hip.x, raw_ankle.y - hip.y, 0.0)
    )
    maximum_horizontal = math.sqrt(
        max(0.0, maximum_reach * maximum_reach - vertical * vertical)
    )
    if horizontal.length > maximum_horizontal:
        horizontal.normalize()
        horizontal *= maximum_horizontal
    desired_ankle = Vector(
        (
            hip.x + horizontal.x,
            hip.y + horizontal.y,
            desired_ankle_z,
        )
    )

    hip_to_ankle = desired_ankle - hip
    distance = hip_to_ankle.length
    assert distance > 1e-6 and distance <= maximum_reach + 1e-6
    axis = hip_to_ankle.normalized()
    along = (
        upper_length * upper_length
        - lower_length * lower_length
        + distance * distance
    ) / (2.0 * distance)
    bend_height = math.sqrt(
        max(0.0, upper_length * upper_length - along * along)
    )
    bend_center = hip + axis * along
    bend_hint = raw_knee - bend_center
    bend_hint -= axis * bend_hint.dot(axis)
    if bend_hint.length <= 1e-7:
        bend_hint = FORWARD - axis * FORWARD.dot(axis)
    if bend_hint.length <= 1e-7:
        bend_hint = Vector((1.0, 0.0, 0.0)) - axis * axis.x
    bend_hint.normalize()
    desired_knee = bend_center + bend_hint * bend_height
    upper_direction = (desired_knee - hip).normalized()
    lower_direction = (desired_ankle - desired_knee).normalized()

    aim_bone_world(rig, f"upper_leg.{side}", upper_direction)
    aim_bone_world(rig, f"lower_leg.{side}", lower_direction)
    # Parent-chain corrections rotate the footwear; restore its guarded world
    # directions after solving the contact leg.
    aim_bone_world(rig, f"foot.{side}", directions[f"foot.{side}"])
    aim_bone_world(rig, f"toe.{side}", directions[f"toe.{side}"])
    solved_shoe_z = shoe_minimum_z(partitions, side)
    assert abs(solved_shoe_z - desired_shoe_z) <= 0.003, (
        side,
        desired_shoe_z,
        solved_shoe_z,
    )


def replace_run_action(rig: bpy.types.Object) -> bpy.types.Action:
    rig.animation_data_create()
    old_run = bpy.data.actions.get("Run")
    assert old_run is not None
    if rig.animation_data.action == old_run:
        rig.animation_data.action = None
    for track in list(rig.animation_data.nla_tracks):
        if track.name == "Run" or any(strip.action == old_run for strip in track.strips):
            rig.animation_data.nla_tracks.remove(track)
    bpy.data.actions.remove(old_run)
    run = bpy.data.actions.new("Run")
    run.use_fake_user = True
    run.use_frame_range = True
    run.frame_start = 1
    run.frame_end = 17
    run.use_cyclic = True
    rig.animation_data.action = run
    return run


def insert_pose_keys(
    rig: bpy.types.Object,
    frame: int,
    first_quaternions: dict[str, object],
    previous_quaternions: dict[str, object],
) -> None:
    for bone in rig.pose.bones:
        quaternion = bone.rotation_quaternion.copy().normalized()
        if frame == 17:
            quaternion = first_quaternions[bone.name].copy()
        elif frame > 1 and previous_quaternions[bone.name].dot(quaternion) < 0.0:
            quaternion.negate()
        bone.rotation_quaternion = quaternion
        if frame == 1:
            first_quaternions[bone.name] = quaternion.copy()
        previous_quaternions[bone.name] = quaternion.copy()
        bone.keyframe_insert(
            "rotation_quaternion",
            frame=frame,
            group=bone.name,
        )
    root = rig.pose.bones["root"]
    if frame == 17:
        root.location = first_quaternions["__root_location__"].copy()
    elif frame == 1:
        first_quaternions["__root_location__"] = root.location.copy()
    root.keyframe_insert("location", frame=frame, group="root")


def layered_fcurves(action: bpy.types.Action) -> list[bpy.types.FCurve]:
    result: list[bpy.types.FCurve] = []
    seen: set[int] = set()
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for curve in channelbag.fcurves:
                    pointer = curve.as_pointer()
                    if pointer not in seen:
                        seen.add(pointer)
                        result.append(curve)
    for curve in getattr(action, "fcurves", ()):
        pointer = curve.as_pointer()
        if pointer not in seen:
            seen.add(pointer)
            result.append(curve)
    return result


def build_run(
    source_rig: bpy.types.Object,
    target_rig: bpy.types.Object,
    action: bpy.types.Action,
    partitions: dict[str, list[tuple[bpy.types.Object, list[int]]]],
    source_samples: tuple[float, ...],
) -> dict[str, object]:
    del action
    hips_z: list[float] = []
    for source_frame in source_samples[:-1]:
        bpy.context.scene.frame_set(
            int(source_frame),
            subframe=source_frame - int(source_frame),
        )
        bpy.context.view_layer.update()
        hips_z.append(source_head(source_rig, "Hips", rest=False).z)
    hips_mean = sum(hips_z) / len(hips_z)

    first_basis: dict[str, Matrix] = {}
    first_quaternions: dict[str, object] = {}
    previous_quaternions: dict[str, object] = {}
    lean_samples: list[float] = []
    foot_samples: dict[int, dict[str, float]] = {}
    root_samples: dict[int, float] = {}

    for target_frame, source_frame in zip(spec.TARGET_FRAMES, source_samples):
        if target_frame == 17:
            for bone in target_rig.pose.bones:
                bone.matrix_basis = first_basis[bone.name].copy()
            bpy.context.view_layer.update()
            lean_samples.append(lean_samples[0])
            foot_samples[target_frame] = dict(foot_samples[1])
            root_samples[target_frame] = root_samples[1]
            insert_pose_keys(
                target_rig,
                target_frame,
                first_quaternions,
                previous_quaternions,
            )
            continue

        bpy.context.scene.frame_set(
            int(source_frame),
            subframe=source_frame - int(source_frame),
        )
        bpy.context.view_layer.update()
        source_hips_z = source_head(source_rig, "Hips", rest=False).z
        root_bounce = ROOT_BASE_OFFSET + (source_hips_z - hips_mean) * 0.25
        lean, directions = solve_target_pose(
            source_rig,
            target_rig,
            root_bounce,
        )
        stance_side = STANCE_SIDE_BY_FRAME.get(target_frame)
        if stance_side is not None:
            solve_leg_to_shoe_height(
                target_rig,
                directions,
                partitions,
                stance_side,
                GROUND_HEIGHT,
            )
        else:
            desired_minimum = FLIGHT_HEIGHTS[target_frame]
            for side in ("L", "R"):
                if shoe_minimum_z(partitions, side) < desired_minimum:
                    solve_leg_to_shoe_height(
                        target_rig,
                        directions,
                        partitions,
                        side,
                        desired_minimum,
                    )
        evaluated_minima = {
            side: shoe_minimum_z(partitions, side) for side in ("L", "R")
        }
        lean_samples.append(lean)
        foot_samples[target_frame] = evaluated_minima
        root_samples[target_frame] = (
            target_rig.matrix_world @ target_rig.pose.bones["root"].head
        ).z
        if target_frame == 1:
            first_basis = {
                bone.name: bone.matrix_basis.copy()
                for bone in target_rig.pose.bones
            }
        insert_pose_keys(
            target_rig,
            target_frame,
            first_quaternions,
            previous_quaternions,
        )

    for curve in layered_fcurves(bpy.data.actions["Run"]):
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"
    track = target_rig.animation_data.nla_tracks.new()
    track.name = "Run"
    track.strips.new("Run", 1, bpy.data.actions["Run"])
    track.mute = True
    target_rig.animation_data.action = None
    return {
        "source_samples": source_samples,
        "torso_lean_degrees": [
            min(lean_samples),
            max(lean_samples),
        ],
        "root_z_range": max(root_samples.values()) - min(root_samples.values()),
        "shoe_minima": foot_samples,
    }


def clean_imported_data(
    before: dict[str, set[object]],
    target_rig: bpy.types.Object,
    run_action: bpy.types.Action,
) -> None:
    target_rig.animation_data.action = None
    for obj in list(set(bpy.data.objects) - before["objects"]):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection_name in (
        "collections",
        "meshes",
        "armatures",
        "materials",
        "images",
        "cameras",
        "lights",
    ):
        collection = getattr(bpy.data, collection_name)
        for block in list(set(collection) - before[collection_name]):
            if (
                collection_name == "collections"
                and len(block.objects) == 0
                and len(block.children) == 0
            ):
                collection.remove(block, do_unlink=True)
            elif getattr(block, "users", 0) == 0:
                collection.remove(block)
    for action in list(set(bpy.data.actions) - before["actions"]):
        if action != run_action:
            bpy.data.actions.remove(action)


@contextmanager
def temporarily_shift_run_for_export(
    action: bpy.types.Action,
):
    """Shift only Run to frame zero and restore its authored data exactly."""

    assert action.name == "Run"
    assert action.use_frame_range
    original_range = (action.frame_start, action.frame_end)
    assert original_range == (1.0, 17.0), original_range
    offset = spec.RUN_EXPORT_FRAME_OFFSET
    points = [
        point
        for curve in layered_fcurves(action)
        for point in curve.keyframe_points
    ]
    assert points, "Run has no keyframes to export"
    snapshots = [
        (
            point,
            point.co.x,
            point.handle_left.x,
            point.handle_right.x,
        )
        for point in points
    ]
    try:
        for point, co_x, left_x, right_x in snapshots:
            point.co.x = co_x + offset
            point.handle_left.x = left_x + offset
            point.handle_right.x = right_x + offset
        action.frame_start = original_range[0] + offset
        action.frame_end = original_range[1] + offset
        assert tuple(action.frame_range) == (0.0, 16.0), action.frame_range
        yield
    finally:
        for point, co_x, left_x, right_x in snapshots:
            point.co.x = co_x
            point.handle_left.x = left_x
            point.handle_right.x = right_x
        action.frame_start, action.frame_end = original_range
        assert tuple(action.frame_range) == original_range, action.frame_range
        assert all(
            point.co.x == co_x
            and point.handle_left.x == left_x
            and point.handle_right.x == right_x
            for point, co_x, left_x, right_x in snapshots
        ), "Run keyframes were not restored exactly after export"


def export_candidate(
    target_rig: bpy.types.Object,
    meshes: list[bpy.types.Object],
    output_path: Path,
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.hide_set(False)
        obj.hide_render = False
        obj.select_set(True)
    target_rig.hide_set(False)
    target_rig.select_set(True)
    bpy.context.view_layer.objects.active = target_rig
    run = bpy.data.actions.get("Run")
    assert run is not None
    with temporarily_shift_run_for_export(run):
        result = bpy.ops.export_scene.gltf(
            filepath=str(output_path),
            export_format="GLB",
            use_selection=True,
            export_animations=True,
            export_animation_mode="ACTIONS",
            export_force_sampling=True,
            export_anim_slide_to_zero=False,
            export_optimize_animation_size=True,
            export_optimize_animation_keep_anim_armature=True,
            export_materials="EXPORT",
            export_tangents=True,
            export_yup=True,
            export_cameras=False,
            export_lights=False,
            export_extras=True,
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12,
        )
    assert result == {"FINISHED"}, result
    assert output_path.is_file(), output_path


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 4, (
        "Expected SOURCE_BLEND RAW_ANIMATION_GLB OUTPUT_BLEND OUTPUT_GLB"
    )
    source_path = existing_path(arguments[0], ".blend")
    raw_path = existing_path(arguments[1], ".glb")
    output_blend = safe_output_path(arguments[2], ".blend")
    output_glb = safe_output_path(arguments[3], ".glb")
    assert source_path == AUTHORITATIVE_SOURCE, source_path
    assert raw_path == RAW_ANIMATION, raw_path
    assert raw_path.name == "animation.glb", "Processed FBX input is forbidden"
    assert output_blend != source_path

    result = bpy.ops.wm.open_mainfile(filepath=str(source_path))
    assert result == {"FINISHED"}, result
    scene = bpy.context.scene
    scene.render.fps = spec.TARGET_FPS
    scene.render.fps_base = 1.0
    target_rig = one_target_rig()
    mute_nla(target_rig)
    meshes = target_character_meshes(target_rig)
    partitions = shoe_partitions(meshes)
    before_import = snapshot_data_blocks()

    result = bpy.ops.import_scene.gltf(filepath=str(raw_path))
    assert result == {"FINISHED"}, result
    source_rigs = [
        obj
        for obj in set(bpy.data.objects) - before_import["objects"]
        if obj.type == "ARMATURE"
    ]
    assert len(source_rigs) == 1, [obj.name for obj in source_rigs]
    source_rig = source_rigs[0]
    source_actions = list(set(bpy.data.actions) - before_import["actions"])
    assert len(source_actions) == 1, [action.name for action in source_actions]
    source_action = source_actions[0]
    source_rig.animation_data_create()
    mute_nla(source_rig)
    source_rig.animation_data.action = source_action
    source_start, source_end = source_action.frame_range
    source_duration = (source_end - source_start) / scene.render.fps
    assert abs(source_duration - spec.SOURCE_LOOP_SECONDS) <= 1e-5, source_duration
    source_samples = spec.resample_cycle_frames(source_start, source_end)

    run = replace_run_action(target_rig)
    report = build_run(
        source_rig,
        target_rig,
        run,
        partitions,
        source_samples,
    )
    clean_imported_data(before_import, target_rig, run)

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend), check_existing=False)
    export_candidate(target_rig, meshes, output_glb)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend), check_existing=False)
    print(
        "SANIC_MESHY_RETARGET_V4=PASS",
        json.dumps(
            {
                "source": str(source_path),
                "raw_animation": str(raw_path),
                "output_blend": str(output_blend),
                "output_glb": str(output_glb),
                "source_duration_seconds": source_duration,
                "run": report,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
