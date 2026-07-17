"""Compare every SANIC action and handoff-semantic field in two Blender files."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sys
from pathlib import Path

import bpy


ACTION_NAMES = ("Idle", "Run", "Jump", "Crash")


@dataclass
class AssetSnapshot:
    metadata: dict[str, object]
    action_values: dict[str, list[float]]
    action_hashes: dict[str, str]


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def encoded_hash(values: list[float]) -> str:
    encoded = json.dumps(values, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def snapshot(path: Path) -> AssetSnapshot:
    if not path.is_file():
        raise FileNotFoundError(path)
    bpy.ops.wm.open_mainfile(filepath=str(path))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(rigs) == 1, f"Expected one armature, got {[obj.name for obj in rigs]}"
    rig = rigs[0]
    actions = {name: bpy.data.actions.get(name) for name in ACTION_NAMES}
    assert all(action is not None for action in actions.values()), {
        name: action is not None for name, action in actions.items()
    }
    ranges = {
        name: (
            int(round(action.frame_range[0])),
            int(round(action.frame_range[1])),
        )
        for name, action in actions.items()
    }
    meshes = sorted(
        (
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
            and all(
                collection.name != "glTF_not_exported"
                for collection in obj.users_collection
            )
        ),
        key=lambda obj: obj.name,
    )
    metadata: dict[str, object] = {
        "armature_name": rig.name,
        "bone_names": sorted(rig.data.bones.keys()),
        "sanic_rig_version": rig.get("sanic_rig_version"),
        "sanic_run_variant": rig.get("sanic_run_variant"),
        "action_ranges": ranges,
        "scene_fps": [
            bpy.context.scene.render.fps,
            bpy.context.scene.render.fps_base,
        ],
        "mesh_names": [obj.name for obj in meshes],
        "material_slots": {
            obj.name: [
                slot.material.name if slot.material is not None else ""
                for slot in obj.material_slots
            ]
            for obj in meshes
        },
    }

    rig.animation_data_create()
    action_values: dict[str, list[float]] = {}
    action_hashes: dict[str, str] = {}
    for name in ACTION_NAMES:
        action = actions[name]
        assert action is not None
        rig.animation_data.action = action
        first, last = ranges[name]
        values: list[float] = []
        for frame in range(first, last + 1):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            for bone in sorted(rig.pose.bones, key=lambda item: item.name):
                values.extend(
                    component
                    for row in bone.matrix_basis
                    for component in row
                )
        action_values[name] = values
        action_hashes[name] = encoded_hash(values)
    rig.animation_data.action = None
    return AssetSnapshot(metadata, action_values, action_hashes)


def compare(
    baseline: AssetSnapshot,
    candidate: AssetSnapshot,
) -> dict[str, object]:
    assert baseline.metadata == candidate.metadata, {
        "baseline": baseline.metadata,
        "candidate": candidate.metadata,
    }
    action_report: dict[str, object] = {}
    for name in ACTION_NAMES:
        first = baseline.action_values[name]
        second = candidate.action_values[name]
        assert len(first) == len(second), (name, len(first), len(second))
        maximum_delta = max(
            abs(baseline_value - candidate_value)
            for baseline_value, candidate_value in zip(first, second)
        )
        assert maximum_delta == 0.0, (name, maximum_delta)
        assert baseline.action_hashes[name] == candidate.action_hashes[name], (
            name,
            baseline.action_hashes[name],
            candidate.action_hashes[name],
        )
        action_report[name] = {
            "samples": len(first),
            "sha256": baseline.action_hashes[name],
            "maximum_delta": maximum_delta,
            "frame_range": list(
                baseline.metadata["action_ranges"][name]
            ),
        }
    return {
        "metadata": baseline.metadata,
        "actions": action_report,
        "maximum_delta": max(
            report["maximum_delta"] for report in action_report.values()
        ),
    }


def main() -> None:
    args = arguments_after_separator()
    assert len(args) == 2, "Expected baseline and candidate .blend paths"
    report = compare(
        snapshot(Path(args[0]).expanduser().resolve()),
        snapshot(Path(args[1]).expanduser().resolve()),
    )
    print(
        "SANIC_ACTION_COMPARISON=PASS",
        json.dumps(report, separators=(",", ":"), sort_keys=True),
    )


if __name__ == "__main__":
    main()
