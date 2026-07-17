"""Validate the balanced SANIC v3 sprint against source or re-imported GLB.

Usage::

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_run_v3.py -- source /path/to/runner.blend

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_run_v3.py -- glb /path/to/runner.glb
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


FORWARD = Vector((0.0, -1.0, 0.0))
LATERAL = Vector((1.0, 0.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
ALL_RUN_FRAMES = tuple(range(1, 18))
STRIKE = ((1, "L"), (9, "R"))
LOAD = ((3, "L"), (11, "R"))
TOE_OFF = ((5, "L"), (13, "R"))
FLIGHT = (7, 15)
RECOVERY = ((5, "R", "L"), (13, "L", "R"))
FLIGHT_RECOVERY = ((7, "L"), (15, "R"))
V2_STRIDE_METERS = 0.504341721534729
MINIMUM_V3_STRIDE_METERS = V2_STRIDE_METERS * 1.35

MINIMUM_TORSO_LEAN_DEGREES = 11.0
MAXIMUM_TORSO_LEAN_DEGREES = 14.0
MINIMUM_ROOT_VERTICAL_RANGE = 0.035
MAXIMUM_ROOT_VERTICAL_RANGE = 0.050
MAXIMUM_ADJACENT_ROOT_DELTA = 0.018
MAXIMUM_SECOND_ROOT_DELTA = 0.020
MAXIMUM_ROOT_HORIZONTAL_RANGE_X = 0.001
MAXIMUM_ROOT_HORIZONTAL_RANGE_Y = 0.001
MINIMUM_KNEE_FLEXION = 15.0
MINIMUM_RECOVERY_KNEE_HEIGHT_DELTA = 0.120
MINIMUM_FLIGHT_RECOVERY_KNEE_FORWARD = 0.120
MAXIMUM_FLIGHT_RECOVERY_KNEE_FORWARD = 0.220
MINIMUM_FLIGHT_RECOVERY_ANKLE_BEHIND_KNEE = 0.180
MAXIMUM_FLIGHT_RECOVERY_ANKLE_BEHIND_KNEE = 0.225
MINIMUM_FLIGHT_RECOVERY_ANKLE_BELOW_KNEE = 0.050
MAXIMUM_FLIGHT_RECOVERY_ANKLE_BELOW_KNEE = 0.120
MINIMUM_FLIGHT_RECOVERY_KNEE_FLEXION = 80.0
MAXIMUM_FLIGHT_RECOVERY_KNEE_FLEXION = 115.0
MINIMUM_STANCE_PITCH_PROGRESSION = 22.0
MAXIMUM_STRIKE_FOREFOOT_Z = 0.006
MINIMUM_STRIKE_HEEL_Z = 0.015
MAXIMUM_STRIKE_HEEL_Z = 0.045
MAXIMUM_LOAD_CONTACT_REGION_Z = 0.008
MAXIMUM_TOE_OFF_FOREFOOT_Z = 0.008
MINIMUM_TOE_OFF_HEEL_Z = 0.060
MINIMUM_ALL_FRAME_SHOE_Z = -0.003
MINIMUM_FLIGHT_SHOE_Z = 0.025
MINIMUM_ELBOW_ANGLE = 75.0
MAXIMUM_ELBOW_ANGLE = 105.0
MINIMUM_ELBOW_ANGLE_RANGE = 18.0
MAXIMUM_ADJACENT_SHOULDER_DELTA = 20.0
MAXIMUM_IDENTICAL_SHOULDER_RUN = 1
IDENTICAL_SHOULDER_EPSILON_DEGREES = 0.05
MINIMUM_REAR_GLOVE_HEIGHT_SEPARATION = 0.120
MAXIMUM_HAND_ROOT_RELATIVE_LATERAL_RANGE = 0.050
MAXIMUM_FIRST_LAST_POSE_ERROR = 1e-4
MAXIMUM_SOURCE_GLB_STANCE_PITCH_DELTA = 0.25

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


@dataclass(frozen=True)
class WeightedVertex:
    object_name: str
    index: int
    rest_world: Vector


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def load(mode: str, path: Path) -> bpy.types.Object:
    if not path.is_file():
        raise FileNotFoundError(path)
    if mode == "source":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    elif mode == "glb":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        result = bpy.ops.import_scene.gltf(filepath=str(path))
        assert result == {"FINISHED"}, result
    else:
        raise ValueError(f"Unknown mode: {mode}")
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(rigs) == 1, f"Expected one armature, got {[obj.name for obj in rigs]}"
    rig = rigs[0]
    missing = EXPECTED_BONES - set(rig.data.bones.keys())
    assert not missing, f"Rig is missing bones: {sorted(missing)}"
    return rig


def point(rig: bpy.types.Object, bone_name: str, endpoint: str) -> Vector:
    bone = rig.pose.bones[bone_name]
    local = bone.head if endpoint == "head" else bone.tail
    return rig.matrix_world @ local


def joint_angle(first: Vector, joint: Vector, last: Vector) -> float:
    first_vector = first - joint
    last_vector = last - joint
    return math.degrees(first_vector.angle(last_vector))


def sagittal_torso_angle(direction: Vector) -> float:
    return math.degrees(math.atan2(direction.dot(FORWARD), direction.dot(UP)))


def sagittal_foot_pitch(direction: Vector) -> float:
    return math.degrees(math.atan2(direction.dot(UP), direction.dot(FORWARD)))


def partition_shoes() -> dict[str, dict[str, set[tuple[str, int]]]]:
    partitions: dict[str, dict[str, set[tuple[str, int]]]] = {}
    for side in ("L", "R"):
        group_names = {f"foot.{side}", f"toe.{side}"}
        weighted_vertices: list[WeightedVertex] = []
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            group_indices = {
                group.index
                for group in obj.vertex_groups
                if group.name in group_names
            }
            if not group_indices:
                continue
            for vertex in obj.data.vertices:
                if any(
                    membership.group in group_indices
                    and membership.weight > 1e-4
                    for membership in vertex.groups
                ):
                    weighted_vertices.append(
                        WeightedVertex(
                            object_name=obj.name,
                            index=vertex.index,
                            rest_world=obj.matrix_world @ vertex.co,
                        )
                    )
        assert weighted_vertices, f"Missing weighted shoe vertices for {side}"
        ordered = sorted(
            weighted_vertices,
            key=lambda item: item.rest_world.dot(FORWARD),
        )
        quarter = max(1, len(ordered) // 4)
        heel_vertices = {
            (item.object_name, item.index) for item in ordered[:quarter]
        }
        forefoot_vertices = {
            (item.object_name, item.index) for item in ordered[-quarter:]
        }
        shoe_vertices = {
            (item.object_name, item.index) for item in ordered
        }
        assert heel_vertices, f"Missing weighted heel vertices for {side}"
        assert forefoot_vertices, f"Missing weighted forefoot vertices for {side}"
        assert shoe_vertices, f"Missing weighted whole-shoe vertices for {side}"
        partitions[side] = {
            "heel": heel_vertices,
            "forefoot": forefoot_vertices,
            "shoe": shoe_vertices,
        }
    return partitions


def evaluated_region_minima(
    depsgraph: bpy.types.Depsgraph,
    partitions: dict[str, dict[str, set[tuple[str, int]]]],
) -> dict[str, dict[str, float]]:
    minima = {
        side: {region: float("inf") for region in ("heel", "forefoot", "shoe")}
        for side in ("L", "R")
    }
    keys_by_object: dict[str, set[int]] = {}
    for side_regions in partitions.values():
        for keys in side_regions.values():
            for object_name, index in keys:
                keys_by_object.setdefault(object_name, set()).add(index)

    objects = {obj.name: obj for obj in bpy.context.scene.objects if obj.type == "MESH"}
    evaluated_heights: dict[tuple[str, int], float] = {}
    for object_name, indices in keys_by_object.items():
        obj = objects.get(object_name)
        assert obj is not None, f"Missing weighted mesh object {object_name}"
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            for index in indices:
                assert index < len(mesh.vertices), (
                    object_name,
                    index,
                    len(mesh.vertices),
                )
                evaluated_heights[(object_name, index)] = (
                    evaluated.matrix_world @ mesh.vertices[index].co
                ).z
        finally:
            evaluated.to_mesh_clear()

    for side, side_regions in partitions.items():
        for region, keys in side_regions.items():
            heights = [evaluated_heights[key] for key in keys]
            assert heights, f"Missing evaluated {region} vertices for {side}"
            minima[side][region] = min(heights)
            assert math.isfinite(minima[side][region]), (
                side,
                region,
                minima[side][region],
            )
    return minima


def matrix_basis_values(rig: bpy.types.Object) -> list[float]:
    return [
        component
        for bone in sorted(rig.pose.bones, key=lambda item: item.name)
        for row in bone.matrix_basis
        for component in row
    ]


def sample(
    rig: bpy.types.Object,
    partitions: dict[str, dict[str, set[tuple[str, int]]]],
    frame: int,
) -> dict[str, object]:
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_rig = rig.evaluated_get(depsgraph)
    root = point(evaluated_rig, "root", "head")
    hips = point(evaluated_rig, "hips", "head")
    chest = point(evaluated_rig, "chest", "tail")
    region_minima = evaluated_region_minima(depsgraph, partitions)
    result: dict[str, object] = {
        "root": root,
        "torso_lean": sagittal_torso_angle(chest - hips),
        "basis": matrix_basis_values(evaluated_rig),
    }
    for side in ("L", "R"):
        shoulder = point(evaluated_rig, f"upper_arm.{side}", "head")
        elbow = point(evaluated_rig, f"lower_arm.{side}", "head")
        hand = point(evaluated_rig, f"hand.{side}", "head")
        hip = point(evaluated_rig, f"upper_leg.{side}", "head")
        knee = point(evaluated_rig, f"lower_leg.{side}", "head")
        ankle = point(evaluated_rig, f"foot.{side}", "head")
        foot_end = point(evaluated_rig, f"foot.{side}", "tail")
        toe = point(evaluated_rig, f"toe.{side}", "tail")
        upper_arm_direction = (elbow - shoulder).normalized()
        result[side] = {
            "shoe_z": region_minima[side]["shoe"],
            "heel_z": region_minima[side]["heel"],
            "forefoot_z": region_minima[side]["forefoot"],
            "foot_pitch": sagittal_foot_pitch(foot_end - ankle),
            "toe": toe,
            "hip": hip,
            "knee": knee,
            "ankle": ankle,
            "knee_flexion": 180.0 - joint_angle(hip, knee, ankle),
            "shoulder": shoulder,
            "elbow": elbow,
            "hand": hand,
            "elbow_angle": joint_angle(shoulder, elbow, hand),
            "upper_arm_direction": upper_arm_direction,
        }
    return result


def rounded(value: float) -> float:
    return round(float(value), 8)


def rounded_vector(value: Vector) -> list[float]:
    return [rounded(component) for component in value]


def maximum_identical_run(changes: list[float]) -> int:
    longest = 0
    current = 0
    for change in changes:
        if change < IDENTICAL_SHOULDER_EPSILON_DEGREES:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def validate(rig: bpy.types.Object) -> tuple[dict[str, object], list[dict[str, object]]]:
    run = bpy.data.actions.get("Run")
    jump = bpy.data.actions.get("Jump")
    assert run is not None, "Missing Run action"
    assert jump is not None, "Missing Jump action"
    assert tuple(round(value) for value in run.frame_range) == (1, 17), run.frame_range[:]
    assert tuple(round(value) for value in jump.frame_range) == (1, 30), jump.frame_range[:]

    partitions = partition_shoes()
    rig.animation_data_create()
    rig.animation_data.action = run
    samples = {
        frame: sample(rig, partitions, frame)
        for frame in ALL_RUN_FRAMES
    }

    roots = [samples[frame]["root"] for frame in ALL_RUN_FRAMES]
    root_z = [root.z for root in roots]
    adjacent_root_deltas = [
        abs(root_z[index] - root_z[index - 1])
        for index in range(1, len(root_z))
    ]
    second_root_deltas = [
        abs(root_z[index + 1] - 2.0 * root_z[index] + root_z[index - 1])
        for index in range(1, len(root_z) - 1)
    ]
    torso_leans = [samples[frame]["torso_lean"] for frame in ALL_RUN_FRAMES]
    knee_flexions = [
        samples[frame][side]["knee_flexion"]
        for frame in ALL_RUN_FRAMES
        for side in ("L", "R")
    ]
    recovery_deltas = {
        f"{frame}:{recovery}": (
            samples[frame][recovery]["knee"].z
            - samples[frame][support]["knee"].z
        )
        for frame, recovery, support in RECOVERY
    }
    flight_recovery_chain = {
        f"{frame}:{side}": {
            "knee_forward_of_hip": (
                samples[frame][side]["knee"]
                - samples[frame][side]["hip"]
            ).dot(FORWARD),
            "ankle_behind_knee": (
                samples[frame][side]["knee"]
                - samples[frame][side]["ankle"]
            ).dot(FORWARD),
            "ankle_below_knee": (
                samples[frame][side]["knee"]
                - samples[frame][side]["ankle"]
            ).dot(UP),
            "knee_flexion": samples[frame][side]["knee_flexion"],
        }
        for frame, side in FLIGHT_RECOVERY
    }
    stance_pitch_progression = {
        side: max(samples[frame][side]["foot_pitch"] for frame in frames)
        - min(samples[frame][side]["foot_pitch"] for frame in frames)
        for side, frames in {
            "L": (STRIKE[0][0], LOAD[0][0], TOE_OFF[0][0]),
            "R": (STRIKE[1][0], LOAD[1][0], TOE_OFF[1][0]),
        }.items()
    }
    strike_forefoot = [
        samples[frame][side]["forefoot_z"] for frame, side in STRIKE
    ]
    strike_heel = [samples[frame][side]["heel_z"] for frame, side in STRIKE]
    load_contact_regions = {
        f"{frame}:{side}": {
            "heel_z": samples[frame][side]["heel_z"],
            "forefoot_z": samples[frame][side]["forefoot_z"],
        }
        for frame, side in LOAD
    }
    load_contact_region_maxima = [
        max(regions.values()) for regions in load_contact_regions.values()
    ]
    toe_off_forefoot = [
        samples[frame][side]["forefoot_z"] for frame, side in TOE_OFF
    ]
    toe_off_heel = [samples[frame][side]["heel_z"] for frame, side in TOE_OFF]
    toe_separations = [
        abs(
            (
                samples[frame]["L"]["toe"]
                - samples[frame]["R"]["toe"]
            ).dot(FORWARD)
        )
        for frame in ALL_RUN_FRAMES
    ]
    flight_shoe = [
        samples[frame][side]["shoe_z"]
        for frame in FLIGHT
        for side in ("L", "R")
    ]
    all_frame_shoe_minima = {
        str(frame): {
            side: samples[frame][side]["shoe_z"]
            for side in ("L", "R")
        }
        for frame in ALL_RUN_FRAMES
    }
    elbow_angles = {
        side: [
            samples[frame][side]["elbow_angle"]
            for frame in ALL_RUN_FRAMES
        ]
        for side in ("L", "R")
    }
    elbow_ranges = {
        side: max(values) - min(values)
        for side, values in elbow_angles.items()
    }
    shoulder_changes = {
        side: [
            math.degrees(
                samples[frame - 1][side]["upper_arm_direction"].angle(
                    samples[frame][side]["upper_arm_direction"]
                )
            )
            for frame in ALL_RUN_FRAMES[1:]
        ]
        for side in ("L", "R")
    }
    identical_shoulder_runs = {
        side: maximum_identical_run(changes)
        for side, changes in shoulder_changes.items()
    }
    glove_height_separations = [
        abs(samples[frame]["L"]["hand"].z - samples[frame]["R"]["hand"].z)
        for frame in ALL_RUN_FRAMES
    ]
    hand_lateral_ranges = {}
    for side in ("L", "R"):
        positions = [
            (
                samples[frame][side]["hand"] - samples[frame]["root"]
            ).dot(LATERAL)
            for frame in ALL_RUN_FRAMES
        ]
        hand_lateral_ranges[side] = max(positions) - min(positions)
    first_basis = samples[ALL_RUN_FRAMES[0]]["basis"]
    last_basis = samples[ALL_RUN_FRAMES[-1]]["basis"]
    assert len(first_basis) == len(last_basis)
    first_last_pose_error = max(
        abs(first - last) for first, last in zip(first_basis, last_basis)
    )

    metrics: dict[str, object] = {
        "torso_lean_degrees": {
            "minimum": rounded(min(torso_leans)),
            "maximum": rounded(max(torso_leans)),
        },
        "root_vertical_range": rounded(max(root_z) - min(root_z)),
        "max_adjacent_root_delta": rounded(max(adjacent_root_deltas)),
        "max_second_root_delta": rounded(max(second_root_deltas)),
        "root_horizontal_range_x": rounded(
            max(root.x for root in roots) - min(root.x for root in roots)
        ),
        "root_horizontal_range_y": rounded(
            max(root.y for root in roots) - min(root.y for root in roots)
        ),
        "minimum_knee_flexion": rounded(min(knee_flexions)),
        "recovery_knee_height_delta": {
            "minimum": rounded(min(recovery_deltas.values())),
            "samples": {
                key: rounded(value) for key, value in recovery_deltas.items()
            },
        },
        "flight_recovery_chain": {
            "samples": {
                key: {
                    metric: rounded(value)
                    for metric, value in values.items()
                }
                for key, values in flight_recovery_chain.items()
            },
        },
        "stance_pitch_progression": {
            "minimum": rounded(min(stance_pitch_progression.values())),
            "sides": {
                side: rounded(value)
                for side, value in stance_pitch_progression.items()
            },
        },
        "strike_forefoot_z": {"maximum": rounded(max(strike_forefoot))},
        "strike_heel_z": {
            "minimum": rounded(min(strike_heel)),
            "maximum": rounded(max(strike_heel)),
        },
        "load_contact_region_z": {
            "maximum": rounded(max(load_contact_region_maxima)),
            "samples": {
                key: {
                    region: rounded(value)
                    for region, value in regions.items()
                }
                for key, regions in load_contact_regions.items()
            },
        },
        "toe_off_forefoot_z": {"maximum": rounded(max(toe_off_forefoot))},
        "toe_off_heel_z": {"minimum": rounded(min(toe_off_heel))},
        "maximum_toe_separation": rounded(max(toe_separations)),
        "all_frame_shoe_z": {
            "minimum": rounded(
                min(
                    value
                    for sides in all_frame_shoe_minima.values()
                    for value in sides.values()
                )
            ),
            "samples": {
                frame: {
                    side: rounded(value)
                    for side, value in sides.items()
                }
                for frame, sides in all_frame_shoe_minima.items()
            },
        },
        "minimum_flight_shoe_z": rounded(min(flight_shoe)),
        "elbow_angle": {
            "minimum": rounded(
                min(min(values) for values in elbow_angles.values())
            ),
            "maximum": rounded(
                max(max(values) for values in elbow_angles.values())
            ),
        },
        "elbow_angle_range": {
            "minimum": rounded(min(elbow_ranges.values())),
            "sides": {
                side: rounded(value) for side, value in elbow_ranges.items()
            },
        },
        "maximum_adjacent_shoulder_delta": {
            "maximum": rounded(
                max(max(changes) for changes in shoulder_changes.values())
            ),
            "sides": {
                side: rounded(max(changes))
                for side, changes in shoulder_changes.items()
            },
        },
        "maximum_identical_shoulder_run": {
            "maximum": max(identical_shoulder_runs.values()),
            "sides": identical_shoulder_runs,
        },
        "rear_glove_height_separation": rounded(
            max(glove_height_separations)
        ),
        "hand_root_relative_lateral_range": {
            "maximum": rounded(max(hand_lateral_ranges.values())),
            "sides": {
                side: rounded(value)
                for side, value in hand_lateral_ranges.items()
            },
        },
        "first_last_pose_error": rounded(first_last_pose_error),
    }

    frame_report = {
        str(frame): {
            "root": rounded_vector(samples[frame]["root"]),
            "torso_lean": rounded(samples[frame]["torso_lean"]),
            **{
                side: {
                    "shoe_z": rounded(samples[frame][side]["shoe_z"]),
                    "heel_z": rounded(samples[frame][side]["heel_z"]),
                    "forefoot_z": rounded(samples[frame][side]["forefoot_z"]),
                    "foot_pitch": rounded(samples[frame][side]["foot_pitch"]),
                    "toe": rounded_vector(samples[frame][side]["toe"]),
                    "hip": rounded_vector(samples[frame][side]["hip"]),
                    "knee": rounded_vector(samples[frame][side]["knee"]),
                    "ankle": rounded_vector(samples[frame][side]["ankle"]),
                    "knee_flexion": rounded(
                        samples[frame][side]["knee_flexion"]
                    ),
                    "elbow_angle": rounded(
                        samples[frame][side]["elbow_angle"]
                    ),
                }
                for side in ("L", "R")
            },
        }
        for frame in ALL_RUN_FRAMES
    }

    problems: list[dict[str, object]] = []

    def check(
        name: str,
        condition: bool,
        actual: object,
        expected: str,
    ) -> None:
        if not condition:
            problems.append(
                {"metric": name, "actual": actual, "expected": expected}
            )

    check(
        "torso_lean_degrees",
        min(torso_leans) >= MINIMUM_TORSO_LEAN_DEGREES
        and max(torso_leans) <= MAXIMUM_TORSO_LEAN_DEGREES,
        metrics["torso_lean_degrees"],
        f"{MINIMUM_TORSO_LEAN_DEGREES}..{MAXIMUM_TORSO_LEAN_DEGREES}",
    )
    root_vertical_range = max(root_z) - min(root_z)
    check(
        "root_vertical_range",
        MINIMUM_ROOT_VERTICAL_RANGE
        <= root_vertical_range
        <= MAXIMUM_ROOT_VERTICAL_RANGE,
        metrics["root_vertical_range"],
        f"{MINIMUM_ROOT_VERTICAL_RANGE}..{MAXIMUM_ROOT_VERTICAL_RANGE}",
    )
    check(
        "max_adjacent_root_delta",
        max(adjacent_root_deltas) <= MAXIMUM_ADJACENT_ROOT_DELTA,
        metrics["max_adjacent_root_delta"],
        f"<= {MAXIMUM_ADJACENT_ROOT_DELTA}",
    )
    check(
        "max_second_root_delta",
        max(second_root_deltas) <= MAXIMUM_SECOND_ROOT_DELTA,
        metrics["max_second_root_delta"],
        f"<= {MAXIMUM_SECOND_ROOT_DELTA}",
    )
    root_horizontal_range_x = (
        max(root.x for root in roots) - min(root.x for root in roots)
    )
    check(
        "root_horizontal_range_x",
        root_horizontal_range_x <= MAXIMUM_ROOT_HORIZONTAL_RANGE_X,
        metrics["root_horizontal_range_x"],
        f"<= {MAXIMUM_ROOT_HORIZONTAL_RANGE_X}",
    )
    root_horizontal_range_y = (
        max(root.y for root in roots) - min(root.y for root in roots)
    )
    check(
        "root_horizontal_range_y",
        root_horizontal_range_y <= MAXIMUM_ROOT_HORIZONTAL_RANGE_Y,
        metrics["root_horizontal_range_y"],
        f"<= {MAXIMUM_ROOT_HORIZONTAL_RANGE_Y}",
    )
    check(
        "minimum_knee_flexion",
        min(knee_flexions) >= MINIMUM_KNEE_FLEXION,
        metrics["minimum_knee_flexion"],
        f">= {MINIMUM_KNEE_FLEXION}",
    )
    check(
        "recovery_knee_height_delta",
        min(recovery_deltas.values())
        >= MINIMUM_RECOVERY_KNEE_HEIGHT_DELTA,
        metrics["recovery_knee_height_delta"],
        f">= {MINIMUM_RECOVERY_KNEE_HEIGHT_DELTA}",
    )
    flight_recovery_knee_forward = [
        values["knee_forward_of_hip"]
        for values in flight_recovery_chain.values()
    ]
    flight_recovery_ankle_behind = [
        values["ankle_behind_knee"]
        for values in flight_recovery_chain.values()
    ]
    flight_recovery_ankle_below = [
        values["ankle_below_knee"]
        for values in flight_recovery_chain.values()
    ]
    flight_recovery_knee_flexion = [
        values["knee_flexion"] for values in flight_recovery_chain.values()
    ]
    check(
        "flight_recovery_chain",
        all(
            MINIMUM_FLIGHT_RECOVERY_KNEE_FORWARD
            <= value
            <= MAXIMUM_FLIGHT_RECOVERY_KNEE_FORWARD
            for value in flight_recovery_knee_forward
        )
        and all(
            MINIMUM_FLIGHT_RECOVERY_ANKLE_BEHIND_KNEE
            <= value
            <= MAXIMUM_FLIGHT_RECOVERY_ANKLE_BEHIND_KNEE
            for value in flight_recovery_ankle_behind
        )
        and all(
            MINIMUM_FLIGHT_RECOVERY_ANKLE_BELOW_KNEE
            <= value
            <= MAXIMUM_FLIGHT_RECOVERY_ANKLE_BELOW_KNEE
            for value in flight_recovery_ankle_below
        )
        and all(
            MINIMUM_FLIGHT_RECOVERY_KNEE_FLEXION
            <= value
            <= MAXIMUM_FLIGHT_RECOVERY_KNEE_FLEXION
            for value in flight_recovery_knee_flexion
        ),
        metrics["flight_recovery_chain"],
        (
            "knee_forward_of_hip "
            f"{MINIMUM_FLIGHT_RECOVERY_KNEE_FORWARD}"
            f"..{MAXIMUM_FLIGHT_RECOVERY_KNEE_FORWARD}; "
            "ankle_behind_knee "
            f"{MINIMUM_FLIGHT_RECOVERY_ANKLE_BEHIND_KNEE}"
            f"..{MAXIMUM_FLIGHT_RECOVERY_ANKLE_BEHIND_KNEE}; "
            "ankle_below_knee "
            f"{MINIMUM_FLIGHT_RECOVERY_ANKLE_BELOW_KNEE}"
            f"..{MAXIMUM_FLIGHT_RECOVERY_ANKLE_BELOW_KNEE}; "
            "knee_flexion "
            f"{MINIMUM_FLIGHT_RECOVERY_KNEE_FLEXION}"
            f"..{MAXIMUM_FLIGHT_RECOVERY_KNEE_FLEXION}"
        ),
    )
    check(
        "stance_pitch_progression",
        min(stance_pitch_progression.values())
        >= MINIMUM_STANCE_PITCH_PROGRESSION,
        metrics["stance_pitch_progression"],
        f">= {MINIMUM_STANCE_PITCH_PROGRESSION}",
    )
    check(
        "strike_forefoot_z",
        max(strike_forefoot) <= MAXIMUM_STRIKE_FOREFOOT_Z,
        metrics["strike_forefoot_z"],
        f"<= {MAXIMUM_STRIKE_FOREFOOT_Z}",
    )
    check(
        "strike_heel_z",
        min(strike_heel) >= MINIMUM_STRIKE_HEEL_Z
        and max(strike_heel) <= MAXIMUM_STRIKE_HEEL_Z,
        metrics["strike_heel_z"],
        f"{MINIMUM_STRIKE_HEEL_Z}..{MAXIMUM_STRIKE_HEEL_Z}",
    )
    check(
        "load_contact_region_z",
        max(load_contact_region_maxima) <= MAXIMUM_LOAD_CONTACT_REGION_Z,
        metrics["load_contact_region_z"],
        f"<= {MAXIMUM_LOAD_CONTACT_REGION_Z}",
    )
    check(
        "toe_off_forefoot_z",
        max(toe_off_forefoot) <= MAXIMUM_TOE_OFF_FOREFOOT_Z,
        metrics["toe_off_forefoot_z"],
        f"<= {MAXIMUM_TOE_OFF_FOREFOOT_Z}",
    )
    check(
        "toe_off_heel_z",
        min(toe_off_heel) >= MINIMUM_TOE_OFF_HEEL_Z,
        metrics["toe_off_heel_z"],
        f">= {MINIMUM_TOE_OFF_HEEL_Z}",
    )
    check(
        "maximum_toe_separation",
        max(toe_separations) >= MINIMUM_V3_STRIDE_METERS,
        metrics["maximum_toe_separation"],
        f">= {MINIMUM_V3_STRIDE_METERS}",
    )
    minimum_all_frame_shoe_z = min(
        value
        for sides in all_frame_shoe_minima.values()
        for value in sides.values()
    )
    check(
        "all_frame_shoe_z",
        minimum_all_frame_shoe_z >= MINIMUM_ALL_FRAME_SHOE_Z,
        metrics["all_frame_shoe_z"],
        f">= {MINIMUM_ALL_FRAME_SHOE_Z}",
    )
    check(
        "minimum_flight_shoe_z",
        min(flight_shoe) >= MINIMUM_FLIGHT_SHOE_Z,
        metrics["minimum_flight_shoe_z"],
        f">= {MINIMUM_FLIGHT_SHOE_Z}",
    )
    minimum_elbow_angle = min(
        min(values) for values in elbow_angles.values()
    )
    maximum_elbow_angle = max(
        max(values) for values in elbow_angles.values()
    )
    check(
        "elbow_angle",
        minimum_elbow_angle >= MINIMUM_ELBOW_ANGLE
        and maximum_elbow_angle <= MAXIMUM_ELBOW_ANGLE,
        metrics["elbow_angle"],
        f"{MINIMUM_ELBOW_ANGLE}..{MAXIMUM_ELBOW_ANGLE}",
    )
    check(
        "elbow_angle_range",
        min(elbow_ranges.values()) >= MINIMUM_ELBOW_ANGLE_RANGE,
        metrics["elbow_angle_range"],
        f">= {MINIMUM_ELBOW_ANGLE_RANGE}",
    )
    maximum_shoulder_delta = max(
        max(changes) for changes in shoulder_changes.values()
    )
    check(
        "maximum_adjacent_shoulder_delta",
        maximum_shoulder_delta <= MAXIMUM_ADJACENT_SHOULDER_DELTA,
        metrics["maximum_adjacent_shoulder_delta"],
        f"<= {MAXIMUM_ADJACENT_SHOULDER_DELTA}",
    )
    maximum_shoulder_run = max(identical_shoulder_runs.values())
    check(
        "maximum_identical_shoulder_run",
        maximum_shoulder_run <= MAXIMUM_IDENTICAL_SHOULDER_RUN,
        metrics["maximum_identical_shoulder_run"],
        f"<= {MAXIMUM_IDENTICAL_SHOULDER_RUN}",
    )
    check(
        "rear_glove_height_separation",
        max(glove_height_separations)
        >= MINIMUM_REAR_GLOVE_HEIGHT_SEPARATION,
        metrics["rear_glove_height_separation"],
        f">= {MINIMUM_REAR_GLOVE_HEIGHT_SEPARATION}",
    )
    check(
        "hand_root_relative_lateral_range",
        max(hand_lateral_ranges.values())
        <= MAXIMUM_HAND_ROOT_RELATIVE_LATERAL_RANGE,
        metrics["hand_root_relative_lateral_range"],
        f"<= {MAXIMUM_HAND_ROOT_RELATIVE_LATERAL_RANGE}",
    )
    check(
        "first_last_pose_error",
        first_last_pose_error <= MAXIMUM_FIRST_LAST_POSE_ERROR,
        metrics["first_last_pose_error"],
        f"<= {MAXIMUM_FIRST_LAST_POSE_ERROR}",
    )

    return {
        "run_range": [round(value) for value in run.frame_range],
        "jump_range": [round(value) for value in jump.frame_range],
        "metrics": metrics,
        "frames": frame_report,
    }, problems


def compare_pitch_semantics(
    source_path: Path,
    glb_path: Path,
) -> dict[str, object]:
    source_report, _ = validate(load("source", source_path))
    glb_report, _ = validate(load("glb", glb_path))
    source_sides = source_report["metrics"]["stance_pitch_progression"]["sides"]
    glb_sides = glb_report["metrics"]["stance_pitch_progression"]["sides"]
    deltas = {
        side: abs(source_sides[side] - glb_sides[side])
        for side in ("L", "R")
    }
    return {
        "semantic": "stance pitch from foot head to connected foot tail",
        "source_degrees": source_sides,
        "glb_degrees": glb_sides,
        "absolute_delta_degrees": {
            side: rounded(value) for side, value in deltas.items()
        },
        "maximum_absolute_delta_degrees": rounded(max(deltas.values())),
        "maximum_allowed_delta_degrees": (
            MAXIMUM_SOURCE_GLB_STANCE_PITCH_DELTA
        ),
    }


def main() -> None:
    args = arguments_after_separator()
    if len(args) == 3 and args[0] == "compare-pitch":
        comparison = compare_pitch_semantics(
            Path(args[1]).expanduser().resolve(),
            Path(args[2]).expanduser().resolve(),
        )
        print(
            "SANIC_V3_PITCH_COMPARISON="
            f"{json.dumps(comparison, separators=(',', ':'), sort_keys=True)}"
        )
        maximum_delta = comparison["maximum_absolute_delta_degrees"]
        if maximum_delta > MAXIMUM_SOURCE_GLB_STANCE_PITCH_DELTA:
            print("SANIC_V3_PITCH_COMPARISON=FAIL")
            raise AssertionError(
                "Source/GLB stance pitch delta "
                f"{maximum_delta} exceeds "
                f"{MAXIMUM_SOURCE_GLB_STANCE_PITCH_DELTA}"
            )
        print("SANIC_V3_PITCH_COMPARISON=PASS")
        return
    assert len(args) == 2, "Expected mode and asset path"
    report, problems = validate(
        load(args[0], Path(args[1]).expanduser().resolve())
    )
    print(f"SANIC_V3_RUN_REPORT={json.dumps(report, separators=(',', ':'), sort_keys=True)}")
    if problems:
        print(
            "SANIC_V3_RUN_VALIDATION=FAIL",
            json.dumps(problems, separators=(",", ":"), sort_keys=True),
        )
        names = ", ".join(problem["metric"] for problem in problems)
        raise AssertionError(f"SANIC v3 sprint metrics failed: {names}")
    print("SANIC_V3_RUN_VALIDATION=PASS")


if __name__ == "__main__":
    main()
