"""Validate the reproducible SANIC Blender source assets.

Usage (Blender consumes arguments before ``--``)::

    blender --background blender/sanic-source.blend \
      --python blender/scripts/validate_assets.py -- character
    blender --background blender/world-source.blend \
      --python blender/scripts/validate_assets.py -- world
"""

from __future__ import annotations

import sys
import math
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


FACE_OBJECTS = {
    "SANIC_Head",
    "SANIC_EyeMask",
    "SANIC_Eyelid.L",
    "SANIC_Eyelid.R",
    "SANIC_Muzzle",
    "SANIC_Nose",
    "SANIC_Mouth",
    "SANIC_BrowText",
}
LEGACY_FACE_OBJECTS = {
    "SANIC_Eyes",
    "SANIC_Eye.R",
    "SANIC_Lid.L",
    "SANIC_Lid.R",
    "SANIC_Brow.L",
    "SANIC_Brow.R",
    "SANIC_MuzzleCheek.L",
    "SANIC_MuzzleCheek.R",
    "SANIC_LipUpper",
    "SANIC_LipLower",
    "SANIC_Nostril.L",
    "SANIC_Nostril.R",
}
FACE_MESH_OBJECTS = FACE_OBJECTS - {"SANIC_BrowText"}

CHARACTER_OBJECTS = {
    "SANIC_Armature",
    "SANIC_BodySculpt",
    "SANIC_Quills",
    *FACE_OBJECTS,
    "SANIC_GloveShell.L",
    "SANIC_GloveShell.R",
    "SANIC_ShoeUpper.L",
    "SANIC_ShoeUpper.R",
    "SANIC_ShoeMidsole.L",
    "SANIC_ShoeMidsole.R",
    "SANIC_ShoeOutsole.L",
    "SANIC_ShoeOutsole.R",
    "SANIC_ShoeStrap.L",
    "SANIC_ShoeStrap.R",
    "SANIC_ShoeCollar.L",
    "SANIC_ShoeCollar.R",
    "SANIC_ShoeHeelCounter.L",
    "SANIC_ShoeHeelCounter.R",
}
CHARACTER_ACTIONS = {"Idle", "Run", "Jump", "Crash"}
CHARACTER_BONES = {
    "root", "hips", "spine", "spine_upper", "chest", "neck", "head",
    "clavicle.L", "clavicle.R",
    "upper_arm.L", "upper_arm.R", "upper_arm_twist.L", "upper_arm_twist.R",
    "lower_arm.L", "lower_arm.R", "lower_arm_twist.L", "lower_arm_twist.R",
    "hand.L", "hand.R", "thumb.L", "thumb.R",
    "finger_index.L", "finger_index.R", "finger_middle.L", "finger_middle.R",
    "finger_ring.L", "finger_ring.R", "finger_pinky.L", "finger_pinky.R",
    "upper_leg.L", "upper_leg.R", "upper_leg_twist.L", "upper_leg_twist.R",
    "lower_leg.L", "lower_leg.R", "lower_leg_twist.L", "lower_leg_twist.R",
    "foot.L", "foot.R", "toe.L", "toe.R",
    "quill_upper", "quill_mid", "quill_lower",
}
BLOCKY_SOURCE_OBJECTS = {
    "SANIC_Sole.L", "SANIC_Sole.R", "SANIC_Midsole.L", "SANIC_Midsole.R",
    "SANIC_Shoe.L", "SANIC_Shoe.R", "SANIC_ShoeToe.L", "SANIC_ShoeToe.R",
}
LEGACY_GLOVE_OBJECTS = {
    "SANIC_Glove.L", "SANIC_Glove.R",
    "SANIC_GloveCuff.L", "SANIC_GloveCuff.R",
    "SANIC_Thumb.L", "SANIC_Thumb.R",
    *(f"SANIC_Finger{index}.{side}" for side in ("L", "R") for index in range(1, 5)),
}
FORBIDDEN_PLACEHOLDER_OBJECTS = BLOCKY_SOURCE_OBJECTS | LEGACY_GLOVE_OBJECTS | {
    "SANIC_SockCuff.L", "SANIC_SockCuff.R",
}
ACTION_FRAME_RANGES = {
    "Idle": (1, 60),
    "Run": (1, 21),
    "Jump": (1, 30),
    "Crash": (1, 42),
}
WORLD_OBJECTS = {
    "SANIC_Ring",
    "KIT_Tree_A",
    "KIT_Tree_B",
    "KIT_Grass",
    "KIT_Fern",
    "KIT_Rock",
    "KIT_Mushroom",
    "KIT_Log",
    "KIT_Candle",
    "KIT_FUD",
    "KIT_Gap",
    "KIT_Sign_Stimmy",
    "KIT_Sign_Trenches",
    "KIT_Sign_Coping",
    "KIT_Sign_Memes",
}
WORLD_EXPORT_COLLECTIONS = {"WORLD_RING_EXPORT", "WORLD_KIT_EXPORT"}

TASK3_OBJECTS = {
    name
    for name in CHARACTER_OBJECTS
    if name.startswith("SANIC_Glove") or name.startswith("SANIC_Shoe")
}
DIGIT_GROUP_STEMS = (
    "thumb",
    "finger_index",
    "finger_middle",
    "finger_ring",
    "finger_pinky",
)
EXPECTED_GLOVE_GROUP_VERTEX_COUNTS = {
    "hand": 362,
    "thumb": 97,
    "finger_index": 88,
    "finger_middle": 92,
    "finger_ring": 92,
    "finger_pinky": 96,
}
CANONICAL_SHOE_Y = (0.060, -0.072, -0.252, -0.420, -0.552, -0.660)
SUPPORT_SHOE_Y = (0.102, 0.081, -0.681, -0.702)
AUDITED_SHOE_ASSEMBLY_SIZE = Vector((0.990000, 1.376000, 0.622189))
SHOE_FOOTPRINT_RATIO_RANGE = (0.58, 0.62)
SHOE_HEIGHT_RATIO_RANGE = (0.65, 0.75)
SHOE_LENGTH_SCALE = 0.60
SHOE_WIDTH_SCALE = 0.60
SHOE_HEIGHT_SCALE = 0.70
FOOT_CONTAINMENT_RAY_JITTER = 1e-5
FOOT_CONTAINMENT_APERTURE_MIN_HEIGHT_RATIO = 0.60
FOOT_CONTAINMENT_COLLAR_TOP_EPSILON = 5e-4
FOOT_CONTAINMENT_INNER_RAY_EPSILON = 1e-5


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def evaluated_triangle_count(objects: list[bpy.types.Object]) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return triangles


def mesh_adjacency(mesh: bpy.types.Mesh) -> dict[int, set[int]]:
    adjacency = {vertex.index: set() for vertex in mesh.vertices}
    for edge in mesh.edges:
        first, second = edge.vertices
        adjacency[first].add(second)
        adjacency[second].add(first)
    return adjacency


def connected_component_count(
    adjacency: dict[int, set[int]],
    members: set[int],
) -> int:
    remaining = set(members)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            current = stack.pop()
            linked = adjacency[current] & remaining
            remaining.difference_update(linked)
            stack.extend(linked)
    return components


def vertex_group_members(obj: bpy.types.Object, name: str) -> set[int]:
    group = obj.vertex_groups.get(name)
    assert group is not None, f"{obj.name} is missing vertex group {name}"
    return {
        vertex.index
        for vertex in obj.data.vertices
        if any(
            membership.group == group.index and membership.weight >= 0.999
            for membership in vertex.groups
        )
    }


def object_names_rooted_at(
    object_names: set[str],
    roots: set[str],
    *,
    include_exact: bool,
) -> set[str]:
    return {
        name
        for name in object_names
        if any(
            (include_exact and name == root) or name.startswith(f"{root}.")
            for root in roots
        )
    }


def assert_closed_all_quad_mesh(obj: bpy.types.Object, minimum_vertices: int) -> None:
    assert obj.type == "MESH", (obj.name, obj.type)
    mesh = obj.data
    assert len(mesh.vertices) >= minimum_vertices, (obj.name, len(mesh.vertices))
    assert mesh.polygons, f"{obj.name} has no faces"
    assert all(len(polygon.vertices) == 4 for polygon in mesh.polygons), (
        f"{obj.name} contains non-quad faces"
    )
    face_uses: dict[tuple[int, int], int] = defaultdict(int)
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            face_uses[tuple(sorted(edge_key))] += 1
    nonmanifold = {
        tuple(sorted(edge.vertices)): face_uses.get(tuple(sorted(edge.vertices)), 0)
        for edge in mesh.edges
        if face_uses.get(tuple(sorted(edge.vertices)), 0) != 2
    }
    assert not nonmanifold, f"{obj.name} is not closed manifold: {len(nonmanifold)} edges"
    adjacency = mesh_adjacency(mesh)
    assert connected_component_count(adjacency, set(adjacency)) == 1, (
        f"{obj.name} must have one connected component"
    )


def nonadjacent_self_intersection_count(
    obj: bpy.types.Object,
    evaluated: bool,
) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_obj = obj.evaluated_get(depsgraph)
    mesh = evaluated_obj.to_mesh() if evaluated else obj.data
    try:
        mesh.calc_loop_triangles()
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        points = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
        return sum(
            1
            for first, second in tree.overlap(tree)
            if first < second
            and set(triangles[first]).isdisjoint(triangles[second])
        )
    finally:
        if evaluated:
            evaluated_obj.to_mesh_clear()


def evaluated_world_points(obj: bpy.types.Object) -> list[Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def point_cloud_size(points: list[Vector]) -> Vector:
    assert points
    return Vector(tuple(
        max(point[axis] for point in points) - min(point[axis] for point in points)
        for axis in range(3)
    ))


def vertical_span_near_x(
    points: list[Vector],
    target_x: float,
    half_width: float,
) -> float:
    samples = [point.z for point in points if abs(point.x - target_x) <= half_width]
    assert len(samples) >= 4, (target_x, half_width, len(samples))
    return max(samples) - min(samples)


def validate_full_head_binding(obj: bpy.types.Object) -> None:
    assert obj.type == "MESH", (obj.name, obj.type)
    members = vertex_group_members(obj, "head")
    assert members == {vertex.index for vertex in obj.data.vertices}, (
        obj.name,
        "head vertex group must cover every base vertex at weight 1.0",
        len(members),
        len(obj.data.vertices),
    )


def validate_lobed_face_mesh(
    name: str,
    *,
    expected_centers: tuple[float, float],
    bridge_range: tuple[float, float],
    width_range: tuple[float, float],
    depth_range: tuple[float, float],
    height_range: tuple[float, float],
    minimum_lobe_to_bridge_ratio: float,
) -> None:
    obj = bpy.data.objects[name]
    adjacency = mesh_adjacency(obj.data)
    components = connected_component_count(adjacency, set(adjacency))
    assert components == 1, (name, "connected components", components)
    assert obj.get("sanic_face_profile") == "lobed-ellipsoid", (
        name,
        obj.get("sanic_face_profile"),
    )
    lobe_centers = tuple(round(float(value), 3) for value in obj.get("sanic_lobe_centers", ()))
    assert lobe_centers == expected_centers, (name, "lobe centers", lobe_centers)
    bridge = obj.get("sanic_bridge_ratio")
    assert isinstance(bridge, (int, float)) and bridge_range[0] <= bridge <= bridge_range[1], (
        name,
        "bridge ratio",
        bridge,
    )

    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    size = point_cloud_size(points)
    assert width_range[0] <= size.x <= width_range[1], (name, "width", size.x)
    assert depth_range[0] <= size.y <= depth_range[1], (name, "depth", size.y)
    assert height_range[0] <= size.z <= height_range[1], (name, "height", size.z)
    center_x = sum(point.x for point in points) / len(points)
    lobe_spans = tuple(
        vertical_span_near_x(points, center_x + offset, 0.065)
        for offset in expected_centers
    )
    bridge_span = vertical_span_near_x(points, center_x, 0.045)
    assert bridge_span >= 0.14, (name, "bridge collapsed", bridge_span)
    assert min(lobe_spans) >= bridge_span * minimum_lobe_to_bridge_ratio, (
        name,
        "two readable lobes with a subtle bridge",
        lobe_spans,
        bridge_span,
    )

    intersections = {
        "base": nonadjacent_self_intersection_count(obj, evaluated=False),
        "evaluated": nonadjacent_self_intersection_count(obj, evaluated=True),
    }
    assert intersections == {"base": 0, "evaluated": 0}, (
        name,
        "non-adjacent self intersections",
        intersections,
    )


def validate_eye_opening_patches(mask: bpy.types.Object) -> None:
    material_names = [material.name for material in mask.data.materials]
    assert material_names == ["SANIC_MAT_White", "SANIC_MAT_Black"], (
        mask.name,
        "white mask plus flush black eye-opening patches",
        material_names,
    )
    assert len(mask.data.vertices) >= 3_000, (
        mask.name,
        "eye-mask control surface must be refined before assigning organic material patches",
        len(mask.data.vertices),
    )
    black_index = material_names.index("SANIC_MAT_Black")
    patch_centers = [
        mask.matrix_world @ polygon.center
        for polygon in mask.data.polygons
        if polygon.material_index == black_index
    ]
    assert sum(point.x > 0.10 for point in patch_centers) >= 12, (
        mask.name,
        "missing left eye opening patch",
        len(patch_centers),
    )
    assert sum(point.x < -0.10 for point in patch_centers) >= 12, (
        mask.name,
        "missing right eye opening patch",
        len(patch_centers),
    )
    assert not [point for point in patch_centers if abs(point.x) < 0.075], (
        mask.name,
        "black material crosses the white bridge like a visor",
    )
    patch_center_z = mask.matrix_world.translation.z - 0.02
    lobe_centers = tuple(float(value) for value in mask.get("sanic_lobe_centers", ()))
    ellipse_metrics = [
        min(
            ((point.x - center_x) / 0.13) ** 2
            + ((point.z - patch_center_z) / 0.15) ** 2
            for center_x in lobe_centers
        )
        for point in patch_centers
    ]
    assert ellipse_metrics and max(ellipse_metrics) <= 1.0, (
        mask.name,
        "eye openings must be two restrained oval patches, not angular visor blocks",
        max(ellipse_metrics, default=None),
    )
    for label, side_points in (
        ("L", [point for point in patch_centers if point.x > 0.0]),
        ("R", [point for point in patch_centers if point.x < 0.0]),
    ):
        assert len(side_points) >= 8, (mask.name, label, "readable eye opening", len(side_points))
        x_span = max(point.x for point in side_points) - min(point.x for point in side_points)
        z_span = max(point.z for point in side_points) - min(point.z for point in side_points)
        aspect = x_span / z_span
        assert 0.82 <= aspect <= 1.35 and z_span <= 0.20, (
            mask.name,
            label,
            "compact organic eye opening, not a tall mascara slab",
            {"x_span": x_span, "z_span": z_span, "aspect": aspect},
        )


def validate_face_surface_integration() -> None:
    head_points = evaluated_world_points(bpy.data.objects["SANIC_Head"])
    mask_points = evaluated_world_points(bpy.data.objects["SANIC_EyeMask"])
    muzzle = bpy.data.objects["SANIC_Muzzle"]
    muzzle_points = evaluated_world_points(muzzle)
    nose_points = evaluated_world_points(bpy.data.objects["SANIC_Nose"])
    mouth = bpy.data.objects["SANIC_Mouth"]
    mouth_points = evaluated_world_points(mouth)

    head_front = min(point.y for point in head_points)
    mask_rear = max(point.y for point in mask_points)
    muzzle_rear = max(point.y for point in muzzle_points)
    muzzle_front = min(point.y for point in muzzle_points)
    nose_front = min(point.y for point in nose_points)
    muzzle_tree = evaluated_world_bvh(muzzle)
    mouth_offsets = [muzzle_tree.find_nearest(point)[3] for point in mouth_points]
    problems: dict[str, object] = {}
    if mask_rear < head_front + 0.06:
        problems["eye-mask/head overlap"] = (mask_rear, head_front)
    if muzzle_rear < head_front + 0.06:
        problems["muzzle/head overlap"] = (muzzle_rear, head_front)
    if nose_front < muzzle_front - 0.10:
        problems["nose forward projection"] = (nose_front, muzzle_front)
    if not mouth_offsets or max(mouth_offsets) > 0.018:
        problems["mouth/muzzle surface offset"] = {
            "max": max(mouth_offsets, default=None),
            "mean": sum(mouth_offsets) / len(mouth_offsets) if mouth_offsets else None,
        }
    assert not problems, ("facial surface integration", problems)


def validate_humanesque_head_profile(head: bpy.types.Object) -> None:
    assert head.get("sanic_face_profile") == "humanesque-tapered-head"
    assert 0.08 <= float(head.get("sanic_lower_cheek_taper", 0.0)) <= 0.10
    assert 0.04 <= float(head.get("sanic_brow_broaden", 0.0)) <= 0.06
    assert 0.03 <= float(head.get("sanic_rear_lower_flatten", 0.0)) <= 0.05
    points = evaluated_world_points(head)
    lower = [point for point in points if 4.68 <= point.z <= 4.82]
    brow = [point for point in points if 5.34 <= point.z <= 5.48]
    assert lower and brow, (head.name, "profile slice samples")
    lower_width = max(point.x for point in lower) - min(point.x for point in lower)
    brow_width = max(point.x for point in brow) - min(point.x for point in brow)
    ratio = lower_width / brow_width
    assert 0.75 <= ratio <= 0.87, (
        head.name,
        "lower cheek must read narrower than the brow plane",
        {"lower_width": lower_width, "brow_width": brow_width, "ratio": ratio},
    )


def validate_brow_text_integration(text: bpy.types.Object) -> None:
    assert text.type == "FONT", (text.name, text.type)
    assert text.data.body == "I Love to Go Fast", text.data.body
    conform = text.modifiers.get("SANIC_ForeheadConform")
    assert conform is not None and conform.type == "SHRINKWRAP", (
        text.name,
        "brow text must conform to the forehead surface",
    )
    assert conform.target == bpy.data.objects["SANIC_Head"], (
        text.name,
        "forehead conform target",
        conform.target,
    )
    text_points = evaluated_world_points(text)
    head = bpy.data.objects["SANIC_Head"]
    head_points = evaluated_world_points(head)
    head_tree = evaluated_world_bvh(head)
    surface_offsets = [head_tree.find_nearest(point)[3] for point in text_points]
    assert surface_offsets and max(surface_offsets) <= 0.035, (
        text.name,
        "floating brow text",
        {"max": max(surface_offsets, default=None), "mean": sum(surface_offsets) / len(surface_offsets)},
    )
    assert min(point.x for point in text_points) >= min(point.x for point in head_points) + 0.12
    assert max(point.x for point in text_points) <= max(point.x for point in head_points) - 0.12
    eyelid_points = [
        point
        for side in ("L", "R")
        for point in evaluated_world_points(bpy.data.objects[f"SANIC_Eyelid.{side}"])
    ]
    assert min(point.z for point in text_points) >= max(point.z for point in eyelid_points) + 0.08, (
        "SANIC_BrowText",
        "text overlaps eyelid bounds",
        min(point.z for point in text_points),
        max(point.z for point in eyelid_points),
    )
    assert text.get("sanic_text_role") == "high-readable-brow-text"


def validate_face_geometry() -> None:
    objects = set(bpy.data.objects.keys())
    missing = FACE_OBJECTS - objects
    legacy = object_names_rooted_at(objects, LEGACY_FACE_OBJECTS, include_exact=True)
    duplicates = object_names_rooted_at(objects, FACE_OBJECTS, include_exact=False)
    assert not missing and not legacy and not duplicates, (
        "face object contract",
        f"missing={sorted(missing)}",
        f"legacy={sorted(legacy)}",
        f"duplicates={sorted(duplicates)}",
    )

    for name in sorted(FACE_MESH_OBJECTS):
        validate_full_head_binding(bpy.data.objects[name])

    validate_lobed_face_mesh(
        "SANIC_EyeMask",
        expected_centers=(-0.23, 0.23),
        bridge_range=(0.50, 0.62),
        width_range=(1.02, 1.18),
        depth_range=(0.20, 0.30),
        height_range=(0.44, 0.70),
        minimum_lobe_to_bridge_ratio=1.18,
    )
    mask = bpy.data.objects["SANIC_EyeMask"]
    validate_eye_opening_patches(mask)

    validate_lobed_face_mesh(
        "SANIC_Muzzle",
        expected_centers=(-0.25, 0.25),
        bridge_range=(0.72, 0.74),
        width_range=(0.95, 1.10),
        depth_range=(0.26, 0.38),
        height_range=(0.38, 0.62),
        minimum_lobe_to_bridge_ratio=1.05,
    )

    mouth = bpy.data.objects["SANIC_Mouth"]
    mouth_components = connected_component_count(
        mesh_adjacency(mouth.data),
        {vertex.index for vertex in mouth.data.vertices},
    )
    assert mouth_components == 1, (mouth.name, "connected components", mouth_components)
    assert mouth.get("sanic_face_role") == "crooked-mouth", (
        mouth.name,
        mouth.get("sanic_face_role"),
    )
    mouth_points = evaluated_world_points(mouth)
    assert len(mouth_points) >= 96, (mouth.name, "evaluated vertices", len(mouth_points))
    mouth_materials = {material.name for material in mouth.data.materials}
    assert mouth_materials == {"SANIC_MAT_Black", "SANIC_MAT_Beige"}, (
        mouth.name,
        "integrated dark opening and restrained tan rim",
        mouth_materials,
    )
    assert abs(float(mouth.get("sanic_right_corner_raise", 999.0)) - 0.035) <= 1e-6
    assert abs(float(mouth.get("sanic_left_corner_drop", 999.0)) - (-0.020)) <= 1e-6
    validate_face_surface_integration()

    for side in ("L", "R"):
        eyelid = bpy.data.objects[f"SANIC_Eyelid.{side}"]
        assert eyelid.get("sanic_face_role") == "curved-sleepy-eyelid", (
            eyelid.name,
            eyelid.get("sanic_face_role"),
        )
        assert eyelid.get("sanic_curve_points") == 3, (
            eyelid.name,
            eyelid.get("sanic_curve_points"),
        )
        assert float(eyelid.get("sanic_arc_sag", 0.0)) >= 0.045, (
            eyelid.name,
            "curved three-point arc",
            eyelid.get("sanic_arc_sag"),
        )
        assert eyelid.modifiers.get("SANIC_Rounded") is None, (
            eyelid.name,
            "rounded-box placeholder",
        )
        eyelid_size = point_cloud_size(evaluated_world_points(eyelid))
        assert 0.32 <= eyelid_size.x <= 0.58, (eyelid.name, eyelid_size)
        assert 0.045 <= eyelid_size.z <= 0.18, (eyelid.name, "curvature", eyelid_size)

    head = bpy.data.objects["SANIC_Head"]
    validate_humanesque_head_profile(head)

    nose = bpy.data.objects["SANIC_Nose"]
    nose_points = evaluated_world_points(nose)
    nose_center_x = sum(point.x for point in nose_points) / len(nose_points)
    nose_size = point_cloud_size(nose_points)
    assert abs(nose_center_x) <= 0.01, (nose.name, "central oval", nose_center_x)
    assert 0.25 <= nose_size.x <= 0.40 and 0.20 <= nose_size.z <= 0.36, (
        nose.name,
        "central oval",
        nose_size,
    )

    for side in ("L", "R"):
        ear = bpy.data.objects[f"SANIC_Ear.{side}"]
        assert ear.get("sanic_ear_profile") == "raised-sharp", (
            ear.name,
            ear.get("sanic_ear_profile"),
        )
        ear_points = evaluated_world_points(ear)
        ear_size = point_cloud_size(ear_points)
        assert max(point.z for point in ear_points) >= 5.68, (ear.name, "raised ear")
        assert ear_size.z >= ear_size.x * 1.35, (ear.name, "sharpened ear", ear_size)

    validate_brow_text_integration(bpy.data.objects["SANIC_BrowText"])


def validate_glove_shell(side: str) -> None:
    obj = bpy.data.objects[f"SANIC_GloveShell.{side}"]
    assert_closed_all_quad_mesh(obj, minimum_vertices=600)
    intersections = {
        "base": nonadjacent_self_intersection_count(obj, evaluated=False),
        "evaluated": nonadjacent_self_intersection_count(obj, evaluated=True),
    }
    assert intersections == {"base": 0, "evaluated": 0}, (
        obj.name,
        "self-intersecting palm/finger/cuff triangles",
        intersections,
    )
    palm_ratio = obj.get("sanic_glove_palm_inflate_ratio")
    digit_ratio = obj.get("sanic_glove_digit_inflate_ratio")
    palm_distance = obj.get("sanic_glove_palm_max_inflate_distance")
    digit_distance = obj.get("sanic_glove_digit_max_inflate_distance")
    palm_depth = obj.get("sanic_glove_palm_depth")
    assert isinstance(palm_ratio, (int, float)) and 0.10 <= palm_ratio <= 0.14
    assert isinstance(digit_ratio, (int, float)) and 0.0 < digit_ratio <= 0.015
    assert isinstance(palm_depth, (int, float)) and palm_depth > 0.12
    assert isinstance(palm_distance, (int, float)) and abs(
        palm_distance - palm_depth * palm_ratio
    ) <= 1e-6
    assert isinstance(digit_distance, (int, float)) and abs(
        digit_distance - palm_depth * digit_ratio
    ) <= 1e-6
    adjacency = mesh_adjacency(obj.data)
    palm_name = f"hand.{side}"
    digit_names = {f"{stem}.{side}" for stem in DIGIT_GROUP_STEMS}
    anatomical_names = {
        group.name
        for group in obj.vertex_groups
        if group.name == palm_name
        or group.name.startswith("thumb.")
        or group.name.startswith("finger_")
    }
    assert anatomical_names == {palm_name, *digit_names}, (
        obj.name,
        sorted(anatomical_names),
    )

    palm = vertex_group_members(obj, palm_name)
    assert len(palm) == EXPECTED_GLOVE_GROUP_VERTEX_COUNTS["hand"], (
        obj.name,
        palm_name,
        "source-derived anatomical membership fingerprint",
        len(palm),
    )
    assert len(palm) >= 150, (obj.name, palm_name, len(palm))
    assert connected_component_count(adjacency, palm) == 1, (obj.name, palm_name)
    covered = set(palm)
    digit_members: dict[str, set[int]] = {}
    digit_centers: dict[str, Vector] = {}
    digit_tips: dict[str, Vector] = {}
    palm_center = sum(
        (obj.data.vertices[index].co for index in palm),
        Vector(),
    ) / len(palm)
    for name in sorted(digit_names):
        members = vertex_group_members(obj, name)
        digit_members[name] = members
        covered.update(members)
        stem = name.removesuffix(f".{side}")
        assert len(members) == EXPECTED_GLOVE_GROUP_VERTEX_COUNTS[stem], (
            obj.name,
            name,
            "source-derived anatomical membership fingerprint",
            len(members),
        )
        assert len(members) >= 60, (obj.name, name, len(members))
        assert len(members - palm) >= 40, (obj.name, name, "no meaningful digit")
        assert len(members & palm) >= 2, (obj.name, name, "digit is not continuous from palm")
        assert connected_component_count(adjacency, members) == 1, (
            obj.name,
            name,
            "disconnected digit",
        )
        points = [obj.data.vertices[index].co for index in members]
        spans = [
            max(point[axis] for point in points) - min(point[axis] for point in points)
            for axis in range(3)
        ]
        assert max(spans) >= 0.16 and max(spans) / max(min(spans), 1e-6) >= 1.20, (
            obj.name,
            name,
            "digit lacks a tapered anatomical span",
            spans,
        )
        center = sum(points, Vector()) / len(points)
        direction = (center - palm_center).normalized()
        tip = max(points, key=lambda point: (point - palm_center).dot(direction)).copy()
        assert (center - palm_center).length >= 0.045, (obj.name, name, center)
        digit_centers[name] = center
        digit_tips[name] = tip
    assert covered == set(adjacency), (
        obj.name,
        "anatomical groups do not cover the closed glove shell",
        len(set(adjacency) - covered),
    )
    for first_name, first in digit_members.items():
        for second_name, second in digit_members.items():
            if first_name >= second_name:
                continue
            assert len(first ^ second) >= 40, (
                obj.name,
                first_name,
                second_name,
                "digit memberships are not meaningfully distinct",
            )
            assert (digit_centers[first_name] - digit_centers[second_name]).length >= 0.025, (
                obj.name,
                first_name,
                second_name,
                "digit centroids collapse together",
            )
            assert (digit_tips[first_name] - digit_tips[second_name]).length >= 0.035, (
                obj.name,
                first_name,
                second_name,
                "digit tips are not visibly separated",
            )

    ordered_fingers = [
        digit_centers[f"finger_{finger}.{side}"]
        for finger in ("index", "middle", "ring", "pinky")
    ]
    assert all(
        first.y > second.y
        for first, second in zip(ordered_fingers, ordered_fingers[1:])
    ), (
        obj.name,
        "anatomical finger labels must run index-to-pinky across the hand",
        [center.y for center in ordered_fingers],
    )
    outward_sign = 1.0 if side == "L" else -1.0
    thumb_center = digit_centers[f"thumb.{side}"]
    assert outward_sign * thumb_center.x + 0.10 < min(
        outward_sign * center.x for center in ordered_fingers
    ), (
        obj.name,
        "thumb label is not spatially distinct from the four fingers",
        thumb_center,
        ordered_fingers,
    )


def canonical_section_rings(obj: bpy.types.Object) -> dict[float, list[int]]:
    rings = {
        y: [
            vertex.index
            for vertex in obj.data.vertices
            if abs(vertex.co.y - y) <= 1e-6
        ]
        for y in CANONICAL_SHOE_Y
    }
    assert all(len(ring) == 28 for ring in rings.values()), (
        obj.name,
        "radial contract",
        {key: len(value) for key, value in rings.items()},
    )
    return rings


def object_world_bounds(obj: bpy.types.Object) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return (
        tuple(min(point[axis] for point in points) for axis in range(3)),
        tuple(max(point[axis] for point in points) for axis in range(3)),
    )


def shoe_assembly_size(side: str) -> Vector:
    names = (
        f"SANIC_ShoeUpper.{side}", f"SANIC_ShoeMidsole.{side}",
        f"SANIC_ShoeOutsole.{side}", f"SANIC_ShoeStrap.{side}",
        f"SANIC_ShoeCollar.{side}", f"SANIC_ShoeHeelCounter.{side}",
    )
    points = [
        bpy.data.objects[name].matrix_world @ Vector(corner)
        for name in names
        for corner in bpy.data.objects[name].bound_box
    ]
    return Vector(tuple(
        max(point[axis] for point in points) - min(point[axis] for point in points)
        for axis in range(3)
    ))


def evaluated_world_geometry(
    obj: bpy.types.Object,
) -> tuple[list[Vector], list[tuple[int, int, int]]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
    finally:
        evaluated.to_mesh_clear()
    return points, triangles


def evaluated_world_bvh(obj: bpy.types.Object) -> BVHTree:
    points, triangles = evaluated_world_geometry(obj)
    return BVHTree.FromPolygons(points, triangles, all_triangles=True)


def robust_ray_hit(tree: BVHTree, point: Vector, direction: Vector) -> bool:
    if abs(direction.x) > 0.5:
        jitters = (
            Vector((0.0, 0.0, 0.0)),
            Vector((0.0, FOOT_CONTAINMENT_RAY_JITTER, FOOT_CONTAINMENT_RAY_JITTER)),
            Vector((0.0, -FOOT_CONTAINMENT_RAY_JITTER, -FOOT_CONTAINMENT_RAY_JITTER)),
        )
    else:
        jitters = (
            Vector((0.0, 0.0, 0.0)),
            Vector((FOOT_CONTAINMENT_RAY_JITTER, 0.0, FOOT_CONTAINMENT_RAY_JITTER)),
            Vector((-FOOT_CONTAINMENT_RAY_JITTER, 0.0, -FOOT_CONTAINMENT_RAY_JITTER)),
        )
    hits = sum(
        tree.ray_cast(point + jitter, direction, 10.0)[0] is not None
        for jitter in jitters
    )
    return hits >= 2


def projection_cover(
    trees: dict[str, BVHTree],
    point: Vector,
    directions: tuple[Vector, Vector],
) -> tuple[str, str] | None:
    """Return the covering object(s) only when both projection rays are blocked."""
    covering_names = []
    for direction in directions:
        hits = tuple(
            name
            for name, tree in trees.items()
            if robust_ray_hit(tree, point, direction)
        )
        if not hits:
            return None
        covering_names.append("|".join(
            name.removeprefix("SANIC_Shoe")
            for name in hits
        ))
    return tuple(covering_names)


def collar_aperture_measurements(
    collar: bpy.types.Object,
    collar_points: list[Vector],
    side: str,
) -> tuple[Vector, Matrix, Matrix, float, float]:
    """Measure the evaluated tilted collar frame used by the lower leg."""
    sign = 1.0 if side == "L" else -1.0
    expected_center = Vector((0.51 * sign, -0.057, 0.3535))
    stored_center = Vector(collar.get("sanic_collar_center", ()))
    assert (stored_center - expected_center).length <= 1e-6, (
        collar.name,
        "collar center metadata",
        tuple(stored_center),
        tuple(expected_center),
    )
    tilt_degrees = float(collar.get("sanic_collar_tilt_degrees", 999.0))
    assert abs(tilt_degrees - (-10.0)) <= 1e-6, (
        collar.name,
        "collar tilt metadata",
        tilt_degrees,
    )
    center = collar.matrix_world @ stored_center
    local_to_world = (
        collar.matrix_world.to_3x3()
        @ Matrix.Rotation(math.radians(tilt_degrees), 3, "X")
    )
    world_to_local = local_to_world.inverted()
    local_points = [world_to_local @ (point - center) for point in collar_points]
    radius_x = max(abs(point.x) for point in local_points)
    radius_y = max(abs(point.y) for point in local_points)
    top_z = max(point.z for point in local_points)
    assert 0.17 <= radius_x <= 0.19, (collar.name, "evaluated collar radius X", radius_x)
    assert 0.13 <= radius_y <= 0.15, (collar.name, "evaluated collar radius Y", radius_y)
    assert 0.03 <= top_z <= 0.04, (collar.name, "evaluated collar tube height", top_z)
    minimum_local_z = top_z * FOOT_CONTAINMENT_APERTURE_MIN_HEIGHT_RATIO
    return center, local_to_world, world_to_local, top_z, minimum_local_z


def collar_local_point(
    point: Vector,
    aperture: tuple[Vector, Matrix, Matrix, float, float],
) -> Vector:
    center, _, world_to_local, _, _ = aperture
    return world_to_local @ (point - center)


def point_is_above_collar(
    point: Vector,
    aperture: tuple[Vector, Matrix, Matrix, float, float],
) -> bool:
    local = collar_local_point(point, aperture)
    return local.z >= aperture[3] - FOOT_CONTAINMENT_COLLAR_TOP_EPSILON


def point_emerges_through_collar_aperture(
    point: Vector,
    aperture: tuple[Vector, Matrix, Matrix, float, float],
    collar_tree: BVHTree,
) -> bool:
    """Allow only points before the evaluated torus's first inner-surface hit."""
    center, local_to_world, _, top_z, minimum_local_z = aperture
    local = collar_local_point(point, aperture)
    if not minimum_local_z <= local.z < top_z - FOOT_CONTAINMENT_COLLAR_TOP_EPSILON:
        return False
    radial = Vector((local.x, local.y, 0.0))
    if radial.length <= FOOT_CONTAINMENT_INNER_RAY_EPSILON:
        return True
    origin = center + local_to_world @ Vector((0.0, 0.0, local.z))
    direction = (local_to_world @ radial.normalized()).normalized()
    hit = collar_tree.ray_cast(origin, direction, 1.0)
    assert hit[0] is not None, (
        "evaluated collar inner ray missed",
        tuple(point),
        tuple(local),
    )
    point_distance = (point - origin).length
    return point_distance <= hit[3] + FOOT_CONTAINMENT_INNER_RAY_EPSILON


def validate_hidden_foot_containment(body: bpy.types.Object, side: str) -> None:
    sign = 1.0 if side == "L" else -1.0
    visible_names = (
        f"SANIC_ShoeUpper.{side}",
        f"SANIC_ShoeMidsole.{side}",
        f"SANIC_ShoeOutsole.{side}",
        f"SANIC_ShoeCollar.{side}",
    )
    visible_trees = {
        name: evaluated_world_bvh(bpy.data.objects[name])
        for name in visible_names
    }
    upper_tree = visible_trees[f"SANIC_ShoeUpper.{side}"]
    collar = bpy.data.objects[f"SANIC_ShoeCollar.{side}"]
    collar_points, _ = evaluated_world_geometry(collar)
    aperture = collar_aperture_measurements(collar, collar_points, side)
    body_points, _ = evaluated_world_geometry(body)
    side_points = [
        point
        for point in body_points
        if sign * point.x > 0.26
    ]
    above_collar = [
        point
        for point in side_points
        if point_is_above_collar(point, aperture)
    ]
    candidates = [
        point
        for point in side_points
        if not point_is_above_collar(point, aperture)
    ]
    assert candidates, (body.name, side, "missing hidden-foot candidates")

    x_directions = (Vector((1.0, 0.0, 0.0)), Vector((-1.0, 0.0, 0.0)))
    y_directions = (Vector((0.0, 1.0, 0.0)), Vector((0.0, -1.0, 0.0)))
    counts: defaultdict[str, int] = defaultdict(int)
    counts["above-collar-lower-leg"] = len(above_collar)
    failures = []
    for point in candidates:
        inside_upper = all(
            robust_ray_hit(upper_tree, point, direction)
            for direction in x_directions
        )
        if inside_upper:
            counts["inside:ShoeUpper"] += 1
            continue
        side_cover = projection_cover(visible_trees, point, x_directions)
        front_cover = projection_cover(visible_trees, point, y_directions)
        if side_cover is not None and front_cover is not None:
            counts[f"side:{'/'.join(side_cover)}"] += 1
            counts[f"front:{'/'.join(front_cover)}"] += 1
            continue
        if point_emerges_through_collar_aperture(
            point,
            aperture,
            visible_trees[f"SANIC_ShoeCollar.{side}"],
        ):
            counts["collar-inner-opening"] += 1
            continue
        failures.append((
            tuple(round(value, 6) for value in point),
            side_cover,
            front_cover,
        ))

    diagnostics = {
        "side": side,
        "side_points": len(side_points),
        "above_collar": len(above_collar),
        "candidates": len(candidates),
        "covered": len(candidates) - len(failures),
        "failures": len(failures),
        "cover_counts": dict(sorted(counts.items())),
    }
    print("SANIC_HIDDEN_FOOT_CONTAINMENT", diagnostics)
    assert not failures, (
        body.name,
        "hidden foot containment",
        diagnostics,
        failures[:8],
    )


def strap_station_clearances(strap: bpy.types.Object, upper: bpy.types.Object) -> tuple[float, ...]:
    upper_points, upper_triangles = evaluated_world_geometry(upper)
    strap_points, strap_triangles = evaluated_world_geometry(strap)
    upper_tree = BVHTree.FromPolygons(upper_points, upper_triangles, all_triangles=True)
    strap_tree = BVHTree.FromPolygons(strap_points, strap_triangles, all_triangles=True)
    assert not strap_tree.overlap(upper_tree), f"{strap.name} intersects {upper.name}"
    minimum_x = min(point.x for point in strap_points)
    maximum_x = max(point.x for point in strap_points)
    width = maximum_x - minimum_x
    assert width > 0.3 * SHOE_WIDTH_SCALE, (strap.name, width)
    stations: list[list[float]] = [[] for _ in range(5)]
    for point in strap_points:
        normalized = max(0.0, min(1.0, (point.x - minimum_x) / width))
        station = min(4, int(normalized * 5.0))
        nearest = upper_tree.find_nearest(point)
        assert nearest is not None
        stations[station].append(nearest[3])
    assert all(station for station in stations), (strap.name, [len(station) for station in stations])
    return tuple(min(station) for station in stations)


def validate_footwear(side: str) -> None:
    upper = bpy.data.objects[f"SANIC_ShoeUpper.{side}"]
    midsole = bpy.data.objects[f"SANIC_ShoeMidsole.{side}"]
    outsole = bpy.data.objects[f"SANIC_ShoeOutsole.{side}"]
    strap = bpy.data.objects[f"SANIC_ShoeStrap.{side}"]
    collar = bpy.data.objects[f"SANIC_ShoeCollar.{side}"]
    counter = bpy.data.objects[f"SANIC_ShoeHeelCounter.{side}"]

    assembly_size = shoe_assembly_size(side)
    assembly_ratios = Vector(tuple(
        assembly_size[axis] / AUDITED_SHOE_ASSEMBLY_SIZE[axis]
        for axis in range(3)
    ))
    assert all(
        SHOE_FOOTPRINT_RATIO_RANGE[0] <= assembly_ratios[axis] <= SHOE_FOOTPRINT_RATIO_RANGE[1]
        for axis in (0, 1)
    ), (side, "shoe footprint ratios", tuple(assembly_ratios), tuple(assembly_size))
    assert SHOE_HEIGHT_RATIO_RANGE[0] <= assembly_ratios.z <= SHOE_HEIGHT_RATIO_RANGE[1], (
        side,
        "shoe height ratio",
        tuple(assembly_ratios),
        tuple(assembly_size),
    )

    for shell in (upper, midsole, outsole):
        assert shell.type == "MESH", (shell.name, shell.type)
        rings = canonical_section_rings(shell)
        support_counts = {
            y: sum(abs(vertex.co.y - y) <= 1e-6 for vertex in shell.data.vertices)
            for y in SUPPORT_SHOE_Y
        }
        assert all(count == 28 for count in support_counts.values()), (
            shell.name,
            "rounded terminal support-ring contract",
            support_counts,
        )
        ring_bottoms = {
            y: min(shell.data.vertices[index].co.z for index in ring)
            for y, ring in rings.items()
        }
        assert ring_bottoms[-0.660] - min(
            ring_bottoms[y] for y in (-0.252, -0.420)
        ) >= 0.042, (
            shell.name,
            "toe spring",
            ring_bottoms,
        )
        minimum_y = min(vertex.co.y for vertex in shell.data.vertices)
        maximum_y = max(vertex.co.y for vertex in shell.data.vertices)
        assert sum(abs(vertex.co.y - minimum_y) <= 1e-6 for vertex in shell.data.vertices) <= 2
        assert sum(abs(vertex.co.y - maximum_y) <= 1e-6 for vertex in shell.data.vertices) <= 2

    upper_rings = canonical_section_rings(upper)
    widths = {
        y: max(upper.data.vertices[index].co.x for index in upper_rings[y])
        - min(upper.data.vertices[index].co.x for index in upper_rings[y])
        for y in (0.060, -0.420, -0.660)
    }
    assert widths[-0.420] > 1.20 * widths[0.060], (upper.name, "formed last", widths)
    assert widths[-0.660] < 0.90 * widths[-0.420], (upper.name, "rounded toe taper", widths)

    expected_materials = {
        upper.name: "SANIC_MAT_Red",
        midsole.name: "SANIC_MAT_Midsole",
        outsole.name: "SANIC_MAT_Sole",
        strap.name: "SANIC_MAT_White",
        collar.name: "SANIC_MAT_White",
        counter.name: "SANIC_MAT_Red",
    }
    for name, expected in expected_materials.items():
        actual = {material.name for material in bpy.data.objects[name].data.materials}
        assert expected in actual, (name, actual, expected)

    counter_bounds = object_world_bounds(counter)
    counter_y_span = counter_bounds[1][1] - counter_bounds[0][1]
    assert counter_y_span <= 0.072, (
        counter.name,
        "heel counter is a projecting wedge instead of a rear-hugging wrap",
        counter_y_span,
    )
    counter_points, _ = evaluated_world_geometry(counter)
    upper_points, upper_triangles = evaluated_world_geometry(upper)
    upper_tree = BVHTree.FromPolygons(upper_points, upper_triangles, all_triangles=True)
    counter_projection = max(upper_tree.find_nearest(point)[3] for point in counter_points)
    assert counter_projection <= 0.085 * SHOE_HEIGHT_SCALE, (
        counter.name,
        "heel counter projects too far from upper",
        counter_projection,
    )

    upper_bounds = object_world_bounds(upper)
    midsole_bounds = object_world_bounds(midsole)
    outsole_bounds = object_world_bounds(outsole)
    assert outsole_bounds[0][2] <= 0.0084, (outsole.name, "ground contact", outsole_bounds)
    upper_width = upper_bounds[1][0] - upper_bounds[0][0]
    upper_height = upper_bounds[1][2] - upper_bounds[0][2]
    assert upper_height / upper_width >= 0.30, (
        upper.name,
        "upper is slab-like",
        upper_height,
        upper_width,
    )
    assert outsole_bounds[1][2] < midsole_bounds[1][2] < upper_bounds[1][2], (
        side,
        "shoe layers are not vertically ordered",
        outsole_bounds,
        midsole_bounds,
        upper_bounds,
    )
    clearances = strap_station_clearances(strap, upper)
    assert all(0.003 <= clearance <= 0.018001 for clearance in clearances), (
        strap.name,
        "five-station strap clearance",
        clearances,
    )

    outsole_rings = canonical_section_rings(outsole)
    main_bottom = min(
        outsole.data.vertices[index].co.z
        for ring in outsole_rings.values()
        for index in ring
    )
    tread_projection = main_bottom - outsole_bounds[0][2]
    assert 0.010 * SHOE_HEIGHT_SCALE <= tread_projection <= 0.025 * SHOE_HEIGHT_SCALE, (
        outsole.name,
        "tread projection",
        tread_projection,
    )
    outsole_adjacency = mesh_adjacency(outsole.data)
    assert connected_component_count(outsole_adjacency, set(outsole_adjacency)) == 7, (
        outsole.name,
        "three ribs and three-piece raised heel edge must be joined into the outsole object",
    )

    assert_closed_all_quad_mesh(collar, minimum_vertices=256)
    vertices = len(collar.data.vertices)
    edges = len(collar.data.edges)
    faces = len(collar.data.polygons)
    assert (vertices, faces) == (256, 256), (collar.name, vertices, faces)
    assert vertices - edges + faces == 0, (
        collar.name,
        "padded collar must retain one clean opening",
        (vertices, edges, faces),
    )


def validate_task3_geometry() -> None:
    objects = set(bpy.data.objects.keys())
    validate_face_geometry()
    forbidden = object_names_rooted_at(
        objects,
        FORBIDDEN_PLACEHOLDER_OBJECTS,
        include_exact=True,
    )
    assert not forbidden, f"Forbidden glove/footwear placeholders remain: {sorted(forbidden)}"
    duplicates = object_names_rooted_at(objects, TASK3_OBJECTS, include_exact=False)
    assert not duplicates, f"Duplicate Task 3 object roots remain: {sorted(duplicates)}"
    missing = TASK3_OBJECTS - objects
    assert not missing, f"Missing Task 3 objects: {sorted(missing)}"
    body = bpy.data.objects.get("SANIC_BodySculpt")
    assert body is not None, "Missing SANIC_BodySculpt"
    assert tuple(round(value, 2) for value in body.get("sanic_hidden_foot_scale", ())) == (
        0.60,
        0.60,
        0.70,
    ), body.get("sanic_hidden_foot_scale")
    assert abs(float(body.get("sanic_hidden_foot_pivot_y", 999.0)) - (-0.30)) <= 1e-6, (
        body.get("sanic_hidden_foot_pivot_y"),
        "hidden-foot cage must share the scaled footwear Y pivot",
    )
    assert abs(float(body.get("sanic_hidden_foot_pivot_z", 999.0)) - 0.34) <= 1e-6, (
        body.get("sanic_hidden_foot_pivot_z"),
        "hidden-foot cage must retain the seated source-body Z pivot",
    )
    assert_closed_all_quad_mesh(body, minimum_vertices=5_000)
    assert all(polygon.use_smooth for polygon in body.data.polygons)
    assert body.data.attributes.get(".sculpt_face_set") is None, (
        "Source face sets must be consumed only after both hand regions are preserved"
    )
    for side in ("L", "R"):
        validate_glove_shell(side)
        validate_footwear(side)
        validate_hidden_foot_containment(body, side)
    source = list(bpy.data.collections["SANIC_SOURCE_HIGH"].all_objects)
    source_triangles = evaluated_triangle_count(source)
    assert 350_000 <= source_triangles <= 600_000, source_triangles
    print({"mode": "task3-neutral", "source_triangles": source_triangles})


ANIMATION_FORWARD = Vector((0.0, -1.0, 0.0))
ANIMATION_UP = Vector((0.0, 0.0, 1.0))
ANIMATION_LATERAL = Vector((1.0, 0.0, 0.0))


def pose_world_point(
    rig: bpy.types.Object,
    bone_name: str,
    endpoint: str,
) -> Vector:
    pose_bone = rig.pose.bones[bone_name]
    point = pose_bone.head if endpoint == "head" else pose_bone.tail
    return rig.matrix_world @ point


def pose_snapshot(rig: bpy.types.Object, frame: int) -> dict[str, object]:
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    points = {
        name: {
            "head": pose_world_point(rig, name, "head"),
            "tail": pose_world_point(rig, name, "tail"),
        }
        for name in (
            "root", "hips", "spine", "chest", "neck", "head",
            "upper_arm.L", "upper_arm.R", "lower_arm.L", "lower_arm.R",
            "hand.L", "hand.R",
            "upper_leg.L", "upper_leg.R", "lower_leg.L", "lower_leg.R",
            "foot.L", "foot.R",
        )
    }
    world_rotation = rig.matrix_world.to_3x3()
    axes = {
        name: (
            world_rotation
            @ (rig.pose.bones[name].matrix.to_3x3() @ Vector((1.0, 0.0, 0.0)))
        ).normalized()
        for name in ("hips", "chest")
    }
    return {"points": points, "axes": axes}


def joint_angle(first: Vector, joint: Vector, third: Vector) -> float:
    return math.degrees((first - joint).angle(third - joint))


def signed_sagittal_angle(vector: Vector, vertical: Vector) -> float:
    return math.degrees(math.atan2(vector.dot(ANIMATION_FORWARD), vector.dot(vertical)))


def yaw_degrees(axis: Vector) -> float:
    return math.degrees(math.atan2(axis.dot(ANIMATION_FORWARD), axis.dot(ANIMATION_LATERAL)))


def action_fcurves(action: bpy.types.Action) -> list[bpy.types.FCurve]:
    """Return curves from both legacy and Blender 5 layered Actions."""
    curves: list[bpy.types.FCurve] = []
    seen: set[int] = set()
    for curve in getattr(action, "fcurves", ()):
        pointer = curve.as_pointer()
        if pointer not in seen:
            seen.add(pointer)
            curves.append(curve)
    for layer in getattr(action, "layers", ()):
        for strip in layer.strips:
            for channelbag in getattr(strip, "channelbags", ()):
                for curve in channelbag.fcurves:
                    pointer = curve.as_pointer()
                    if pointer not in seen:
                        seen.add(pointer)
                        curves.append(curve)
    return curves


def validate_action_contract() -> None:
    actions = set(bpy.data.actions.keys())
    assert actions == CHARACTER_ACTIONS, (
        "exact animation clips",
        sorted(actions),
        sorted(CHARACTER_ACTIONS),
    )
    assert bpy.context.scene.render.fps == 30
    assert abs(bpy.context.scene.render.fps_base - 1.0) <= 1e-9
    actual_ranges = {
        name: tuple(int(value) for value in bpy.data.actions[name].frame_range)
        for name in sorted(CHARACTER_ACTIONS)
    }
    assert actual_ranges == ACTION_FRAME_RANGES, (
        "exact action frame ranges",
        actual_ranges,
        ACTION_FRAME_RANGES,
    )
    assert all(bpy.data.actions[name].use_frame_range for name in CHARACTER_ACTIONS)
    durations = {
        name: (frame_range[1] - frame_range[0]) / 30.0
        for name, frame_range in actual_ranges.items()
    }
    assert abs(durations["Run"] - (20.0 / 30.0)) <= 1e-9, durations
    assert abs(durations["Jump"] - (29.0 / 30.0)) <= 1e-9, durations
    invalid_channels: dict[str, list[str]] = {}
    sparse_channels: dict[str, list[tuple[str, int, int]]] = {}
    for name in sorted(CHARACTER_ACTIONS):
        action = bpy.data.actions[name]
        curves = action_fcurves(action)
        paths = sorted({curve.data_path for curve in curves})
        invalid = [
            path
            for path in paths
            if not path.startswith('pose.bones["')
            or not (
                path.endswith(".rotation_quaternion")
                or path == 'pose.bones["root"].location'
            )
        ]
        if invalid:
            invalid_channels[name] = invalid
        expected_frames = set(range(ACTION_FRAME_RANGES[name][0], ACTION_FRAME_RANGES[name][1] + 1))
        sparse = []
        for curve in curves:
            keyed_frames = {int(round(point.co.x)) for point in curve.keyframe_points}
            if keyed_frames != expected_frames:
                sparse.append((curve.data_path, curve.array_index, len(keyed_frames)))
        if sparse:
            sparse_channels[name] = sparse
    assert not invalid_channels, (
        "actions must use spatially-authored pose-bone quaternions and bounded root motion only",
        invalid_channels,
    )
    assert not sparse_channels, (
        "every spatial channel must be solved and keyed on every integer action frame",
        sparse_channels,
    )


def validate_run_kinematics(rig: bpy.types.Object) -> None:
    previous_action = rig.animation_data.action if rig.animation_data else None
    previous_frame = bpy.context.scene.frame_current
    rig.animation_data_create()
    rest_root = rig.matrix_world @ rig.data.bones["root"].head_local
    rig.animation_data.action = bpy.data.actions["Run"]
    try:
        samples = {frame: pose_snapshot(rig, frame) for frame in range(1, 22)}
    finally:
        rig.animation_data.action = previous_action
        bpy.context.scene.frame_set(previous_frame)
        bpy.context.view_layer.update()

    problems: list[object] = []
    lateral_metrics: list[tuple[int, str, float, float, float]] = []
    root_deltas: list[tuple[int, float, float, float]] = []
    for frame, sample in samples.items():
        points = sample["points"]
        root = points["root"]["head"]
        root_delta = root - rest_root
        root_lateral = root_delta.dot(ANIMATION_LATERAL)
        root_forward = root_delta.dot(ANIMATION_FORWARD)
        root_up = root_delta.dot(ANIMATION_UP)
        root_deltas.append((frame, root_lateral, root_forward, root_up))
        if abs(root_lateral) > 0.02 or abs(root_forward) > 0.08 or abs(root_up) > 0.08:
            problems.append((
                "Run root body-mechanics cap",
                frame,
                root_lateral,
                root_forward,
                root_up,
            ))
        torso = points["chest"]["tail"] - points["chest"]["head"]
        torso_lean = signed_sagittal_angle(torso, ANIMATION_UP)
        if not 8.0 <= torso_lean <= 12.0:
            problems.append(("all-frame forward torso lean", frame, torso_lean))
        shoulder_half_width = 0.5 * (
            points["upper_arm.L"]["head"].x - points["upper_arm.R"]["head"].x
        )
        lower_bound = 0.55 * shoulder_half_width
        upper_bound = 1.65 * shoulder_half_width
        for side, sign in (("L", 1.0), ("R", -1.0)):
            wrist = points[f"lower_arm.{side}"]["tail"]
            signed_lateral = sign * (wrist.x - root.x)
            lateral_metrics.append((frame, side, signed_lateral, lower_bound, upper_bound))
            if not lower_bound <= signed_lateral <= upper_bound:
                problems.append(("wrist lateral bound", frame, side, signed_lateral, lower_bound, upper_bound))

            shoulder = points[f"upper_arm.{side}"]["head"]
            elbow = points[f"lower_arm.{side}"]["head"]
            wrist = points[f"lower_arm.{side}"]["tail"]
            upper_vector = elbow - shoulder
            elbow_angle = joint_angle(shoulder, elbow, wrist)
            abduction = math.degrees(math.atan2(
                abs(upper_vector.dot(ANIMATION_LATERAL)),
                max((upper_vector - ANIMATION_LATERAL * upper_vector.dot(ANIMATION_LATERAL)).length, 1e-9),
            ))
            if not 70.0 <= elbow_angle <= 110.0:
                problems.append(("all-frame elbow flexion", frame, side, elbow_angle))
            if abduction > 12.0:
                problems.append(("all-frame shoulder abduction", frame, side, abduction))
    vertical_values = [row[3] for row in root_deltas]
    if max(vertical_values) - min(vertical_values) < 0.02 or max(vertical_values) - min(vertical_values) > 0.10:
        problems.append(("subtle vertical COM bob", min(vertical_values), max(vertical_values)))

    contact_metrics: dict[int, dict[str, object]] = {}
    for frame in (1, 11):
        sample = samples[frame]
        points = sample["points"]
        wrists = {
            side: points[f"lower_arm.{side}"]["tail"]
            for side in ("L", "R")
        }
        knees = {
            side: points[f"lower_leg.{side}"]["head"]
            for side in ("L", "R")
        }
        hand_delta = (wrists["L"] - wrists["R"]).dot(ANIMATION_FORWARD)
        knee_delta = (knees["L"] - knees["R"]).dot(ANIMATION_FORWARD)
        if abs(hand_delta) < 0.55 or abs(knee_delta) < 0.55 or hand_delta * knee_delta >= 0.0:
            problems.append(("contralateral arm-leg phase", frame, hand_delta, knee_delta))

        arm_angles: dict[str, float] = {}
        elbow_angles: dict[str, float] = {}
        abduction_angles: dict[str, float] = {}
        thigh_angles: dict[str, float] = {}
        knee_angles: dict[str, float] = {}
        for side in ("L", "R"):
            shoulder = points[f"upper_arm.{side}"]["head"]
            elbow = points[f"lower_arm.{side}"]["head"]
            wrist = points[f"lower_arm.{side}"]["tail"]
            upper_vector = elbow - shoulder
            arm_angles[side] = signed_sagittal_angle(upper_vector, -ANIMATION_UP)
            elbow_angles[side] = joint_angle(shoulder, elbow, wrist)
            abduction_angles[side] = math.degrees(math.atan2(
                abs(upper_vector.dot(ANIMATION_LATERAL)),
                max((upper_vector - ANIMATION_LATERAL * upper_vector.x).length, 1e-9),
            ))
            hip = points[f"upper_leg.{side}"]["head"]
            knee = points[f"lower_leg.{side}"]["head"]
            ankle = points[f"lower_leg.{side}"]["tail"]
            thigh_angles[side] = signed_sagittal_angle(knee - hip, -ANIMATION_UP)
            knee_angles[side] = joint_angle(hip, knee, ankle)

        if not all(35.0 <= abs(value) <= 50.0 for value in arm_angles.values()):
            problems.append(("upper-arm sagittal swing", frame, arm_angles))
        if not all(75.0 <= value <= 105.0 for value in elbow_angles.values()):
            problems.append(("elbow flexion", frame, elbow_angles))
        if not all(value <= 12.0 for value in abduction_angles.values()):
            problems.append(("shoulder abduction", frame, abduction_angles))
        ordered_thighs = sorted(thigh_angles.values())
        if not (-35.0 <= ordered_thighs[0] <= -25.0 and 45.0 <= ordered_thighs[1] <= 55.0):
            problems.append(("lead/rear thigh swing", frame, thigh_angles))
        lead_side = max(thigh_angles, key=thigh_angles.get)
        if not 140.0 <= knee_angles[lead_side] <= 165.0:
            problems.append(("contact lead-knee extension", frame, lead_side, knee_angles[lead_side]))

        torso = points["chest"]["tail"] - points["chest"]["head"]
        torso_lean = signed_sagittal_angle(torso, ANIMATION_UP)
        pelvis_yaw = yaw_degrees(sample["axes"]["hips"])
        chest_yaw = yaw_degrees(sample["axes"]["chest"])
        if not 8.0 <= torso_lean <= 12.0:
            problems.append(("forward torso lean", frame, torso_lean))
        if not 4.0 <= abs(pelvis_yaw) <= 6.0:
            problems.append(("pelvis yaw", frame, pelvis_yaw))
        if not 6.0 <= abs(chest_yaw) <= 8.0 or pelvis_yaw * chest_yaw >= 0.0:
            problems.append(("counter chest yaw", frame, pelvis_yaw, chest_yaw))
        contact_metrics[frame] = {
            "hand_delta": hand_delta,
            "knee_delta": knee_delta,
            "arm_angles": arm_angles,
            "elbows": elbow_angles,
            "thigh_angles": thigh_angles,
            "knees": knee_angles,
            "torso_lean": torso_lean,
            "pelvis_yaw": pelvis_yaw,
            "chest_yaw": chest_yaw,
        }
    if contact_metrics[1]["hand_delta"] * contact_metrics[11]["hand_delta"] >= 0.0:
        problems.append(("run contacts do not alternate", contact_metrics))
    if contact_metrics[1]["pelvis_yaw"] * contact_metrics[11]["pelvis_yaw"] >= 0.0:
        problems.append(("pelvis yaw does not reverse across contacts", contact_metrics))
    if contact_metrics[1]["chest_yaw"] * contact_metrics[11]["chest_yaw"] >= 0.0:
        problems.append(("chest yaw does not reverse across contacts", contact_metrics))

    passing_metrics: dict[int, dict[str, float | str]] = {}
    recovery_sides: list[str] = []
    for frame in (6, 16):
        points = samples[frame]["points"]
        knee_angles = {}
        for side in ("L", "R"):
            hip = points[f"upper_leg.{side}"]["head"]
            knee = points[f"lower_leg.{side}"]["head"]
            ankle = points[f"lower_leg.{side}"]["tail"]
            knee_angles[side] = joint_angle(hip, knee, ankle)
        recovery_side = min(knee_angles, key=knee_angles.get)
        support_side = "R" if recovery_side == "L" else "L"
        recovery_sides.append(recovery_side)
        if not 80.0 <= knee_angles[recovery_side] <= 105.0:
            problems.append(("passing recovery-knee flexion", frame, recovery_side, knee_angles))
        if not 125.0 <= knee_angles[support_side] <= 175.0:
            problems.append(("passing support-knee extension", frame, support_side, knee_angles))
        passing_metrics[frame] = {
            "recovery_side": recovery_side,
            "recovery_knee": knee_angles[recovery_side],
            "support_knee": knee_angles[support_side],
        }
    if recovery_sides[0] == recovery_sides[1]:
        problems.append(("passing recovery leg does not alternate", passing_metrics))

    for bone_name in (
        "root", "hips", "spine", "chest", "neck", "head",
        "upper_arm.L", "upper_arm.R", "lower_arm.L", "lower_arm.R", "hand.L", "hand.R",
        "upper_leg.L", "upper_leg.R", "lower_leg.L", "lower_leg.R", "foot.L", "foot.R",
    ):
        for endpoint in ("head", "tail"):
            distance = (
                samples[1]["points"][bone_name][endpoint]
                - samples[21]["points"][bone_name][endpoint]
            ).length
            if distance > 1e-4:
                problems.append(("run loop continuity", bone_name, endpoint, distance))
    assert not problems, (
        "Run biomechanical kinematics",
        problems[:24],
        {
            "contacts": contact_metrics,
            "passing": passing_metrics,
            "wrist_bounds": lateral_metrics[:4],
            "root_deltas": root_deltas,
        },
    )
    print({"mode": "run-kinematics", "contacts": contact_metrics, "passing": passing_metrics})


def validate_jump_kinematics(rig: bpy.types.Object) -> None:
    previous_action = rig.animation_data.action if rig.animation_data else None
    previous_frame = bpy.context.scene.frame_current
    rig.animation_data_create()
    rest_root = rig.matrix_world @ rig.data.bones["root"].head_local
    rig.animation_data.action = bpy.data.actions["Jump"]
    try:
        samples = {frame: pose_snapshot(rig, frame) for frame in range(1, 31)}
    finally:
        rig.animation_data.action = previous_action
        bpy.context.scene.frame_set(previous_frame)
        bpy.context.view_layer.update()

    problems: list[object] = []
    root_deltas: list[tuple[int, float, float, float]] = []
    for frame, sample in samples.items():
        root = sample["points"]["root"]["head"]
        delta = root - rest_root
        lateral = delta.dot(ANIMATION_LATERAL)
        forward = delta.dot(ANIMATION_FORWARD)
        vertical = delta.dot(ANIMATION_UP)
        root_deltas.append((frame, lateral, forward, vertical))
        if abs(lateral) > 0.02 or abs(forward) > 0.08 or abs(vertical) > 0.08:
            problems.append(("Jump root body-mechanics cap", frame, lateral, forward, vertical))

    peak = samples[17]["points"]
    forward_knees: dict[str, float] = {}
    knee_angles: dict[str, float] = {}
    for side in ("L", "R"):
        hip = peak[f"upper_leg.{side}"]["head"]
        knee = peak[f"lower_leg.{side}"]["head"]
        ankle = peak[f"lower_leg.{side}"]["tail"]
        forward_knees[side] = (knee - hip).dot(ANIMATION_FORWARD)
        knee_angles[side] = joint_angle(hip, knee, ankle)
    if min(forward_knees.values()) < 0.10 or max(forward_knees.values()) < 0.45:
        problems.append(("Jump apex knees forward of hips", forward_knees))
    lead_side = max(forward_knees, key=forward_knees.get)
    trail_side = "R" if lead_side == "L" else "L"
    if not 120.0 <= knee_angles[lead_side] <= 165.0:
        problems.append(("Jump lead leg partly extended", lead_side, knee_angles[lead_side]))
    if not 65.0 <= knee_angles[trail_side] <= 110.0:
        problems.append(("Jump trail leg tucked", trail_side, knee_angles[trail_side]))
    if knee_angles[lead_side] - knee_angles[trail_side] < 25.0:
        problems.append(("Jump hurdle asymmetry", knee_angles))
    assert not problems, (
        "Jump biomechanical kinematics",
        problems[:24],
        {"peak_forward_knees": forward_knees, "peak_knee_angles": knee_angles, "root_deltas": root_deltas},
    )
    print({
        "mode": "jump-kinematics",
        "peak_forward_knees": forward_knees,
        "peak_knee_angles": knee_angles,
        "root_extents": {
            "lateral": (min(row[1] for row in root_deltas), max(row[1] for row in root_deltas)),
            "forward": (min(row[2] for row in root_deltas), max(row[2] for row in root_deltas)),
            "vertical": (min(row[3] for row in root_deltas), max(row[3] for row in root_deltas)),
        },
    })


def validate_character() -> None:
    objects = set(bpy.data.objects.keys())
    missing_objects = CHARACTER_OBJECTS - objects
    missing_actions = CHARACTER_ACTIONS - set(bpy.data.actions.keys())
    assert not missing_objects, f"Missing objects: {sorted(missing_objects)}"
    validate_task3_geometry()
    assert not missing_actions, f"Missing actions: {sorted(missing_actions)}"

    body = bpy.data.objects["SANIC_BodySculpt"]
    assert body.get("sanic_base_license") == "CC0-1.0"
    assert body.get("sanic_base_source") == "Blender Studio Human Base Meshes v1.4.1"
    assert body.get("sanic_base_object") == "GEO-body_male_realistic"
    assert all(polygon.use_smooth for polygon in body.data.polygons)
    max_arm_scale = body.get("sanic_max_arm_scale")
    assert isinstance(max_arm_scale, (int, float)), max_arm_scale
    assert max_arm_scale <= 1.080001, max_arm_scale
    assert all(len(polygon.vertices) == 4 for polygon in body.data.polygons)

    rig = bpy.data.objects["SANIC_Armature"]
    actual_bones = {bone.name for bone in rig.data.bones}
    missing_bones = CHARACTER_BONES - actual_bones
    assert not missing_bones, f"Missing deformation bones: {sorted(missing_bones)}"

    validate_action_contract()
    validate_run_kinematics(rig)
    validate_jump_kinematics(rig)

    source = list(bpy.data.collections["SANIC_SOURCE_HIGH"].all_objects)
    web = list(bpy.data.collections["SANIC_WEB"].all_objects)
    source_triangles = evaluated_triangle_count(source)
    web_triangles = evaluated_triangle_count(web)
    assert 350_000 <= source_triangles <= 600_000, source_triangles
    assert 100_000 <= web_triangles <= 140_000, web_triangles

    glb_path = Path(bpy.data.filepath).parents[1] / "public/models/sanic-runner.glb"
    assert glb_path.is_file()
    assert 1_000_000 <= glb_path.stat().st_size < 5_000_000, glb_path.stat().st_size

    assert Path(bpy.data.filepath).name == "sanic-source.blend"
    print(
        {
            "mode": "character",
            "objects": len(bpy.data.objects),
            "actions": sorted(CHARACTER_ACTIONS),
            "source_triangles": source_triangles,
            "web_triangles": web_triangles,
            "glb_bytes": glb_path.stat().st_size,
        }
    )


def validate_world() -> None:
    missing_collections = WORLD_EXPORT_COLLECTIONS - set(bpy.data.collections.keys())
    assert not missing_collections, f"Missing export collections: {sorted(missing_collections)}"

    missing_objects = WORLD_OBJECTS - set(bpy.data.objects.keys())
    assert not missing_objects, f"Missing world objects: {sorted(missing_objects)}"

    suffixed_duplicates = {
        obj.name
        for obj in bpy.data.objects
        if any(obj.name.startswith(f"{required}.") for required in WORLD_OBJECTS)
    }
    assert not suffixed_duplicates, f"Suffixed duplicate world roots: {sorted(suffixed_duplicates)}"

    required = [bpy.data.objects[name] for name in sorted(WORLD_OBJECTS)]
    wrong_types = {obj.name: obj.type for obj in required if obj.type != "MESH"}
    assert not wrong_types, f"World roots must be Mesh objects: {wrong_types}"
    parented = sorted(obj.name for obj in required if obj.parent is not None)
    assert not parented, f"World roots must be unparented: {parented}"

    missing_uvs = sorted(obj.name for obj in required if not obj.data.uv_layers)
    assert not missing_uvs, f"World roots missing UV maps: {missing_uvs}"
    negative_scales = {
        obj.name: tuple(round(value, 6) for value in obj.scale)
        for obj in required
        if any(value < 0.0 for value in obj.scale)
    }
    assert not negative_scales, f"Negative world-root scales: {negative_scales}"
    unapplied_scales = {
        obj.name: tuple(round(value, 6) for value in obj.scale)
        for obj in required
        if any(abs(value - 1.0) > 1e-5 for value in obj.scale)
    }
    assert not unapplied_scales, f"World-root scales are not applied: {unapplied_scales}"

    exported: list[bpy.types.Object] = []
    for collection_name in sorted(WORLD_EXPORT_COLLECTIONS):
        exported.extend(bpy.data.collections[collection_name].all_objects)
    exported_unique = list({obj.name: obj for obj in exported}.values())
    exported_names = {obj.name for obj in exported_unique}
    assert exported_names == WORLD_OBJECTS, (
        f"Export collection contract mismatch; missing={sorted(WORLD_OBJECTS - exported_names)}, "
        f"extra={sorted(exported_names - WORLD_OBJECTS)}"
    )
    triangles = evaluated_triangle_count(exported_unique)
    assert triangles < 120_000, f"World export triangle count is {triangles}"
    assert Path(bpy.data.filepath).name == "world-source.blend"
    print(
        {
            "mode": "world",
            "objects": sorted(exported_names),
            "triangles": triangles,
        }
    )


def main() -> None:
    args = arguments_after_separator()
    assert len(args) == 1 and args[0] in {"character", "world", "task3-neutral"}, (
        "Expected exactly one validation mode after '--': character, world, or task3-neutral"
    )
    if args[0] == "character":
        validate_character()
    elif args[0] == "task3-neutral":
        validate_task3_geometry()
    else:
        validate_world()


if __name__ == "__main__":
    main()
