"""Build a non-destructive corrected Meshy SANIC rigging master.

The raw generated GLB remains untouched and is preserved inside an excluded
collection in the saved Blender source. Generated binary handoff files stay
outside the repository.

Usage::

    SANIC_MESHY_SOURCE=/path/to/SANIC-meshy6-v1.glb \
    SANIC_MESHY_OUTPUT_DIR=/path/to/output \
    blender --background --factory-startup \
      --python blender/scripts/correct_meshy_sanic.py
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SOURCE = Path(os.environ["SANIC_MESHY_SOURCE"]).expanduser().resolve()
OUTPUT_DIR = Path(
    os.environ.get("SANIC_MESHY_OUTPUT_DIR", SOURCE.parent)
).expanduser().resolve()
BLEND_PATH = OUTPUT_DIR / "SANIC-meshy6-v1-corrected.blend"
CHARACTER_GLB = OUTPUT_DIR / "SANIC-meshy6-v1-corrected.glb"

TARGET_HEIGHT = 1.70
RAW_COLLECTION_NAME = "SANIC_RAW_PRIVATE"
CHARACTER_COLLECTION_NAME = "SANIC_CHARACTER_EXPORT"
SPIN_COLLECTION_NAME = "SANIC_SPIN_EXPORT"


def reset_scene() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"SANIC Meshy source does not exist: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_EEVEE"


def new_collection(name: str) -> bpy.types.Collection:
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def move_to_collection(
    obj: bpy.types.Object,
    destination: bpy.types.Collection,
) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    destination.objects.link(obj)


def find_layer_collection(
    root: bpy.types.LayerCollection,
    name: str,
) -> bpy.types.LayerCollection | None:
    if root.collection.name == name:
        return root
    for child in root.children:
        match = find_layer_collection(child, name)
        if match is not None:
            return match
    return None


def material(
    name: str,
    color: tuple[float, float, float, float],
    *,
    roughness: float,
    metallic: float = 0.0,
) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = color
    principled = result.node_tree.nodes.get("Principled BSDF")
    assert principled is not None
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic
    return result


def object_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector(
            (
                min(point.x for point in points),
                min(point.y for point in points),
                min(point.z for point in points),
            )
        ),
        Vector(
            (
                max(point.x for point in points),
                max(point.y for point in points),
                max(point.z for point in points),
            )
        ),
    )


def mesh_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    assert points, f"{obj.name} has no vertices"
    return (
        Vector(
            (
                min(point.x for point in points),
                min(point.y for point in points),
                min(point.z for point in points),
            )
        ),
        Vector(
            (
                max(point.x for point in points),
                max(point.y for point in points),
                max(point.z for point in points),
            )
        ),
    )


def import_private_source(
    raw_collection: bpy.types.Collection,
) -> bpy.types.Object:
    result = bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    assert result == {"FINISHED"}, result
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    assert len(meshes) == 1, f"Expected one Meshy mesh, got {[obj.name for obj in meshes]}"
    source = meshes[0]
    source.name = "SANIC_RawMeshySource"
    source.data.name = "SANIC_RawMeshySource_Mesh"
    move_to_collection(source, raw_collection)
    source.hide_render = True
    source.hide_set(True)
    return source


def duplicate_working_body(
    source: bpy.types.Object,
    character_collection: bpy.types.Collection,
) -> bpy.types.Object:
    body = source.copy()
    body.data = source.data.copy()
    body.name = "SANIC_BodyBase"
    body.data.name = "SANIC_BodyBase_Mesh"
    body.hide_render = False
    body.hide_viewport = False
    character_collection.objects.link(body)
    return body


def correct_crown_and_remove_hand_tips(body: bpy.types.Object) -> None:
    mesh = body.data
    coordinates = [vertex.co.copy() for vertex in mesh.vertices]
    minimum_x = min(point.x for point in coordinates)
    maximum_x = max(point.x for point in coordinates)
    center_x = (minimum_x + maximum_x) * 0.5
    half_width = (maximum_x - minimum_x) * 0.5

    cutoff = half_width * 0.83
    bm = bmesh.new()
    bm.from_mesh(mesh)
    remove = [
        vertex
        for vertex in bm.verts
        if abs(vertex.co.x - center_x) > cutoff
    ]
    assert remove, "Expected pointed Meshy hand vertices beyond the cuff planes"
    bmesh.ops.delete(bm, geom=remove, context="VERTS")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    bpy.context.view_layer.update()


def normalize_body(body: bpy.types.Object) -> None:
    minimum, maximum = mesh_bounds(body)
    height = maximum.z - minimum.z
    assert height > 0.0
    uniform_scale = TARGET_HEIGHT / height
    body.scale = (uniform_scale, uniform_scale, uniform_scale)
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    body.select_set(False)

    minimum, maximum = mesh_bounds(body)
    center_x = (minimum.x + maximum.x) * 0.5
    center_y = (minimum.y + maximum.y) * 0.5
    body.location = (-center_x, -center_y, -minimum.z)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.select_set(False)


def finish_mesh(
    obj: bpy.types.Object,
    mat: bpy.types.Material,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    move_to_collection(obj, collection)
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def ellipsoid(
    name: str,
    location: Vector,
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    segments: int = 24,
    rings: int = 14,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, mat, collection)


def capsule_between(
    name: str,
    start: Vector,
    end: Vector,
    radius: float,
    mat: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    segments: int = 16,
) -> bpy.types.Object:
    delta = end - start
    obj = ellipsoid(
        name,
        (start + end) * 0.5,
        (radius, radius, max(radius, delta.length * 0.56)),
        mat,
        collection,
        segments=segments,
        rings=max(8, segments // 2),
    )
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = delta.to_track_quat("Z", "Y")
    return obj


def join_objects(
    objects: list[bpy.types.Object],
    name: str,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    assert objects
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    active = objects[0]
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    active.name = name
    move_to_collection(active, collection)
    return active


def conform_to_surface(
    obj: bpy.types.Object,
    target: bpy.types.Object,
    offset: float,
) -> None:
    modifier = obj.modifiers.new("SANIC_FaceConform", "SHRINKWRAP")
    modifier.target = target
    modifier.wrap_method = "NEAREST_SURFACEPOINT"
    modifier.wrap_mode = "ON_SURFACE"
    modifier.offset = offset
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    result = bpy.ops.object.modifier_apply(modifier=modifier.name)
    assert result == {"FINISHED"}, result
    obj.select_set(False)


def cuff_anchor(body: bpy.types.Object, side: str) -> Vector:
    sign = -1.0 if side == "L" else 1.0
    points = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
    extreme_x = min(point.x for point in points) if sign < 0.0 else max(
        point.x for point in points
    )
    tolerance = TARGET_HEIGHT * 0.012
    region = [
        point
        for point in points
        if abs(point.x - extreme_x) <= tolerance
        and TARGET_HEIGHT * 0.55 <= point.z <= TARGET_HEIGHT * 0.75
    ]
    assert region, f"Could not locate {side} cuff anchor"
    return Vector(
        (
            extreme_x,
            sum(point.y for point in region) / len(region),
            sum(point.z for point in region) / len(region),
        )
    )


def build_glove(
    side: str,
    anchor: Vector,
    hand_length: float,
    mat: bpy.types.Material,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    sign = -1.0 if side == "L" else 1.0
    palm_center = anchor + Vector((sign * hand_length * 0.28, 0.0, 0.0))
    parts = [
        ellipsoid(
            f"SANIC_GlovePalm.{side}",
            palm_center,
            (hand_length * 0.30, hand_length * 0.17, hand_length * 0.21),
            mat,
            collection,
            segments=24,
            rings=14,
        )
    ]
    digit_specs = (
        ("Index", -0.025, 0.90, 0.12),
        ("Middle", -0.008, 1.00, 0.040),
        ("Ring", 0.008, 0.92, -0.040),
        ("Pinky", 0.025, 0.78, -0.12),
    )
    for label, y_factor, length_scale, z_factor in digit_specs:
        start = anchor + Vector(
            (
                sign * hand_length * 0.43,
                hand_length * y_factor,
                hand_length * z_factor,
            )
        )
        tip = anchor + Vector(
            (
                sign * hand_length * 0.98 * length_scale,
                hand_length * y_factor * 1.08,
                hand_length * (z_factor - 0.055),
            )
        )
        parts.append(
            capsule_between(
                f"SANIC_{label}.{side}",
                start,
                tip,
                hand_length * 0.070,
                mat,
                collection,
                segments=20,
            )
        )

    thumb_start = anchor + Vector(
        (sign * hand_length * 0.17, -hand_length * 0.03, -hand_length * 0.16)
    )
    thumb_tip = anchor + Vector(
        (sign * hand_length * 0.54, -hand_length * 0.17, -hand_length * 0.31)
    )
    parts.append(
        capsule_between(
            f"SANIC_Thumb.{side}",
            thumb_start,
            thumb_tip,
            hand_length * 0.088,
            mat,
            collection,
            segments=20,
        )
    )
    return join_objects(parts, f"SANIC_Glove.{side}", collection)


def build_sleepy_face_overlays(
    body: bpy.types.Object,
    dark: bpy.types.Material,
    collection: bpy.types.Collection,
) -> list[bpy.types.Object]:
    minimum, maximum = mesh_bounds(body)
    height = maximum.z - minimum.z
    eye_z = minimum.z + height * 0.852
    eye_x = height * 0.053
    body_points = [body.matrix_world @ vertex.co for vertex in body.data.vertices]

    def surface_y(x: float, z: float) -> float:
        search_radius = height * 0.032
        candidates = [
            point
            for point in body_points
            if abs(point.x - x) <= search_radius
            and abs(point.z - z) <= search_radius
        ]
        assert candidates, f"Could not find face surface near x={x:.4f}, z={z:.4f}"
        return min(point.y for point in candidates) - height * 0.0015

    def face_point(x: float, z: float) -> Vector:
        return Vector((x, surface_y(x, z), z))

    overlays: list[bpy.types.Object] = []

    for side, sign in (("L", -1.0), ("R", 1.0)):
        eyelid_outer = face_point(
            sign * (eye_x + height * 0.033),
            eye_z + height * 0.008,
        )
        eyelid_inner = face_point(
            sign * (eye_x - height * 0.030),
            eye_z + height * 0.002,
        )
        eyelid = capsule_between(
            f"SANIC_Face_Eyelid.{side}",
            eyelid_outer,
            eyelid_inner,
            height * 0.0045,
            dark,
            collection,
            segments=24,
        )
        conform_to_surface(eyelid, body, height * 0.002)
        overlays.append(eyelid)

        outer = face_point(
            sign * (eye_x + height * 0.036),
            eye_z + height * 0.051,
        )
        inner = face_point(
            sign * (eye_x - height * 0.030),
            eye_z + height * 0.044,
        )
        brow = capsule_between(
            f"SANIC_Face_Brow.{side}",
            outer,
            inner,
            height * 0.006,
            dark,
            collection,
            segments=16,
        )
        conform_to_surface(brow, body, height * 0.002)
        overlays.append(brow)
    return overlays


def export_selected(objects: list[bpy.types.Object], path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    result = bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_materials="EXPORT",
        export_tangents=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_extras=True,
    )
    assert result == {"FINISHED"}, result


def main() -> None:
    reset_scene()
    raw_collection = new_collection(RAW_COLLECTION_NAME)
    character_collection = new_collection(CHARACTER_COLLECTION_NAME)
    new_collection(SPIN_COLLECTION_NAME)

    raw = import_private_source(raw_collection)
    body = duplicate_working_body(raw, character_collection)
    correct_crown_and_remove_hand_tips(body)
    normalize_body(body)

    white = material(
        "SANIC_MAT_CorrectedGlove",
        (0.94, 0.965, 1.0, 1.0),
        roughness=0.48,
    )
    dark = material(
        "SANIC_MAT_CorrectedBrow",
        (0.004, 0.006, 0.012, 1.0),
        roughness=0.52,
    )

    hand_length = TARGET_HEIGHT * 0.105
    gloves = [
        build_glove(
            side,
            cuff_anchor(body, side),
            hand_length,
            white,
            character_collection,
        )
        for side in ("L", "R")
    ]
    face_overlays = build_sleepy_face_overlays(
        body,
        dark,
        character_collection,
    )

    raw_layer = find_layer_collection(
        bpy.context.view_layer.layer_collection,
        RAW_COLLECTION_NAME,
    )
    assert raw_layer is not None
    raw_layer.exclude = True

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)
    character_objects = [body, *gloves, *face_overlays]
    export_selected(character_objects, CHARACTER_GLB)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)

    minimum, maximum = object_bounds(body)
    print(
        "SANIC_CORRECTION_BUILD=PASS",
        {
            "source": str(SOURCE),
            "blend": str(BLEND_PATH),
            "character_glb": str(CHARACTER_GLB),
            "body_dimensions": tuple(round(value, 6) for value in maximum - minimum),
            "character_objects": [obj.name for obj in character_objects],
        },
    )


if __name__ == "__main__":
    main()
