"""Pure retargeting contracts for the Meshy 644 SANIC sprint candidate."""

from __future__ import annotations

import math


SOURCE_FPS = 30
SOURCE_LOOP_SECONDS = 0.6
TARGET_FPS = 24
TARGET_FRAMES = tuple(range(1, 18))
UNIQUE_TARGET_POSES = len(TARGET_FRAMES) - 1

MIN_TORSO_LEAN_DEGREES = 11.0
MAX_TORSO_LEAN_DEGREES = 14.0
TORSO_LEAN_DAMPING = 0.55
MIN_ELBOW_ANGLE_DEGREES = 75.0
MAX_ELBOW_ANGLE_DEGREES = 105.0
MIN_KNEE_FLEX_DEGREES = 15.0
LATERAL_DIRECTION_DAMPING = 0.16
MIN_FOOT_PITCH_DEGREES = -35.0
MAX_FOOT_PITCH_DEGREES = 18.0
MAX_FOOT_LATERAL_COMPONENT = 0.08
SHOULDER_RETARGET_DAMPING = 0.22
ARM_RETARGET_ORDER = ("shoulder", "upper_arm", "lower_arm", "hand")
SHOULDER_DELTA_JOINTS = {
    "R": ("LeftShoulder", "LeftArm"),
    "L": ("RightShoulder", "RightArm"),
}
RUN_EXPORT_FRAME_OFFSET = -1.0
EXPECTED_EXPORTED_ACTION_RANGES = {
    "Crash": (1, 36),
    "Idle": (1, 60),
    "Jump": (1, 30),
    "Run": (0, 16),
}

# Meshy labels its physical +X side "Left".  SANIC's authoritative armature
# uses .R for +X, hence the intentional side swap.
SOURCE_TO_TARGET_BONES: dict[str, str] = {
    "Hips": "hips",
    "Spine02": "spine",
    "Spine01": "chest",
    "neck": "neck",
    "Head": "head",
    "LeftShoulder": "shoulder.R",
    "LeftArm": "upper_arm.R",
    "LeftForeArm": "lower_arm.R",
    "LeftHand": "hand.R",
    "RightShoulder": "shoulder.L",
    "RightArm": "upper_arm.L",
    "RightForeArm": "lower_arm.L",
    "RightHand": "hand.L",
    "LeftUpLeg": "upper_leg.R",
    "LeftLeg": "lower_leg.R",
    "LeftFoot": "foot.R",
    "LeftToeBase": "toe.R",
    "RightUpLeg": "upper_leg.L",
    "RightLeg": "lower_leg.L",
    "RightFoot": "foot.L",
    "RightToeBase": "toe.L",
}

# Directions are reconstructed from animated joint positions in armature world
# space.  Bone-local source rotations are never copied.
TARGET_DIRECTION_JOINTS: dict[str, tuple[str, str]] = {
    "hips": ("Hips", "Spine02"),
    "spine": ("Spine02", "Spine01"),
    "chest": ("Spine01", "neck"),
    "neck": ("neck", "Head"),
    "head": ("Head", "head_end"),
    "shoulder.R": ("LeftShoulder", "LeftArm"),
    "upper_arm.R": ("LeftArm", "LeftForeArm"),
    "lower_arm.R": ("LeftForeArm", "LeftHand"),
    "shoulder.L": ("RightShoulder", "RightArm"),
    "upper_arm.L": ("RightArm", "RightForeArm"),
    "lower_arm.L": ("RightForeArm", "RightHand"),
    "upper_leg.R": ("LeftUpLeg", "LeftLeg"),
    "lower_leg.R": ("LeftLeg", "LeftFoot"),
    "foot.R": ("LeftFoot", "LeftToeBase"),
    "upper_leg.L": ("RightUpLeg", "RightLeg"),
    "lower_leg.L": ("RightLeg", "RightFoot"),
    "foot.L": ("RightFoot", "RightToeBase"),
}


def resample_cycle_frames(source_start: float, source_end: float) -> tuple[float, ...]:
    """Return 16 periodic samples plus an exact duplicate of the first."""

    if source_end <= source_start:
        raise ValueError("source cycle must have positive duration")
    step = (source_end - source_start) / UNIQUE_TARGET_POSES
    unique = tuple(source_start + index * step for index in range(UNIQUE_TARGET_POSES))
    return unique + (unique[0],)


def target_torso_lean_degrees(source_lean_degrees: float) -> float:
    damped = source_lean_degrees * TORSO_LEAN_DAMPING
    return min(MAX_TORSO_LEAN_DEGREES, max(MIN_TORSO_LEAN_DEGREES, damped))


def clamp_elbow_angle_degrees(angle: float) -> float:
    return min(MAX_ELBOW_ANGLE_DEGREES, max(MIN_ELBOW_ANGLE_DEGREES, angle))


def ensure_knee_flex_degrees(angle: float) -> float:
    return max(MIN_KNEE_FLEX_DEGREES, angle)


def damp_lateral_direction(
    direction: tuple[float, float, float],
    factor: float = LATERAL_DIRECTION_DAMPING,
) -> tuple[float, float, float]:
    x, y, z = direction
    damped = (x * factor, y, z)
    length = math.sqrt(sum(value * value for value in damped))
    if length <= 1e-8:
        raise ValueError("direction must be non-zero after lateral damping")
    return tuple(value / length for value in damped)


def vertical_root_offset(
    translation: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (0.0, 0.0, float(translation[2]))


def guard_foot_direction(
    direction: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Keep retargeted footwear forward with a plausible sagittal pitch."""

    x, y, z = direction
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-8:
        raise ValueError("foot direction must be non-zero")
    x, y, z = x / length, y / length, z / length
    pitch = math.degrees(math.atan2(z, -y))
    guarded_pitch = min(
        MAX_FOOT_PITCH_DEGREES,
        max(MIN_FOOT_PITCH_DEGREES, pitch),
    )
    lateral = min(
        MAX_FOOT_LATERAL_COMPONENT,
        max(-MAX_FOOT_LATERAL_COMPONENT, x * LATERAL_DIRECTION_DAMPING),
    )
    sagittal = math.sqrt(max(0.0, 1.0 - lateral * lateral))
    radians = math.radians(guarded_pitch)
    return (
        lateral,
        -math.cos(radians) * sagittal,
        math.sin(radians) * sagittal,
    )
