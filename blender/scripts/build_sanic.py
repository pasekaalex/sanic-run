"""Build the original high-detail Buff Sanic runner and optimized web export.

Run inside Blender 5.1+ through Blender MCP.  Checkpoint execution is controlled
by ``SANIC_BUILD_STAGE`` in the globals passed to ``exec``:

``neutral``
    Materials and the complete neutral high-detail character.
``rig``
    Neutral character plus armature, weights, and four actions.
``all``
    Complete source scene, web collection, save, and GLB export.
"""

from __future__ import annotations

import math
import os
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def resolve_project_root() -> Path:
    """Resolve the active checkout without depending on a disposable worktree name."""
    override = globals().get("SANIC_PROJECT_ROOT") or os.environ.get("SANIC_PROJECT_ROOT")

    def valid_root(candidate: Path) -> bool:
        return (
            (candidate / "package.json").is_file()
            and (candidate / "blender" / "scripts" / "build_sanic.py").is_file()
        )

    if override:
        explicit = Path(override).expanduser().resolve()
        if not valid_root(explicit):
            raise RuntimeError(f"SANIC_PROJECT_ROOT is not a Sanic Run checkout: {explicit}")
        return explicit

    starts: list[Path] = []
    script_file = globals().get("__file__")
    if script_file:
        starts.append(Path(script_file).expanduser().resolve().parent)
    starts.append(Path.cwd().resolve())
    if bpy.data.filepath:
        starts.append(Path(bpy.data.filepath).expanduser().resolve().parent)

    visited: set[Path] = set()
    for start in starts:
        for candidate in (start, *start.parents):
            if candidate in visited:
                continue
            visited.add(candidate)
            if valid_root(candidate):
                return candidate
    raise RuntimeError(
        "Could not locate the Sanic Run checkout. Set SANIC_PROJECT_ROOT to the active repository root."
    )


ROOT = resolve_project_root()
BLEND_PATH = ROOT / "blender" / "sanic-source.blend"
GLB_PATH = ROOT / "public" / "models" / "sanic-runner.glb"
VENDOR_BASE_PATH = ROOT / "blender/vendor/human-base-mesh/body-male-realistic-cc0.blend"
STAGE = globals().get("SANIC_BUILD_STAGE", "all")
SAVE_BLEND = bool(globals().get("SANIC_SAVE_BLEND", True))

SOURCE_COLLECTION: bpy.types.Collection | None = None
WEB_COLLECTION: bpy.types.Collection | None = None
RIG_COLLECTION: bpy.types.Collection | None = None
MATERIALS: dict[str, bpy.types.Material] = {}
PART_BINDINGS: dict[str, tuple[tuple[str, float], ...]] = {}
CANONICAL_FACE_OBJECTS = {
    "SANIC_Head",
    "SANIC_EyeMask",
    "SANIC_Eyelid.L",
    "SANIC_Eyelid.R",
    "SANIC_Muzzle",
    "SANIC_Nose",
    "SANIC_Mouth",
    "SANIC_BrowText",
}
MUZZLE_CENTER = (0.0, -0.675, 4.88)
MUZZLE_SCALE = (0.52, 0.17, 0.29)
MUZZLE_LOBE_CENTERS = (-0.25, 0.25)
MUZZLE_BRIDGE = 0.73

HAND_FACE_SETS = {
    "L": {
        "hand": {9},
        "finger_index": set(range(64, 68)),
        "finger_middle": set(range(68, 72)),
        "finger_ring": set(range(72, 76)),
        "finger_pinky": set(range(76, 80)),
        "thumb": set(range(80, 84)),
    },
    "R": {
        "hand": {10},
        "thumb": set(range(84, 88)),
        "finger_pinky": set(range(88, 92)),
        "finger_ring": set(range(92, 96)),
        "finger_middle": set(range(96, 100)),
        "finger_index": set(range(100, 104)),
    },
}

SHOE_LENGTH_SCALE = 0.60
SHOE_WIDTH_SCALE = 0.60
SHOE_HEIGHT_SCALE = 0.70
SHOE_PIVOT_Y = -0.30
SHOE_GROUND_Z = 0.0

AUDITED_UPPER = (
    (0.30, 0.31, 0.33, 0.20),
    (0.08, 0.39, 0.32, 0.23),
    (-0.22, 0.43, 0.31, 0.24),
    (-0.50, 0.45, 0.32, 0.23),
    (-0.72, 0.42, 0.37, 0.21),
    (-0.90, 0.34, 0.44, 0.15),
)
AUDITED_MIDSOLE = tuple(
    (y, width + 0.025, z - 0.17, 0.075)
    for y, width, z, _ in AUDITED_UPPER
)
AUDITED_OUTSOLE = tuple(
    (y, width + 0.045, z - 0.245, 0.055)
    for y, width, z, _ in AUDITED_UPPER
)


def scale_shoe_y(y: float) -> float:
    return SHOE_PIVOT_Y + (y - SHOE_PIVOT_Y) * SHOE_LENGTH_SCALE


def scale_shoe_section(
    section: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    y, half_width, center_z, half_height = section
    return (
        scale_shoe_y(y),
        half_width * SHOE_WIDTH_SCALE,
        SHOE_GROUND_Z + (center_z - SHOE_GROUND_Z) * SHOE_HEIGHT_SCALE,
        half_height * SHOE_HEIGHT_SCALE,
    )


UPPER = tuple(scale_shoe_section(section) for section in AUDITED_UPPER)
MIDSOLE = tuple(scale_shoe_section(section) for section in AUDITED_MIDSOLE)
OUTSOLE = tuple(scale_shoe_section(section) for section in AUDITED_OUTSOLE)


def reset_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for datablocks in (
        bpy.data.actions,
        bpy.data.armatures,
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            datablocks.remove(datablock)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.012, 0.016, 0.035)
    scene.frame_start = 1
    scene.frame_end = 48
    scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
    PART_BINDINGS.clear()
    MATERIALS.clear()


def collection(name: str) -> bpy.types.Collection:
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def move_to_collection(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    target.objects.link(obj)


def material(
    name: str,
    color: tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.36,
    coat_weight: float = 0.035,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    principled = mat.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Coat Weight"].default_value = coat_weight
    principled.inputs["Coat Roughness"].default_value = 0.58
    return mat


def setup_materials() -> None:
    MATERIALS.update(
        cobalt=material("SANIC_MAT_Cobalt", (0.016, 0.055, 0.82, 1.0), 0.0, 0.34, 0.08),
        white=material("SANIC_MAT_White", (0.92, 0.95, 1.0, 1.0), 0.0, 0.46),
        red=material("SANIC_MAT_Red", (0.82, 0.012, 0.018, 1.0), 0.0, 0.24, 0.18),
        midsole=material("SANIC_MAT_Midsole", (0.92, 0.95, 1.0, 1.0), 0.0, 0.38),
        sole=material("SANIC_MAT_Sole", (0.024, 0.027, 0.035, 1.0), 0.0, 0.76),
        beige=material("SANIC_MAT_Beige", (0.64, 0.255, 0.12, 1.0), 0.0, 0.54),
        black=material("SANIC_MAT_Black", (0.004, 0.006, 0.012, 1.0), 0.0, 0.38),
    )


def finish_mesh(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    bindings: tuple[tuple[str, float], ...],
    subdiv: int = 1,
) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    move_to_collection(obj, SOURCE_COLLECTION)
    obj.data.name = f"{obj.name}_Mesh"
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    if subdiv:
        modifier = obj.modifiers.new("SANIC_HighDetail", "SUBSURF")
        modifier.subdivision_type = "CATMULL_CLARK"
        modifier.levels = subdiv
        modifier.render_levels = subdiv
        modifier.show_only_control_edges = True
    obj["sanic_source"] = True
    obj["sanic_material"] = mat.name
    PART_BINDINGS[obj.name] = bindings
    return obj


def bind_full_mesh_to_group(obj: bpy.types.Object, binding: str) -> None:
    """Populate a neutral-build rigid binding instead of only recording intent."""
    assert obj.type == "MESH", (obj.name, obj.type)
    indices = [vertex.index for vertex in obj.data.vertices]
    assert indices, obj.name
    group = obj.vertex_groups.get(binding) or obj.vertex_groups.new(name=binding)
    group.add(indices, 1.0, "REPLACE")


def uv_sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    bindings: tuple[tuple[str, float], ...],
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    subdiv: int = 1,
    segments: int = 24,
    ring_count: int = 16,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=ring_count,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, mat, bindings, subdiv=subdiv)


def capsule_between(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
    bindings: tuple[tuple[str, float], ...],
    squash: float = 1.0,
    subdiv: int = 1,
    segments: int = 24,
    ring_count: int = 16,
) -> bpy.types.Object:
    start_v = Vector(start)
    end_v = Vector(end)
    delta = end_v - start_v
    obj = uv_sphere(
        name,
        tuple((start_v + end_v) * 0.5),
        (radius, radius * squash, max(delta.length * 0.56, radius)),
        mat,
        bindings,
        subdiv=subdiv,
        segments=segments,
        ring_count=ring_count,
    )
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = delta.to_track_quat("Z", "Y")
    return obj


def rounded_box(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
    bindings: tuple[tuple[str, float], ...],
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new("SANIC_Rounded", "BEVEL")
    bevel.width = radius
    bevel.segments = 5
    bevel.limit_method = "ANGLE"
    return finish_mesh(obj, mat, bindings, subdiv=0)


def torus(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    mat: bpy.types.Material,
    bindings: tuple[tuple[str, float], ...],
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=24,
        minor_segments=10,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector(axis).to_track_quat("Z", "Y")
    return finish_mesh(obj, mat, bindings, subdiv=1)


def quill(
    name: str,
    root: tuple[float, float, float],
    tip: tuple[float, float, float],
    width: float,
) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    root_v = Vector(root)
    tip_v = Vector(tip)
    direction = (tip_v - root_v).normalized()
    helper = Vector((0.0, 0.0, 1.0))
    if abs(direction.dot(helper)) > 0.9:
        helper = Vector((1.0, 0.0, 0.0))
    axis_a = direction.cross(helper).normalized()
    axis_b = direction.cross(axis_a).normalized()
    profiles = (0.58, 0.76, 0.90, 1.0, 0.94, 0.78, 0.48, 0.035)
    radial_segments = 20
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for ring_index, profile in enumerate(profiles):
        t = ring_index / (len(profiles) - 1)
        center = root_v.lerp(tip_v, t)
        bend = math.sin(t * math.pi) * width * 0.12
        center += axis_b * bend
        for segment in range(radial_segments):
            angle = 2.0 * math.pi * segment / radial_segments
            radius_a = width * profile
            radius_b = width * 0.72 * profile
            vertex = center + axis_a * math.cos(angle) * radius_a + axis_b * math.sin(angle) * radius_b
            vertices.append(tuple(vertex))
    for ring_index in range(len(profiles) - 1):
        ring_start = ring_index * radial_segments
        next_start = (ring_index + 1) * radial_segments
        for segment in range(radial_segments):
            nxt = (segment + 1) % radial_segments
            faces.append((ring_start + segment, ring_start + nxt, next_start + nxt, next_start + segment))
    faces.append(tuple(reversed(range(radial_segments))))
    final = (len(profiles) - 1) * radial_segments
    faces.append(tuple(final + i for i in range(radial_segments)))
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    SOURCE_COLLECTION.objects.link(obj)
    return finish_mesh(obj, MATERIALS["cobalt"], (("head", 1.0),), subdiv=1)


def brow_text() -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    curve = bpy.data.curves.new("SANIC_BrowText_Curve", "FONT")
    curve.body = "I Love to Go Fast"
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = 0.15
    curve.extrude = 0.006
    curve.bevel_depth = 0.002
    curve.bevel_resolution = 2
    curve.materials.append(MATERIALS["black"])
    obj = bpy.data.objects.new("SANIC_BrowText", curve)
    SOURCE_COLLECTION.objects.link(obj)
    obj.location = (0.0, -0.625, 5.66)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (0.68, 0.68, 0.68)
    conform = obj.modifiers.new("SANIC_ForeheadConform", "SHRINKWRAP")
    conform.target = bpy.data.objects["SANIC_Head"]
    conform.wrap_method = "NEAREST_SURFACEPOINT"
    conform.wrap_mode = "ON_SURFACE"
    conform.offset = 0.006
    obj["sanic_source"] = True
    obj["sanic_material"] = MATERIALS["black"].name
    obj["sanic_text_role"] = "high-readable-brow-text"
    PART_BINDINGS[obj.name] = (("head", 1.0),)
    return obj


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def gaussian(value: float, center: float, width: float) -> float:
    return math.exp(-((value - center) / width) ** 2)


def reshape_humanesque_head(head: bpy.types.Object) -> bpy.types.Object:
    """Establish cheeks, a brow plane, and a flatter rear without changing topology."""
    for vertex in head.data.vertices:
        normalized_z = vertex.co.z / 0.86
        lower_weight = 1.0 - smoothstep(-0.18, 0.12, normalized_z)
        brow_weight = gaussian(normalized_z, 0.38, 0.28)
        rear_weight = smoothstep(0.02, 0.58, vertex.co.y / 0.62) * lower_weight
        vertex.co.x *= (1.0 - 0.10 * lower_weight) * (1.0 + 0.06 * brow_weight)
        vertex.co.y *= 1.0 - 0.05 * rear_weight
    head.data.update()
    head["sanic_face_profile"] = "humanesque-tapered-head"
    head["sanic_lower_cheek_taper"] = 0.10
    head["sanic_brow_broaden"] = 0.06
    head["sanic_rear_lower_flatten"] = 0.05
    return head


def build_raised_ear(side: str, sign: float) -> tuple[bpy.types.Object, bpy.types.Object]:
    rotation = (0.0, math.radians(10.0 * sign), 0.0)
    outer = uv_sphere(
        f"SANIC_Ear.{side}",
        (0.64 * sign, 0.02, 5.37),
        (0.17, 0.14, 0.38),
        MATERIALS["cobalt"],
        (("head", 1.0),),
        rotation=rotation,
        subdiv=1,
        segments=32,
        ring_count=24,
    )
    for vertex in outer.data.vertices:
        normalized_z = max(0.0, vertex.co.z / 0.38)
        vertex.co.x *= 1.0 - 0.22 * normalized_z
        vertex.co.y *= 1.0 - 0.18 * normalized_z
    outer.data.update()
    outer["sanic_ear_profile"] = "raised-sharp"

    inner = uv_sphere(
        f"SANIC_EarInner.{side}",
        (0.655 * sign, -0.125, 5.36),
        (0.082, 0.040, 0.245),
        MATERIALS["beige"],
        (("head", 1.0),),
        rotation=rotation,
        subdiv=1,
        segments=24,
        ring_count=16,
    )
    return outer, inner


def lobed_ellipsoid(
    name: str,
    center: tuple[float, float, float],
    scale: tuple[float, float, float],
    lobe_centers: tuple[float, float],
    bridge: float,
    material: bpy.types.Material,
    binding: str = "head",
) -> bpy.types.Object:
    """Return one smooth closed two-lobed mesh with no overlapping components."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=40,
        ring_count=24,
        location=center,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    lobe_width = 0.20 if name == "SANIC_EyeMask" else 0.23
    for vertex in obj.data.vertices:
        lobe_field = max(
            gaussian(vertex.co.x, lobe_center, lobe_width)
            for lobe_center in lobe_centers
        )
        vertical_factor = bridge + (1.0 - bridge) * lobe_field
        vertex.co.z *= vertical_factor
        vertex.co.y *= 0.92 + 0.08 * lobe_field
    obj.data.update()
    obj = finish_mesh(obj, material, ((binding, 1.0),), subdiv=1)
    bind_full_mesh_to_group(obj, binding)
    obj["sanic_face_profile"] = "lobed-ellipsoid"
    obj["sanic_lobe_centers"] = lobe_centers
    obj["sanic_bridge_ratio"] = bridge
    return obj


def build_eye_mask() -> bpy.types.Object:
    mask = lobed_ellipsoid(
        "SANIC_EyeMask",
        (0.0, -0.595, 5.22),
        (0.56, 0.125, 0.34),
        (-0.23, 0.23),
        0.54,
        MATERIALS["white"],
    )
    # Preserve the mandated 40x24 construction, then bake one smooth pass so
    # the flush eye-opening material boundary can be oval instead of blocky.
    bpy.ops.object.select_all(action="DESELECT")
    mask.select_set(True)
    bpy.context.view_layer.objects.active = mask
    baked_detail = mask.modifiers.get("SANIC_HighDetail")
    assert baked_detail is not None
    bpy.ops.object.modifier_apply(modifier=baked_detail.name)
    high_detail = mask.modifiers.new("SANIC_HighDetail", "SUBSURF")
    high_detail.subdivision_type = "CATMULL_CLARK"
    high_detail.levels = 1
    high_detail.render_levels = 1
    high_detail.show_only_control_edges = True
    bind_full_mesh_to_group(mask, "head")
    mask.data.materials.append(MATERIALS["black"])
    black_index = len(mask.data.materials) - 1
    for polygon in mask.data.polygons:
        center = polygon.center
        patch_metric = min(
            ((center.x - offset) / 0.12) ** 2
            + ((center.z + 0.045) / 0.105) ** 2
            for offset in (-0.23, 0.23)
        )
        if (
            center.y < -0.065
            and patch_metric <= 1.0
            and abs(center.x) > 0.09
        ):
            polygon.material_index = black_index
    mask["sanic_eye_openings"] = "two-flush-material-patches"
    return mask


def build_deadpan_eyelid(side: str, sign: float) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    if side == "L":
        controls = (
            Vector((0.43, -0.724, 5.335)),
            Vector((0.255, -0.729, 5.255)),
            Vector((0.075, -0.722, 5.300)),
        )
    else:
        controls = (
            Vector((-0.43, -0.724, 5.315)),
            Vector((-0.255, -0.729, 5.245)),
            Vector((-0.075, -0.722, 5.285)),
        )
    assert sign == (1.0 if side == "L" else -1.0)
    curve = bpy.data.curves.new(f"SANIC_Eyelid.{side}_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = 0.018
    curve.bevel_resolution = 3
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(2)
    for point, coordinate in zip(spline.bezier_points, controls):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(f"SANIC_Eyelid.{side}", curve)
    SOURCE_COLLECTION.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.name = f"SANIC_Eyelid.{side}"
    obj = finish_mesh(obj, MATERIALS["black"], (("head", 1.0),), subdiv=0)
    bind_full_mesh_to_group(obj, "head")
    arc_sag = ((controls[0].z + controls[2].z) * 0.5) - controls[1].z
    obj["sanic_face_role"] = "curved-sleepy-eyelid"
    obj["sanic_curve_points"] = 3
    obj["sanic_arc_sag"] = arc_sag
    obj["sanic_curve_control_points"] = tuple(
        coordinate
        for point in controls
        for coordinate in point
    )
    return obj


def build_muzzle() -> bpy.types.Object:
    muzzle = lobed_ellipsoid(
        "SANIC_Muzzle",
        MUZZLE_CENTER,
        MUZZLE_SCALE,
        MUZZLE_LOBE_CENTERS,
        MUZZLE_BRIDGE,
        MATERIALS["beige"],
    )
    muzzle["sanic_philtrum_bridge"] = True
    return muzzle


def muzzle_front_surface_y(x: float, z: float) -> float:
    local_x = x - MUZZLE_CENTER[0]
    local_z = z - MUZZLE_CENTER[2]
    lobe_field = max(
        gaussian(local_x, lobe_center, 0.23)
        for lobe_center in MUZZLE_LOBE_CENTERS
    )
    vertical_factor = MUZZLE_BRIDGE + (1.0 - MUZZLE_BRIDGE) * lobe_field
    depth_factor = 0.92 + 0.08 * lobe_field
    normalized_x = local_x / MUZZLE_SCALE[0]
    normalized_z = local_z / (MUZZLE_SCALE[2] * vertical_factor)
    radial_squared = 1.0 - normalized_x * normalized_x - normalized_z * normalized_z
    assert radial_squared > 0.0, (x, z, radial_squared)
    return MUZZLE_CENTER[1] - MUZZLE_SCALE[1] * depth_factor * math.sqrt(radial_squared)


def build_crooked_mouth() -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    segments = 48
    center_z = 4.785
    outer_width = 0.29
    outer_height = 0.095
    inner_width = 0.23
    inner_height = 0.047
    vertices: list[tuple[float, float, float]] = []
    for ring_index, (width, height) in enumerate(
        ((outer_width, outer_height), (inner_width, inner_height))
    ):
        for segment in range(segments):
            angle = 2.0 * math.pi * segment / segments
            normalized_x = math.cos(angle)
            corner_offset = 0.0075 - 0.0275 * normalized_x
            human_crook = 0.010 * math.sin(2.0 * angle)
            x = width * normalized_x
            z = center_z + height * math.sin(angle) + corner_offset + human_crook
            surface_y = muzzle_front_surface_y(x, z)
            surface_offset = -0.008 if ring_index == 0 else -0.006
            vertices.append((x, surface_y + surface_offset, z))
    center_point_z = center_z + 0.006
    center_point_y = muzzle_front_surface_y(0.0, center_point_z) - 0.001
    vertices.append((0.0, center_point_y, center_point_z))
    center_index = len(vertices) - 1
    faces: list[tuple[int, ...]] = []
    for segment in range(segments):
        nxt = (segment + 1) % segments
        faces.append((segment, nxt, segments + nxt, segments + segment))
    for segment in range(segments):
        nxt = (segment + 1) % segments
        faces.append((segments + segment, segments + nxt, center_index))
    mesh = bpy.data.meshes.new("SANIC_Mouth_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mouth = bpy.data.objects.new("SANIC_Mouth", mesh)
    SOURCE_COLLECTION.objects.link(mouth)
    mouth = finish_mesh(mouth, MATERIALS["beige"], (("head", 1.0),), subdiv=0)
    mouth.data.materials.append(MATERIALS["black"])
    for polygon in mouth.data.polygons[segments:]:
        polygon.material_index = 1
    bind_full_mesh_to_group(mouth, "head")
    mouth["sanic_face_role"] = "crooked-mouth"
    mouth["sanic_right_corner_raise"] = 0.035
    mouth["sanic_left_corner_drop"] = -0.020
    mouth["sanic_mouth_surface_offset"] = 0.008
    return mouth


def append_cc0_body() -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    assert VENDOR_BASE_PATH.is_file(), VENDOR_BASE_PATH
    with bpy.data.libraries.load(str(VENDOR_BASE_PATH), link=False) as (source, target):
        assert "SANIC_CC0_MaleBase" in source.objects
        target.objects = ["SANIC_CC0_MaleBase"]
    body = target.objects[0]
    assert body is not None and body.type == "MESH", body
    SOURCE_COLLECTION.objects.link(body)
    body.name = "SANIC_BodySculpt"
    return body


def remove_imported_head(body: bpy.types.Object, cutoff_z: float = 1.45) -> int:
    """Remove the human head and close the neck where SANIC_Head conceals it."""
    multires = [modifier for modifier in body.modifiers if modifier.type == "MULTIRES"]
    assert len(multires) == 1, multires
    body.modifiers.remove(multires[0])

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT")
    editable = bmesh.from_edit_mesh(body.data)
    head_vertices = [vertex for vertex in editable.verts if vertex.co.z > cutoff_z]
    removed_vertices = len(head_vertices)
    assert removed_vertices > 2_000, removed_vertices
    bmesh.ops.delete(editable, geom=head_vertices, context="VERTS")

    bpy.ops.mesh.select_all(action="DESELECT")
    boundary = [edge for edge in editable.edges if len(edge.link_faces) == 1]
    assert boundary, "Head removal did not expose a neck boundary"
    for edge in boundary:
        edge.select_set(True)
        for vertex in edge.verts:
            vertex.select_set(True)
    bmesh.update_edit_mesh(body.data, loop_triangles=False, destructive=True)
    assert bpy.ops.mesh.fill_grid(use_interp_simple=True) == {"FINISHED"}

    editable = bmesh.from_edit_mesh(body.data)
    assert all(len(face.verts) == 4 for face in editable.faces)
    assert not [edge for edge in editable.edges if len(edge.link_faces) != 2]
    remaining = set(editable.verts)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    assert components == 1, components
    bmesh.ops.recalc_face_normals(editable, faces=list(editable.faces))
    bmesh.update_edit_mesh(body.data, loop_triangles=True, destructive=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    body.data.update()
    return removed_vertices


def reduce_hidden_feet(body: bpy.types.Object) -> None:
    """Shrink only the concealed source feet, fading to the original ankle sculpt."""
    hidden_scale = Vector((0.60, 0.60, 0.70))
    for vertex in body.data.vertices:
        source = vertex.co.copy()
        if source.z >= 0.58 or abs(source.x) <= 0.26:
            continue
        sign = 1.0 if source.x >= 0.0 else -1.0
        # The longitudinal cage must share the scaled footwear pivot.  Keeping
        # the source-body Y pivot (-0.18) leaves the reduced heel 0.048 units
        # behind the 60%-length shoe, while the original Z pivot keeps the
        # plantar surface seated above the layered sole.
        pivot = Vector((0.51 * sign, SHOE_PIVOT_Y, 0.34))
        weight = 1.0 - smoothstep(0.36, 0.58, source.z)
        reduced = pivot + Vector(tuple(
            (source[axis] - pivot[axis]) * hidden_scale[axis]
            for axis in range(3)
        ))
        vertex.co = source.lerp(reduced, weight)
    body.data.update()
    body["sanic_hidden_foot_scale"] = tuple(hidden_scale)
    body["sanic_hidden_foot_pivot_y"] = SHOE_PIVOT_Y
    body["sanic_hidden_foot_pivot_z"] = 0.34


def reshape_cc0_body(body: bpy.types.Object) -> bpy.types.Object:
    """Turn the realistic CC0 base into SANIC's continuous neutral body sculpt."""
    assert SOURCE_COLLECTION is not None
    assert body.name == "SANIC_BodySculpt", body.name

    # The verified source is already a relaxed, arms-down pose.  Rotate its
    # continuous arm regions outward around anatomical shoulder pivots to meet
    # the existing restrained A-pose hand landmarks.  The smooth mask also
    # preserves the clavicle/deltoid transition rather than creating joints.
    arm_angle = math.radians(22.0)
    forward_angle = math.radians(5.0)
    max_arm_scale = 1.0
    for vertex in body.data.vertices:
        source = vertex.co.copy()
        z = source.z
        lateral = abs(source.x)
        shoulder_blend = smoothstep(0.55, 0.72, z) * (
            1.0 - smoothstep(1.39, 1.47, z)
        )
        arm_threshold = 0.235 - 0.055 * smoothstep(1.16, 1.39, z)
        arm_weight = shoulder_blend * smoothstep(
            arm_threshold,
            arm_threshold + 0.055,
            lateral,
        )

        chest = gaussian(z, 1.28, 0.21)
        waist = gaussian(z, 1.02, 0.16)
        thigh = gaussian(z, 0.72, 0.24)
        calf = gaussian(z, 0.39, 0.17)
        torso_falloff = 1.0 - smoothstep(0.20, 0.50, arm_weight)
        arm_gain = 0.06 * chest * arm_weight
        x_scale = 1.0 + 0.20 * chest * torso_falloff + arm_gain
        x_scale -= 0.08 * waist * torso_falloff
        x_scale += 0.10 * thigh * torso_falloff + 0.05 * calf * torso_falloff
        depth_scale = 1.0 + 0.10 * thigh * torso_falloff
        depth_scale += 0.05 * calf * torso_falloff
        if arm_weight > 0.5:
            max_arm_scale = max(max_arm_scale, x_scale, depth_scale)

        shaped = source.copy()
        shaped.x *= x_scale
        shaped.y *= depth_scale
        if arm_weight > 0.0:
            sign = 1.0 if source.x >= 0.0 else -1.0
            pivot = Vector((0.22 * sign, 0.0, 1.385))
            outward = Matrix.Rotation(-sign * arm_angle, 3, "Y")
            forward = Matrix.Rotation(-sign * forward_angle, 3, "Z")
            rotation = forward @ outward
            rotated = pivot + rotation @ (shaped - pivot)
            shaped = shaped.lerp(rotated, arm_weight)
        vertex.co = shaped

    assert max_arm_scale <= 1.080001, max_arm_scale

    removed_vertices = remove_imported_head(body)

    # Uniformly map the retained source ground/neck span onto the established
    # SANIC ground and hidden-neck landmarks, then apply every object transform.
    ground = min(vertex.co.z for vertex in body.data.vertices)
    neck = max(vertex.co.z for vertex in body.data.vertices)
    target_neck_z = 4.46
    uniform_scale = target_neck_z / (neck - ground)
    body.scale = (uniform_scale, uniform_scale, uniform_scale)
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    body.location.z = -min(vertex.co.z for vertex in body.data.vertices)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    reduce_hidden_feet(body)

    body.data.materials.clear()
    body.data.materials.append(MATERIALS["cobalt"])
    for polygon in body.data.polygons:
        polygon.use_smooth = True

    body["sanic_source"] = True
    body["sanic_material"] = "SANIC_MAT_Cobalt"
    body["sanic_base_license"] = "CC0-1.0"
    body["sanic_base_source"] = "Blender Studio Human Base Meshes v1.4.1"
    body["sanic_base_object"] = "GEO-body_male_realistic"
    body["sanic_max_arm_scale"] = float(max_arm_scale)
    PART_BINDINGS[body.name] = (("root", 1.0),)
    print(
        "SANIC_CC0_BODY_RESHAPED",
        {
            "removed_head_vertices": removed_vertices,
            "base_vertices": len(body.data.vertices),
            "base_polygons": len(body.data.polygons),
            "uniform_scale": round(uniform_scale, 6),
            "max_arm_scale": round(max_arm_scale, 6),
        },
    )
    return body


def mesh_topology_metrics(obj: bpy.types.Object) -> dict[str, int | bool]:
    mesh = obj.data
    face_uses: dict[tuple[int, int], int] = defaultdict(int)
    adjacency = {vertex.index: set() for vertex in mesh.vertices}
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            face_uses[tuple(sorted(edge_key))] += 1
    for edge in mesh.edges:
        first, second = edge.vertices
        adjacency[first].add(second)
        adjacency[second].add(first)
    edge_face_counts = [
        face_uses.get(tuple(sorted(edge.vertices)), 0)
        for edge in mesh.edges
    ]
    remaining = set(adjacency)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            linked = adjacency[stack.pop()] & remaining
            remaining.difference_update(linked)
            stack.extend(linked)
    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.polygons),
        "boundary_edges": sum(count == 1 for count in edge_face_counts),
        "nonmanifold_edges": sum(count != 2 for count in edge_face_counts),
        "components": components,
        "all_quads": all(len(polygon.vertices) == 4 for polygon in mesh.polygons),
    }


def assert_closed_all_quad(obj: bpy.types.Object, expected_components: int = 1) -> dict[str, int | bool]:
    metrics = mesh_topology_metrics(obj)
    assert metrics["all_quads"], (obj.name, metrics)
    assert metrics["nonmanifold_edges"] == 0, (obj.name, metrics)
    assert metrics["components"] == expected_components, (obj.name, metrics)
    return metrics


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
        tree = BVHTree.FromPolygons(
            [obj.matrix_world @ vertex.co for vertex in mesh.vertices],
            triangles,
            all_triangles=True,
        )
        return sum(
            1
            for first, second in tree.overlap(tree)
            if first < second
            and set(triangles[first]).isdisjoint(triangles[second])
        )
    finally:
        if evaluated:
            evaluated_obj.to_mesh_clear()


def add_body_multires(body: bpy.types.Object) -> None:
    """Add high-detail levels only after both source hands have been extracted."""
    assert body.modifiers.get("SANIC_Multires") is None
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    detail = body.modifiers.new("SANIC_Multires", "MULTIRES")
    for _ in range(2):
        bpy.ops.object.multires_subdivide(modifier=detail.name, mode="CATMULL_CLARK")
    detail.levels = 2
    detail.sculpt_levels = 2
    detail.render_levels = 2


def face_region_metrics(mesh: bpy.types.Mesh, selected: set[int]) -> dict[str, int | bool]:
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    face_neighbors: dict[int, set[int]] = defaultdict(set)
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            edge_faces[tuple(sorted(edge_key))].append(polygon.index)
    for linked in edge_faces.values():
        if len(linked) == 2:
            first, second = linked
            face_neighbors[first].add(second)
            face_neighbors[second].add(first)
    vertices = {
        vertex_index
        for polygon_index in selected
        for vertex_index in mesh.polygons[polygon_index].vertices
    }
    boundary = [
        edge
        for edge, linked in edge_faces.items()
        if len(linked) == 2 and sum(index in selected for index in linked) == 1
    ]
    remaining = set(selected)
    components = 0
    while remaining:
        components += 1
        queue = deque([remaining.pop()])
        while queue:
            linked = face_neighbors[queue.popleft()] & remaining
            remaining.difference_update(linked)
            queue.extend(linked)
    return {
        "faces": len(selected),
        "vertices": len(vertices),
        "boundary_edges": len(boundary),
        "components": components,
        "all_quads": all(len(mesh.polygons[index].vertices) == 4 for index in selected),
    }


def selected_boundary_edges(obj: bpy.types.Object) -> list[int]:
    face_uses: dict[tuple[int, int], int] = defaultdict(int)
    for polygon in obj.data.polygons:
        for edge_key in polygon.edge_keys:
            face_uses[tuple(sorted(edge_key))] += 1
    return [
        edge.index
        for edge in obj.data.edges
        if face_uses[tuple(sorted(edge.vertices))] == 1
    ]


def grid_fill_boundary(
    obj: bpy.types.Object,
    expected_edges: int = 22,
    span: int | None = None,
) -> tuple[int, int]:
    """Close one even wrist loop with Blender's deterministic all-quad grid fill."""
    boundary_edges = selected_boundary_edges(obj)
    assert len(boundary_edges) == expected_edges, (obj.name, len(boundary_edges))
    before_vertices = len(obj.data.vertices)
    before_faces = len(obj.data.polygons)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for vertex in obj.data.vertices:
        vertex.select = False
    for edge in obj.data.edges:
        edge.select = False
    for edge_index in boundary_edges:
        edge = obj.data.edges[edge_index]
        edge.select = True
        for vertex_index in edge.vertices:
            obj.data.vertices[vertex_index].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    if span is None:
        result = bpy.ops.mesh.fill_grid(use_interp_simple=True)
    else:
        result = bpy.ops.mesh.fill_grid(span=span, use_interp_simple=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    assert result == {"FINISHED"}, (obj.name, result)
    obj.data.update()
    added_vertices = len(obj.data.vertices) - before_vertices
    added_faces = len(obj.data.polygons) - before_faces
    assert (added_vertices, added_faces) == (8, 18), (
        obj.name,
        added_vertices,
        added_faces,
    )
    return added_vertices, added_faces


def ordered_boundary_loop(boundary_edges: list[bmesh.types.BMEdge]) -> list[bmesh.types.BMVert]:
    neighbors: dict[bmesh.types.BMVert, list[bmesh.types.BMVert]] = defaultdict(list)
    for edge in boundary_edges:
        first, second = edge.verts
        neighbors[first].append(second)
        neighbors[second].append(first)
    assert neighbors and all(len(linked) == 2 for linked in neighbors.values())
    start = min(neighbors, key=lambda vertex: vertex.index)
    loop = [start]
    previous = None
    current = start
    while True:
        candidates = [vertex for vertex in neighbors[current] if vertex is not previous]
        assert candidates
        following = candidates[0]
        if following is start:
            break
        assert following not in loop, "Boundary traversal encountered a secondary loop"
        loop.append(following)
        previous, current = current, following
    assert len(loop) == len(neighbors), (len(loop), len(neighbors))
    return loop


def inflate_and_cuff_glove(glove: bpy.types.Object, side: str, sign: float) -> dict[str, int | bool | float]:
    """Inflate the preserved source hand and extend its single wrist into an integrated cuff."""
    mesh = glove.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    source_vertices = len(bm.verts)
    source_faces = len(bm.faces)
    assert (source_vertices, source_faces) == (699, 687), (glove.name, source_vertices, source_faces)

    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    assert len(boundary_edges) == 22, (glove.name, len(boundary_edges))
    boundary = ordered_boundary_loop(boundary_edges)
    boundary_set = set(boundary)
    deform = bm.verts.layers.deform.verify()
    palm_group = glove.vertex_groups[f"hand.{side}"]
    palm_vertices = [vertex for vertex in bm.verts if palm_group.index in vertex[deform]]
    assert len(palm_vertices) >= 150, (glove.name, len(palm_vertices))
    palm_center = sum((vertex.co for vertex in palm_vertices), Vector()) / len(palm_vertices)
    wrist_center = sum((vertex.co for vertex in boundary), Vector()) / len(boundary)
    cuff_axis = (wrist_center - palm_center).normalized()
    assert cuff_axis.x * sign < -0.25, (glove.name, tuple(cuff_axis))

    distances = {vertex: 0 for vertex in boundary}
    queue = deque(boundary)
    while queue:
        current = queue.popleft()
        for edge in current.link_edges:
            linked = edge.other_vert(current)
            if linked not in distances:
                distances[linked] = distances[current] + 1
                queue.append(linked)
    assert len(distances) == source_vertices, (glove.name, len(distances), source_vertices)

    palm_y = [vertex.co.y for vertex in palm_vertices]
    palm_depth = max(palm_y) - min(palm_y)
    assert palm_depth > 0.12, (glove.name, palm_depth)
    palm_inflate_ratio = 0.12
    digit_inflate_ratio = 0.015
    assert 0.10 <= palm_inflate_ratio <= 0.14
    assert 0.0 < digit_inflate_ratio <= 0.015
    source_normals = {vertex: vertex.normal.copy() for vertex in bm.verts}
    distal_axis = -cuff_axis
    palm_long = [(vertex.co - palm_center).dot(distal_axis) for vertex in palm_vertices]
    long_min, long_max = min(palm_long), max(palm_long)
    long_span = max(long_max - long_min, 1e-6)
    palm_side = Vector((-sign, 0.0, 0.0))

    digit_group_indices = {
        glove.vertex_groups[f"thumb.{side}"].index,
        glove.vertex_groups[f"finger_index.{side}"].index,
        glove.vertex_groups[f"finger_middle.{side}"].index,
        glove.vertex_groups[f"finger_ring.{side}"].index,
        glove.vertex_groups[f"finger_pinky.{side}"].index,
    }
    palm_inflate_distances = []
    digit_inflate_distances = []
    for vertex in list(bm.verts):
        taper = smoothstep(0.0, 5.0, float(distances[vertex]))
        is_digit = any(index in vertex[deform] for index in digit_group_indices)
        local_ratio = digit_inflate_ratio if is_digit else palm_inflate_ratio
        local_distance = palm_depth * local_ratio * taper
        vertex.co += source_normals[vertex] * local_distance
        (digit_inflate_distances if is_digit else palm_inflate_distances).append(local_distance)
        if palm_group.index not in vertex[deform]:
            continue
        facing = smoothstep(0.05, 0.55, source_normals[vertex].dot(palm_side))
        along = ((vertex.co - palm_center).dot(distal_axis) - long_min) / long_span
        across = (vertex.co.y - sum(palm_y) / len(palm_y)) / palm_depth
        crease = (
            gaussian(along, 0.40, 0.065) * gaussian(across, -0.22, 0.42)
            + 0.72 * gaussian(along, 0.61, 0.055) * gaussian(across, 0.24, 0.36)
        )
        vertex.co -= source_normals[vertex] * palm_depth * 0.035 * facing * crease

    previous_ring = boundary
    for distance, radial_scale, depth_scale in (
        (0.045, 1.03, 0.98),
        (0.095, 1.11, 0.94),
        (0.150, 1.18, 0.90),
    ):
        ring: list[bmesh.types.BMVert] = []
        center = wrist_center + cuff_axis * distance
        for source_vertex in boundary:
            radial = source_vertex.co - wrist_center
            axial = cuff_axis * radial.dot(cuff_axis)
            cross = radial - axial
            shaped = cross * radial_scale
            shaped.y *= depth_scale
            created = bm.verts.new(center + shaped)
            created[deform][palm_group.index] = 1.0
            ring.append(created)
        for index, vertex in enumerate(previous_ring):
            following = (index + 1) % len(previous_ring)
            bm.faces.new((vertex, previous_ring[following], ring[following], ring[index]))
        previous_ring = ring

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    before_cap_vertices = len(mesh.vertices)
    grid_fill_boundary(glove, span=2)
    new_cap_vertices = list(range(before_cap_vertices, len(mesh.vertices)))
    palm_group.add(new_cap_vertices, 1.0, "REPLACE")
    mesh.update()

    metrics = assert_closed_all_quad(glove)
    assert metrics["vertices"] == 773, (glove.name, metrics)
    assert metrics["faces"] == 771, (glove.name, metrics)
    metrics["palm_inflate_ratio"] = palm_inflate_ratio
    metrics["digit_inflate_ratio"] = digit_inflate_ratio
    metrics["palm_max_inflate_distance"] = max(palm_inflate_distances)
    metrics["digit_max_inflate_distance"] = max(digit_inflate_distances)
    metrics["palm_depth"] = float(palm_depth)
    return metrics


def extract_glove_shell(body: bpy.types.Object, side: str, sign: float) -> bpy.types.Object:
    """Separate the audited source hand face sets and retain their anatomical quad flow."""
    assert body.modifiers.get("SANIC_Multires") is None, "Hands must be extracted before SANIC_Multires"
    attribute = body.data.attributes.get(".sculpt_face_set")
    assert attribute is not None, "CC0 body has no .sculpt_face_set attribute"
    assert attribute.domain == "FACE" and attribute.data_type == "INT", (
        attribute.domain,
        attribute.data_type,
    )
    group_face_sets = HAND_FACE_SETS[side]
    hand_face_sets = set().union(*group_face_sets.values())
    selected = {
        polygon.index
        for polygon in body.data.polygons
        if attribute.data[polygon.index].value in hand_face_sets
    }
    region = face_region_metrics(body.data, selected)
    assert region == {
        "faces": 687,
        "vertices": 699,
        "boundary_edges": 22,
        "components": 1,
        "all_quads": True,
    }, (side, region)

    created_group_names = []
    for stem, face_sets in group_face_sets.items():
        name = f"{stem}.{side}"
        group = body.vertex_groups.new(name=name)
        indices = {
            vertex_index
            for polygon in body.data.polygons
            if attribute.data[polygon.index].value in face_sets
            for vertex_index in polygon.vertices
        }
        assert len(indices) >= 60, (name, len(indices))
        group.add(sorted(indices), 1.0, "REPLACE")
        created_group_names.append(name)

    existing_names = set(bpy.data.objects.keys())
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for polygon in body.data.polygons:
        polygon.select = polygon.index in selected
    bpy.ops.object.mode_set(mode="EDIT")
    result = bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    assert result == {"FINISHED"}, (side, result)
    separated = [
        obj
        for obj in bpy.data.objects
        if obj.name not in existing_names and obj.type == "MESH"
    ]
    assert len(separated) == 1, (side, [obj.name for obj in separated])
    glove = separated[0]
    glove.name = f"SANIC_GloveShell.{side}"
    glove.data.name = f"{glove.name}_Mesh"
    assert face_region_metrics(glove.data, set(range(len(glove.data.polygons)))) == {
        "faces": 687,
        "vertices": 699,
        "boundary_edges": 0,
        "components": 1,
        "all_quads": True,
    }, glove.name
    assert len(selected_boundary_edges(glove)) == 22, glove.name

    for name in created_group_names:
        group = body.vertex_groups.get(name)
        if group is not None:
            body.vertex_groups.remove(group)
    grid_fill_boundary(body)
    assert_closed_all_quad(body)

    glove.data.materials.clear()
    metrics = inflate_and_cuff_glove(glove, side, sign)
    finish_mesh(glove, MATERIALS["white"], ((f"hand.{side}", 1.0),), subdiv=1)
    intersections = {
        "base": nonadjacent_self_intersection_count(glove, evaluated=False),
        "evaluated": nonadjacent_self_intersection_count(glove, evaluated=True),
    }
    assert intersections == {"base": 0, "evaluated": 0}, (glove.name, intersections)
    glove["sanic_preserved_source_vertices"] = 699
    glove["sanic_preserved_source_faces"] = 687
    glove["sanic_glove_palm_inflate_ratio"] = metrics["palm_inflate_ratio"]
    glove["sanic_glove_digit_inflate_ratio"] = metrics["digit_inflate_ratio"]
    glove["sanic_glove_palm_max_inflate_distance"] = metrics["palm_max_inflate_distance"]
    glove["sanic_glove_digit_max_inflate_distance"] = metrics["digit_max_inflate_distance"]
    glove["sanic_glove_palm_depth"] = metrics["palm_depth"]
    print("SANIC_GLOVE_TOPOLOGY", side, metrics)
    return glove


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def shoe_ring_point(
    side_x: float,
    section: tuple[float, float, float, float],
    angle: float,
    heel_y: float,
    toe_y: float,
) -> Vector:
    """Evaluate the softened, contact-flattened footwear section shared by all trim."""
    y, half_width, center_z, half_height = section
    sign = 1.0 if side_x > 0.0 else -1.0
    length_t = clamp01((heel_y - y) / (heel_y - toe_y))
    toe_t = smoothstep(0.48, 0.92, length_t)
    horizontal = math.cos(angle)
    vertical = math.sin(angle)
    asymmetric_width = horizontal * (1.0 - 0.07 * toe_t * sign * horizontal)
    shaped_vertical = vertical ** 0.86 if vertical >= 0.0 else max(vertical, -0.72)
    return Vector(
        (
            side_x + half_width * asymmetric_width,
            y,
            center_z + half_height * shaped_vertical,
        )
    )


def interpolated_section(
    sections: tuple[tuple[float, float, float, float], ...],
    y: float,
) -> tuple[float, float, float, float]:
    if y >= sections[0][0]:
        return sections[0]
    if y <= sections[-1][0]:
        return sections[-1]
    for index in range(len(sections) - 1):
        first = sections[index]
        second = sections[index + 1]
        if first[0] >= y >= second[0]:
            factor = (first[0] - y) / (first[0] - second[0])
            return tuple(
                first[column] + (second[column] - first[column]) * factor
                for column in range(4)
            )
    raise AssertionError((y, sections[0][0], sections[-1][0]))


def shoe_shell(
    name: str,
    side_x: float,
    sections: tuple[tuple[float, float, float, float], ...],
    material_key: str,
    binding: str,
    radial_segments: int = 28,
) -> bpy.types.Object:
    """Loft (y, half_width, center_z, half_height) footwear sections."""
    assert SOURCE_COLLECTION is not None
    assert radial_segments == 28, radial_segments
    assert len(sections) == 6, len(sections)
    heel = sections[0]
    toe = sections[-1]

    def reduced(
        source: tuple[float, float, float, float],
        y_offset: float,
        radius_scale: float,
        height_scale: float,
        z_lift: float,
    ) -> tuple[float, float, float, float]:
        y, width, center_z, half_height = source
        return (
            y + y_offset,
            width * radius_scale,
            center_z + z_lift,
            half_height * height_scale,
        )

    loft = (
        reduced(
            heel,
            +0.070 * SHOE_LENGTH_SCALE,
            0.30,
            0.40,
            0.020 * SHOE_HEIGHT_SCALE,
        ),
        reduced(
            heel,
            +0.035 * SHOE_LENGTH_SCALE,
            0.72,
            0.76,
            0.007 * SHOE_HEIGHT_SCALE,
        ),
        *sections,
        reduced(
            toe,
            -0.035 * SHOE_LENGTH_SCALE,
            0.72,
            0.76,
            0.018 * SHOE_HEIGHT_SCALE,
        ),
        reduced(
            toe,
            -0.070 * SHOE_LENGTH_SCALE,
            0.30,
            0.40,
            0.032 * SHOE_HEIGHT_SCALE,
        ),
    )
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for section in loft:
        for segment in range(radial_segments):
            angle = 2.0 * math.pi * segment / radial_segments
            vertices.append(
                tuple(
                    shoe_ring_point(
                        side_x,
                        section,
                        angle,
                        sections[0][0],
                        sections[-1][0],
                    )
                )
            )
    for ring in range(len(loft) - 1):
        current = ring * radial_segments
        following = (ring + 1) * radial_segments
        for segment in range(radial_segments):
            nxt = (segment + 1) % radial_segments
            faces.append(
                (
                    current + segment,
                    current + nxt,
                    following + nxt,
                    following + segment,
                )
            )

    heel_ring = loft[0]
    toe_ring = loft[-1]
    heel_pole = len(vertices)
    vertices.append((
        side_x,
        heel_ring[0] + 0.018 * SHOE_LENGTH_SCALE,
        heel_ring[2] + 0.006 * SHOE_HEIGHT_SCALE,
    ))
    toe_pole = len(vertices)
    vertices.append((
        side_x,
        toe_ring[0] - 0.018 * SHOE_LENGTH_SCALE,
        toe_ring[2] + 0.008 * SHOE_HEIGHT_SCALE,
    ))
    toe_start = (len(loft) - 1) * radial_segments
    for segment in range(radial_segments):
        nxt = (segment + 1) % radial_segments
        faces.append((heel_pole, nxt, segment))
        faces.append((toe_pole, toe_start + segment, toe_start + nxt))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    assert not mesh.validate(verbose=True), name
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    SOURCE_COLLECTION.objects.link(obj)

    canonical_rings = {
        round(section[0], 6): [
            vertex
            for vertex in mesh.vertices
            if round(vertex.co.y, 6) == round(section[0], 6)
        ]
        for section in sections
    }
    assert all(len(ring) == radial_segments for ring in canonical_rings.values()), (
        name,
        {key: len(value) for key, value in canonical_rings.items()},
    )
    bottom_counts = []
    for section in sections:
        ring = canonical_rings[round(section[0], 6)]
        minimum = min(vertex.co.z for vertex in ring)
        bottom_counts.append(sum(abs(vertex.co.z - minimum) <= 1e-6 for vertex in ring))
    assert min(bottom_counts) >= 6, (name, bottom_counts)
    toe_bottom = min(vertex.co.z for vertex in canonical_rings[round(sections[-1][0], 6)])
    other_bottom = min(
        vertex.co.z
        for section in sections[:-1]
        for vertex in canonical_rings[round(section[0], 6)]
    )
    assert toe_bottom - other_bottom >= 0.05 * SHOE_HEIGHT_SCALE, (
        name,
        toe_bottom,
        other_bottom,
    )
    subdiv = 0 if material_key == "sole" else 1
    return finish_mesh(
        obj,
        MATERIALS[material_key],
        ((binding, 1.0),),
        subdiv=subdiv,
    )


def upper_surface_point(side_x: float, y: float, fraction: float) -> Vector:
    section = interpolated_section(UPPER, y)
    angle = math.acos(max(-0.94, min(0.94, fraction)))
    return shoe_ring_point(side_x, section, angle, UPPER[0][0], UPPER[-1][0])


def upper_surface_normal(side_x: float, y: float, fraction: float) -> Vector:
    epsilon_y = 0.002 * SHOE_LENGTH_SCALE
    epsilon_fraction = 0.004
    tangent_fraction = (
        upper_surface_point(side_x, y, fraction + epsilon_fraction)
        - upper_surface_point(side_x, y, fraction - epsilon_fraction)
    )
    tangent_y = (
        upper_surface_point(side_x, y + epsilon_y, fraction)
        - upper_surface_point(side_x, y - epsilon_y, fraction)
    )
    normal = tangent_fraction.cross(tangent_y).normalized()
    if normal.z < 0.0:
        normal.negate()
    return normal


def tread_piece(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new("SANIC_TreadRound", "BEVEL")
    bevel.width = 0.012 * SHOE_WIDTH_SCALE
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    move_to_collection(obj, SOURCE_COLLECTION)
    obj.data.materials.append(MATERIALS["sole"])
    return obj


def join_treads_and_heel_edge(outsole: bpy.types.Object, side: str, sign: float) -> None:
    side_x = 0.51 * sign
    pieces = []
    for index, audited_y in enumerate((-0.42, -0.20, 0.02), 1):
        y = scale_shoe_y(audited_y)
        section = interpolated_section(OUTSOLE, y)
        bottom = shoe_ring_point(side_x, section, 1.5 * math.pi, OUTSOLE[0][0], OUTSOLE[-1][0]).z
        pieces.append(
            tread_piece(
                f"SANIC_TreadTemp{index}.{side}",
                (side_x, y, bottom - 0.006 * SHOE_HEIGHT_SCALE),
                (
                    section[1] * 0.82,
                    0.035 * SHOE_LENGTH_SCALE,
                    0.012 * SHOE_HEIGHT_SCALE,
                ),
            )
        )

    heel_y = scale_shoe_y(0.235)
    heel = interpolated_section(OUTSOLE, heel_y)
    heel_bottom = shoe_ring_point(side_x, heel, 1.5 * math.pi, OUTSOLE[0][0], OUTSOLE[-1][0]).z
    pieces.append(
        tread_piece(
            f"SANIC_HeelTreadTemp.{side}",
            (side_x, heel_y, heel_bottom - 0.006 * SHOE_HEIGHT_SCALE),
            (
                heel[1] * 0.88,
                0.035 * SHOE_LENGTH_SCALE,
                0.012 * SHOE_HEIGHT_SCALE,
            ),
        )
    )
    for lateral_sign in (-1.0, 1.0):
        pieces.append(
            tread_piece(
                f"SANIC_HeelEdgeTemp{int(lateral_sign):+d}.{side}",
                (
                    side_x + lateral_sign * heel[1] * 0.78,
                    scale_shoe_y(0.175),
                    heel_bottom - 0.006 * SHOE_HEIGHT_SCALE,
                ),
                (
                    0.026 * SHOE_WIDTH_SCALE,
                    0.090 * SHOE_LENGTH_SCALE,
                    0.012 * SHOE_HEIGHT_SCALE,
                ),
            )
        )

    bpy.ops.object.select_all(action="DESELECT")
    outsole.select_set(True)
    for piece in pieces:
        piece.select_set(True)
    bpy.context.view_layer.objects.active = outsole
    bpy.ops.object.join()
    outsole.name = f"SANIC_ShoeOutsole.{side}"
    outsole.data.name = f"{outsole.name}_Mesh"
    assert not any(obj.name.startswith("SANIC_TreadTemp") for obj in bpy.data.objects)
    outsole["sanic_tread_ribs"] = 3
    outsole["sanic_heel_edge_pieces"] = 3


def build_heel_counter(side: str, sign: float) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    side_x = 0.51 * sign
    fractions = tuple(-0.90 + 1.80 * index / 12 for index in range(13))
    vertices: list[tuple[float, float, float]] = []
    for fraction in fractions:
        side_fade = max(0.0, 1.0 - abs(fraction) ** 1.6)
        rear_y = scale_shoe_y(0.30)
        forward_y = scale_shoe_y(0.255 - 0.030 * abs(fraction) ** 1.4)
        rear = upper_surface_point(side_x, rear_y, fraction)
        rear += (
            upper_surface_normal(side_x, rear_y, fraction)
            * 0.010
            * SHOE_WIDTH_SCALE
        )
        rear.z += 0.060 * SHOE_HEIGHT_SCALE * side_fade
        front = upper_surface_point(side_x, forward_y, fraction)
        front += (
            upper_surface_normal(side_x, forward_y, fraction)
            * 0.008
            * SHOE_WIDTH_SCALE
        )
        front.z += 0.045 * SHOE_HEIGHT_SCALE * side_fade
        vertices.extend((tuple(rear), tuple(front)))
    faces = [
        (2 * index, 2 * (index + 1), 2 * (index + 1) + 1, 2 * index + 1)
        for index in range(len(fractions) - 1)
    ]
    name = f"SANIC_ShoeHeelCounter.{side}"
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    SOURCE_COLLECTION.objects.link(obj)
    solidify = obj.modifiers.new("SANIC_HeelCounterThickness", "SOLIDIFY")
    solidify.thickness = 0.012 * SHOE_WIDTH_SCALE
    solidify.offset = 1.0
    bevel = obj.modifiers.new("SANIC_HeelCounterSoftEdge", "BEVEL")
    bevel.width = 0.010 * SHOE_WIDTH_SCALE
    bevel.segments = 2
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=solidify.name)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    y_values = [vertex.co.y for vertex in obj.data.vertices]
    z_values = [vertex.co.z for vertex in obj.data.vertices]
    assert max(y_values) - min(y_values) <= 0.12 * SHOE_LENGTH_SCALE, (
        name,
        "heel counter must hug the rear rather than form a wedge",
        max(y_values) - min(y_values),
    )
    assert max(z_values) - min(z_values) <= 0.20 * SHOE_HEIGHT_SCALE, (
        name,
        max(z_values) - min(z_values),
    )
    return finish_mesh(obj, MATERIALS["red"], ((f"foot.{side}", 1.0),), subdiv=1)


def build_fitted_strap(side: str, sign: float) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    side_x = 0.51 * sign
    bevel_depth = 0.036 * SHOE_WIDTH_SCALE
    clearance = 0.010 * SHOE_WIDTH_SCALE
    fractions = (-0.78, -0.39, 0.0, 0.39, 0.78)
    points = []
    for fraction in fractions:
        strap_y = scale_shoe_y(-0.30)
        surface = upper_surface_point(side_x, strap_y, fraction)
        normal = upper_surface_normal(side_x, strap_y, fraction)
        points.append(surface + normal * (bevel_depth + clearance))

    name = f"SANIC_ShoeStrap.{side}"
    curve = bpy.data.curves.new(f"{name}_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for control, point in zip(spline.bezier_points, points):
        control.co = point
        control.handle_left_type = "AUTO"
        control.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    SOURCE_COLLECTION.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    strap = bpy.context.object
    strap.name = name
    strap.data.name = f"{name}_Mesh"
    strap["sanic_strap_control_points"] = 5
    strap["sanic_strap_clearance"] = clearance
    return finish_mesh(strap, MATERIALS["white"], ((f"foot.{side}", 1.0),), subdiv=0)


def build_padded_collar(side: str, sign: float) -> bpy.types.Object:
    assert SOURCE_COLLECTION is not None
    side_x = 0.51 * sign
    major_segments = 32
    tube_segments = 8
    radius_x = 0.255 * SHOE_WIDTH_SCALE
    radius_y = 0.190 * SHOE_LENGTH_SCALE
    tube_radius_xy = 0.052 * SHOE_WIDTH_SCALE
    tube_radius_z = 0.052 * SHOE_HEIGHT_SCALE
    center = Vector((
        side_x,
        scale_shoe_y(0.105),
        SHOE_GROUND_Z + (0.505 - SHOE_GROUND_Z) * SHOE_HEIGHT_SCALE,
    ))
    tilt_degrees = -10.0
    tilt = Matrix.Rotation(math.radians(tilt_degrees), 3, "X")
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for major in range(major_segments):
        angle = 2.0 * math.pi * major / major_segments
        centerline = Vector((radius_x * math.cos(angle), radius_y * math.sin(angle), 0.0))
        outward = Vector((math.cos(angle) / radius_x, math.sin(angle) / radius_y, 0.0)).normalized()
        for tube in range(tube_segments):
            tube_angle = 2.0 * math.pi * tube / tube_segments
            local = (
                centerline
                + tube_radius_xy * outward * math.cos(tube_angle)
                + tube_radius_z * Vector((0.0, 0.0, 1.0)) * math.sin(tube_angle)
            )
            vertices.append(tuple(center + tilt @ local))
    for major in range(major_segments):
        next_major = (major + 1) % major_segments
        for tube in range(tube_segments):
            next_tube = (tube + 1) % tube_segments
            faces.append(
                (
                    major * tube_segments + tube,
                    next_major * tube_segments + tube,
                    next_major * tube_segments + next_tube,
                    major * tube_segments + next_tube,
                )
            )
    name = f"SANIC_ShoeCollar.{side}"
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    SOURCE_COLLECTION.objects.link(obj)
    metrics = assert_closed_all_quad(obj)
    assert metrics["vertices"] == 256 and metrics["faces"] == 256, (name, metrics)
    obj["sanic_collar_major_segments"] = major_segments
    obj["sanic_collar_center"] = tuple(center)
    obj["sanic_collar_tilt_degrees"] = tilt_degrees
    return finish_mesh(obj, MATERIALS["white"], ((f"foot.{side}", 1.0),), subdiv=1)


def build_shoe(side: str, sign: float) -> tuple[bpy.types.Object, ...]:
    side_x = 0.51 * sign
    binding = f"foot.{side}"
    upper = shoe_shell(f"SANIC_ShoeUpper.{side}", side_x, UPPER, "red", binding)
    midsole = shoe_shell(
        f"SANIC_ShoeMidsole.{side}",
        side_x,
        MIDSOLE,
        "midsole",
        binding,
    )
    outsole = shoe_shell(f"SANIC_ShoeOutsole.{side}", side_x, OUTSOLE, "sole", binding)
    join_treads_and_heel_edge(outsole, side, sign)
    counter = build_heel_counter(side, sign)
    strap = build_fitted_strap(side, sign)
    collar = build_padded_collar(side, sign)
    built = (upper, midsole, outsole, counter, strap, collar)
    assert all(PART_BINDINGS[obj.name] == ((binding, 1.0),) for obj in built)
    return built


def build_neutral_character() -> None:
    cobalt = MATERIALS["cobalt"]
    white = MATERIALS["white"]
    red = MATERIALS["red"]
    sole = MATERIALS["sole"]
    beige = MATERIALS["beige"]
    black = MATERIALS["black"]

    body = append_cc0_body()
    reshape_cc0_body(body)

    # Preserve and sculpt the audited continuous CC0 palm/thumb/finger regions.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        extract_glove_shell(body, side, sign)
    face_sets = body.data.attributes.get(".sculpt_face_set")
    assert face_sets is not None
    body.data.attributes.remove(face_sets)
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    add_body_multires(body)

    # The section-driven assembly retains the source feet inside fitted collars.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        build_shoe(side, sign)

    # Humanesque deadpan parody face: one tapered head, connected lobes, and a
    # crooked recessed mouth instead of a visor and floating mascot capsules.
    head = uv_sphere("SANIC_Head", (0.0, -0.01, 5.08), (0.74, 0.62, 0.86), cobalt, (("head", 1.0),), subdiv=2, segments=32, ring_count=24)
    reshape_humanesque_head(head)
    bind_full_mesh_to_group(head, "head")
    for side, sign in (("L", 1.0), ("R", -1.0)):
        build_raised_ear(side, sign)
    build_eye_mask()
    for side, sign in (("L", 1.0), ("R", -1.0)):
        build_deadpan_eyelid(side, sign)
    build_muzzle()
    nose = uv_sphere("SANIC_Nose", (0.0, -0.815, 5.045), (0.155, 0.105, 0.120), black, (("head", 1.0),), subdiv=1, segments=32, ring_count=24)
    bind_full_mesh_to_group(nose, "head")
    build_crooked_mouth()
    brow_text()
    assert all(
        PART_BINDINGS.get(name) == (("head", 1.0),)
        for name in CANONICAL_FACE_OBJECTS
    ), {name: PART_BINDINGS.get(name) for name in sorted(CANONICAL_FACE_OBJECTS)}

    # Backward quill fan gives a crisp gameplay-distance rear silhouette.
    for name, root, tip, width in (
        ("SANIC_Quills", (0.0, 0.38, 5.48), (0.0, 1.38, 5.86), 0.34),
        ("SANIC_QuillTop", (0.0, 0.28, 5.65), (0.0, 1.04, 6.22), 0.30),
        ("SANIC_QuillUpper.L", (0.27, 0.34, 5.47), (0.72, 1.27, 5.82), 0.32),
        ("SANIC_QuillUpper.R", (-0.27, 0.34, 5.47), (-0.72, 1.27, 5.82), 0.32),
        ("SANIC_QuillMid.L", (0.38, 0.34, 5.16), (0.91, 1.34, 5.23), 0.33),
        ("SANIC_QuillMid.R", (-0.38, 0.34, 5.16), (-0.91, 1.34, 5.23), 0.33),
        ("SANIC_QuillLow.L", (0.28, 0.35, 4.93), (0.72, 1.20, 4.58), 0.30),
        ("SANIC_QuillLow.R", (-0.28, 0.35, 4.93), (-0.72, 1.20, 4.58), 0.30),
        ("SANIC_QuillTail", (0.0, 0.35, 4.82), (0.0, 1.27, 4.34), 0.31),
    ):
        quill(name, root, tip, width)


def triangle_count(objects: list[bpy.types.Object] | None = None) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    candidates = objects if objects is not None else list(bpy.data.objects)
    for obj in candidates:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        total += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    return total


def boost_high_detail() -> None:
    """Keep the source sculpt over budget without increasing the web meshes."""
    hero_names = (
        "SANIC_Head",
        "SANIC_Muzzle",
        "SANIC_EyeMask",
        "SANIC_Nose",
    )
    for name in hero_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        modifier = obj.modifiers.get("SANIC_HighDetail")
        if modifier:
            modifier.levels = 2
            modifier.render_levels = 2


def create_armature() -> bpy.types.Object:
    assert RIG_COLLECTION is not None
    data = bpy.data.armatures.new("SANIC_ArmatureData")
    rig = bpy.data.objects.new("SANIC_Armature", data)
    RIG_COLLECTION.objects.link(rig)
    rig.show_in_front = True
    rig.display_type = "WIRE"
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
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
        if parent:
            edit_bone.parent = data.edit_bones[parent]
            edit_bone.use_connect = connected

    bone("root", (0.0, 0.0, 0.02), (0.0, 0.0, 0.42))
    bone("hips", (0.0, 0.0, 1.40), (0.0, 0.0, 2.08), "root")
    bone("spine", (0.0, 0.0, 2.08), (0.0, 0.0, 3.24), "hips", True)
    bone("chest", (0.0, 0.0, 3.24), (0.0, 0.0, 4.30), "spine", True)
    bone("neck", (0.0, 0.0, 4.30), (0.0, 0.0, 4.70), "chest", True)
    bone("head", (0.0, 0.0, 4.70), (0.0, 0.0, 5.62), "neck", True)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        bone(f"upper_arm.{side}", (0.67 * sign, 0.0, 4.02), (1.43 * sign, -0.04, 3.55), "chest")
        bone(f"lower_arm.{side}", (1.43 * sign, -0.04, 3.55), (1.92 * sign, -0.17, 2.93), f"upper_arm.{side}", True)
        bone(f"hand.{side}", (1.92 * sign, -0.17, 2.93), (2.09 * sign, -0.28, 2.61), f"lower_arm.{side}", True)
        bone(f"upper_leg.{side}", (0.34 * sign, 0.0, 2.04), (0.48 * sign, 0.0, 1.17), "hips")
        bone(f"lower_leg.{side}", (0.48 * sign, 0.0, 1.17), (0.51 * sign, 0.0, 0.46), f"upper_leg.{side}", True)
        bone(f"foot.{side}", (0.51 * sign, 0.0, 0.46), (0.51 * sign, -0.66, 0.20), f"lower_leg.{side}", True)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig["sanic_rig"] = True
    return rig


def bind_web_parts(rig: bpy.types.Object) -> None:
    """Bind source parts rigidly, blending only cartoon joint masses."""
    assert SOURCE_COLLECTION is not None
    for obj in SOURCE_COLLECTION.objects:
        bindings = PART_BINDINGS.get(obj.name, (("root", 1.0),))
        if obj.type in {"CURVE", "FONT"}:
            world = obj.matrix_world.copy()
            obj.parent = rig
            obj.parent_type = "BONE"
            obj.parent_bone = bindings[0][0]
            obj.matrix_world = world
            continue
        if obj.type != "MESH":
            continue
        indices = [vertex.index for vertex in obj.data.vertices]
        for bone_name, weight in bindings:
            group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
            group.add(indices, weight, "REPLACE")
        modifier = obj.modifiers.new("SANIC_ArmatureDeform", "ARMATURE")
        modifier.object = rig
        modifier.use_deform_preserve_volume = True
        obj.parent = rig
        obj.matrix_parent_inverse = rig.matrix_world.inverted()


def create_actions(rig: bpy.types.Object) -> dict[str, bpy.types.Action]:
    """Author compact biomechanical clips in armature space.

    The rig's local axes are intentionally not treated as semantic pitch/yaw axes.
    Every integer frame is rebuilt from rest, parent-first, by aiming bone segments
    at world-space targets.  The resulting local quaternions (and the root's
    matrix-derived translation) are the only keyed channels.
    """
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    rig.location = (0.0, 0.0, 0.0)
    rig.rotation_mode = "QUATERNION"
    rig.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    rig.scale = (1.0, 1.0, 1.0)
    rig.animation_data_create()
    actions: dict[str, bpy.types.Action] = {}

    lateral = Vector((1.0, 0.0, 0.0))
    forward = Vector((0.0, -1.0, 0.0))
    up = Vector((0.0, 0.0, 1.0))

    def direction(side: float, forward_amount: float, up_amount: float) -> Vector:
        return (lateral * side + forward * forward_amount + up * up_amount).normalized()

    def side_direction(side: str, values: tuple[float, float, float]) -> Vector:
        sign = 1.0 if side == "L" else -1.0
        return direction(sign * values[0], values[1], values[2])

    def nlerp(first: Vector, second: Vector, factor: float) -> Vector:
        mixed = first.lerp(second, factor)
        assert mixed.length > 1e-8, (first, second, factor)
        return mixed.normalized()

    def semantic_nlerp(
        first: tuple[float, float, float],
        second: tuple[float, float, float],
        factor: float,
    ) -> tuple[float, float, float]:
        mixed = Vector(first).lerp(Vector(second), factor)
        assert mixed.length > 1e-8, (first, second, factor)
        return tuple(mixed.normalized())

    def blend_value(key: str, first: object, second: object, factor: float) -> object:
        if isinstance(first, dict):
            assert isinstance(second, dict) and first.keys() == second.keys(), key
            return {
                child_key: blend_value(child_key, first[child_key], second[child_key], factor)
                for child_key in first
            }
        if isinstance(first, Vector):
            assert isinstance(second, Vector)
            return first.lerp(second, factor) if key == "root_offset" else nlerp(first, second, factor)
        assert isinstance(first, (int, float)) and isinstance(second, (int, float)), (key, first, second)
        return float(first) + (float(second) - float(first)) * factor

    def blend_pose(first: dict[str, object], second: dict[str, object], factor: float) -> dict[str, object]:
        assert first.keys() == second.keys()
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
        for pose_bone in rig.pose.bones:
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()

    def world_direction_to_armature(world_direction: Vector) -> Vector:
        return (rig.matrix_world.inverted_safe().to_3x3() @ world_direction).normalized()

    def set_root_world_offset(world_offset: Vector) -> None:
        root = rig.pose.bones["root"]
        armature_offset = rig.matrix_world.inverted_safe().to_3x3() @ world_offset
        desired_head = rig.data.bones["root"].head_local + armature_offset
        matrix = root.matrix.copy()
        matrix.translation += desired_head - root.head
        root.matrix = matrix
        bpy.context.view_layer.update()

    def set_bone_basis(
        bone_name: str,
        world_direction: Vector,
        yaw_degrees: float,
    ) -> None:
        """Set an absolute armature-space basis whose Y axis follows the bone."""
        pose_bone = rig.pose.bones[bone_name]
        y_axis = world_direction_to_armature(world_direction)
        lateral_axis = world_direction_to_armature(lateral)
        forward_axis = world_direction_to_armature(forward)
        yaw = math.radians(yaw_degrees)
        x_hint = lateral_axis * math.cos(yaw) + forward_axis * math.sin(yaw)
        x_axis = x_hint - y_axis * x_hint.dot(y_axis)
        x_axis.normalize()
        z_axis = x_axis.cross(y_axis).normalized()
        basis = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
        basis.translation = pose_bone.head.copy()
        pose_bone.matrix = basis
        bpy.context.view_layer.update()

    def aim_pose_bone(bone_name: str, desired_world_direction: Vector) -> None:
        """Swing a segment about its current head while preserving its roll."""
        pose_bone = rig.pose.bones[bone_name]
        current = (pose_bone.tail - pose_bone.head).normalized()
        desired = world_direction_to_armature(desired_world_direction)
        swing = current.rotation_difference(desired)
        pivot = pose_bone.head.copy()
        pose_bone.matrix = (
            Matrix.Translation(pivot)
            @ swing.to_matrix().to_4x4()
            @ Matrix.Translation(-pivot)
            @ pose_bone.matrix
        )
        bpy.context.view_layer.update()

    def solve_pose(pose: dict[str, object]) -> None:
        reset_pose()
        set_root_world_offset(pose["root_offset"])
        lean = float(pose["lean"])
        pelvis_yaw = float(pose["pelvis_yaw"])
        chest_yaw = float(pose["chest_yaw"])
        set_bone_basis("hips", up, pelvis_yaw)
        set_bone_basis(
            "spine",
            up * math.cos(math.radians(lean * 0.65))
            + forward * math.sin(math.radians(lean * 0.65)),
            pelvis_yaw * 0.55 + chest_yaw * 0.15,
        )
        set_bone_basis(
            "chest",
            up * math.cos(math.radians(lean)) + forward * math.sin(math.radians(lean)),
            chest_yaw,
        )
        set_bone_basis(
            "neck",
            up * math.cos(math.radians(lean * 0.38))
            + forward * math.sin(math.radians(lean * 0.38)),
            chest_yaw * 0.75,
        )
        set_bone_basis(
            "head",
            up * math.cos(math.radians(lean * 0.18))
            + forward * math.sin(math.radians(lean * 0.18)),
            chest_yaw * 0.55,
        )
        for side in ("L", "R"):
            arms = pose["arms"][side]
            aim_pose_bone(f"upper_arm.{side}", arms["upper"])
            aim_pose_bone(f"lower_arm.{side}", arms["lower"])
            aim_pose_bone(f"hand.{side}", arms["lower"])
        for side in ("L", "R"):
            legs = pose["legs"][side]
            aim_pose_bone(f"upper_leg.{side}", legs["upper"])
            aim_pose_bone(f"lower_leg.{side}", legs["lower"])
            aim_pose_bone(f"foot.{side}", legs["foot"])

    def key_spatial_pose(
        frame: int,
        pose: dict[str, object],
        previous_quaternions: dict[str, object],
    ) -> None:
        solve_pose(pose)
        for pose_bone in rig.pose.bones:
            quaternion = pose_bone.rotation_quaternion.copy().normalized()
            previous = previous_quaternions.get(pose_bone.name)
            if previous is not None and previous.dot(quaternion) < 0.0:
                quaternion.negate()
            pose_bone.rotation_quaternion = quaternion
            previous_quaternions[pose_bone.name] = quaternion.copy()
            pose_bone.keyframe_insert(
                "rotation_quaternion",
                frame=frame,
                group=pose_bone.name,
            )
        rig.pose.bones["root"].keyframe_insert(
            "location",
            frame=frame,
            group="root",
        )

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

    def make(
        name: str,
        end: int,
        anchors: dict[int, dict[str, object]],
        cyclic: bool = False,
    ) -> bpy.types.Action:
        assert min(anchors) == 1 and max(anchors) == end, (name, sorted(anchors))
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = 1
        action.frame_end = end
        action.use_cyclic = cyclic
        rig.animation_data.action = action
        previous_quaternions: dict[str, object] = {}
        for frame in range(1, end + 1):
            scene.frame_set(frame)
            key_spatial_pose(frame, pose_between(anchors, frame), previous_quaternions)
        for curve in layered_fcurves(action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        track.mute = True
        rig.animation_data.action = None
        actions[name] = action
        return action

    arm_forward_upper = (0.07, 0.70, -0.71)
    arm_forward_lower = (0.05, 0.62, 0.783)
    arm_back_upper = (0.07, -0.574, -0.816)
    arm_back_lower = (0.05, 0.806, -0.590)
    arm_up_upper = (0.04, 0.94, -0.34)
    arm_up_lower = (0.04, 0.34, 0.94)
    arm_relaxed_upper = (0.07, 0.05, -0.995)
    arm_relaxed_lower = (0.05, 0.72, -0.692)
    arm_passing_upper = semantic_nlerp(arm_back_upper, arm_forward_upper, 0.5)
    arm_passing_lower = semantic_nlerp(arm_back_lower, arm_forward_lower, 0.5)

    leg_lead_upper = (0.04, 0.766, -0.642)
    leg_lead_lower = (0.02, 0.34, -0.94)
    leg_rear_upper = (0.04, -0.50, -0.865)
    leg_rear_lower = (0.02, 0.259, -0.966)
    leg_swing_upper = (0.04, 0.766, -0.642)
    leg_swing_lower = (0.02, -0.574, -0.819)
    leg_stance_upper = (0.02, -0.174, -0.985)
    leg_stance_lower = (0.02, -0.50, -0.866)
    leg_jump_lead_upper = (0.04, 0.766, -0.642)
    leg_jump_lead_lower = (0.02, 0.17, -0.985)
    leg_jump_trail_upper = (0.04, 0.50, -0.865)
    leg_jump_trail_lower = (0.02, -0.819, -0.574)
    leg_neutral_upper = (0.03, 0.0, -1.0)
    leg_neutral_lower = (0.02, 0.0, -1.0)
    leg_takeoff_upper = (0.03, 0.259, -0.966)
    leg_takeoff_lower = (0.02, 0.087, -0.996)
    leg_landing_lead_upper = (0.04, 0.766, -0.642)
    leg_landing_lead_lower = (0.02, -0.087, -0.996)
    leg_landing_trail_upper = (0.04, 0.259, -0.966)
    leg_landing_trail_lower = (0.02, -0.643, -0.766)

    foot_flat = (0.01, 0.93, -0.37)
    foot_toeoff = (0.01, 0.75, -0.66)
    foot_swing = (0.01, 0.995, 0.10)
    foot_tucked = (0.01, 0.72, -0.69)

    def make_pose(
        *,
        root_up: float,
        lean: float,
        pelvis_yaw: float,
        chest_yaw: float,
        arms: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]],
        legs: dict[
            str,
            tuple[
                tuple[float, float, float],
                tuple[float, float, float],
                tuple[float, float, float],
            ],
        ],
    ) -> dict[str, object]:
        return {
            "root_offset": up * root_up,
            "lean": lean,
            "pelvis_yaw": pelvis_yaw,
            "chest_yaw": chest_yaw,
            "arms": {
                side: {
                    "upper": side_direction(side, targets[0]),
                    "lower": side_direction(side, targets[1]),
                }
                for side, targets in arms.items()
            },
            "legs": {
                side: {
                    "upper": side_direction(side, targets[0]),
                    "lower": side_direction(side, targets[1]),
                    "foot": side_direction(side, targets[2]),
                }
                for side, targets in legs.items()
            },
        }

    relaxed_arms = {
        side: (arm_relaxed_upper, arm_relaxed_lower)
        for side in ("L", "R")
    }
    neutral_legs = {
        side: (leg_neutral_upper, leg_neutral_lower, foot_flat)
        for side in ("L", "R")
    }
    idle_start = make_pose(
        root_up=0.0,
        lean=2.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms=relaxed_arms,
        legs=neutral_legs,
    )
    idle_breathe = make_pose(
        root_up=0.015,
        lean=3.0,
        pelvis_yaw=1.0,
        chest_yaw=-1.5,
        arms=relaxed_arms,
        legs=neutral_legs,
    )
    make("Idle", 60, {1: idle_start, 30: idle_breathe, 60: idle_start}, cyclic=True)

    run_contact_a = make_pose(
        root_up=0.01,
        lean=10.0,
        pelvis_yaw=-5.0,
        chest_yaw=7.0,
        arms={
            "L": (arm_back_upper, arm_back_lower),
            "R": (arm_forward_upper, arm_forward_lower),
        },
        legs={
            "L": (leg_lead_upper, leg_lead_lower, foot_flat),
            "R": (leg_rear_upper, leg_rear_lower, foot_toeoff),
        },
    )
    run_passing_a = make_pose(
        root_up=0.0,
        lean=10.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms={
            side: (arm_passing_upper, arm_passing_lower)
            for side in ("L", "R")
        },
        legs={
            "L": (leg_stance_upper, leg_stance_lower, foot_flat),
            "R": (leg_swing_upper, leg_swing_lower, foot_swing),
        },
    )
    run_contact_b = make_pose(
        root_up=0.01,
        lean=10.0,
        pelvis_yaw=5.0,
        chest_yaw=-7.0,
        arms={
            "L": (arm_forward_upper, arm_forward_lower),
            "R": (arm_back_upper, arm_back_lower),
        },
        legs={
            "L": (leg_rear_upper, leg_rear_lower, foot_toeoff),
            "R": (leg_lead_upper, leg_lead_lower, foot_flat),
        },
    )
    run_passing_b = make_pose(
        root_up=0.0,
        lean=10.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms={
            side: (arm_passing_upper, arm_passing_lower)
            for side in ("L", "R")
        },
        legs={
            "L": (leg_swing_upper, leg_swing_lower, foot_swing),
            "R": (leg_stance_upper, leg_stance_lower, foot_flat),
        },
    )
    run_down_a = blend_pose(run_contact_a, run_passing_a, 0.60)
    run_down_a["root_offset"] = up * -0.04
    run_flight_a = blend_pose(run_passing_a, run_contact_b, 0.60)
    run_flight_a["root_offset"] = up * 0.03
    run_down_b = blend_pose(run_contact_b, run_passing_b, 0.60)
    run_down_b["root_offset"] = up * -0.04
    run_flight_b = blend_pose(run_passing_b, run_contact_a, 0.60)
    run_flight_b["root_offset"] = up * 0.03
    make(
        "Run",
        21,
        {
            1: run_contact_a,
            4: run_down_a,
            6: run_passing_a,
            9: run_flight_a,
            11: run_contact_b,
            14: run_down_b,
            16: run_passing_b,
            19: run_flight_b,
            21: run_contact_a,
        },
        cyclic=True,
    )

    jump_entry = make_pose(
        root_up=0.0,
        lean=8.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms=relaxed_arms,
        legs=neutral_legs,
    )
    jump_anticipation = make_pose(
        root_up=-0.06,
        lean=12.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms={side: (arm_back_upper, arm_back_lower) for side in ("L", "R")},
        legs={
            side: (leg_jump_trail_upper, leg_swing_lower, foot_flat)
            for side in ("L", "R")
        },
    )
    jump_takeoff = make_pose(
        root_up=0.02,
        lean=8.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms={side: (arm_up_upper, arm_up_lower) for side in ("L", "R")},
        legs={
            side: (leg_takeoff_upper, leg_takeoff_lower, foot_toeoff)
            for side in ("L", "R")
        },
    )
    jump_peak = make_pose(
        root_up=0.03,
        lean=6.0,
        pelvis_yaw=-3.0,
        chest_yaw=4.0,
        arms={side: (arm_up_upper, arm_up_lower) for side in ("L", "R")},
        legs={
            "L": (leg_jump_lead_upper, leg_jump_lead_lower, foot_swing),
            "R": (leg_jump_trail_upper, leg_jump_trail_lower, foot_tucked),
        },
    )
    jump_ascent = blend_pose(jump_takeoff, jump_peak, 0.58)
    jump_ascent["root_offset"] = up * 0.04
    jump_descent = make_pose(
        root_up=0.01,
        lean=8.0,
        pelvis_yaw=-1.5,
        chest_yaw=2.0,
        arms={side: (arm_forward_upper, arm_forward_lower) for side in ("L", "R")},
        legs={
            "L": ((0.04, 0.574, -0.819), (0.02, 0.087, -0.996), foot_flat),
            "R": ((0.04, 0.259, -0.966), (0.02, -0.342, -0.94), foot_swing),
        },
    )
    jump_landing = make_pose(
        root_up=-0.05,
        lean=12.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms={side: (arm_forward_upper, arm_forward_lower) for side in ("L", "R")},
        legs={
            "L": (leg_landing_lead_upper, leg_landing_lead_lower, foot_flat),
            "R": (leg_landing_trail_upper, leg_landing_trail_lower, foot_flat),
        },
    )
    make(
        "Jump",
        30,
        {
            1: jump_entry,
            4: jump_anticipation,
            6: jump_takeoff,
            10: jump_ascent,
            17: jump_peak,
            23: jump_descent,
            28: jump_landing,
            30: jump_entry,
        },
    )

    crash_brace = make_pose(
        root_up=-0.02,
        lean=15.0,
        pelvis_yaw=0.0,
        chest_yaw=0.0,
        arms={side: (arm_up_upper, arm_up_lower) for side in ("L", "R")},
        legs={
            side: (leg_takeoff_upper, leg_lead_lower, foot_flat)
            for side in ("L", "R")
        },
    )
    crash_impact = make_pose(
        root_up=-0.06,
        lean=30.0,
        pelvis_yaw=4.0,
        chest_yaw=-6.0,
        arms={side: (arm_forward_upper, arm_forward_lower) for side in ("L", "R")},
        legs={
            "L": (leg_landing_lead_upper, leg_landing_lead_lower, foot_flat),
            "R": (leg_landing_trail_upper, leg_landing_trail_lower, foot_flat),
        },
    )
    crash_recoil = make_pose(
        root_up=-0.03,
        lean=18.0,
        pelvis_yaw=-3.0,
        chest_yaw=5.0,
        arms={
            "L": (arm_back_upper, arm_back_lower),
            "R": (arm_forward_upper, arm_forward_lower),
        },
        legs={
            side: (leg_jump_trail_upper, leg_swing_lower, foot_flat)
            for side in ("L", "R")
        },
    )
    make(
        "Crash",
        42,
        {1: jump_entry, 8: crash_brace, 18: crash_impact, 30: crash_recoil, 42: jump_entry},
    )
    rig.animation_data.action = actions["Idle"]
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return actions


def fuse_cobalt_web(obj: bpy.types.Object, rig: bpy.types.Object) -> int:
    """Replace intersecting cobalt parts with one manifold, rigged web skin."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = world
    for modifier in list(obj.modifiers):
        if modifier.type == "ARMATURE":
            obj.modifiers.remove(modifier)
    obj.vertex_groups.clear()

    remesh = obj.modifiers.new("SANIC_FusedVoxel", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = 0.04
    remesh.use_remove_disconnected = False
    remesh.use_smooth_shade = True
    remesh.threshold = 0.5
    bpy.ops.object.modifier_apply(modifier=remesh.name)

    smooth = obj.modifiers.new("SANIC_FusedSmooth", "SMOOTH")
    smooth.factor = 0.28
    smooth.iterations = 2
    bpy.ops.object.modifier_apply(modifier=smooth.name)

    obj.data.calc_loop_triangles()
    before_decimate = len(obj.data.loop_triangles)
    target_triangles = 30_000
    if before_decimate > target_triangles:
        decimate = obj.modifiers.new("SANIC_FusedDecimate", "DECIMATE")
        decimate.decimate_type = "COLLAPSE"
        decimate.ratio = target_triangles / before_decimate
        decimate.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=decimate.name)

    # Bone heat produces smooth shoulder/hip/elbow/knee transitions on the one-piece skin.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    rig.hide_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO", keep_transform=True)
    deform = next((modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"), None)
    if deform is None:
        raise RuntimeError("Automatic weighting did not create an armature modifier on fused cobalt skin")
    deform.name = "SANIC_ArmatureDeform"
    deform.use_deform_preserve_volume = True

    # Match glTF's four-influence skinning limit in Blender instead of relying on
    # exporter-side truncation, then renormalize the retained bone heat weights.
    for vertex in obj.data.vertices:
        influences = sorted(
            ((element.group, element.weight) for element in vertex.groups),
            key=lambda item: item[1],
            reverse=True,
        )
        for group_index, _ in influences[4:]:
            obj.vertex_groups[group_index].remove([vertex.index])
        retained = influences[:4]
        total = sum(weight for _, weight in retained)
        if total > 0.0:
            for group_index, weight in retained:
                obj.vertex_groups[group_index].add([vertex.index], weight / total, "REPLACE")
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = world

    obj.data.calc_loop_triangles()
    final_triangles = len(obj.data.loop_triangles)
    deform_groups = {group.name for group in obj.vertex_groups}
    expected_groups = {bone.name for bone in rig.data.bones if bone.use_deform}
    max_influences = max((len(vertex.groups) for vertex in obj.data.vertices), default=0)
    if len(deform_groups & expected_groups) < 12:
        raise RuntimeError(
            f"Fused cobalt automatic weights cover too few bones: {sorted(deform_groups & expected_groups)}"
        )
    if not 25_000 <= final_triangles <= 35_000:
        raise RuntimeError(f"Fused cobalt triangle count is {final_triangles}, expected 25k-35k")
    if max_influences > 4:
        raise RuntimeError(f"Fused cobalt has {max_influences} influences on a vertex")
    obj["sanic_fused_web"] = True
    print(
        "SANIC_FUSED_COBALT",
        {
            "before_decimate": before_decimate,
            "triangles": final_triangles,
            "weighted_bones": len(deform_groups & expected_groups),
            "max_influences": max_influences,
        },
    )
    return final_triangles


def build_web_collection(rig: bpy.types.Object) -> tuple[bpy.types.Collection, int]:
    global WEB_COLLECTION
    assert SOURCE_COLLECTION is not None
    WEB_COLLECTION = collection("SANIC_WEB")
    duplicates: list[bpy.types.Object] = []
    for source in list(SOURCE_COLLECTION.objects):
        duplicate = source.copy()
        duplicate.data = source.data.copy()
        duplicate.name = f"SANIC_WEB_{source.name.removeprefix('SANIC_')}"
        WEB_COLLECTION.objects.link(duplicate)
        duplicate["sanic_web"] = True
        if duplicate.type in {"CURVE", "FONT"}:
            world = duplicate.matrix_world.copy()
            source_name = duplicate.name
            material_name = duplicate.get("sanic_material", "SANIC_MAT_Black")
            depsgraph = bpy.context.evaluated_depsgraph_get()
            mesh = bpy.data.meshes.new_from_object(
                duplicate.evaluated_get(depsgraph),
                preserve_all_data_layers=True,
                depsgraph=depsgraph,
            )
            bpy.data.objects.remove(duplicate, do_unlink=True)
            duplicate = bpy.data.objects.new(source_name, mesh)
            WEB_COLLECTION.objects.link(duplicate)
            duplicate.matrix_world = world
            duplicate["sanic_web"] = True
            duplicate["sanic_material"] = material_name
            indices = [vertex.index for vertex in duplicate.data.vertices]
            group = duplicate.vertex_groups.new(name="head")
            group.add(indices, 1.0, "REPLACE")
            modifier = duplicate.modifiers.new("SANIC_ArmatureDeform", "ARMATURE")
            modifier.object = rig
            duplicate.parent = rig
            duplicate.matrix_parent_inverse = rig.matrix_world.inverted()
        for modifier in list(duplicate.modifiers):
            if modifier.type == "SUBSURF":
                duplicate.modifiers.remove(modifier)
        for modifier in list(duplicate.modifiers):
            if modifier.type == "ARMATURE":
                continue
            bpy.ops.object.select_all(action="DESELECT")
            duplicate.select_set(True)
            bpy.context.view_layer.objects.active = duplicate
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        duplicates.append(duplicate)

    joined: list[bpy.types.Object] = []
    by_material: dict[str, list[bpy.types.Object]] = {}
    for obj in duplicates:
        by_material.setdefault(obj.get("sanic_material", "SANIC_MAT_Cobalt"), []).append(obj)
    for material_name, objects in by_material.items():
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.hide_set(False)
            obj.select_set(True)
        active = objects[0]
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.join()
        active.name = f"SANIC_WEB_{material_name.removeprefix('SANIC_MAT_')}"
        active.data.name = f"{active.name}_Mesh"
        active["sanic_web"] = True
        if material_name == "SANIC_MAT_Cobalt":
            fuse_cobalt_web(active, rig)
        else:
            world = active.matrix_world.copy()
            active.parent = None
            active.matrix_world = world
        joined.append(active)
    web_triangles = triangle_count(joined)
    print("SANIC_WEB_CHECKPOINT", {"objects": len(joined), "triangles": web_triangles})
    return WEB_COLLECTION, web_triangles


def save_and_export(rig: bpy.types.Object, web: bpy.types.Collection) -> None:
    assert SOURCE_COLLECTION is not None
    BLEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)
    source_triangles = triangle_count([obj for obj in SOURCE_COLLECTION.objects if obj.type == "MESH"])
    web_triangles = triangle_count([obj for obj in web.objects if obj.type == "MESH"])
    total_triangles = triangle_count()
    assert 250_000 <= source_triangles <= 500_000, source_triangles
    assert 45_000 <= web_triangles <= 80_000, web_triangles
    if SAVE_BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in web.objects:
        obj.hide_set(False)
        obj.select_set(True)
    rig.hide_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_PATH),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_anim_slide_to_zero=True,
        export_materials="EXPORT",
        export_tangents=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
    )
    for obj in web.objects:
        obj.hide_set(True)
    for obj in SOURCE_COLLECTION.objects:
        obj.hide_set(False)
    rig.hide_set(True)
    if SAVE_BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)
    print("SANIC_EXPORT_COMPLETE", {"source_triangles": source_triangles, "web_triangles": web_triangles, "scene_triangles": total_triangles, "blend_saved": SAVE_BLEND, "blend": str(BLEND_PATH), "glb": str(GLB_PATH)})


def build_neutral() -> None:
    global SOURCE_COLLECTION, RIG_COLLECTION
    reset_scene()
    SOURCE_COLLECTION = collection("SANIC_SOURCE_HIGH")
    RIG_COLLECTION = collection("SANIC_RIG")
    setup_materials()
    build_neutral_character()
    boost_high_detail()
    body = bpy.data.objects["SANIC_BodySculpt"]
    assert body.get("sanic_base_license") == "CC0-1.0"
    assert body.get("sanic_base_source") == "Blender Studio Human Base Meshes v1.4.1"
    assert body.get("sanic_base_object") == "GEO-body_male_realistic"
    assert all(polygon.use_smooth for polygon in body.data.polygons)
    source_triangles = triangle_count(list(SOURCE_COLLECTION.objects))
    assert 350_000 <= source_triangles <= 600_000, source_triangles
    print(
        "SANIC_NEUTRAL_CHECKPOINT",
        {
            "objects": len(SOURCE_COLLECTION.objects),
            "materials": sorted(mat.name for mat in MATERIALS.values()),
            "triangles": source_triangles,
        },
    )


if STAGE == "neutral":
    build_neutral()
elif STAGE in {"rig", "all"}:
    build_neutral()
    armature = create_armature()
    bind_web_parts(armature)
    built_actions = create_actions(armature)
    print("SANIC_RIG_CHECKPOINT", {"bones": len(armature.data.bones), "actions": sorted(built_actions)})
    if STAGE == "rig":
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)
    else:
        web_collection, _ = build_web_collection(armature)
        save_and_export(armature, web_collection)
else:
    raise ValueError(f"Unknown SANIC_BUILD_STAGE: {STAGE}")
