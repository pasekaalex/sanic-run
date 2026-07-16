# SANIC Character Correction and Spin Ball Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the accepted Meshy 6 base into a correctly scaled, cleaner static SANIC rigging master and a lightweight dedicated spin-ball model without modifying or publishing the raw generation.

**Architecture:** A deterministic Blender build script imports the private raw GLB from a caller-supplied path, preserves it in a hidden source collection, creates a 1.70 m correction copy, replaces the pointed glove tips with five-digit glove assemblies, projects restrained sleepy-face overlays onto the actual surface, and builds a separate low-poly spin-ball. Direct deformation of the single textured quill surface is intentionally excluded after turnaround QA showed unacceptable UV stretching; the clean generated crown is preserved for a later manual topology pass. A second Blender script validates the exported GLBs, saved source scene, and deterministic renders. Generated binary assets remain in `/home/alex/Downloads/SANIC-Meshy-v1`; only reproducible scripts and tests enter the public repository.

**Tech Stack:** Blender 5.1 Python API, bmesh, Blender glTF exporter, GLB, Vitest for repository tests.

## Global Constraints

- Preserve `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.glb` byte-for-byte.
- Use no additional Meshy credits.
- Keep raw references, textures, task identifiers, and generated masters out of git.
- Target character height is `1.70` meters with the feet on `Z = 0`.
- The corrected master remains a neutral T-pose with separated arms and legs.
- Each glove visibly contains a palm, thumb, index, middle, ring, and pinky form.
- Shoes remain compact and no larger than the accepted Meshy generation.
- The spin ball is a separate mesh asset under `8,000` triangles and contains blue quills plus restrained red-shoe and white-glove flashes.
- No third-party character mesh, texture, skeleton, or animation is copied into the output.

---

### Task 1: Define executable correction validation

**Files:**
- Create: `blender/scripts/validate_meshy_correction.py`
- Read: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend`
- Read: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.glb`
- Read: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-spin-ball-v1.glb`

**Interfaces:**
- Consumes: `-- source|character|spin-ball` and the corresponding Blender file path.
- Produces: process exit `0` plus `SANIC_CORRECTION_VALIDATION=PASS`; failed assertions identify the violated asset contract.

- [ ] **Step 1: Write the validation script before the builder**

The script must implement these checks:

```python
EXPECTED_CORRECTED = {
    "SANIC_BodyBase",
    "SANIC_Glove.L",
    "SANIC_Glove.R",
    "SANIC_Face_Eyelid.L",
    "SANIC_Face_Eyelid.R",
    "SANIC_Face_Brow.L",
    "SANIC_Face_Brow.R",
}
EXPECTED_SPIN = {"SANIC_SpinBall"}

def renderable_bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))), \
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))

def triangle_count(objects):
    total = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        total += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    return total
```

For `source`, assert both export collections exist and the private raw collection is excluded from the active view layer. For `character`, assert the expected names, `1.68 <= height <= 1.72`, `abs(min_z) <= 0.002`, no armature/actions, and fewer than `180,000` evaluated triangles. For `spin-ball`, assert exactly one exported root named `SANIC_SpinBall`, a maximum dimension between `0.55` and `0.85` m, and at most `8,000` triangles.

- [ ] **Step 2: Run the validator to verify RED**

Run:

```bash
/usr/bin/blender --background --factory-startup \
  --python blender/scripts/validate_meshy_correction.py -- \
  character /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.glb
```

Expected: FAIL because the corrected asset does not exist yet.

- [ ] **Step 3: Keep the validator failure precise**

The missing-input branch must raise:

```python
raise FileNotFoundError(f"SANIC correction input does not exist: {asset_path}")
```

- [ ] **Step 4: Commit the red validator**

```bash
git add blender/scripts/validate_meshy_correction.py
git commit -m "test: define corrected SANIC asset contract"
```

### Task 2: Build the non-destructive corrected character master

**Files:**
- Create: `blender/scripts/correct_meshy_sanic.py`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.glb`
- Test: `blender/scripts/validate_meshy_correction.py`

**Interfaces:**
- Consumes: environment variable `SANIC_MESHY_SOURCE` and optional `SANIC_MESHY_OUTPUT_DIR`.
- Produces: the corrected `.blend` source and character-only `.glb` at stable handoff paths.

- [ ] **Step 1: Add input/output resolution and a clean scene**

```python
SOURCE = Path(os.environ["SANIC_MESHY_SOURCE"]).expanduser().resolve()
OUTPUT_DIR = Path(os.environ.get("SANIC_MESHY_OUTPUT_DIR", SOURCE.parent)).expanduser().resolve()
BLEND_PATH = OUTPUT_DIR / "SANIC-meshy6-v1-corrected.blend"
CHARACTER_GLB = OUTPUT_DIR / "SANIC-meshy6-v1-corrected.glb"
SPIN_GLB = OUTPUT_DIR / "SANIC-spin-ball-v1.glb"

if not SOURCE.is_file():
    raise FileNotFoundError(f"SANIC Meshy source does not exist: {SOURCE}")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
```

- [ ] **Step 2: Preserve the source and normalize the working copy**

Import the GLB, move its mesh into `SANIC_RAW_PRIVATE`, duplicate it as `SANIC_BodyBase` in `SANIC_CHARACTER_EXPORT`, and exclude the raw collection. Compute world bounds, scale the working copy uniformly by `1.70 / height`, apply scale, translate it by `-min_z`, and apply location. Do not edit the imported mesh datablock shared with the raw copy.

- [ ] **Step 3: Replace pointed hand tips with five-digit glove assemblies**

Delete working-copy vertices beyond the left and right cuff planes derived from the outermost `17%` of the total X span. Build each glove from one smooth palm ellipsoid, one angled thumb capsule, and four tapered finger capsules. Join each side into exactly one object named `SANIC_Glove.L` or `SANIC_Glove.R`, intersect the palm slightly with the surviving cuff, use a matte white material, and keep finger lengths descending from middle to pinky.

Use these helpers so every digit has an explicit, reviewable form:

```python
def capsule_between(name: str, start: Vector, end: Vector, radius: float,
                    material: bpy.types.Material, segments: int = 16) -> bpy.types.Object:
    delta = end - start
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=max(8, segments // 2),
        location=(start + end) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = (radius, radius, max(radius, delta.length * 0.58))
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = delta.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj

def build_glove(side: str, cuff_x: float, arm_z: float,
                front_y: float, hand_length: float,
                material: bpy.types.Material) -> bpy.types.Object:
    sign = -1.0 if side == "L" else 1.0
    palm_start = Vector((cuff_x - sign * hand_length * 0.03, front_y, arm_z))
    palm_end = Vector((cuff_x + sign * hand_length * 0.48, front_y, arm_z))
    parts = [capsule_between(f"SANIC_GlovePalm.{side}", palm_start, palm_end,
                             hand_length * 0.22, material, 20)]
    digit_specs = (
        ("Index", -0.075, 0.95, 0.015),
        ("Middle", -0.025, 1.00, 0.005),
        ("Ring", 0.025, 0.90, -0.005),
        ("Pinky", 0.075, 0.76, -0.018),
    )
    for label, y_offset, length_scale, z_offset in digit_specs:
        start = Vector((cuff_x + sign * hand_length * 0.37,
                        front_y + y_offset, arm_z + z_offset))
        end = start + Vector((sign * hand_length * 0.58 * length_scale, 0.0, -0.012))
        parts.append(capsule_between(f"SANIC_{label}.{side}", start, end,
                                     hand_length * 0.075, material, 16))
    thumb_start = Vector((cuff_x + sign * hand_length * 0.20,
                          front_y - 0.01, arm_z - hand_length * 0.12))
    thumb_end = thumb_start + Vector((sign * hand_length * 0.38,
                                      -hand_length * 0.12,
                                      -hand_length * 0.16))
    parts.append(capsule_between(f"SANIC_Thumb.{side}", thumb_start, thumb_end,
                                 hand_length * 0.09, material, 16))
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    parts[0].name = f"SANIC_Glove.{side}"
    return parts[0]
```

- [ ] **Step 4: Preserve crown quality and correct face readability**

Keep the accepted Meshy crown topology and UVs unchanged. Add thin separate sleepy eyelid and brow meshes, named with the `SANIC_Face_*` contract, then apply and bake a nearest-surface shrinkwrap so every accent remains within `0.018 m` of the face from side and three-quarter views. Keep the underlying Meshy texture and compact shoes unchanged. Any later crown reshape requires a manual retopology/sculpt pass rather than coordinate warping of the textured triangulated mesh.

- [ ] **Step 5: Save and export only the correction collection**

```python
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
select_collection_objects(character_collection)
bpy.ops.export_scene.gltf(
    filepath=str(CHARACTER_GLB),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_yup=True,
    export_materials="EXPORT",
)
```

- [ ] **Step 6: Run the builder and verify GREEN for character**

```bash
SANIC_MESHY_SOURCE=/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.glb \
SANIC_MESHY_OUTPUT_DIR=/home/alex/Downloads/SANIC-Meshy-v1 \
/usr/bin/blender --background --factory-startup \
  --python blender/scripts/correct_meshy_sanic.py

/usr/bin/blender --background --factory-startup \
  --python blender/scripts/validate_meshy_correction.py -- \
  character /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.glb
```

Expected: `SANIC_CORRECTION_VALIDATION=PASS`.

- [ ] **Step 7: Commit the deterministic correction builder**

```bash
git add blender/scripts/correct_meshy_sanic.py
git commit -m "feat: build corrected SANIC rigging master"
```

### Task 3: Build the dedicated curl-and-spin model

**Files:**
- Modify: `blender/scripts/correct_meshy_sanic.py`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-spin-ball-v1.glb`
- Test: `blender/scripts/validate_meshy_correction.py`

**Interfaces:**
- Consumes: the normalized character dimensions and correction material palette.
- Produces: a standalone `SANIC_SpinBall` export centered on its origin for runtime rotation.

- [ ] **Step 1: Extend the validator expectation and verify RED**

Run the spin-ball validator before exporting it:

```bash
/usr/bin/blender --background --factory-startup \
  --python blender/scripts/validate_meshy_correction.py -- \
  spin-ball /home/alex/Downloads/SANIC-Meshy-v1/SANIC-spin-ball-v1.glb
```

Expected: FAIL because no spin-ball GLB exists.

- [ ] **Step 2: Build one compact silhouette**

Create a 32-segment blue UV sphere with a `0.31 m` radius, six low-resolution swept quill cones around its rear hemisphere, two small red flattened shoe flashes, and two smaller white glove flashes. Join all visible parts into one root object named `SANIC_SpinBall`, keep material slots bounded to blue/red/white, shade smooth, and set the object origin to geometry bounds center.

```python
def build_spin_ball(collection: bpy.types.Collection,
                    blue: bpy.types.Material,
                    red: bpy.types.Material,
                    white: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=0.31)
    core = bpy.context.object
    core.name = "SANIC_SpinCore"
    core.data.materials.append(blue)
    parts = [core]
    for index, angle in enumerate((-70, -42, -14, 14, 42, 70)):
        radians = math.radians(angle)
        location = Vector((0.0, 0.15 * math.cos(radians), 0.15 * math.sin(radians)))
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.13, radius2=0.025,
                                        depth=0.34, location=location)
        quill = bpy.context.object
        quill.name = f"SANIC_SpinQuill.{index + 1:02d}"
        quill.data.materials.append(blue)
        direction = Vector((0.0, 0.28, 0.18 * math.sin(radians)))
        quill.rotation_mode = "QUATERNION"
        quill.rotation_quaternion = direction.to_track_quat("Z", "Y")
        parts.append(quill)
    for label, material, location, scale in (
        ("ShoeFlash.L", red, (-0.17, -0.18, -0.09), (0.11, 0.055, 0.07)),
        ("ShoeFlash.R", red, (0.17, 0.18, 0.09), (0.11, 0.055, 0.07)),
        ("GloveFlash.L", white, (-0.19, 0.08, 0.14), (0.07, 0.045, 0.06)),
        ("GloveFlash.R", white, (0.19, -0.08, -0.14), (0.07, 0.045, 0.06)),
    ):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10,
                                             location=location)
        flash = bpy.context.object
        flash.name = f"SANIC_Spin{label}"
        flash.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        flash.data.materials.append(material)
        parts.append(flash)
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = core
    bpy.ops.object.join()
    core.name = "SANIC_SpinBall"
    move_to_collection(core, collection)
    bpy.context.view_layer.objects.active = core
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    return core
```

- [ ] **Step 3: Export and verify GREEN**

Select only `SANIC_SPIN_EXPORT`, export `SANIC-spin-ball-v1.glb`, and run:

```bash
/usr/bin/blender --background --factory-startup \
  --python blender/scripts/validate_meshy_correction.py -- \
  spin-ball /home/alex/Downloads/SANIC-Meshy-v1/SANIC-spin-ball-v1.glb
```

Expected: `SANIC_CORRECTION_VALIDATION=PASS` with at most `8,000` triangles.

- [ ] **Step 4: Validate the saved source scene**

```bash
/usr/bin/blender --background \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend \
  --python blender/scripts/validate_meshy_correction.py -- source
```

Expected: both export collections are present and the raw collection is excluded.

- [ ] **Step 5: Commit the spin-ball builder**

```bash
git add blender/scripts/correct_meshy_sanic.py blender/scripts/validate_meshy_correction.py
git commit -m "feat: add SANIC spin-ball asset builder"
```

### Task 4: Produce visual and binary handoff evidence

**Files:**
- Modify: `blender/scripts/correct_meshy_sanic.py`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/corrected-turnaround/front.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/corrected-turnaround/back.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/corrected-turnaround/left.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/corrected-turnaround/right.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/corrected-turnaround/three-quarter.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-corrected-turnaround.png`

**Interfaces:**
- Consumes: the corrected source scene.
- Produces: five deterministic inspection renders, a contact sheet, hashes, and an accept/revise decision before rigging.

- [ ] **Step 1: Add a deterministic QA render function**

Render orthographic views at `1024×1024` with the character framed from the same target and camera scale in every view. Use Eevee, three neutral area lights, a dark neutral world, and a ground plane that is excluded from GLB exports.

- [ ] **Step 2: Rebuild and inspect all views**

Run the correction builder, verify all PNG dimensions with `identify`, assemble the contact sheet with ImageMagick, and inspect it at original resolution. Reject the result if fingers collapse into one point, crown peaks still resemble ears, eyelids obscure the eyes, the feet float, or the spin-ball no longer reads as the same blue/red/white character.

- [ ] **Step 3: Run binary verification**

```bash
sha256sum \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.glb \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.glb \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-spin-ball-v1.glb

git status --short
npm test
```

Expected: raw source hash remains `d9f4c4dd617c26f4b01ff4febc142e0eda3432b811dad31425cfea2d0c7da12f`; generated binaries are outside git; all repository tests pass.

- [ ] **Step 4: Commit the QA render support**

```bash
git add blender/scripts/correct_meshy_sanic.py
git commit -m "test: render corrected SANIC turnaround"
```

- [ ] **Step 5: Hand off to the rigging plan**

Record exact paths, sizes, hashes, dimensions, triangle counts, visual disposition, and any localized correction still needed. The next plan may fit the canonical humanoid rig and bake `Idle`, `Run`, `Jump`, and `Crash`; it must not replace the live asset until animation and browser gameplay tests pass.
