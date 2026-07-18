"""Build a clean textured A-pose proxy for Meshy humanoid pose estimation.

This proxy is only a motion-generation bridge.  It deliberately omits SANIC's
quills, earring, gloves, shoes, face mesh, production skin, and armature.

Usage::

    blender --background --factory-startup --python-exit-code 1 \
      --python blender/scripts/prepare_meshy_rig_proxy.py -- \
      /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/proxy.glb
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from meshy_rig_proxy_spec import (  # noqa: E402
    EllipsoidPart,
    MATERIAL_COLORS,
    SegmentPart,
    proxy_parts,
)


REFERENCE_ROOT = Path(
    "/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference"
).resolve()
TEXTURE_SIZE = 32


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def safe_output_path(argument: str) -> Path:
    output_argument = Path(argument).expanduser()
    absolute = Path(os.path.abspath(output_argument))
    resolved = absolute.resolve()
    assert (
        absolute.is_relative_to(REFERENCE_ROOT)
        and resolved.is_relative_to(REFERENCE_ROOT)
    ), "Meshy proxy output must stay under the local reference root"
    assert resolved.suffix.lower() == ".glb", "Meshy proxy output must be GLB"
    return resolved


def create_textured_material(
    name: str,
    color: tuple[float, float, float, float],
) -> bpy.types.Material:
    image = bpy.data.images.new(
        f"{name}_Texture",
        width=TEXTURE_SIZE,
        height=TEXTURE_SIZE,
        alpha=True,
    )
    image.file_format = "PNG"
    image.pixels = list(color) * (TEXTURE_SIZE * TEXTURE_SIZE)
    image.pack()

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    shader.inputs["Roughness"].default_value = 0.72
    shader.inputs["Metallic"].default_value = 0.0
    material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def finish_mesh(
    obj: bpy.types.Object,
    material: bpy.types.Material,
) -> bpy.types.Object:
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.hide_render = False
    obj.hide_viewport = False
    return obj


def create_ellipsoid(
    part: EllipsoidPart,
    material: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32,
        ring_count=16,
        location=part.center,
    )
    obj = bpy.context.object
    obj.name = part.name
    obj.scale = part.radii
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, material)


def create_segment(
    part: SegmentPart,
    material: bpy.types.Material,
) -> bpy.types.Object:
    start = Vector(part.start)
    end = Vector(part.end)
    direction = end - start
    length = direction.length
    assert length > 0.0, f"{part.name} segment has no length"
    bpy.ops.mesh.primitive_cone_add(
        vertices=32,
        radius1=part.radius_start,
        radius2=part.radius_end,
        depth=length,
        end_fill_type="NGON",
        location=(start + end) / 2.0,
    )
    obj = bpy.context.object
    obj.name = part.name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(
        direction.normalized()
    )
    return finish_mesh(obj, material)


def build_proxy() -> list[bpy.types.Object]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials = {
        name: create_textured_material(name, color)
        for name, color in MATERIAL_COLORS.items()
    }
    objects: list[bpy.types.Object] = []
    for part in proxy_parts():
        material = materials[part.material]
        if isinstance(part, EllipsoidPart):
            objects.append(create_ellipsoid(part, material))
        elif isinstance(part, SegmentPart):
            objects.append(create_segment(part, material))
        else:
            raise AssertionError(f"Unsupported proxy part: {part}")
    return objects


def triangle_count(objects: list[bpy.types.Object]) -> int:
    return sum(len(obj.data.polygons) for obj in objects)


def export_proxy(
    objects: list[bpy.types.Object],
    output_path: Path,
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_materials="EXPORT",
        export_tangents=False,
        export_yup=True,
        export_draco_mesh_compression_enable=False,
    )
    assert result == {"FINISHED"}, result
    assert output_path.is_file(), "Meshy proxy export was not created"


def main() -> None:
    arguments = arguments_after_separator()
    assert len(arguments) == 1, "Expected exactly OUTPUT_GLB"
    output_path = safe_output_path(arguments[0])
    objects = build_proxy()
    export_proxy(objects, output_path)
    print(
        "MESHY_PROXY_EXPORT="
        + json.dumps(
            {
                "path": str(output_path),
                "bytes": output_path.stat().st_size,
                "meshes": len(objects),
                "triangles": triangle_count(objects),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
