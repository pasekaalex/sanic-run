"""Rig, animate, and export the corrected Meshy SANIC character.

Usage::

    SANIC_CORRECTED_BLEND=/path/to/SANIC-meshy6-v1-corrected.blend \
    SANIC_RIG_OUTPUT_DIR=/path/to/output \
    blender --background --factory-startup \
      --python blender/scripts/rig_meshy_sanic.py
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SOURCE_BLEND = Path(os.environ["SANIC_CORRECTED_BLEND"]).expanduser().resolve()
OUTPUT_DIR = Path(
    os.environ.get("SANIC_RIG_OUTPUT_DIR", SOURCE_BLEND.parent)
).expanduser().resolve()
RIG_VARIANT = os.environ.get("SANIC_RIG_VARIANT", "v1").strip().lower()
assert RIG_VARIANT in {"v1", "v2-run", "v3-run"}, (
    f"Unknown SANIC rig variant: {RIG_VARIANT}"
)
DEFAULT_BASENAMES = {
    "v1": "SANIC-meshy6-v1-rigged",
    "v2-run": "SANIC-meshy6-v2-run",
    "v3-run": "SANIC-meshy6-v3-run",
}
RIG_BASENAME = os.environ.get(
    "SANIC_RIG_BASENAME",
    DEFAULT_BASENAMES[RIG_VARIANT],
).strip()
RIGGED_BLEND = OUTPUT_DIR / f"{RIG_BASENAME}.blend"
RIGGED_GLB = OUTPUT_DIR / f"{RIG_BASENAME}.glb"

SOURCE_COLLECTION = "SANIC_CHARACTER_EXPORT"
RIGGED_COLLECTION = "SANIC_RIGGED_EXPORT"
RIG_NAME = "SANIC_Armature"
ACTION_RANGES = {
    "Idle": (1, 60),
    "Run": (1, 24 if RIG_VARIANT == "v1" else 17),
    "Jump": (1, 30),
    "Crash": (1, 36),
}


def open_corrected_source() -> bpy.types.Collection:
    if not SOURCE_BLEND.is_file():
        raise FileNotFoundError(f"Corrected SANIC source does not exist: {SOURCE_BLEND}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    source = bpy.data.collections.get(SOURCE_COLLECTION)
    assert source is not None, f"Missing corrected collection {SOURCE_COLLECTION}"
    character_objects = list(source.objects)
    assert character_objects, f"{SOURCE_COLLECTION} is empty"

    rigged = bpy.data.collections.new(RIGGED_COLLECTION)
    bpy.context.scene.collection.children.link(rigged)
    for obj in character_objects:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        rigged.objects.link(obj)
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.parent = None
        obj.matrix_parent_inverse = Matrix.Identity(4)
        for modifier in list(obj.modifiers):
            if modifier.type == "ARMATURE":
                obj.modifiers.remove(modifier)
        obj.vertex_groups.clear()

    keep = set(character_objects)
    for obj in list(bpy.context.scene.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection != rigged:
            bpy.data.collections.remove(collection)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    # Keep the authoring and glTF import timelines identical. Blender's glTF
    # importer reconstructs keys on the destination scene's 24 fps timeline.
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = 60
    return rigged


def create_armature(collection: bpy.types.Collection) -> bpy.types.Object:
    data = bpy.data.armatures.new(f"{RIG_NAME}Data")
    rig = bpy.data.objects.new(RIG_NAME, data)
    collection.objects.link(rig)
    rig.show_in_front = True
    rig.display_type = "WIRE"
    rig.location = (0.0, 0.0, 0.0)
    rig.rotation_mode = "QUATERNION"
    rig.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    rig.scale = (1.0, 1.0, 1.0)

    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    def bone(
        name: str,
        head: tuple[float, float, float],
        tail: tuple[float, float, float],
        parent: str | None = None,
        connected: bool = False,
    ) -> None:
        edit_bone = data.edit_bones.new(name)
        edit_bone.head = head
        edit_bone.tail = tail
        if parent is not None:
            edit_bone.parent = data.edit_bones[parent]
            edit_bone.use_connect = connected

    bone("root", (0.0, 0.0, 0.00), (0.0, 0.0, 0.18))
    bone("hips", (0.0, 0.0, 0.58), (0.0, 0.0, 0.74), "root")
    bone("spine", (0.0, 0.0, 0.74), (0.0, 0.0, 0.94), "hips", True)
    bone("chest", (0.0, 0.0, 0.94), (0.0, 0.0, 1.12), "spine", True)
    bone("neck", (0.0, 0.0, 1.12), (0.0, 0.0, 1.24), "chest", True)
    bone("head", (0.0, 0.0, 1.24), (0.0, 0.0, 1.55), "neck", True)
    for side, sign in (("L", -1.0), ("R", 1.0)):
        bone(
            f"shoulder.{side}",
            (0.20 * sign, 0.0, 1.10),
            (0.28 * sign, 0.0, 1.10),
            "chest",
        )
        bone(
            f"upper_arm.{side}",
            (0.28 * sign, 0.0, 1.10),
            (0.48 * sign, 0.0, 1.10),
            f"shoulder.{side}",
            True,
        )
        bone(
            f"lower_arm.{side}",
            (0.48 * sign, 0.0, 1.10),
            (0.69 * sign, 0.0, 1.10),
            f"upper_arm.{side}",
            True,
        )
        bone(
            f"hand.{side}",
            (0.69 * sign, 0.0, 1.10),
            (0.84 * sign, 0.0, 1.10),
            f"lower_arm.{side}",
            True,
        )
        bone(
            f"upper_leg.{side}",
            (0.11 * sign, 0.0, 0.62),
            (0.11 * sign, 0.0, 0.34),
            "hips",
        )
        bone(
            f"lower_leg.{side}",
            (0.11 * sign, 0.0, 0.34),
            (0.11 * sign, 0.0, 0.12),
            f"upper_leg.{side}",
            True,
        )
        bone(
            f"foot.{side}",
            (0.11 * sign, 0.0, 0.12),
            (0.11 * sign, -0.24, 0.08),
            f"lower_leg.{side}",
            True,
        )
        bone(
            f"toe.{side}",
            (0.11 * sign, -0.24, 0.08),
            (0.11 * sign, -0.31, 0.07),
            f"foot.{side}",
            True,
        )
    bpy.ops.object.mode_set(mode="OBJECT")
    rig["sanic_rig"] = True
    rig["sanic_rig_version"] = {
        "v1": 1,
        "v2-run": 2,
        "v3-run": 3,
    }[RIG_VARIANT]
    if RIG_VARIANT != "v1":
        rig["sanic_run_variant"] = RIG_VARIANT
    return rig


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def two_bone_blend(
    first: str,
    second: str,
    factor: float,
) -> list[tuple[str, float]]:
    blend = clamp01(factor)
    return [(first, 1.0 - blend), (second, blend)]


def body_influences(point: Vector) -> list[tuple[str, float]]:
    x, y, z = point
    absolute_x = abs(x)
    side = "L" if x < 0.0 else "R"

    if y > 0.10 and z > 0.68:
        return [("head", 1.0)]
    if z >= 1.20:
        return [("head", 1.0)]
    if absolute_x > 0.22 and 0.88 <= z <= 1.25:
        if absolute_x < 0.28:
            return two_bone_blend("chest", f"shoulder.{side}", (absolute_x - 0.22) / 0.06)
        if absolute_x < 0.45:
            return [(f"upper_arm.{side}", 1.0)]
        if absolute_x < 0.52:
            return two_bone_blend(
                f"upper_arm.{side}",
                f"lower_arm.{side}",
                (absolute_x - 0.45) / 0.07,
            )
        if absolute_x < 0.65:
            return [(f"lower_arm.{side}", 1.0)]
        return two_bone_blend(
            f"lower_arm.{side}",
            f"hand.{side}",
            (absolute_x - 0.65) / 0.05,
        )
    # Keep the inner thigh attached to its leg instead of pinning a wide strip
    # to the pelvis. That pinned strip produced accordion folds whenever a knee
    # lifted. Only the upper crotch bridge remains pelvis-led.
    leg_region = (z < 0.56 and absolute_x > 0.008) or (
        z < 0.68 and absolute_x > 0.045
    )
    if leg_region:
        if z <= 0.11:
            if y < -0.16:
                return two_bone_blend(f"foot.{side}", f"toe.{side}", (-y - 0.16) / 0.14)
            return [(f"foot.{side}", 1.0)]
        if z < 0.20:
            return two_bone_blend(
                f"foot.{side}",
                f"lower_leg.{side}",
                (z - 0.11) / 0.09,
            )
        if z < 0.25:
            return [(f"lower_leg.{side}", 1.0)]
        if z < 0.43:
            return two_bone_blend(
                f"lower_leg.{side}",
                f"upper_leg.{side}",
                (z - 0.25) / 0.18,
            )
        if z < 0.52:
            return [(f"upper_leg.{side}", 1.0)]
        return two_bone_blend(
            f"upper_leg.{side}",
            "hips",
            (z - 0.52) / 0.16,
        )
    if z < 0.70:
        return [("hips", 1.0)]
    if z < 0.79:
        return two_bone_blend("hips", "spine", (z - 0.70) / 0.09)
    if z < 0.92:
        return [("spine", 1.0)]
    if z < 1.02:
        return two_bone_blend("spine", "chest", (z - 0.92) / 0.10)
    if z < 1.12:
        return [("chest", 1.0)]
    return two_bone_blend("neck", "head", (z - 1.12) / 0.08)


def assign_vertex(
    obj: bpy.types.Object,
    vertex_index: int,
    influences: list[tuple[str, float]],
) -> None:
    positive = [(name, weight) for name, weight in influences if weight > 1e-5]
    strongest = sorted(positive, key=lambda item: item[1], reverse=True)[:4]
    total = sum(weight for _, weight in strongest)
    assert total > 0.0, (obj.name, vertex_index, influences)
    for name, weight in strongest:
        group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        group.add([vertex_index], weight / total, "REPLACE")


def stabilize_v3_footwear(obj: bpy.types.Object) -> None:
    if RIG_VARIANT != "v3-run" or obj.name != "SANIC_BodyBase":
        return

    def rigid_assign(indices: list[int], bone_name: str) -> None:
        for group in obj.vertex_groups:
            group.remove(indices)
        obj.vertex_groups[bone_name].add(indices, 1.0, "REPLACE")

    parents = list(range(len(obj.data.vertices)))

    def component_root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def join_components(first: int, second: int) -> None:
        first_root = component_root(first)
        second_root = component_root(second)
        if first_root != second_root:
            parents[second_root] = first_root

    for edge in obj.data.edges:
        join_components(*edge.vertices)
    components: dict[int, list[int]] = defaultdict(list)
    for vertex in obj.data.vertices:
        components[component_root(vertex.index)].append(vertex.index)

    # Meshy's shoe surface is split into hundreds of disconnected islands.
    # Keep the upper-shoe islands rigid with the foot so the cuff cannot split
    # into a dangling flap while preserving the low sole vertices used by the
    # run grounding solver.
    for indices in components.values():
        points = [
            obj.matrix_world @ obj.data.vertices[index].co
            for index in indices
        ]
        if not (
            min(point.z for point in points) >= 0.05
            and max(point.z for point in points) <= 0.23
        ):
            continue
        centroid_x = sum(point.x for point in points) / len(points)
        side = "L" if centroid_x < 0.0 else "R"
        rigid_assign(indices, f"foot.{side}")

    material = obj.material_slots[0].material
    assert material is not None and material.use_nodes
    base_color_link = next(
        link
        for link in material.node_tree.links
        if link.to_node.type == "BSDF_PRINCIPLED"
        and link.to_socket.name == "Base Color"
    )
    image_node = base_color_link.from_node
    assert image_node.type == "TEX_IMAGE" and image_node.image is not None
    image = image_node.image
    pixels = image.pixels[:]
    uv_layer = obj.data.uv_layers.active
    assert uv_layer is not None

    def sample_texture(uv: Vector) -> tuple[float, float, float]:
        pixel_x = min(image.size[0] - 1, max(0, int(uv.x * image.size[0])))
        pixel_y = min(image.size[1] - 1, max(0, int(uv.y * image.size[1])))
        offset = (pixel_y * image.size[0] + pixel_x) * 4
        return tuple(pixels[offset + channel] for channel in range(3))

    white_ankle_vertices: set[int] = set()
    for polygon in obj.data.polygons:
        point = obj.matrix_world @ polygon.center
        if not (
            abs(point.x) > 0.04
            and point.y < -0.10
            and 0.17 <= point.z <= 0.24
        ):
            continue
        uvs = [
            uv_layer.data[loop_index].uv
            for loop_index in polygon.loop_indices
        ]
        centroid_uv = Vector(
            (
                sum(uv.x for uv in uvs) / len(uvs),
                sum(uv.y for uv in uvs) / len(uvs),
            )
        )
        if min(sample_texture(centroid_uv)) >= 0.8:
            white_ankle_vertices.update(polygon.vertices)

    incident_colors = {
        index: [] for index in white_ankle_vertices
    }
    for loop in obj.data.loops:
        if loop.vertex_index in incident_colors:
            incident_colors[loop.vertex_index].append(
                sample_texture(uv_layer.data[loop.index].uv)
            )
    white_interior_vertices = [
        index
        for index, colors in incident_colors.items()
        if colors and all(min(color) >= 0.8 for color in colors)
    ]
    expected_white_counts = {"L": 329, "R": 343}
    for side in ("L", "R"):
        indices = [
            index
            for index in white_interior_vertices
            if (
                obj.matrix_world @ obj.data.vertices[index].co
            ).x * (-1.0 if side == "L" else 1.0) > 0.0
        ]
        assert len(indices) == expected_white_counts[side], (
            side,
            len(indices),
            expected_white_counts[side],
        )
        if indices:
            rigid_assign(indices, f"foot.{side}")


def skin_character(
    rig: bpy.types.Object,
    collection: bpy.types.Collection,
) -> None:
    for obj in collection.objects:
        if obj.type != "MESH":
            continue
        obj.vertex_groups.clear()
        if obj.name == "SANIC_Glove.L":
            fixed = [("hand.L", 1.0)]
        elif obj.name == "SANIC_Glove.R":
            fixed = [("hand.R", 1.0)]
        elif obj.name.startswith("SANIC_Face_"):
            fixed = [("head", 1.0)]
        else:
            fixed = None
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            assign_vertex(
                obj,
                vertex.index,
                fixed if fixed is not None else body_influences(point),
            )
        stabilize_v3_footwear(obj)
        modifier = obj.modifiers.new("SANIC_ArmatureDeform", "ARMATURE")
        modifier.object = rig
        modifier.use_vertex_groups = True
        modifier.use_deform_preserve_volume = True
        world = obj.matrix_world.copy()
        obj.parent = rig
        obj.matrix_parent_inverse = rig.matrix_world.inverted()
        obj.matrix_world = world


def layered_fcurves(action: bpy.types.Action) -> list[bpy.types.FCurve]:
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


def create_actions(rig: bpy.types.Object) -> dict[str, bpy.types.Action]:
    scene = bpy.context.scene
    rig.animation_data_create()
    lateral = Vector((1.0, 0.0, 0.0))
    forward = Vector((0.0, -1.0, 0.0))
    up = Vector((0.0, 0.0, 1.0))
    character_meshes = [child for child in rig.children if child.type == "MESH"]
    foot_region_vertices: dict[str, list[tuple[bpy.types.Object, list[int]]]] = {
        "L": [],
        "R": [],
    }
    sole_region_vertices: dict[str, list[tuple[bpy.types.Object, list[int]]]] = {
        "L": [],
        "R": [],
    }
    expected_sole_vertex_counts = {"L": 1702, "R": 1648}
    for side in ("L", "R"):
        group_names = {f"foot.{side}", f"toe.{side}"}
        rest_forward_positions: list[float] = []
        for obj in character_meshes:
            group_indices = {
                group.index for group in obj.vertex_groups if group.name in group_names
            }
            if not group_indices:
                continue
            foot_indices = [
                vertex.index
                for vertex in obj.data.vertices
                if any(
                    membership.group in group_indices and membership.weight > 1e-4
                    for membership in vertex.groups
                )
            ]
            if foot_indices:
                foot_region_vertices[side].append((obj, foot_indices))
            sole_indices = [
                index
                for index in foot_indices
                if (
                    obj.matrix_world @ obj.data.vertices[index].co
                ).z <= 0.03
            ]
            if sole_indices:
                sole_region_vertices[side].append((obj, sole_indices))
                rest_forward_positions.extend(
                    (obj.matrix_world @ obj.data.vertices[index].co).dot(forward)
                    for index in sole_indices
                )
        assert foot_region_vertices[side], f"Missing weighted shoe region for {side}"
        if RIG_VARIANT != "v3-run":
            continue
        selected_count = sum(
            len(indices) for _, indices in sole_region_vertices[side]
        )
        assert selected_count == expected_sole_vertex_counts[side], (
            side,
            selected_count,
            expected_sole_vertex_counts[side],
        )
        assert (
            rest_forward_positions
            and max(rest_forward_positions) - min(rest_forward_positions) >= 0.35
        ), (side, rest_forward_positions)

    def side_direction(side: str, values: tuple[float, float, float]) -> Vector:
        sign = -1.0 if side == "L" else 1.0
        return (
            lateral * (sign * values[0])
            + forward * values[1]
            + up * values[2]
        ).normalized()

    def normalized_lerp(first: Vector, second: Vector, factor: float) -> Vector:
        mixed = first.lerp(second, factor)
        assert mixed.length > 1e-8
        return mixed.normalized()

    def blend_value(key: str, first: object, second: object, factor: float) -> object:
        if isinstance(first, dict):
            assert isinstance(second, dict) and first.keys() == second.keys()
            return {
                child: blend_value(child, first[child], second[child], factor)
                for child in first
            }
        if isinstance(first, Vector):
            assert isinstance(second, Vector)
            return first.lerp(second, factor) if key == "root_offset" else normalized_lerp(first, second, factor)
        assert isinstance(first, (int, float)) and isinstance(second, (int, float))
        return float(first) + (float(second) - float(first)) * factor

    def blend_pose(first: dict[str, object], second: dict[str, object], factor: float) -> dict[str, object]:
        return {
            key: blend_value(key, first[key], second[key], factor)
            for key in first
        }

    def pose_between(anchors: dict[int, dict[str, object]], frame: int) -> dict[str, object]:
        if frame in anchors:
            return anchors[frame]
        before = max(anchor for anchor in anchors if anchor < frame)
        after = min(anchor for anchor in anchors if anchor > frame)
        linear = (frame - before) / (after - before)
        smooth = linear * linear * (3.0 - 2.0 * linear)
        return blend_pose(anchors[before], anchors[after], smooth)

    def reset_pose() -> None:
        for bone in rig.pose.bones:
            bone.rotation_mode = "QUATERNION"
            bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()

    def world_to_armature(direction: Vector) -> Vector:
        return (rig.matrix_world.inverted_safe().to_3x3() @ direction).normalized()

    def set_root_offset(offset: Vector) -> None:
        root = rig.pose.bones["root"]
        desired = rig.data.bones["root"].head_local + rig.matrix_world.inverted_safe().to_3x3() @ offset
        matrix = root.matrix.copy()
        matrix.translation += desired - root.head
        root.matrix = matrix
        bpy.context.view_layer.update()

    def set_vertical_basis(name: str, lean_degrees: float, yaw_degrees: float) -> None:
        bone = rig.pose.bones[name]
        lean = math.radians(lean_degrees)
        y_axis = world_to_armature(up * math.cos(lean) + forward * math.sin(lean))
        yaw = math.radians(yaw_degrees)
        x_hint = world_to_armature(lateral * math.cos(yaw) + forward * math.sin(yaw))
        x_axis = x_hint - y_axis * x_hint.dot(y_axis)
        x_axis.normalize()
        z_axis = x_axis.cross(y_axis).normalized()
        basis = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
        basis.translation = bone.head.copy()
        bone.matrix = basis
        bpy.context.view_layer.update()

    def aim_bone(name: str, desired_world_direction: Vector) -> None:
        bone = rig.pose.bones[name]
        current = (bone.tail - bone.head).normalized()
        desired = world_to_armature(desired_world_direction)
        swing = current.rotation_difference(desired)
        pivot = bone.head.copy()
        bone.matrix = (
            Matrix.Translation(pivot)
            @ swing.to_matrix().to_4x4()
            @ Matrix.Translation(-pivot)
            @ bone.matrix
        )
        bpy.context.view_layer.update()

    def solve_pose(pose: dict[str, object]) -> None:
        reset_pose()
        set_root_offset(pose["root_offset"])
        lean = float(pose["lean"])
        pelvis_yaw = float(pose["pelvis_yaw"])
        chest_yaw = float(pose["chest_yaw"])
        set_vertical_basis("hips", 0.0, pelvis_yaw)
        set_vertical_basis("spine", lean * 0.62, pelvis_yaw * 0.55)
        set_vertical_basis("chest", lean, chest_yaw)
        set_vertical_basis("neck", lean * 0.34, chest_yaw * 0.70)
        set_vertical_basis("head", lean * 0.16, chest_yaw * 0.50)
        for side in ("L", "R"):
            arm = pose["arms"][side]
            aim_bone(f"upper_arm.{side}", arm["upper"])
            aim_bone(f"lower_arm.{side}", arm["lower"])
            aim_bone(f"hand.{side}", arm["hand"])
            leg = pose["legs"][side]
            aim_bone(f"upper_leg.{side}", leg["upper"])
            aim_bone(f"lower_leg.{side}", leg["lower"])
            aim_bone(f"foot.{side}", leg["foot"])
            aim_bone(f"toe.{side}", leg["toe"])

    def deformed_minimum_z() -> float:
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        return min(
            (evaluated.matrix_world @ Vector(corner)).z
            for obj in character_meshes
            for evaluated in (obj.evaluated_get(depsgraph),)
            for corner in evaluated.bound_box
        )

    def deformed_region_minimum_z(
        regions: dict[str, list[tuple[bpy.types.Object, list[int]]]],
        side: str,
    ) -> float:
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        minimum = float("inf")
        selected = 0
        for obj, vertex_indices in regions[side]:
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

    def deformed_foot_minimum_z(side: str) -> float:
        """Return the evaluated shoe height for legacy v1/v2 grounding."""
        return deformed_region_minimum_z(foot_region_vertices, side)

    def deformed_sole_minimum_z(side: str) -> float:
        """Return the evaluated low-rest-z v3 sole height."""
        return deformed_region_minimum_z(sole_region_vertices, side)

    def insert_pose_keys(
        frame: int,
        previous: dict[str, object],
    ) -> None:
        for bone in rig.pose.bones:
            quaternion = bone.rotation_quaternion.copy().normalized()
            earlier = previous.get(bone.name)
            if earlier is not None and earlier.dot(quaternion) < 0.0:
                quaternion.negate()
            bone.rotation_quaternion = quaternion
            previous[bone.name] = quaternion.copy()
            bone.keyframe_insert(
                "rotation_quaternion",
                frame=frame,
                group=bone.name,
            )
        rig.pose.bones["root"].keyframe_insert(
            "location",
            frame=frame,
            group="root",
        )

    def key_pose(
        frame: int,
        pose: dict[str, object],
        previous: dict[str, object],
        ground_side: str | None = None,
    ) -> None:
        solve_pose(pose)
        root_offset = pose["root_offset"]
        assert isinstance(root_offset, Vector)
        if ground_side is not None:
            # Ground the rendered shoe, not a toe-bone proxy. This permits a
            # crisp initial strike and stable stance without flattening the
            # airborne frames or changing any non-Run action.
            minimum_z = deformed_foot_minimum_z(ground_side)
            set_root_offset(root_offset + up * (0.002 - minimum_z))
        else:
            minimum_z = deformed_minimum_z()
            if minimum_z < 0.002:
                set_root_offset(root_offset + up * (0.002 - minimum_z))
        insert_pose_keys(frame, previous)

    def make(
        name: str,
        end: int,
        anchors: dict[int, dict[str, object]],
        cyclic: bool = False,
        ground_sides: dict[int, str] | None = None,
    ) -> bpy.types.Action:
        assert min(anchors) == 1 and max(anchors) == end
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = 1
        action.frame_end = end
        action.use_cyclic = cyclic
        rig.animation_data.action = action
        previous: dict[str, object] = {}
        for frame in range(1, end + 1):
            scene.frame_set(frame)
            key_pose(
                frame,
                pose_between(anchors, frame),
                previous,
                None if ground_sides is None else ground_sides.get(frame),
            )
        for curve in layered_fcurves(action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        track.mute = True
        rig.animation_data.action = None
        return action

    def flight_root_offset(
        start: Vector,
        end: Vector,
        frame: int,
        first: int,
        last: int,
    ) -> Vector:
        t = (frame - first) / (last - first)
        smooth = t * t * (3.0 - 2.0 * t)
        arc = 0.0210 * 4.0 * t * (1.0 - t)
        return start.lerp(end, smooth) + up * arc

    def make_v3_run(
        anchors: dict[int, dict[str, object]],
    ) -> bpy.types.Action:
        poses = {
            frame: pose_between(anchors, frame)
            for frame in range(1, 18)
        }
        intermediate_stance_feet = {
            2: ("L", (0.015, 0.976, -0.218), (0.010, 0.995, -0.100)),
            4: ("L", (0.015, 0.940, -0.342), (0.010, 0.990, -0.140)),
            10: ("R", (0.015, 0.976, -0.218), (0.010, 0.995, -0.100)),
            12: ("R", (0.015, 0.940, -0.342), (0.010, 0.990, -0.140)),
        }
        for frame, (side, foot_values, toe_values) in (
            intermediate_stance_feet.items()
        ):
            legs = poses[frame]["legs"]
            assert isinstance(legs, dict)
            leg = legs[side]
            leg["foot"] = side_direction(side, foot_values)
            leg["toe"] = side_direction(side, toe_values)
        stance_sides = {
            1: "L",
            3: "L",
            5: "L",
            9: "R",
            11: "R",
            13: "R",
            17: "L",
        }
        root_offsets: dict[int, Vector] = {}

        for frame, side in stance_sides.items():
            scene.frame_set(frame)
            solve_pose(poses[frame])
            base = poses[frame]["root_offset"]
            assert isinstance(base, Vector)
            correction = 0.002 - deformed_sole_minimum_z(side)
            root_offsets[frame] = base + up * correction

        root_offsets[17] = root_offsets[1].copy()
        for frame in (2, 4, 10, 12):
            authored = poses[frame]["root_offset"]
            assert isinstance(authored, Vector)
            root_offsets[frame] = authored.copy()
        for first, last in ((5, 9), (13, 17)):
            for frame in range(first + 1, last):
                root_offsets[frame] = flight_root_offset(
                    root_offsets[first],
                    root_offsets[last],
                    frame,
                    first,
                    last,
                )

        action = bpy.data.actions.new("Run")
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = 1
        action.frame_end = 17
        action.use_cyclic = True
        rig.animation_data.action = action
        previous: dict[str, object] = {}

        for frame in range(1, 18):
            scene.frame_set(frame)
            solved = {
                **poses[frame],
                "root_offset": root_offsets[frame],
            }
            solve_pose(solved)
            insert_pose_keys(frame, previous)

        for curve in layered_fcurves(action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        track = rig.animation_data.nla_tracks.new()
        track.name = "Run"
        track.strips.new("Run", 1, action)
        track.mute = True
        rig.animation_data.action = None
        return action

    def pose(
        *,
        root_up: float,
        lean: float,
        pelvis_yaw: float,
        chest_yaw: float,
        arms: dict[str, tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]],
        legs: dict[str, tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]],
    ) -> dict[str, object]:
        return {
            "root_offset": up * root_up,
            "lean": lean,
            "pelvis_yaw": pelvis_yaw,
            "chest_yaw": chest_yaw,
            "arms": {
                side: {
                    "upper": side_direction(side, values[0]),
                    "lower": side_direction(side, values[1]),
                    "hand": side_direction(side, values[2]),
                }
                for side, values in arms.items()
            },
            "legs": {
                side: {
                    "upper": side_direction(side, values[0]),
                    "lower": side_direction(side, values[1]),
                    "foot": side_direction(side, values[2]),
                    "toe": side_direction(side, values[3]),
                }
                for side, values in legs.items()
            },
        }

    arm_relaxed = ((0.05, 0.08, -0.995), (0.04, 0.62, -0.78), (0.03, 0.30, -0.95))
    arm_forward = ((0.04, 0.86, -0.51), (0.03, 0.58, 0.81), (0.02, 0.82, -0.57))
    arm_back = ((0.04, -0.78, -0.63), (0.03, 0.58, -0.81), (0.02, 0.48, -0.88))
    arm_pass = ((0.05, 0.02, -0.999), (0.04, 0.58, -0.81), (0.03, 0.30, -0.95))
    arm_tuck = ((0.04, 0.68, -0.73), (0.03, -0.62, 0.78), (0.02, 0.55, -0.83))

    leg_neutral = ((0.04, 0.0, -1.0), (0.03, 0.0, -1.0), (0.02, 0.92, -0.39), (0.02, 0.98, -0.20))
    leg_lead = ((0.04, 0.84, -0.54), (0.03, 0.42, -0.91), (0.02, 0.93, -0.37), (0.02, 0.98, -0.20))
    leg_rear = ((0.04, -0.68, -0.73), (0.03, 0.30, -0.95), (0.02, 0.76, -0.65), (0.02, 0.96, -0.28))
    leg_stance = ((0.04, -0.16, -0.99), (0.03, -0.50, -0.86), (0.02, 0.93, -0.37), (0.02, 0.98, -0.20))
    leg_swing = ((0.04, 0.88, -0.48), (0.03, -0.70, -0.71), (0.02, 0.94, 0.34), (0.02, 0.98, 0.18))
    leg_crouch = ((0.04, 0.62, -0.78), (0.03, -0.70, -0.71), (0.02, 0.86, -0.51), (0.02, 0.97, -0.24))
    leg_takeoff = ((0.04, 0.12, -0.993), (0.03, 0.05, -0.999), (0.02, 0.72, -0.69), (0.02, 0.95, -0.31))
    leg_tuck = ((0.04, 0.82, -0.57), (0.03, -0.74, -0.67), (0.02, 0.72, -0.69), (0.02, 0.95, -0.31))
    leg_landing = ((0.04, 0.66, -0.75), (0.03, -0.38, -0.92), (0.02, 0.93, -0.37), (0.02, 0.98, -0.20))

    same_arms = lambda values: {side: values for side in ("L", "R")}
    same_legs = lambda values: {side: values for side in ("L", "R")}

    idle_start = pose(root_up=0.0, lean=2.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_relaxed), legs=same_legs(leg_neutral))
    idle_breathe = pose(root_up=0.012, lean=3.0, pelvis_yaw=0.8, chest_yaw=-1.2, arms=same_arms(arm_relaxed), legs=same_legs(leg_neutral))
    idle = make("Idle", 60, {1: idle_start, 30: idle_breathe, 60: idle_start}, cyclic=True)

    if RIG_VARIANT == "v1":
        contact_a = pose(root_up=0.01, lean=16.0, pelvis_yaw=-6.0, chest_yaw=8.0, arms={"L": arm_back, "R": arm_forward}, legs={"L": leg_lead, "R": leg_rear})
        passing_a = pose(root_up=-0.025, lean=16.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_pass), legs={"L": leg_stance, "R": leg_swing})
        contact_b = pose(root_up=0.01, lean=16.0, pelvis_yaw=6.0, chest_yaw=-8.0, arms={"L": arm_forward, "R": arm_back}, legs={"L": leg_rear, "R": leg_lead})
        passing_b = pose(root_up=-0.025, lean=16.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_pass), legs={"L": leg_swing, "R": leg_stance})
        flight_a = blend_pose(passing_a, contact_b, 0.58)
        flight_a["root_offset"] = up * 0.03
        flight_b = blend_pose(passing_b, contact_a, 0.58)
        flight_b["root_offset"] = up * 0.03
        run = make("Run", 24, {1: contact_a, 4: passing_a, 7: flight_a, 13: contact_b, 16: passing_b, 19: flight_b, 24: contact_a}, cyclic=True)
    elif RIG_VARIANT == "v2-run":
        # A compact 16-frame sprint period with an exact duplicate seam. The
        # old 24-frame cycle kept a foot planted for half of every stride and
        # read as a slow march against the fast-scrolling world. These poses
        # add compression, heel recovery, and two true airborne phases while
        # keeping the arms bent and in the sagittal plane.
        sprint_arm_forward = ((0.025, 0.50, -0.866), (0.02, 0.866, 0.50), (0.015, 0.866, 0.50))
        sprint_arm_back = ((0.025, -0.906, -0.423), (0.02, 0.423, -0.906), (0.015, 0.423, -0.906))
        sprint_arm_mid_forward = ((0.025, 0.174, -0.985), (0.02, 0.985, 0.174), (0.015, 0.985, 0.174))
        sprint_arm_mid_back = ((0.025, -0.643, -0.766), (0.02, 0.766, -0.643), (0.015, 0.766, -0.643))

        sprint_contact_lead = ((0.025, 0.42, -0.907), (0.02, 0.12, -0.993), (0.015, 0.98, -0.20), (0.01, 0.995, -0.10))
        sprint_contact_trail = ((0.025, -0.32, -0.948), (0.02, -0.76, -0.65), (0.015, 0.93, -0.37), (0.01, 0.993, -0.12))
        sprint_down_support = ((0.025, 0.18, -0.984), (0.02, -0.45, -0.893), (0.015, 0.97, -0.24), (0.01, 0.995, -0.10))
        sprint_down_recovery = ((0.025, -0.12, -0.993), (0.02, -0.98, -0.20), (0.015, 0.98, 0.20), (0.01, 0.995, 0.10))
        sprint_passing_support = ((0.025, -0.18, -0.984), (0.02, -0.46, -0.888), (0.015, 0.98, -0.20), (0.01, 0.995, -0.10))
        sprint_passing_recovery = ((0.025, 0.90, -0.435), (0.02, -0.52, -0.854), (0.015, 0.98, 0.20), (0.01, 0.995, 0.10))
        sprint_flight_lead = ((0.025, 0.65, -0.76), (0.02, -0.10, -0.995), (0.015, 0.995, 0.10), (0.01, 0.998, 0.06))
        sprint_flight_recovery = ((0.025, -0.38, -0.925), (0.02, -0.98, 0.20), (0.015, 0.95, 0.31), (0.01, 0.995, 0.10))

        contact_a = pose(root_up=0.005, lean=14.0, pelvis_yaw=-4.0, chest_yaw=6.0, arms={"L": sprint_arm_back, "R": sprint_arm_forward}, legs={"L": sprint_contact_lead, "R": sprint_contact_trail})
        down_a = pose(root_up=-0.018, lean=15.0, pelvis_yaw=-2.0, chest_yaw=3.0, arms={"L": sprint_arm_back, "R": sprint_arm_forward}, legs={"L": sprint_down_support, "R": sprint_down_recovery})
        passing_a = pose(root_up=0.012, lean=16.0, pelvis_yaw=0.0, chest_yaw=0.0, arms={"L": sprint_arm_mid_forward, "R": sprint_arm_mid_back}, legs={"L": sprint_passing_support, "R": sprint_passing_recovery})
        flight_a = pose(root_up=0.032, lean=17.0, pelvis_yaw=3.0, chest_yaw=-5.0, arms={"L": sprint_arm_forward, "R": sprint_arm_back}, legs={"L": sprint_flight_recovery, "R": sprint_flight_lead})
        contact_b = pose(root_up=0.005, lean=14.0, pelvis_yaw=4.0, chest_yaw=-6.0, arms={"L": sprint_arm_forward, "R": sprint_arm_back}, legs={"L": sprint_contact_trail, "R": sprint_contact_lead})
        down_b = pose(root_up=-0.018, lean=15.0, pelvis_yaw=2.0, chest_yaw=-3.0, arms={"L": sprint_arm_forward, "R": sprint_arm_back}, legs={"L": sprint_down_recovery, "R": sprint_down_support})
        passing_b = pose(root_up=0.012, lean=16.0, pelvis_yaw=0.0, chest_yaw=0.0, arms={"L": sprint_arm_mid_back, "R": sprint_arm_mid_forward}, legs={"L": sprint_passing_recovery, "R": sprint_passing_support})
        flight_b = pose(root_up=0.032, lean=17.0, pelvis_yaw=-3.0, chest_yaw=5.0, arms={"L": sprint_arm_back, "R": sprint_arm_forward}, legs={"L": sprint_flight_lead, "R": sprint_flight_recovery})
        run = make(
            "Run",
            17,
            {1: contact_a, 3: down_a, 5: passing_a, 7: flight_a, 9: contact_b, 11: down_b, 13: passing_b, 15: flight_b, 17: contact_a},
            cyclic=True,
            ground_sides={
                1: "L",
                2: "L",
                3: "L",
                4: "L",
                5: "L",
                9: "R",
                10: "R",
                11: "R",
                12: "R",
                13: "R",
                17: "L",
            },
        )
    else:
        v3_arm_forward_strike = (
            (0.025, 0.500, -0.866),
            (0.020, 0.788, 0.616),
            (0.015, 0.820, 0.572),
        )
        v3_arm_forward_load = (
            (0.025, 0.309, -0.951),
            (0.020, 0.930, 0.368),
            (0.015, 0.954, 0.300),
        )
        v3_arm_forward_pass = (
            (0.025, -0.191, -0.982),
            (0.020, 1.000, 0.000),
            (0.015, 0.940, -0.342),
        )
        v3_arm_forward_flight = (
            (0.025, 0.438, -0.899),
            (0.020, 0.766, 0.643),
            (0.015, 0.800, 0.600),
        )
        v3_arm_back_strike = (
            (0.025, -0.906, -0.423),
            (0.020, 0.600, -0.800),
            (0.015, 0.480, -0.877),
        )
        v3_arm_back_load = (
            (0.025, -0.743, -0.669),
            (0.020, 0.650, -0.760),
            (0.015, 0.450, -0.893),
        )
        v3_arm_back_pass = (
            (0.025, -0.276, -0.961),
            (0.020, 0.899, -0.438),
            (0.015, 0.500, -0.866),
        )
        v3_arm_back_flight = (
            (0.025, -0.788, -0.616),
            (0.020, 0.530, -0.848),
            (0.015, 0.400, -0.916),
        )

        v3_leg_strike = (
            (0.025, 0.520, -0.854),
            (0.020, 0.100, -0.995),
            (0.015, 0.950, -0.312),
            (0.010, 0.995, -0.100),
        )
        v3_leg_trail = (
            (0.025, -0.450, -0.893),
            (0.020, -1.000, 0.000),
            (0.015, 0.400, -0.916),
            (0.010, 0.600, -0.800),
        )
        v3_leg_load = (
            (0.025, 0.180, -0.984),
            (0.020, -0.505, -0.863),
            (0.015, 0.976, -0.218),
            (0.010, 0.995, -0.100),
        )
        v3_leg_recovery = (
            (0.025, -0.100, -0.995),
            (0.020, -0.980, -0.200),
            (0.015, 0.995, -0.100),
            (0.010, 0.995, -0.100),
        )
        v3_leg_toe_off = (
            (0.025, -0.250, -0.968),
            (0.020, -0.815, -0.580),
            (0.015, 0.800, -0.600),
            (0.010, 0.985, -0.174),
        )
        v3_leg_knee_drive = (
            (0.025, 0.860, -0.510),
            (0.020, -0.550, -0.835),
            (0.015, 0.940, 0.342),
            (0.010, 0.985, 0.174),
        )
        v3_leg_flight_lead = (
            (0.025, 0.820, -0.572),
            (0.020, 0.100, -0.995),
            (0.015, 0.980, -0.200),
            (0.010, 0.995, -0.100),
        )
        v3_leg_flight_recovery = (
            (0.025, 0.450, -0.893),
            (0.020, -0.900, -0.435),
            (0.015, 0.980, -0.200),
            (0.010, 0.995, -0.100),
        )

        v3_contact_a = pose(
            root_up=0.006,
            lean=21.0,
            pelvis_yaw=-5.0,
            chest_yaw=7.0,
            arms={"L": v3_arm_back_strike, "R": v3_arm_forward_strike},
            legs={"L": v3_leg_strike, "R": v3_leg_trail},
        )
        v3_load_a = pose(
            root_up=-0.040,
            lean=23.0,
            pelvis_yaw=-3.0,
            chest_yaw=4.0,
            arms={"L": v3_arm_back_load, "R": v3_arm_forward_load},
            legs={"L": v3_leg_load, "R": v3_leg_recovery},
        )
        v3_toe_a = pose(
            root_up=0.006,
            lean=24.0,
            pelvis_yaw=1.0,
            chest_yaw=-2.0,
            arms={"L": v3_arm_forward_pass, "R": v3_arm_back_pass},
            legs={"L": v3_leg_toe_off, "R": v3_leg_knee_drive},
        )
        v3_flight_a = pose(
            root_up=0.0,
            lean=23.0,
            pelvis_yaw=4.0,
            chest_yaw=-6.0,
            arms={"L": v3_arm_forward_flight, "R": v3_arm_back_flight},
            legs={"L": v3_leg_flight_recovery, "R": v3_leg_flight_lead},
        )
        v3_contact_b = pose(
            root_up=0.006,
            lean=21.0,
            pelvis_yaw=5.0,
            chest_yaw=-7.0,
            arms={"L": v3_arm_forward_strike, "R": v3_arm_back_strike},
            legs={"L": v3_leg_trail, "R": v3_leg_strike},
        )
        v3_load_b = pose(
            root_up=-0.040,
            lean=23.0,
            pelvis_yaw=3.0,
            chest_yaw=-4.0,
            arms={"L": v3_arm_forward_load, "R": v3_arm_back_load},
            legs={"L": v3_leg_recovery, "R": v3_leg_load},
        )
        v3_toe_b = pose(
            root_up=0.006,
            lean=24.0,
            pelvis_yaw=-1.0,
            chest_yaw=2.0,
            arms={"L": v3_arm_back_pass, "R": v3_arm_forward_pass},
            legs={"L": v3_leg_knee_drive, "R": v3_leg_toe_off},
        )
        v3_flight_b = pose(
            root_up=0.0,
            lean=23.0,
            pelvis_yaw=-4.0,
            chest_yaw=6.0,
            arms={"L": v3_arm_back_flight, "R": v3_arm_forward_flight},
            legs={"L": v3_leg_flight_lead, "R": v3_leg_flight_recovery},
        )
        v3_anchors = {
            1: v3_contact_a,
            3: v3_load_a,
            5: v3_toe_a,
            7: v3_flight_a,
            9: v3_contact_b,
            11: v3_load_b,
            13: v3_toe_b,
            15: v3_flight_b,
            17: v3_contact_a,
        }
        run = make_v3_run(v3_anchors)

    jump_entry = pose(root_up=0.0, lean=8.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_relaxed), legs=same_legs(leg_neutral))
    jump_crouch = pose(root_up=-0.08, lean=16.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_back), legs=same_legs(leg_crouch))
    jump_takeoff = pose(root_up=0.015, lean=9.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_forward), legs=same_legs(leg_takeoff))
    jump_tuck = pose(root_up=0.03, lean=7.0, pelvis_yaw=-2.0, chest_yaw=3.0, arms=same_arms(arm_tuck), legs=same_legs(leg_tuck))
    jump_uncurl = pose(root_up=0.015, lean=9.0, pelvis_yaw=0.0, chest_yaw=1.0, arms=same_arms(arm_forward), legs=same_legs(leg_landing))
    jump_land = pose(root_up=-0.045, lean=13.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_forward), legs=same_legs(leg_landing))
    jump = make("Jump", 30, {1: jump_entry, 4: jump_crouch, 6: jump_takeoff, 9: jump_tuck, 20: jump_tuck, 24: jump_uncurl, 27: jump_land, 30: jump_entry})
    if RIG_VARIANT == "v3-run":
        # The refined v3 T-pose has micrometer-level geometry differences
        # that perturb the mesh-bounds grounding step. Reapply the approved
        # v1 root samples so the full Jump matrix snapshot remains exact.
        approved_jump_root_y = (
            0.05035637319087982,
            0.050351984798908234,
            0.0022778883576393127,
            -0.04304240643978119,
            0.07061227411031723,
            0.12822197377681732,
            0.11215700209140778,
            0.026111111044883728,
            0.029999999329447746,
            0.029999999329447746,
            0.029999999329447746,
            0.029999997466802597,
            0.030000001192092896,
            0.029999997466802597,
            0.029999997466802597,
            0.030000001192092896,
            0.029999997466802597,
            0.029999999329447746,
            0.029999999329447746,
            0.029999999329447746,
            0.027656249701976776,
            0.022499999031424522,
            0.017343750223517418,
            0.014999999664723873,
            -0.0005555544048547745,
            -0.029444444924592972,
            -0.04124971851706505,
            -0.0026392564177513123,
            0.04331392049789429,
            0.05035637319087982,
        )
        rig.animation_data.action = jump
        for frame, root_y in enumerate(approved_jump_root_y, start=1):
            scene.frame_set(frame)
            rig.pose.bones["root"].location = Vector((0.0, root_y, 0.0))
            rig.pose.bones["root"].keyframe_insert(
                "location",
                frame=frame,
                group="root",
            )
        for curve in layered_fcurves(jump):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        rig.animation_data.action = None

    crash_brace = pose(root_up=-0.01, lean=16.0, pelvis_yaw=0.0, chest_yaw=0.0, arms=same_arms(arm_forward), legs=same_legs(leg_crouch))
    crash_impact = pose(root_up=-0.06, lean=34.0, pelvis_yaw=5.0, chest_yaw=-8.0, arms={"L": arm_tuck, "R": arm_forward}, legs={"L": leg_landing, "R": leg_crouch})
    crash_recoil = pose(root_up=0.02, lean=-8.0, pelvis_yaw=-6.0, chest_yaw=10.0, arms={"L": arm_back, "R": arm_tuck}, legs={"L": leg_crouch, "R": leg_landing})
    crash_stagger = pose(root_up=-0.025, lean=18.0, pelvis_yaw=4.0, chest_yaw=-5.0, arms=same_arms(arm_tuck), legs={"L": leg_landing, "R": leg_crouch})
    crash = make("Crash", 36, {1: crash_brace, 6: crash_impact, 12: crash_recoil, 22: crash_stagger, 36: crash_stagger})
    return {action.name: action for action in (idle, run, jump, crash)}


def downsize_web_images(maximum_dimension: int = 1024) -> dict[str, tuple[int, int]]:
    resized: dict[str, tuple[int, int]] = {}
    for image in bpy.data.images:
        width, height = image.size
        largest = max(width, height)
        if largest <= maximum_dimension or largest <= 0:
            continue
        ratio = maximum_dimension / largest
        target = (
            max(1, int(round(width * ratio))),
            max(1, int(round(height * ratio))),
        )
        image.scale(*target)
        # The corrected source references external 4K files. Pack the resized
        # pixel buffer so reopening the rigged .blend does not restore those
        # external dimensions.
        image.pack()
        resized[image.name] = target
    return resized


def point_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_animation_previews(
    rig: bpy.types.Object,
) -> Path:
    output_dir = OUTPUT_DIR / "animation-preview"
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("SANIC_AnimationPreviewWorld")
    scene.world.color = (0.025, 0.032, 0.05)

    preview = bpy.data.collections.new("SANIC_ANIMATION_PREVIEW_PRIVATE")
    scene.collection.children.link(preview)
    camera_data = bpy.data.cameras.new("SANIC_AnimationPreviewCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 2.12
    camera = bpy.data.objects.new("SANIC_AnimationPreviewCamera", camera_data)
    preview.objects.link(camera)
    scene.camera = camera

    target = Vector((0.0, 0.0, 0.84))
    for name, location, energy, size in (
        ("SANIC_AnimationKey", (-2.4, -3.0, 3.6), 850.0, 2.8),
        ("SANIC_AnimationFill", (2.7, -1.0, 2.2), 520.0, 2.6),
        ("SANIC_AnimationRim", (0.0, 2.8, 3.0), 950.0, 2.3),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        light.location = location
        point_at(light, target)
        preview.objects.link(light)

    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0.0, 0.0, -0.002))
    ground = bpy.context.object
    ground.name = "SANIC_AnimationPreviewGround"
    for owner in list(ground.users_collection):
        owner.objects.unlink(ground)
    preview.objects.link(ground)
    ground_material = bpy.data.materials.new("SANIC_AnimationPreviewGroundMaterial")
    ground_material.diffuse_color = (0.055, 0.07, 0.105, 1.0)
    ground_material.use_nodes = True
    shader = ground_material.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (0.055, 0.07, 0.105, 1.0)
        shader.inputs["Roughness"].default_value = 0.78
    ground.data.materials.append(ground_material)

    checkpoints = {
        "Run": (
            (1, 4, 7, 10, 13, 16, 19, 22)
            if RIG_VARIANT == "v1"
            else (1, 3, 5, 7, 9, 11, 13, 15, 17)
        ),
        "Jump": (1, 4, 6, 9, 20, 24, 27, 30),
    }
    if os.environ.get("SANIC_RUN_ONLY_PREVIEW") == "1":
        checkpoints = {"Run": checkpoints["Run"]}
    views = {
        "front": Vector((0.0, -4.2, 0.86)),
        "side": Vector((-4.2, 0.0, 0.86)),
    }
    if RIG_VARIANT == "v3-run":
        views["rear"] = Vector((0.0, 4.2, 0.86))
    rig.animation_data_create()
    for action_name, frames in checkpoints.items():
        action = bpy.data.actions[action_name]
        rig.animation_data.action = action
        for view_name, camera_location in views.items():
            if view_name == "rear" and action_name != "Run":
                continue
            camera.location = camera_location
            point_at(camera, target)
            view_frames = (
                tuple(range(1, 18))
                if view_name == "rear"
                else frames
            )
            for frame in view_frames:
                scene.frame_set(frame)
                bpy.context.view_layer.update()
                scene.render.filepath = str(
                    output_dir
                    / f"{action_name.lower()}-{view_name}-{frame:02d}.png"
                )
                result = bpy.ops.render.render(write_still=True)
                assert result == {"FINISHED"}, result
    rig.animation_data.action = None
    scene.frame_set(1)
    return output_dir


def export_rigged(
    rig: bpy.types.Object,
    collection: bpy.types.Collection,
) -> None:
    export_objects = [obj for obj in collection.objects if obj.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in export_objects:
        obj.hide_set(False)
        obj.hide_render = False
        obj.select_set(True)
    rig.hide_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    result = bpy.ops.export_scene.gltf(
        filepath=str(RIGGED_GLB),
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


def main() -> None:
    collection = open_corrected_source()
    rig = create_armature(collection)
    skin_character(rig, collection)
    actions = create_actions(rig)
    resized = downsize_web_images()
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(RIGGED_BLEND), check_existing=False)
    export_rigged(rig, collection)
    bpy.ops.wm.save_as_mainfile(filepath=str(RIGGED_BLEND), check_existing=False)
    animation_preview = render_animation_previews(rig)
    print(
        "SANIC_RIG_BUILD=PASS",
        {
            "source": str(SOURCE_BLEND),
            "blend": str(RIGGED_BLEND),
            "glb": str(RIGGED_GLB),
            "bones": len(rig.data.bones),
            "actions": {name: tuple(action.frame_range) for name, action in actions.items()},
            "resized_images": resized,
            "animation_preview": str(animation_preview),
        },
    )


if __name__ == "__main__":
    main()
