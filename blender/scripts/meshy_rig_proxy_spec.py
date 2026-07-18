"""Detector-friendly humanoid proxy specification for Meshy auto-rigging.

The proxy exists only to obtain a clean reference skeleton and motion.  Its
geometry is intentionally conventional and does not replace SANIC's production
mesh, materials, skin weights, or armature.
"""

from __future__ import annotations

from dataclasses import dataclass


Point = tuple[float, float, float]

HEIGHT_METERS = 1.7
BOUNDS_MINIMUM_Z = 0.0
BLENDER_FORWARD: Point = (0.0, -1.0, 0.0)

MATERIAL_COLORS: dict[str, tuple[float, float, float, float]] = {
    "Proxy_Blue": (0.035, 0.12, 0.72, 1.0),
    "Proxy_Skin": (0.72, 0.43, 0.25, 1.0),
    "Proxy_Red": (0.72, 0.025, 0.02, 1.0),
    "Proxy_White": (0.92, 0.92, 0.92, 1.0),
    "Proxy_Dark": (0.015, 0.02, 0.035, 1.0),
}

LANDMARKS: dict[str, Point] = {
    "pelvis": (0.0, 0.0, 0.84),
    "chest": (0.0, 0.0, 1.20),
    "neck": (0.0, 0.0, 1.36),
    "head": (0.0, 0.0, 1.54),
    "nose": (0.0, -0.125, 1.56),
    "eye.L": (-0.042, -0.100, 1.605),
    "eye.R": (0.042, -0.100, 1.605),
    "shoulder.L": (-0.22, 0.0, 1.30),
    "elbow.L": (-0.48, 0.0, 1.20),
    "wrist.L": (-0.70, 0.0, 1.11),
    "hand.L": (-0.78, -0.01, 1.09),
    "shoulder.R": (0.22, 0.0, 1.30),
    "elbow.R": (0.48, 0.0, 1.20),
    "wrist.R": (0.70, 0.0, 1.11),
    "hand.R": (0.78, -0.01, 1.09),
    "hip.L": (-0.10, 0.0, 0.82),
    "knee.L": (-0.10, 0.0, 0.46),
    "ankle.L": (-0.10, 0.0, 0.10),
    "toe.L": (-0.10, -0.27, 0.055),
    "hip.R": (0.10, 0.0, 0.82),
    "knee.R": (0.10, 0.0, 0.46),
    "ankle.R": (0.10, 0.0, 0.10),
    "toe.R": (0.10, -0.27, 0.055),
}


@dataclass(frozen=True)
class SegmentPart:
    name: str
    start: Point
    end: Point
    radius_start: float
    radius_end: float
    material: str


@dataclass(frozen=True)
class EllipsoidPart:
    name: str
    center: Point
    radii: Point
    material: str


ProxyPart = SegmentPart | EllipsoidPart


def proxy_parts() -> tuple[ProxyPart, ...]:
    """Return a conventional, symmetric A-pose humanoid proxy."""

    return (
        EllipsoidPart(
            "Proxy_Pelvis",
            LANDMARKS["pelvis"],
            (0.18, 0.12, 0.14),
            "Proxy_Blue",
        ),
        EllipsoidPart(
            "Proxy_Torso",
            (0.0, 0.0, 1.08),
            (0.22, 0.13, 0.29),
            "Proxy_Blue",
        ),
        EllipsoidPart(
            "Proxy_Chest",
            (0.0, 0.0, 1.245),
            (0.235, 0.135, 0.15),
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_Neck",
            (0.0, 0.0, 1.32),
            LANDMARKS["neck"],
            0.070,
            0.066,
            "Proxy_Skin",
        ),
        EllipsoidPart(
            "Proxy_Head",
            LANDMARKS["head"],
            (0.12, 0.105, 0.16),
            "Proxy_Skin",
        ),
        EllipsoidPart(
            "Proxy_Nose",
            LANDMARKS["nose"],
            (0.026, 0.036, 0.030),
            "Proxy_Skin",
        ),
        EllipsoidPart(
            "Proxy_Eye.L",
            LANDMARKS["eye.L"],
            (0.025, 0.013, 0.018),
            "Proxy_White",
        ),
        EllipsoidPart(
            "Proxy_Eye.R",
            LANDMARKS["eye.R"],
            (0.025, 0.013, 0.018),
            "Proxy_White",
        ),
        EllipsoidPart(
            "Proxy_Pupil.L",
            (-0.042, -0.112, 1.605),
            (0.008, 0.007, 0.009),
            "Proxy_Dark",
        ),
        EllipsoidPart(
            "Proxy_Pupil.R",
            (0.042, -0.112, 1.605),
            (0.008, 0.007, 0.009),
            "Proxy_Dark",
        ),
        EllipsoidPart(
            "Proxy_Shoulder.L",
            LANDMARKS["shoulder.L"],
            (0.075, 0.072, 0.075),
            "Proxy_Blue",
        ),
        EllipsoidPart(
            "Proxy_Shoulder.R",
            LANDMARKS["shoulder.R"],
            (0.075, 0.072, 0.075),
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_UpperArm.L",
            LANDMARKS["shoulder.L"],
            LANDMARKS["elbow.L"],
            0.061,
            0.052,
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_UpperArm.R",
            LANDMARKS["shoulder.R"],
            LANDMARKS["elbow.R"],
            0.061,
            0.052,
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_LowerArm.L",
            LANDMARKS["elbow.L"],
            LANDMARKS["wrist.L"],
            0.050,
            0.039,
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_LowerArm.R",
            LANDMARKS["elbow.R"],
            LANDMARKS["wrist.R"],
            0.050,
            0.039,
            "Proxy_Blue",
        ),
        EllipsoidPart(
            "Proxy_Hand.L",
            LANDMARKS["hand.L"],
            (0.068, 0.045, 0.056),
            "Proxy_Skin",
        ),
        EllipsoidPart(
            "Proxy_Hand.R",
            LANDMARKS["hand.R"],
            (0.068, 0.045, 0.056),
            "Proxy_Skin",
        ),
        EllipsoidPart(
            "Proxy_Hip.L",
            LANDMARKS["hip.L"],
            (0.080, 0.078, 0.082),
            "Proxy_Blue",
        ),
        EllipsoidPart(
            "Proxy_Hip.R",
            LANDMARKS["hip.R"],
            (0.080, 0.078, 0.082),
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_UpperLeg.L",
            LANDMARKS["hip.L"],
            LANDMARKS["knee.L"],
            0.079,
            0.066,
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_UpperLeg.R",
            LANDMARKS["hip.R"],
            LANDMARKS["knee.R"],
            0.079,
            0.066,
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_LowerLeg.L",
            LANDMARKS["knee.L"],
            LANDMARKS["ankle.L"],
            0.063,
            0.047,
            "Proxy_Blue",
        ),
        SegmentPart(
            "Proxy_LowerLeg.R",
            LANDMARKS["knee.R"],
            LANDMARKS["ankle.R"],
            0.063,
            0.047,
            "Proxy_Blue",
        ),
        EllipsoidPart(
            "Proxy_Foot.L",
            (-0.10, -0.125, 0.06),
            (0.090, 0.175, 0.060),
            "Proxy_Red",
        ),
        EllipsoidPart(
            "Proxy_Foot.R",
            (0.10, -0.125, 0.06),
            (0.090, 0.175, 0.060),
            "Proxy_Red",
        ),
    )
