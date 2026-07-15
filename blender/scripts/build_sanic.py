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
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


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

SOURCE_COLLECTION: bpy.types.Collection | None = None
WEB_COLLECTION: bpy.types.Collection | None = None
RIG_COLLECTION: bpy.types.Collection | None = None
MATERIALS: dict[str, bpy.types.Material] = {}
PART_BINDINGS: dict[str, tuple[tuple[str, float], ...]] = {}


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
    curve.size = 0.16
    curve.extrude = 0.006
    curve.bevel_depth = 0.002
    curve.bevel_resolution = 2
    curve.materials.append(MATERIALS["black"])
    obj = bpy.data.objects.new("SANIC_BrowText", curve)
    SOURCE_COLLECTION.objects.link(obj)
    obj.location = (0.0, -0.667, 5.64)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (0.78, 0.78, 0.78)
    obj["sanic_source"] = True
    obj["sanic_material"] = MATERIALS["black"].name
    PART_BINDINGS[obj.name] = (("head", 1.0),)
    return obj


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def gaussian(value: float, center: float, width: float) -> float:
    return math.exp(-((value - center) / width) ** 2)


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

    editable = bmesh.new()
    editable.from_mesh(body.data)
    head_vertices = [vertex for vertex in editable.verts if vertex.co.z > cutoff_z]
    removed_vertices = len(head_vertices)
    assert removed_vertices > 2_000, removed_vertices
    bmesh.ops.delete(editable, geom=head_vertices, context="VERTS")

    boundary = [edge for edge in editable.edges if len(edge.link_faces) == 1]
    assert boundary, "Head removal did not expose a neck boundary"
    filled = bmesh.ops.holes_fill(editable, edges=boundary)
    assert filled["faces"], "Neck boundary was not capped"
    bmesh.ops.recalc_face_normals(editable, faces=list(editable.faces))
    editable.to_mesh(body.data)
    editable.free()
    body.data.update()
    return removed_vertices


def reshape_cc0_body(body: bpy.types.Object) -> bpy.types.Object:
    """Turn the realistic CC0 base into SANIC's continuous neutral body sculpt."""
    assert SOURCE_COLLECTION is not None
    assert body.name == "SANIC_BodySculpt", body.name

    # The verified source is already a relaxed, arms-down pose.  Rotate its
    # continuous arm regions outward around anatomical shoulder pivots to meet
    # the existing restrained A-pose hand landmarks.  The smooth mask also
    # preserves the clavicle/deltoid transition rather than creating joints.
    arm_angle = math.radians(22.0)
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
        non_arm = 1.0 - arm_weight
        chest_gain = chest * (0.20 * non_arm + 0.06 * arm_weight)
        x_scale = 1.0 + chest_gain - 0.08 * waist * non_arm
        x_scale += 0.10 * thigh * non_arm + 0.05 * calf * non_arm
        depth_scale = 1.0 + 0.10 * thigh * non_arm + 0.05 * calf * non_arm

        shaped = source.copy()
        shaped.x *= x_scale
        shaped.y *= depth_scale
        if arm_weight > 0.0:
            sign = 1.0 if source.x >= 0.0 else -1.0
            pivot = Vector((0.22 * sign, 0.0, 1.385))
            rotation = Matrix.Rotation(-sign * arm_angle, 3, "Y")
            rotated = pivot + rotation @ (shaped - pivot)
            shaped = shaped.lerp(rotated, arm_weight)
        vertex.co = shaped

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

    body.data.materials.clear()
    body.data.materials.append(MATERIALS["cobalt"])
    for polygon in body.data.polygons:
        polygon.use_smooth = True

    detail = body.modifiers.new("SANIC_Multires", "MULTIRES")
    for _ in range(2):
        bpy.ops.object.multires_subdivide(modifier=detail.name, mode="CATMULL_CLARK")
    detail.levels = 2
    detail.sculpt_levels = 2
    detail.render_levels = 2

    body["sanic_source"] = True
    body["sanic_material"] = "SANIC_MAT_Cobalt"
    body["sanic_base_license"] = "CC0-1.0"
    body["sanic_base_source"] = "Blender Studio Human Base Meshes v1.4.1"
    body["sanic_base_object"] = "GEO-body_male_realistic"
    PART_BINDINGS[body.name] = (("root", 1.0),)
    print(
        "SANIC_CC0_BODY_RESHAPED",
        {
            "removed_head_vertices": removed_vertices,
            "base_vertices": len(body.data.vertices),
            "base_polygons": len(body.data.polygons),
            "uniform_scale": round(uniform_scale, 6),
        },
    )
    return body


def build_neutral_character() -> None:
    cobalt = MATERIALS["cobalt"]
    white = MATERIALS["white"]
    red = MATERIALS["red"]
    sole = MATERIALS["sole"]
    beige = MATERIALS["beige"]
    black = MATERIALS["black"]

    body = append_cc0_body()
    reshape_cc0_body(body)

    # The coherent CC0 arms terminate inside the retained glove placeholders.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        lower = f"lower_arm.{side}"
        hand = f"hand.{side}"
        torus(f"SANIC_GloveCuff.{side}", (1.93 * sign, -0.19, 2.86), 0.30, 0.09, white, ((lower, 0.35), (hand, 0.65)), axis=(0.52 * sign, -0.10, -0.85))
        uv_sphere(f"SANIC_Glove.{side}", (2.04 * sign, -0.245, 2.68), (0.34, 0.28, 0.35), white, ((hand, 1.0),))
        for digit, offset in enumerate((-0.15, -0.05, 0.05, 0.15), 1):
            uv_sphere(
                f"SANIC_Finger{digit}.{side}",
                (2.04 * sign + offset, -0.405, 2.64 + 0.025 * abs(offset / 0.05)),
                (0.072, 0.13, 0.17),
                white,
                ((hand, 1.0),),
                rotation=(math.radians(12), 0.0, math.radians(-8 * sign)),
            )
        uv_sphere(f"SANIC_Thumb.{side}", (1.84 * sign, -0.37, 2.72), (0.12, 0.13, 0.19), white, ((hand, 1.0),), rotation=(0.0, math.radians(22 * sign), 0.0))

    # Keep the source hands and feet until Task 3 isolates glove/shoe regions.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        lower = f"lower_leg.{side}"
        foot = f"foot.{side}"
        torus(f"SANIC_SockCuff.{side}", (0.51 * sign, -0.01, 0.43), 0.31, 0.075, white, ((lower, 0.35), (foot, 0.65)))
        rounded_box(f"SANIC_Sole.{side}", (0.51 * sign, -0.30, 0.095), (0.49, 0.76, 0.095), 0.085, sole, ((foot, 1.0),))
        rounded_box(f"SANIC_Midsole.{side}", (0.51 * sign, -0.31, 0.175), (0.47, 0.73, 0.075), 0.07, MATERIALS["midsole"], ((foot, 1.0),))
        rounded_box(f"SANIC_Shoe.{side}", (0.51 * sign, -0.30, 0.31), (0.43, 0.66, 0.22), 0.17, red, ((foot, 1.0),))
        uv_sphere(f"SANIC_ShoeToe.{side}", (0.51 * sign, -0.78, 0.31), (0.44, 0.36, 0.24), red, ((foot, 1.0),))
        rounded_box(f"SANIC_ShoeStrap.{side}", (0.51 * sign, -0.38, 0.45), (0.46, 0.15, 0.085), 0.065, white, ((foot, 1.0),), rotation=(math.radians(-9), 0.0, 0.0))

    # Face: mask-like drooping eyes, sculpted muzzle/lips, black nose and lids.
    uv_sphere("SANIC_Head", (0.0, -0.01, 5.08), (0.74, 0.62, 0.86), cobalt, (("head", 1.0),), subdiv=2, segments=32, ring_count=24)
    uv_sphere("SANIC_Ear.L", (0.63, 0.02, 5.10), (0.22, 0.15, 0.27), cobalt, (("head", 1.0),), rotation=(0.0, math.radians(-15), 0.0))
    uv_sphere("SANIC_Ear.R", (-0.63, 0.02, 5.10), (0.22, 0.15, 0.27), cobalt, (("head", 1.0),), rotation=(0.0, math.radians(15), 0.0))
    uv_sphere("SANIC_EarInner.L", (0.64, -0.13, 5.10), (0.11, 0.05, 0.15), beige, (("head", 1.0),))
    uv_sphere("SANIC_EarInner.R", (-0.64, -0.13, 5.10), (0.11, 0.05, 0.15), beige, (("head", 1.0),))
    uv_sphere("SANIC_Eyes", (0.235, -0.59, 5.22), (0.33, 0.115, 0.31), white, (("head", 1.0),), rotation=(0.0, math.radians(-7), math.radians(-4)), subdiv=2, segments=32, ring_count=24)
    uv_sphere("SANIC_Eye.R", (-0.235, -0.59, 5.22), (0.33, 0.115, 0.31), white, (("head", 1.0),), rotation=(0.0, math.radians(7), math.radians(4)), subdiv=2, segments=32, ring_count=24)
    rounded_box("SANIC_Lid.L", (0.235, -0.711, 5.28), (0.28, 0.045, 0.046), 0.035, black, (("head", 1.0),), rotation=(0.0, math.radians(-4), math.radians(-5)))
    rounded_box("SANIC_Lid.R", (-0.235, -0.711, 5.28), (0.28, 0.045, 0.046), 0.035, black, (("head", 1.0),), rotation=(0.0, math.radians(4), math.radians(5)))
    capsule_between("SANIC_Brow.L", (-0.02, -0.705, 5.48), (0.46, -0.655, 5.43), 0.043, black, (("head", 1.0),), squash=0.62)
    capsule_between("SANIC_Brow.R", (0.02, -0.705, 5.48), (-0.46, -0.655, 5.43), 0.043, black, (("head", 1.0),), squash=0.62)
    uv_sphere("SANIC_Muzzle", (0.0, -0.675, 4.87), (0.48, 0.17, 0.30), beige, (("head", 1.0),), subdiv=2, segments=32, ring_count=24)
    uv_sphere("SANIC_MuzzleCheek.L", (0.30, -0.69, 4.89), (0.28, 0.15, 0.24), beige, (("head", 1.0),), subdiv=2, segments=32, ring_count=24)
    uv_sphere("SANIC_MuzzleCheek.R", (-0.30, -0.69, 4.89), (0.28, 0.15, 0.24), beige, (("head", 1.0),), subdiv=2, segments=32, ring_count=24)
    uv_sphere("SANIC_Nose", (0.0, -0.807, 5.07), (0.18, 0.15, 0.16), black, (("head", 1.0),))
    uv_sphere("SANIC_Nostril.L", (0.07, -0.943, 5.045), (0.032, 0.022, 0.025), sole, (("head", 1.0),), subdiv=0)
    uv_sphere("SANIC_Nostril.R", (-0.07, -0.943, 5.045), (0.032, 0.022, 0.025), sole, (("head", 1.0),), subdiv=0)
    capsule_between("SANIC_Mouth", (-0.235, -0.862, 4.82), (0.235, -0.862, 4.82), 0.075, black, (("head", 1.0),), squash=0.62)
    capsule_between("SANIC_LipUpper", (-0.25, -0.887, 4.87), (0.25, -0.887, 4.87), 0.052, beige, (("head", 1.0),), squash=0.72, subdiv=2, segments=32, ring_count=24)
    capsule_between("SANIC_LipLower", (-0.22, -0.89, 4.75), (0.22, -0.89, 4.75), 0.061, beige, (("head", 1.0),), squash=0.76, subdiv=2, segments=32, ring_count=24)
    brow_text()

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
        "SANIC_Eyes",
        "SANIC_Eye.R",
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
    rig.animation_data_create()
    actions: dict[str, bpy.types.Action] = {}

    def key_pose(
        frame: int,
        rotations: dict[str, tuple[float, float, float]] | None = None,
        root_z: float = 0.0,
        root_scale: float = 1.0,
        chest_scale: float = 1.0,
    ) -> None:
        rotations = rotations or {}
        for pose_bone in rig.pose.bones:
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = rotations.get(pose_bone.name, (0.0, 0.0, 0.0))
            pose_bone.location = (0.0, 0.0, root_z if pose_bone.name == "root" else 0.0)
            pose_bone.scale = (1.0, 1.0, chest_scale if pose_bone.name == "chest" else 1.0)
            pose_bone.keyframe_insert("rotation_euler", frame=frame, group=pose_bone.name)
            pose_bone.keyframe_insert("location", frame=frame, group=pose_bone.name)
            pose_bone.keyframe_insert("scale", frame=frame, group=pose_bone.name)
        rig.scale = (1.0, 1.0, root_scale)
        rig.keyframe_insert("scale", frame=frame)

    def make(
        name: str,
        end: int,
        poses: list[tuple[int, dict[str, tuple[float, float, float]], float, float, float]],
        cyclic: bool = False,
    ) -> bpy.types.Action:
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = 1
        action.frame_end = end
        action.use_cyclic = cyclic
        rig.animation_data.action = action
        for frame, rotations, root_z, root_scale, chest_scale in poses:
            key_pose(frame, rotations, root_z, root_scale, chest_scale)
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        track.mute = True
        rig.animation_data.action = None
        actions[name] = action
        return action

    make(
        "Idle",
        48,
        [
            (1, {}, 0.0, 1.0, 1.0),
            (24, {"head": (0.035, 0.0, 0.02), "chest": (-0.018, 0.0, 0.0)}, 0.025, 1.0, 1.035),
            (48, {}, 0.0, 1.0, 1.0),
        ],
        cyclic=True,
    )
    run_a = {
        "upper_arm.L": (1.05, 0.0, 0.08), "upper_arm.R": (-1.05, 0.0, -0.08),
        "lower_arm.L": (-0.45, 0.0, 0.0), "lower_arm.R": (-0.75, 0.0, 0.0),
        "upper_leg.L": (-0.92, 0.0, 0.03), "upper_leg.R": (0.92, 0.0, -0.03),
        "lower_leg.L": (0.55, 0.0, 0.0), "lower_leg.R": (-0.80, 0.0, 0.0),
        "foot.L": (0.28, 0.0, 0.0), "foot.R": (-0.25, 0.0, 0.0), "head": (-0.06, 0.0, 0.0),
    }
    run_b = {name: (-rot[0], rot[1], -rot[2]) for name, rot in run_a.items()}
    make(
        "Run",
        24,
        [(1, run_a, 0.03, 1.0, 1.0), (7, {}, -0.08, 0.93, 1.03), (13, run_b, 0.03, 1.0, 1.0), (19, {}, -0.08, 0.93, 1.03), (24, run_a, 0.03, 1.0, 1.0)],
        cyclic=True,
    )
    jump_tuck = {
        "upper_arm.L": (-0.72, 0.0, 0.25), "upper_arm.R": (-0.72, 0.0, -0.25),
        "upper_leg.L": (1.05, 0.0, 0.0), "upper_leg.R": (1.05, 0.0, 0.0),
        "lower_leg.L": (-1.18, 0.0, 0.0), "lower_leg.R": (-1.18, 0.0, 0.0),
        "head": (-0.13, 0.0, 0.0),
    }
    make(
        "Jump",
        36,
        [(1, {}, 0.0, 1.0, 1.0), (7, {"upper_leg.L": (0.38, 0.0, 0.0), "upper_leg.R": (0.38, 0.0, 0.0), "lower_leg.L": (-0.45, 0.0, 0.0), "lower_leg.R": (-0.45, 0.0, 0.0)}, -0.10, 0.90, 1.04), (18, jump_tuck, 0.55, 1.0, 1.0), (28, {"upper_arm.L": (0.35, 0.0, 0.18), "upper_arm.R": (0.35, 0.0, -0.18)}, 0.10, 1.04, 0.98), (36, {}, 0.0, 1.0, 1.0)],
    )
    crash_pose = {
        "chest": (0.46, 0.0, 0.0), "head": (-0.38, 0.0, 0.12),
        "upper_arm.L": (-1.22, 0.0, 0.30), "upper_arm.R": (-1.22, 0.0, -0.30),
        "lower_arm.L": (-0.65, 0.0, 0.0), "lower_arm.R": (-0.65, 0.0, 0.0),
        "upper_leg.L": (0.28, 0.0, 0.0), "upper_leg.R": (0.28, 0.0, 0.0),
    }
    make("Crash", 30, [(1, {}, 0.0, 1.0, 1.0), (8, crash_pose, -0.04, 0.91, 0.94), (17, {**crash_pose, "head": (0.24, 0.0, -0.10)}, -0.12, 0.88, 0.92), (30, {}, 0.0, 1.0, 1.0)])
    rig.animation_data.action = actions["Idle"]
    bpy.context.scene.frame_set(1)
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
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)
    print("SANIC_EXPORT_COMPLETE", {"source_triangles": source_triangles, "web_triangles": web_triangles, "scene_triangles": total_triangles, "blend": str(BLEND_PATH), "glb": str(GLB_PATH)})


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
