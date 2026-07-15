"""Build SANIC's original ring collectible and modular meme-forest kit.

This script is designed to be executed inside Blender 5.1+ through Blender MCP.
It discovers the active checkout dynamically; no disposable worktree path is baked
into the source or generated assets.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


def resolve_project_root() -> Path:
    """Resolve the active SANIC checkout without assuming its directory name."""
    override = globals().get("SANIC_PROJECT_ROOT") or os.environ.get("SANIC_PROJECT_ROOT")

    def valid_root(candidate: Path) -> bool:
        return (
            (candidate / "package.json").is_file()
            and (candidate / "blender" / "scripts" / "build_world.py").is_file()
        )

    if override:
        explicit = Path(override).expanduser().resolve()
        if not valid_root(explicit):
            raise RuntimeError(f"SANIC_PROJECT_ROOT is not a SANIC checkout: {explicit}")
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
    raise RuntimeError("Could not locate SANIC checkout; set SANIC_PROJECT_ROOT explicitly")


ROOT = resolve_project_root()
BLEND_PATH = ROOT / "blender" / "world-source.blend"
RING_PATH = ROOT / "public" / "models" / "sanic-ring.glb"
KIT_PATH = ROOT / "public" / "models" / "forest-kit.glb"

RING_COLLECTION: bpy.types.Collection | None = None
KIT_COLLECTION: bpy.types.Collection | None = None
PRESENTATION_COLLECTION: bpy.types.Collection | None = None
MATERIALS: dict[str, bpy.types.Material] = {}


def reset_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for datablocks in (
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
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.018, 0.028, 0.045)
    scene.view_settings.look = "AgX - Medium High Contrast"
    MATERIALS.clear()


def new_collection(name: str) -> bpy.types.Collection:
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def move_to_collection(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    target.objects.link(obj)


def make_material(
    name: str,
    color: tuple[float, float, float, float],
    *,
    metallic: float = 0.0,
    roughness: float = 0.55,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = color
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    coat = bsdf.inputs.get("Coat Weight")
    if coat:
        coat.default_value = 0.12 if metallic else 0.025
    emission_color = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    emission_power = bsdf.inputs.get("Emission Strength")
    if emission and emission_color:
        emission_color.default_value = emission
    if emission_power:
        emission_power.default_value = emission_strength
    material["sanic_palette"] = True
    return material


def setup_materials() -> None:
    MATERIALS.update(
        gold=make_material("WORLD_Gold", (1.0, 0.49, 0.018, 1.0), metallic=0.92, roughness=0.19),
        gold_light=make_material("WORLD_GoldLight", (1.0, 0.79, 0.13, 1.0), metallic=0.72, roughness=0.20),
        glow=make_material(
            "WORLD_GoldGlow",
            (1.0, 0.34, 0.008, 1.0),
            metallic=0.44,
            roughness=0.24,
            emission=(1.0, 0.13, 0.002, 1.0),
            emission_strength=2.8,
        ),
        navy=make_material("WORLD_PlaqueNavy", (0.015, 0.028, 0.13, 1.0), metallic=0.12, roughness=0.28),
        bark=make_material("WORLD_Bark", (0.20, 0.055, 0.018, 1.0), roughness=0.84),
        bark_light=make_material("WORLD_BarkLight", (0.46, 0.17, 0.035, 1.0), roughness=0.74),
        leaf=make_material("WORLD_Leaf", (0.035, 0.38, 0.075, 1.0), roughness=0.64),
        leaf_light=make_material("WORLD_LeafLight", (0.10, 0.69, 0.095, 1.0), roughness=0.56),
        grass=make_material("WORLD_Grass", (0.14, 0.77, 0.14, 1.0), roughness=0.68),
        fern=make_material("WORLD_Fern", (0.02, 0.47, 0.15, 1.0), roughness=0.65),
        rock=make_material("WORLD_Rock", (0.22, 0.29, 0.34, 1.0), metallic=0.08, roughness=0.83),
        rock_light=make_material("WORLD_RockLight", (0.43, 0.51, 0.49, 1.0), roughness=0.75),
        cream=make_material("WORLD_Cream", (1.0, 0.82, 0.47, 1.0), roughness=0.55),
        red=make_material("WORLD_DangerRed", (0.77, 0.018, 0.025, 1.0), metallic=0.05, roughness=0.39),
        flame=make_material(
            "WORLD_Flame",
            (1.0, 0.28, 0.012, 1.0),
            roughness=0.26,
            emission=(1.0, 0.08, 0.001, 1.0),
            emission_strength=3.6,
        ),
        soil=make_material("WORLD_Soil", (0.095, 0.025, 0.018, 1.0), roughness=0.92),
        gap=make_material("WORLD_Gap", (0.008, 0.011, 0.024, 1.0), roughness=0.96),
        sign=make_material("WORLD_SignWood", (0.54, 0.20, 0.035, 1.0), roughness=0.72),
        letters=make_material(
            "WORLD_SignLetters",
            (1.0, 0.72, 0.07, 1.0),
            metallic=0.20,
            roughness=0.34,
            emission=(1.0, 0.30, 0.01, 1.0),
            emission_strength=0.55,
        ),
    )


def assign(obj: bpy.types.Object, material: bpy.types.Material) -> bpy.types.Object:
    obj.data.materials.append(material)
    return obj


def apply_modifier(obj: bpy.types.Object, modifier_name: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier_name)


def cube_part(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    material: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    bevel: float = 0.04,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("WORLD_SoftBevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        modifier.limit_method = "ANGLE"
        apply_modifier(obj, modifier.name)
    return assign(obj, material)


def cylinder_part(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    material: bpy.types.Material,
    *,
    vertices: int = 16,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    radius_top: float | None = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius,
        radius2=radius if radius_top is None else radius_top,
        depth=depth,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    bevel = obj.modifiers.new("WORLD_EdgeBevel", "BEVEL")
    bevel.width = min(radius * 0.10, 0.045)
    bevel.segments = 2
    apply_modifier(obj, bevel.name)
    return assign(obj, material)


def ico_part(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    material: bpy.types.Material,
    *,
    subdivisions: int = 2,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1.0, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return assign(obj, material)


def text_part(
    name: str,
    body: str,
    location: tuple[float, float, float],
    size: float,
    material: bpy.types.Material,
    *,
    extrude: float = 0.018,
    align_x: str = "CENTER",
) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}_Curve", "FONT")
    curve.body = body
    curve.align_x = align_x
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = extrude
    curve.bevel_depth = 0.006
    curve.bevel_resolution = 2
    curve.resolution_u = 3
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    # Blender text faces local +Z; +90 degrees around X presents it toward -Y.
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return obj


def finalize_root(
    name: str,
    parts: list[bpy.types.Object],
    target: bpy.types.Collection,
    *,
    label: str | None = None,
) -> bpy.types.Object:
    if not parts:
        raise ValueError(f"No parts supplied for {name}")
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.hide_set(False)
        part.select_set(True)
    active = parts[0]
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    active.name = name
    active.data.name = f"{name}_Mesh"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    except TypeError:
        bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode="OBJECT")
    triangulate = active.modifiers.new("WORLD_Triangulate", "TRIANGULATE")
    triangulate.keep_custom_normals = True
    apply_modifier(active, triangulate.name)
    for polygon in active.data.polygons:
        polygon.use_smooth = True
    move_to_collection(active, target)
    active["sanic_world_root"] = True
    active["forward_axis"] = "-Z (glTF Y-up)"
    if label:
        active["label"] = label
    return active


def build_ring() -> bpy.types.Object:
    assert RING_COLLECTION is not None
    parts: list[bpy.types.Object] = []
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.64,
        minor_radius=0.155,
        major_segments=48,
        minor_segments=16,
        location=(0.0, 0.0, 0.0),
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    torus = bpy.context.object
    torus.name = "RING_BevelBody"
    assign(torus, MATERIALS["gold"])
    bevel = torus.modifiers.new("RING_Polish", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 3
    apply_modifier(torus, bevel.name)
    parts.append(torus)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.455,
        minor_radius=0.027,
        major_segments=40,
        minor_segments=8,
        location=(0.0, -0.045, 0.0),
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    inner = bpy.context.object
    inner.name = "RING_EmissiveInnerRim"
    parts.append(assign(inner, MATERIALS["glow"]))

    plaque = cylinder_part(
        "RING_InsetPlaque",
        (0.0, 0.015, 0.0),
        0.315,
        0.115,
        MATERIALS["navy"],
        vertices=48,
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    parts.append(plaque)
    parts.append(text_part("RING_Dollar", "$", (0.0, -0.066, 0.0), 0.50, MATERIALS["gold_light"], extrude=0.025))
    ring = finalize_root("SANIC_Ring", parts, RING_COLLECTION, label="$SANIC")
    ring["pivot"] = "center"
    return ring


def build_tree(name: str, variant: int) -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    if variant == 1:
        height, trunk_radius = 5.15, 0.34
        crown_data = [
            ((0.0, 0.0, 3.55), (1.10, 0.88, 1.05), "leaf"),
            ((-0.48, 0.03, 4.16), (0.78, 0.68, 0.84), "leaf_light"),
            ((0.48, 0.05, 4.25), (0.84, 0.70, 0.90), "leaf"),
            ((0.02, 0.02, 4.78), (0.73, 0.61, 0.72), "leaf_light"),
        ]
    else:
        height, trunk_radius = 4.45, 0.29
        crown_data = [
            ((0.0, 0.0, 3.15), (0.92, 0.74, 0.92), "leaf_light"),
            ((-0.42, 0.06, 3.64), (0.67, 0.58, 0.72), "leaf"),
            ((0.40, -0.02, 3.65), (0.66, 0.55, 0.68), "leaf_light"),
            ((0.0, 0.0, 4.10), (0.62, 0.53, 0.60), "leaf"),
        ]
    parts = [
        cylinder_part(
            f"{name}_Trunk",
            (0.0, 0.0, height * 0.39),
            trunk_radius,
            height * 0.78,
            MATERIALS["bark"],
            vertices=12,
            radius_top=trunk_radius * 0.52,
        ),
        cylinder_part(
            f"{name}_TrunkHighlight",
            (-trunk_radius * 0.42, -trunk_radius * 0.68, height * 0.34),
            trunk_radius * 0.10,
            height * 0.46,
            MATERIALS["bark_light"],
            vertices=8,
            radius_top=trunk_radius * 0.06,
        ),
    ]
    for index, (location, scale, material_key) in enumerate(crown_data):
        parts.append(ico_part(f"{name}_Crown{index}", location, scale, MATERIALS[material_key], subdivisions=2))
    return finalize_root(name, parts, KIT_COLLECTION)


def build_grass() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts: list[bpy.types.Object] = []
    for index, (x, y, height, lean) in enumerate(
        [
            (-0.28, 0.03, 0.62, -0.16),
            (-0.13, -0.08, 0.84, -0.10),
            (0.0, 0.02, 0.96, 0.0),
            (0.14, -0.05, 0.79, 0.11),
            (0.28, 0.04, 0.62, 0.18),
            (-0.08, 0.13, 0.58, 0.12),
            (0.10, 0.15, 0.65, -0.12),
        ]
    ):
        blade = cylinder_part(
            f"GrassBlade{index}",
            (x, y, height * 0.5),
            0.085,
            height,
            MATERIALS["grass"],
            vertices=4,
            radius_top=0.012,
            rotation=(0.0, lean, 0.0),
        )
        parts.append(blade)
    return finalize_root("KIT_Grass", parts, KIT_COLLECTION)


def build_fern() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts: list[bpy.types.Object] = [
        cylinder_part("FernStem", (0.0, 0.0, 0.48), 0.035, 0.96, MATERIALS["fern"], vertices=8, radius_top=0.018)
    ]
    for side in (-1.0, 1.0):
        for index in range(5):
            z = 0.24 + index * 0.13
            reach = 0.46 - index * 0.055
            leaf = ico_part(
                f"FernLeaf_{side}_{index}",
                (side * reach * 0.5, -0.01 * index, z),
                (reach * 0.55, 0.06, 0.09),
                MATERIALS["fern" if index % 2 else "grass"],
                subdivisions=1,
                rotation=(0.0, side * 0.16, side * 0.28),
            )
            parts.append(leaf)
    return finalize_root("KIT_Fern", parts, KIT_COLLECTION)


def build_rock() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts = [
        ico_part("RockMain", (0.0, 0.0, 0.38), (0.66, 0.50, 0.44), MATERIALS["rock"], subdivisions=2, rotation=(0.15, 0.08, 0.22)),
        ico_part("RockFacet", (-0.20, -0.40, 0.48), (0.26, 0.08, 0.19), MATERIALS["rock_light"], subdivisions=1, rotation=(0.18, 0.0, -0.25)),
    ]
    return finalize_root("KIT_Rock", parts, KIT_COLLECTION)


def build_mushroom() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts = [
        cylinder_part("MushroomStem", (0.0, 0.0, 0.28), 0.13, 0.56, MATERIALS["cream"], vertices=16, radius_top=0.10),
        ico_part("MushroomCap", (0.0, 0.0, 0.62), (0.43, 0.38, 0.19), MATERIALS["red"], subdivisions=2),
    ]
    for index, (x, y) in enumerate([(-0.17, -0.29), (0.16, -0.31), (0.0, -0.36)]):
        parts.append(ico_part(f"MushroomSpot{index}", (x, y, 0.66), (0.055, 0.035, 0.045), MATERIALS["cream"], subdivisions=1))
    return finalize_root("KIT_Mushroom", parts, KIT_COLLECTION)


def build_log() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts = [
        cylinder_part(
            "LogBody",
            (0.0, 0.0, 0.42),
            0.40,
            2.35,
            MATERIALS["bark"],
            vertices=16,
            rotation=(0.0, math.radians(90.0), 0.0),
        ),
        cylinder_part(
            "LogCutL",
            (-1.19, 0.0, 0.42),
            0.35,
            0.045,
            MATERIALS["bark_light"],
            vertices=16,
            rotation=(0.0, math.radians(90.0), 0.0),
        ),
        cylinder_part(
            "LogCutR",
            (1.19, 0.0, 0.42),
            0.35,
            0.045,
            MATERIALS["bark_light"],
            vertices=16,
            rotation=(0.0, math.radians(90.0), 0.0),
        ),
    ]
    for x in (-0.62, 0.36):
        parts.append(cylinder_part(f"LogBranch{x}", (x, 0.10, 0.68), 0.09, 0.43, MATERIALS["bark"], vertices=10, rotation=(0.5, 0.2, -0.25)))
    root = finalize_root("KIT_Log", parts, KIT_COLLECTION)
    root["collision_height"] = 0.84
    root["jumpable"] = True
    return root


def build_candle_barrier() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts: list[bpy.types.Object] = []
    for index, x in enumerate((-0.88, -0.44, 0.0, 0.44, 0.88)):
        height = 1.18 + (index % 2) * 0.18
        parts.append(cylinder_part(f"Candle{index}", (x, 0.0, height * 0.5), 0.13, height, MATERIALS["red"], vertices=16, radius_top=0.115))
        parts.append(ico_part(f"Flame{index}", (x, -0.02, height + 0.17), (0.09, 0.07, 0.19), MATERIALS["flame"], subdivisions=2))
    root = finalize_root("KIT_Candle", parts, KIT_COLLECTION)
    root["collision_height"] = 1.54
    root["jumpable"] = False
    return root


def build_fud() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts = [
        cube_part("FUD_Board", (0.0, 0.0, 1.02), (2.45, 0.22, 1.05), MATERIALS["red"], bevel=0.10),
        cube_part("FUD_FootL", (-0.78, 0.0, 0.36), (0.22, 0.28, 0.72), MATERIALS["bark"], bevel=0.04),
        cube_part("FUD_FootR", (0.78, 0.0, 0.36), (0.22, 0.28, 0.72), MATERIALS["bark"], bevel=0.04),
        text_part("FUD_Letters", "FUD", (0.0, -0.142, 1.04), 0.68, MATERIALS["cream"], extrude=0.025),
    ]
    root = finalize_root("KIT_FUD", parts, KIT_COLLECTION, label="FUD")
    root["collision_height"] = 1.55
    root["jumpable"] = False
    return root


def build_gap() -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    parts = [
        cube_part("GapVoid", (0.0, 0.0, 0.035), (2.55, 1.68, 0.07), MATERIALS["gap"], bevel=0.10),
        cube_part("GapRimFront", (0.0, -0.79, 0.105), (2.65, 0.18, 0.21), MATERIALS["soil"], bevel=0.07),
        cube_part("GapRimBack", (0.0, 0.79, 0.105), (2.65, 0.18, 0.21), MATERIALS["soil"], bevel=0.07),
        cube_part("GapRimL", (-1.23, 0.0, 0.09), (0.18, 1.48, 0.18), MATERIALS["soil"], bevel=0.06),
        cube_part("GapRimR", (1.23, 0.0, 0.09), (0.18, 1.48, 0.18), MATERIALS["soil"], bevel=0.06),
    ]
    root = finalize_root("KIT_Gap", parts, KIT_COLLECTION)
    root["depth"] = 1.68
    root["jumpable"] = True
    return root


def build_sign(name: str, label: str, text_size: float) -> bpy.types.Object:
    assert KIT_COLLECTION is not None
    board_width = 2.55
    parts = [
        cube_part(f"{name}_PostL", (-0.74, 0.0, 0.76), (0.18, 0.18, 1.52), MATERIALS["bark"], bevel=0.035),
        cube_part(f"{name}_PostR", (0.74, 0.0, 0.76), (0.18, 0.18, 1.52), MATERIALS["bark"], bevel=0.035),
        cube_part(f"{name}_Board", (0.0, 0.0, 1.64), (board_width, 0.18, 0.66), MATERIALS["sign"], bevel=0.095),
        text_part(f"{name}_Text", label, (0.0, -0.118, 1.65), text_size, MATERIALS["letters"], extrude=0.018),
    ]
    root = finalize_root(name, parts, KIT_COLLECTION, label=label)
    root["readable_text"] = label
    return root


def build_kit() -> list[bpy.types.Object]:
    return [
        build_tree("KIT_Tree_A", 1),
        build_tree("KIT_Tree_B", 2),
        build_grass(),
        build_fern(),
        build_rock(),
        build_mushroom(),
        build_log(),
        build_candle_barrier(),
        build_fud(),
        build_gap(),
        build_sign("KIT_Sign_Stimmy", "STIMMY LANE", 0.33),
        build_sign("KIT_Sign_Trenches", "FOR THE TRENCHES", 0.245),
        build_sign("KIT_Sign_Coping", "SIDELINED & COPING", 0.205),
        build_sign("KIT_Sign_Memes", "RETURN TO MEMES", 0.245),
    ]


def triangle_count(objects: list[bpy.types.Object]) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return total


def export_selected(objects: list[bpy.types.Object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
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


def add_presentation_clone(source: bpy.types.Object, location: tuple[float, float, float], rotation_z: float = 0.0) -> bpy.types.Object:
    assert PRESENTATION_COLLECTION is not None
    clone = source.copy()
    clone.data = source.data
    clone.name = f"PRESENT_{source.name}"
    PRESENTATION_COLLECTION.objects.link(clone)
    clone.location = location
    clone.rotation_euler.z = rotation_z
    clone["presentation_only"] = True
    return clone


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_presentation(ring: bpy.types.Object, kit: list[bpy.types.Object]) -> None:
    assert PRESENTATION_COLLECTION is not None
    ground = cube_part("PRESENT_Ground", (0.0, 2.6, -0.13), (14.5, 12.0, 0.25), MATERIALS["soil"], bevel=0.18)
    move_to_collection(ground, PRESENTATION_COLLECTION)

    positions = {
        "KIT_Tree_A": (-6.0, 7.4, 0.0),
        "KIT_Tree_B": (6.0, 7.4, 0.0),
        "KIT_Grass": (-4.6, 0.0, 0.0),
        "KIT_Fern": (-3.4, 0.0, 0.0),
        "KIT_Rock": (-2.0, 0.0, 0.0),
        "KIT_Mushroom": (-0.8, 0.0, 0.0),
        "KIT_Log": (1.1, 0.1, 0.0),
        "KIT_Candle": (4.5, 0.2, 0.0),
        "KIT_FUD": (-4.3, 2.4, 0.0),
        "KIT_Gap": (0.0, 2.8, 0.0),
        "KIT_Sign_Stimmy": (-4.4, 5.8, 0.0),
        "KIT_Sign_Trenches": (-1.48, 5.8, 0.0),
        "KIT_Sign_Coping": (1.48, 5.8, 0.0),
        "KIT_Sign_Memes": (4.4, 5.8, 0.0),
    }
    for root in kit:
        add_presentation_clone(root, positions[root.name])
    ring_clone = add_presentation_clone(ring, (0.0, -0.65, 2.35))
    ring_clone.scale = (1.45, 1.45, 1.45)

    bpy.ops.object.light_add(type="AREA", location=(-3.5, -5.0, 9.5))
    key = bpy.context.object
    key.name = "PRESENT_Key"
    key.data.energy = 1700
    key.data.shape = "DISK"
    key.data.size = 6.0
    key.data.color = (1.0, 0.62, 0.28)
    look_at(key, (0.0, 2.6, 1.5))
    move_to_collection(key, PRESENTATION_COLLECTION)
    bpy.ops.object.light_add(type="AREA", location=(5.5, 2.0, 6.0))
    fill = bpy.context.object
    fill.name = "PRESENT_Fill"
    fill.data.energy = 1000
    fill.data.size = 5.0
    fill.data.color = (0.20, 0.52, 1.0)
    look_at(fill, (0.0, 2.5, 1.2))
    move_to_collection(fill, PRESENTATION_COLLECTION)
    bpy.ops.object.light_add(type="AREA", location=(-1.5, 8.5, 5.5))
    rim = bpy.context.object
    rim.name = "PRESENT_Rim"
    rim.data.energy = 1250
    rim.data.size = 4.0
    rim.data.color = (0.3, 1.0, 0.28)
    look_at(rim, (0.0, 3.0, 1.4))
    move_to_collection(rim, PRESENTATION_COLLECTION)

    bpy.ops.object.camera_add(location=(8.4, -18.8, 9.0))
    camera = bpy.context.object
    camera.name = "PRESENT_Camera"
    camera.data.lens = 53
    camera.data.sensor_width = 36
    look_at(camera, (0.0, 2.85, 1.75))
    move_to_collection(camera, PRESENTATION_COLLECTION)
    bpy.context.scene.camera = camera


def build() -> None:
    global RING_COLLECTION, KIT_COLLECTION, PRESENTATION_COLLECTION
    reset_scene()
    RING_COLLECTION = new_collection("WORLD_RING_EXPORT")
    KIT_COLLECTION = new_collection("WORLD_KIT_EXPORT")
    PRESENTATION_COLLECTION = new_collection("WORLD_PRESENTATION")
    setup_materials()

    ring = build_ring()
    print("WORLD_RING_CHECKPOINT", {"triangles": triangle_count([ring]), "materials": len(ring.material_slots)})
    kit = build_kit()
    export_triangles = triangle_count([ring, *kit])
    assert triangle_count([ring]) < 12_000
    assert export_triangles < 120_000
    print("WORLD_KIT_CHECKPOINT", {"roots": [obj.name for obj in kit], "triangles": export_triangles})

    export_selected([ring], RING_PATH)
    export_selected(kit, KIT_PATH)
    setup_presentation(ring, kit)
    RING_COLLECTION.hide_viewport = True
    RING_COLLECTION.hide_render = True
    KIT_COLLECTION.hide_viewport = True
    KIT_COLLECTION.hide_render = True
    BLEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), check_existing=False)
    print(
        "WORLD_EXPORT_COMPLETE",
        {
            "root": str(ROOT),
            "blend": str(BLEND_PATH),
            "ring": str(RING_PATH),
            "kit": str(KIT_PATH),
            "triangles": export_triangles,
        },
    )


if globals().get("SANIC_SKIP_AUTORUN") is not True:
    build()
