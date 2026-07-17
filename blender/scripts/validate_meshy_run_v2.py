"""Validate the v2 sprint cycle without changing the approved jump clip.

Usage::

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_run_v2.py -- source /path/to/runner.blend

    blender --background --factory-startup \
      --python blender/scripts/validate_meshy_run_v2.py -- glb /path/to/runner.glb
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


FORWARD = Vector((0.0, -1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
CONTACTS = ((1, "L", "R"), (9, "R", "L"))
PASSING = ((5, "L", "R"), (13, "R", "L"))
FLIGHT = (7, 15)
SAMPLE_FRAMES = (1, 3, 5, 7, 9, 11, 13, 15, 17)
ALL_RUN_FRAMES = tuple(range(1, 18))


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
    assert len(rigs) == 1, [obj.name for obj in rigs]
    return rigs[0]


def point(rig: bpy.types.Object, bone_name: str, endpoint: str) -> Vector:
    bone = rig.pose.bones[bone_name]
    local = bone.head if endpoint == "head" else bone.tail
    return rig.matrix_world @ local


def joint_angle(first: Vector, joint: Vector, last: Vector) -> float:
    first_vector = first - joint
    last_vector = last - joint
    return math.degrees(first_vector.angle(last_vector))


def sagittal_angle(direction: Vector) -> float:
    """Signed angle forward from the downward axis, ignoring tiny lateral motion."""
    return math.degrees(math.atan2(direction.dot(FORWARD), -direction.dot(UP)))


def foot_region_minimum_z(rig: bpy.types.Object, side: str) -> float:
    """Measure the evaluated shoe region selected by foot/toe skin weights."""
    group_names = {f"foot.{side}", f"toe.{side}"}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    minimum = float("inf")
    selected = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        group_indices = {
            group.index for group in obj.vertex_groups if group.name in group_names
        }
        if not group_indices:
            continue
        vertex_indices = [
            vertex.index
            for vertex in obj.data.vertices
            if any(
                membership.group in group_indices and membership.weight > 1e-4
                for membership in vertex.groups
            )
        ]
        if not vertex_indices:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            for index in vertex_indices:
                if index >= len(mesh.vertices):
                    continue
                minimum = min(
                    minimum,
                    (evaluated.matrix_world @ mesh.vertices[index].co).z,
                )
                selected += 1
        finally:
            evaluated.to_mesh_clear()
    assert selected > 0 and math.isfinite(minimum), (side, selected, minimum)
    return minimum


def sample(rig: bpy.types.Object, frame: int) -> dict[str, object]:
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    root = point(rig, "root", "head")
    result: dict[str, object] = {"root": root}
    for side in ("L", "R"):
        shoulder = point(rig, f"upper_arm.{side}", "head")
        elbow = point(rig, f"lower_arm.{side}", "head")
        wrist = point(rig, f"hand.{side}", "head")
        hip = point(rig, f"upper_leg.{side}", "head")
        knee = point(rig, f"lower_leg.{side}", "head")
        ankle = point(rig, f"foot.{side}", "head")
        toe = point(rig, f"toe.{side}", "tail")
        upper_arm = elbow - shoulder
        result[side] = {
            "shoulder": shoulder,
            "wrist": wrist,
            "knee": knee,
            "toe": toe,
            "arm_angle": sagittal_angle(upper_arm),
            "shoulder_abduction": math.degrees(math.asin(min(1.0, abs(upper_arm.x) / upper_arm.length))),
            "elbow_angle": joint_angle(shoulder, elbow, wrist),
            "thigh_angle": sagittal_angle(knee - hip),
            "knee_angle": joint_angle(hip, knee, ankle),
            "sole_z": foot_region_minimum_z(rig, side),
        }
    return result


def validate(rig: bpy.types.Object) -> dict[str, object]:
    run = bpy.data.actions.get("Run")
    jump = bpy.data.actions.get("Jump")
    assert run is not None and jump is not None
    assert tuple(round(value) for value in run.frame_range) == (1, 17), run.frame_range[:]
    # The user approved the jump; the sprint-only iteration must preserve its contract.
    assert tuple(round(value) for value in jump.frame_range) == (1, 30), jump.frame_range[:]

    rig.animation_data_create()
    rig.animation_data.action = run
    samples = {frame: sample(rig, frame) for frame in ALL_RUN_FRAMES}
    problems: list[object] = []

    for frame in ALL_RUN_FRAMES:
        for side in ("L", "R"):
            metrics = samples[frame][side]
            if not 68.0 <= metrics["elbow_angle"] <= 118.0:
                problems.append(("elbow stays sprint-flexed", frame, side, metrics["elbow_angle"]))
            if metrics["shoulder_abduction"] > 9.0:
                problems.append(("arm swing leaves sagittal plane", frame, side, metrics["shoulder_abduction"]))
            knee_flexion = 180.0 - metrics["knee_angle"]
            if knee_flexion < 15.0:
                problems.append(("knee retains sprint flexion", frame, side, knee_flexion))

    wrist_travel: dict[str, float] = {}
    for side in ("L", "R"):
        reaches = [
            (samples[frame][side]["wrist"] - samples[frame][side]["shoulder"]).dot(FORWARD)
            for frame in ALL_RUN_FRAMES
        ]
        wrist_travel[side] = max(reaches) - min(reaches)
        if not 0.28 <= wrist_travel[side] <= 0.40:
            problems.append(("controlled fore-aft wrist travel", side, wrist_travel[side]))

    contact_report: dict[int, object] = {}
    for frame, lead, opposite_arm in CONTACTS:
        metrics = samples[frame]
        lead_metrics = metrics[lead]
        trail = "R" if lead == "L" else "L"
        if lead_metrics["sole_z"] > 0.006:
            problems.append(("lead shoe never strikes", frame, lead, lead_metrics["sole_z"]))
        if not 18.0 <= lead_metrics["thigh_angle"] <= 42.0:
            problems.append(("contact thigh reads as march", frame, lead, lead_metrics["thigh_angle"]))
        opposite = metrics[opposite_arm]
        same = metrics[lead]
        opposite_reach = (opposite["wrist"] - opposite["shoulder"]).dot(FORWARD)
        same_reach = (same["wrist"] - same["shoulder"]).dot(FORWARD)
        if opposite_reach - same_reach < 0.16:
            problems.append(("contralateral arm drive", frame, opposite_reach, same_reach))
        contact_report[frame] = {
            "lead": lead,
            "lead_toe_z": round(lead_metrics["toe"].z, 5),
            "lead_sole_z": round(lead_metrics["sole_z"], 5),
            "trail_toe_z": round(metrics[trail]["toe"].z, 5),
            "lead_thigh": round(lead_metrics["thigh_angle"], 3),
            "opposite_arm_reach": round(opposite_reach, 5),
            "same_arm_reach": round(same_reach, 5),
        }

    passing_report: dict[int, object] = {}
    for frame, support, recovery in PASSING:
        metrics = samples[frame]
        recovery_metrics = metrics[recovery]
        support_metrics = metrics[support]
        if recovery_metrics["knee"].z - support_metrics["knee"].z < 0.07:
            problems.append(("recovery knee drive", frame, recovery_metrics["knee"].z, support_metrics["knee"].z))
        if not 48.0 <= recovery_metrics["knee_angle"] <= 112.0:
            problems.append(("recovery heel tuck", frame, recovery, recovery_metrics["knee_angle"]))
        passing_report[frame] = {
            "support": support,
            "recovery": recovery,
            "knee_height_delta": round(recovery_metrics["knee"].z - support_metrics["knee"].z, 5),
            "recovery_knee_angle": round(recovery_metrics["knee_angle"], 3),
        }

    flight_report: dict[int, object] = {}
    for frame in FLIGHT:
        toe_heights = {side: samples[frame][side]["toe"].z for side in ("L", "R")}
        if min(toe_heights.values()) < 0.095:
            problems.append(("true airborne flight phase", frame, toe_heights))
        flight_report[frame] = {side: round(value, 5) for side, value in toe_heights.items()}

    for side in ("L", "R"):
        for key in ("wrist", "knee", "toe"):
            loop_error = (samples[1][side][key] - samples[17][side][key]).length
            if loop_error > 1e-4:
                problems.append(("run loop continuity", side, key, loop_error))

    vertical_root = [samples[frame]["root"].z for frame in ALL_RUN_FRAMES]
    vertical_range = max(vertical_root) - min(vertical_root)
    if not 0.035 <= vertical_range <= 0.055:
        problems.append(("athletic COM travel", min(vertical_root), max(vertical_root)))

    assert not problems, ("SANIC v2 sprint biomechanics", problems[:30])
    return {
        "contacts": contact_report,
        "passing": passing_report,
        "flight": flight_report,
        "root_vertical_range": round(vertical_range, 5),
        "wrist_travel": {side: round(value, 5) for side, value in wrist_travel.items()},
        "run_range": [round(value) for value in run.frame_range],
        "jump_range": [round(value) for value in jump.frame_range],
    }


def main() -> None:
    args = arguments_after_separator()
    assert len(args) == 2, "Expected mode and asset path"
    report = validate(load(args[0], Path(args[1]).expanduser().resolve()))
    print(f"SANIC_RUN_V2_REPORT={json.dumps(report, sort_keys=True)}")
    print("SANIC_RUN_V2_VALIDATION=PASS")


if __name__ == "__main__":
    main()
