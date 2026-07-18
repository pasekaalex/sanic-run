"""Validate the isolated Meshy-644-to-SANIC v4 retarget candidate.

Usage:
    blender --background --factory-startup --python-exit-code 1 \
      --python blender/scripts/validate_meshy_retarget_v4.py -- \
      SOURCE_BLEND CANDIDATE_BLEND CANDIDATE_GLB RAW_ANIMATION_GLB
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import bpy
from mathutils import Vector


ACTION_NAMES = ("Idle", "Run", "Jump", "Crash")
PRESERVED_ACTIONS = ("Idle", "Jump", "Crash")
EXPECTED_EXPORTED_ACTION_RANGES = {
    "Crash": (1, 36),
    "Idle": (1, 60),
    "Jump": (1, 30),
    "Run": (0, 16),
}
RUN_FRAMES = tuple(range(1, 18))
FLIGHT_FRAMES = (5, 13)
FORWARD = Vector((0.0, -1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
V4_ROOT = Path("/home/alex/Downloads/SANIC-Meshy-v4").resolve()


@dataclass(frozen=True)
class AssetSnapshot:
    bones: tuple[str, ...]
    meshes: tuple[str, ...]
    action_ranges: dict[str, tuple[int, int]]
    action_hashes: dict[str, str]
    action_values: dict[str, tuple[float, ...]]


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def require_file(path: Path, suffix: str | None = None) -> Path:
    resolved = path.expanduser().resolve()
    assert resolved.is_file(), f"Missing required asset: {resolved}"
    if suffix is not None:
        assert resolved.suffix.lower() == suffix, resolved
    return resolved


def one_rig() -> bpy.types.Object:
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(rigs) == 1, [obj.name for obj in rigs]
    return rigs[0]


def open_blend(path: Path) -> bpy.types.Object:
    result = bpy.ops.wm.open_mainfile(filepath=str(require_file(path, ".blend")))
    assert result == {"FINISHED"}, result
    return one_rig()


def import_glb(path: Path) -> bpy.types.Object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(require_file(path, ".glb")))
    assert result == {"FINISHED"}, result
    return one_rig()


def mute_nla(rig: bpy.types.Object) -> None:
    rig.animation_data_create()
    for track in rig.animation_data.nla_tracks:
        track.mute = True


def pose_values(rig: bpy.types.Object, action_name: str) -> tuple[float, ...]:
    action = bpy.data.actions.get(action_name)
    assert action is not None, action_name
    mute_nla(rig)
    rig.animation_data.action = action
    first = int(round(action.frame_range[0]))
    last = int(round(action.frame_range[1]))
    values: list[float] = []
    for frame in range(first, last + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        for bone in sorted(rig.pose.bones, key=lambda item: item.name):
            values.extend(value for row in bone.matrix_basis for value in row)
    rig.animation_data.action = None
    return tuple(values)


def encoded_hash(values: tuple[float, ...]) -> str:
    payload = json.dumps(values, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def snapshot(path: Path) -> AssetSnapshot:
    rig = open_blend(path)
    actions = {name: bpy.data.actions.get(name) for name in ACTION_NAMES}
    assert all(action is not None for action in actions.values()), {
        name: action is not None for name, action in actions.items()
    }
    action_ranges = {
        name: (
            int(round(action.frame_range[0])),
            int(round(action.frame_range[1])),
        )
        for name, action in actions.items()
        if action is not None
    }
    values = {
        name: pose_values(rig, name)
        for name in PRESERVED_ACTIONS
    }
    return AssetSnapshot(
        bones=tuple(sorted(rig.data.bones.keys())),
        meshes=tuple(
            sorted(obj.name for obj in bpy.context.scene.objects if obj.type == "MESH")
        ),
        action_ranges=action_ranges,
        action_hashes={name: encoded_hash(sample) for name, sample in values.items()},
        action_values=values,
    )


def compare_preserved_actions(
    source: AssetSnapshot,
    candidate: AssetSnapshot,
) -> dict[str, object]:
    assert source.bones == candidate.bones
    assert source.meshes == candidate.meshes
    report: dict[str, object] = {}
    for name in PRESERVED_ACTIONS:
        assert source.action_ranges[name] == candidate.action_ranges[name], name
        first = source.action_values[name]
        second = candidate.action_values[name]
        assert len(first) == len(second), (name, len(first), len(second))
        maximum_delta = max(abs(a - b) for a, b in zip(first, second))
        assert maximum_delta == 0.0, (name, maximum_delta)
        assert source.action_hashes[name] == candidate.action_hashes[name], name
        report[name] = {
            "samples": len(first),
            "sha256": source.action_hashes[name],
            "maximum_delta": maximum_delta,
        }
    assert candidate.action_ranges["Run"] == (1, 17)
    return report


def point(rig: bpy.types.Object, bone_name: str, endpoint: str = "head") -> Vector:
    bone = rig.pose.bones[bone_name]
    local = bone.head if endpoint == "head" else bone.tail
    return rig.matrix_world @ local


def joint_angle(first: Vector, joint: Vector, last: Vector) -> float:
    return math.degrees((first - joint).angle(last - joint))


def weighted_shoe_vertices() -> dict[str, dict[str, list[int]]]:
    result: dict[str, dict[str, list[int]]] = {"L": {}, "R": {}}
    for side in ("L", "R"):
        names = {f"foot.{side}", f"toe.{side}"}
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            indices = {
                group.index for group in obj.vertex_groups if group.name in names
            }
            selected = [
                vertex.index
                for vertex in obj.data.vertices
                if any(
                    membership.group in indices and membership.weight > 1e-4
                    for membership in vertex.groups
                )
            ]
            if selected:
                result[side][obj.name] = selected
        assert result[side], f"No weighted shoe vertices for {side}"
    return result


def shoe_minimum_z(
    partitions: dict[str, dict[str, list[int]]],
    side: str,
) -> float:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    minimum = float("inf")
    for object_name, indices in partitions[side].items():
        obj = bpy.data.objects[object_name]
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


def matrix_basis_values(rig: bpy.types.Object) -> tuple[float, ...]:
    return tuple(
        value
        for bone in sorted(rig.pose.bones, key=lambda item: item.name)
        for row in bone.matrix_basis
        for value in row
    )


def validate_candidate_run(path: Path) -> dict[str, object]:
    rig = open_blend(path)
    run = bpy.data.actions.get("Run")
    assert run is not None
    assert tuple(round(value) for value in run.frame_range) == (1, 17)
    mute_nla(rig)
    rig.animation_data.action = run
    partitions = weighted_shoe_vertices()
    samples: dict[int, dict[str, object]] = {}
    for frame in RUN_FRAMES:
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        root = point(rig, "root")
        torso = point(rig, "chest", "tail") - point(rig, "chest")
        lean = math.degrees(math.atan2(torso.dot(FORWARD), torso.dot(UP)))
        side_values: dict[str, object] = {}
        for side in ("L", "R"):
            shoulder_bone = rig.pose.bones[f"shoulder.{side}"]
            shoulder_direction = (
                point(rig, f"shoulder.{side}", "tail")
                - point(rig, f"shoulder.{side}")
            ).normalized()
            upper_arm_direction = (
                point(rig, f"upper_arm.{side}", "tail")
                - point(rig, f"upper_arm.{side}")
            ).normalized()
            shoulder = point(rig, f"upper_arm.{side}")
            elbow = point(rig, f"lower_arm.{side}")
            wrist = point(rig, f"hand.{side}")
            hip = point(rig, f"upper_leg.{side}")
            knee = point(rig, f"lower_leg.{side}")
            ankle = point(rig, f"foot.{side}")
            side_values[side] = {
                "elbow": joint_angle(shoulder, elbow, wrist),
                "knee_flex": 180.0 - joint_angle(hip, knee, ankle),
                "shoe_z": shoe_minimum_z(partitions, side),
                "hand_lateral": (wrist - root).x,
                "shoulder_basis": shoulder_bone.matrix_basis.to_quaternion().copy(),
                "shoulder_forward": shoulder_direction.dot(FORWARD),
                "upper_arm_forward": upper_arm_direction.dot(FORWARD),
            }
        samples[frame] = {
            "root": root,
            "lean": lean,
            "basis": matrix_basis_values(rig),
            **side_values,
        }
    rig.animation_data.action = None

    leans = [float(samples[frame]["lean"]) for frame in RUN_FRAMES]
    elbows = [
        float(samples[frame][side]["elbow"])
        for frame in RUN_FRAMES
        for side in ("L", "R")
    ]
    knees = [
        float(samples[frame][side]["knee_flex"])
        for frame in RUN_FRAMES
        for side in ("L", "R")
    ]
    roots = [samples[frame]["root"] for frame in RUN_FRAMES]
    shoes = {
        side: [float(samples[frame][side]["shoe_z"]) for frame in RUN_FRAMES]
        for side in ("L", "R")
    }
    hand_ranges = {
        side: max(float(samples[frame][side]["hand_lateral"]) for frame in RUN_FRAMES)
        - min(float(samples[frame][side]["hand_lateral"]) for frame in RUN_FRAMES)
        for side in ("L", "R")
    }
    shoulder_motion_ranges = {
        side: max(
            math.degrees(first.rotation_difference(second).angle)
            for first in (
                samples[frame][side]["shoulder_basis"] for frame in RUN_FRAMES
            )
            for second in (
                samples[frame][side]["shoulder_basis"] for frame in RUN_FRAMES
            )
        )
        for side in ("L", "R")
    }
    shoulder_forward_values = {
        side: [
            float(samples[frame][side]["shoulder_forward"])
            for frame in RUN_FRAMES
        ]
        for side in ("L", "R")
    }
    shoulder_forward_ranges = {
        side: max(values) - min(values)
        for side, values in shoulder_forward_values.items()
    }
    upper_arm_forward_values = {
        side: [
            float(samples[frame][side]["upper_arm_forward"])
            for frame in RUN_FRAMES
        ]
        for side in ("L", "R")
    }

    def correlation(first: list[float], second: list[float]) -> float:
        first_mean = sum(first) / len(first)
        second_mean = sum(second) / len(second)
        numerator = sum(
            (a - first_mean) * (b - second_mean)
            for a, b in zip(first, second)
        )
        denominator = math.sqrt(
            sum((value - first_mean) ** 2 for value in first)
            * sum((value - second_mean) ** 2 for value in second)
        )
        assert denominator > 1e-10, (first, second)
        return numerator / denominator

    shoulder_forward_correlation = correlation(
        shoulder_forward_values["L"],
        shoulder_forward_values["R"],
    )
    upper_arm_forward_correlation = correlation(
        upper_arm_forward_values["L"],
        upper_arm_forward_values["R"],
    )
    root_vertical_range = max(root.z for root in roots) - min(root.z for root in roots)
    maximum_adjacent_root_delta = max(
        abs(second.z - first.z) for first, second in zip(roots, roots[1:])
    )
    seam_error = max(
        abs(first - last)
        for first, last in zip(samples[1]["basis"], samples[17]["basis"])
    )

    assert min(leans) >= 11.0 and max(leans) <= 14.0, (min(leans), max(leans))
    assert min(elbows) >= 75.0 and max(elbows) <= 105.0, (
        min(elbows),
        max(elbows),
    )
    assert min(knees) >= 15.0, min(knees)
    assert max(root.x for root in roots) - min(root.x for root in roots) <= 1e-5
    assert max(root.y for root in roots) - min(root.y for root in roots) <= 1e-5
    assert root_vertical_range <= 0.08, root_vertical_range
    assert maximum_adjacent_root_delta <= 0.02, maximum_adjacent_root_delta
    assert min(minimum for values in shoes.values() for minimum in values) >= -0.003
    for side in ("L", "R"):
        assert min(shoes[side]) <= 0.006, (side, min(shoes[side]))
        assert hand_ranges[side] <= 0.08, (side, hand_ranges[side])
        assert 2.0 <= shoulder_motion_ranges[side] <= 15.0, (
            side,
            shoulder_motion_ranges[side],
        )
        assert 0.02 <= shoulder_forward_ranges[side] <= 0.20, (
            side,
            shoulder_forward_ranges[side],
        )
    assert shoulder_forward_correlation <= -0.65, shoulder_forward_correlation
    assert upper_arm_forward_correlation <= -0.50, upper_arm_forward_correlation
    for frame in FLIGHT_FRAMES:
        assert min(float(samples[frame][side]["shoe_z"]) for side in ("L", "R")) >= 0.02
    assert seam_error <= 1e-6, seam_error

    return {
        "blend_run_frame_range": [
            int(round(value)) for value in run.frame_range
        ],
        "torso_lean_degrees": [round(min(leans), 4), round(max(leans), 4)],
        "elbow_angle_degrees": [round(min(elbows), 4), round(max(elbows), 4)],
        "minimum_knee_flex_degrees": round(min(knees), 4),
        "root_horizontal_ranges": [
            round(max(root.x for root in roots) - min(root.x for root in roots), 8),
            round(max(root.y for root in roots) - min(root.y for root in roots), 8),
        ],
        "root_vertical_range": round(root_vertical_range, 5),
        "maximum_adjacent_root_delta": round(maximum_adjacent_root_delta, 5),
        "shoe_minimum_z": {
            side: round(min(values), 5) for side, values in shoes.items()
        },
        "flight_minimum_z": {
            str(frame): round(
                min(float(samples[frame][side]["shoe_z"]) for side in ("L", "R")),
                5,
            )
            for frame in FLIGHT_FRAMES
        },
        "hand_lateral_ranges": {
            side: round(value, 5) for side, value in hand_ranges.items()
        },
        "shoulder_motion_range_degrees": {
            side: round(value, 5)
            for side, value in shoulder_motion_ranges.items()
        },
        "shoulder_forward_ranges": {
            side: round(value, 5)
            for side, value in shoulder_forward_ranges.items()
        },
        "shoulder_forward_correlation": round(
            shoulder_forward_correlation,
            5,
        ),
        "upper_arm_forward_correlation": round(
            upper_arm_forward_correlation,
            5,
        ),
        "seam_error": seam_error,
    }


def validate_raw_animation(path: Path) -> dict[str, object]:
    rig = import_glb(path)
    actions = list(bpy.data.actions)
    assert len(actions) == 1, [action.name for action in actions]
    action = actions[0]
    start, end = action.frame_range
    duration = (end - start) / bpy.context.scene.render.fps
    left_x = (rig.matrix_world @ rig.data.bones["LeftArm"].head_local).x
    right_x = (rig.matrix_world @ rig.data.bones["RightArm"].head_local).x
    assert abs(duration - 0.6) <= 1e-5, duration
    assert left_x > 0.0 and right_x < 0.0, (left_x, right_x)
    return {
        "action": action.name,
        "frame_range": [start, end],
        "duration_seconds": duration,
        "left_arm_x": left_x,
        "right_arm_x": right_x,
    }


def validate_export(path: Path) -> dict[str, object]:
    rig = import_glb(path)
    del rig
    actions = {action.name: action for action in bpy.data.actions}
    assert set(actions) == set(ACTION_NAMES), sorted(actions)
    ranges = {
        name: tuple(int(round(value)) for value in action.frame_range)
        for name, action in actions.items()
    }
    assert ranges == EXPECTED_EXPORTED_ACTION_RANGES, ranges
    run_start, _ = actions["Run"].frame_range
    return {
        "actions": sorted(actions),
        "action_frame_ranges": {
            name: list(ranges[name]) for name in sorted(ranges)
        },
        "run_timestamp_start_seconds": (
            run_start / bpy.context.scene.render.fps
        ),
    }


def validate_collection_cleanup(path: Path) -> dict[str, object]:
    open_blend(path)
    imported = bpy.data.collections.get("glTF_not_exported")
    assert imported is None, {
        "collection": imported.name,
        "objects": [obj.name for obj in imported.objects],
    }
    return {"glTF_not_exported": "absent"}


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 4, (
        "Expected SOURCE_BLEND CANDIDATE_BLEND CANDIDATE_GLB RAW_ANIMATION_GLB"
    )
    source_path, candidate_path, glb_path, raw_path = (
        Path(argument) for argument in arguments
    )
    assert candidate_path.expanduser().resolve().is_relative_to(V4_ROOT)
    assert glb_path.expanduser().resolve().is_relative_to(V4_ROOT)
    source = snapshot(source_path)
    candidate = snapshot(candidate_path)
    report = {
        "preserved_actions": compare_preserved_actions(source, candidate),
        "candidate_run": validate_candidate_run(candidate_path),
        "raw_animation": validate_raw_animation(raw_path),
        "export": validate_export(glb_path),
        "collection_cleanup": validate_collection_cleanup(candidate_path),
    }
    print(
        "SANIC_MESHY_RETARGET_V4_VALIDATION=PASS",
        json.dumps(report, separators=(",", ":"), sort_keys=True),
    )


if __name__ == "__main__":
    main()
