"""Prove that a run-only refinement did not change the approved Jump action."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import bpy


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def snapshot(path: Path) -> tuple[str, list[float]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    bpy.ops.wm.open_mainfile(filepath=str(path))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(rigs) == 1, [obj.name for obj in rigs]
    rig = rigs[0]
    action = bpy.data.actions.get("Jump")
    assert action is not None
    assert tuple(round(value) for value in action.frame_range) == (1, 30)
    rig.animation_data_create()
    rig.animation_data.action = action
    values: list[float] = []
    for frame in range(1, 31):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        for bone in sorted(rig.pose.bones, key=lambda item: item.name):
            values.extend(component for row in bone.matrix_basis for component in row)
    encoded = json.dumps(values, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), values


def main() -> None:
    args = arguments_after_separator()
    assert len(args) == 2, "Expected baseline and candidate .blend paths"
    baseline_hash, baseline = snapshot(Path(args[0]).expanduser().resolve())
    candidate_hash, candidate = snapshot(Path(args[1]).expanduser().resolve())
    assert len(baseline) == len(candidate)
    maximum_delta = max(abs(first - second) for first, second in zip(baseline, candidate))
    assert maximum_delta <= 1e-10, maximum_delta
    assert baseline_hash == candidate_hash, (baseline_hash, candidate_hash)
    print(
        "SANIC_JUMP_PRESERVATION=PASS",
        {
            "sha256": baseline_hash,
            "samples": len(baseline),
            "maximum_delta": maximum_delta,
        },
    )


if __name__ == "__main__":
    main()
