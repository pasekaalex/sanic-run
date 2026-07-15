# SANIC Player Model Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blocky player with a smooth, realistic Blender-built SANIC, curved layered footwear, an expanded deformation rig, and cinematic 30 FPS baked animations, then validate, deploy, and publish the finished game.

**Architecture:** Use Blender Studio's official CC0 realistic male Human Base Mesh as the coherent deformation-ready body, retain a trimmed project-local source with provenance, and reshape it through `blender/scripts/build_sanic.py` into the original SANIC silhouette. Keep that script as the reproducible source of custom head/quills/footwear, rig, actions, `.blend`, and GLB export; enforce source/export checks in `blender/scripts/validate_assets.py` and preserve the existing Three.js asset URL/action-name contract.

**Tech Stack:** Blender 5.1/Python API, Blender MCP, glTF/GLB, Three.js 0.185, Vite 8, TypeScript 7, Vitest 4, Playwright 1.61, Vercel, GitHub CLI.

## Global Constraints

- Preserve the exact GLB URL `/models/sanic-runner.glb`.
- Preserve action names `Idle`, `Run`, `Jump`, and `Crash`.
- Bake all exported animation transforms at 30 frames per second.
- Keep the source scene between 350,000 and 600,000 evaluated triangles.
- Keep the web character between 100,000 and 140,000 triangles and under 5 MB.
- Preserve character scale, origin, forward direction, ground contact, and chase-camera framing.
- Preserve the sleepy meme face, forehead phrase, cobalt body, white gloves, red shoes, and backward quills.
- The only permitted external geometry is Blender Studio's verified CC0 realistic male Human Base Mesh; do not import the referenced Pepsiman model, noncommercial assets, proprietary characters, external textures, or runtime dependencies.
- Do not change gameplay rules, controls, environment geometry, score sharing, UI, camera behavior, contract links, or token copy.
- Use the connected Blender tooling for staged scene execution and viewport evidence; a background-only rebuild is not sufficient.
- Publish only to the personal `pasekaalex` account after the public-tree and single-root-history audits pass.

## File map

- Modify `blender/scripts/build_sanic.py`: CC0 base import/reshaping, custom head/quills/footwear, materials, armature, baked actions, web optimization, and export budgets.
- Modify `blender/scripts/validate_assets.py`: enforce geometry, object, rig, action, animation, export-size, and anti-blockiness contracts.
- Create `blender/scripts/prepare_human_base.py`: isolate and normalize the verified Blender Studio base from its official bundle.
- Create `blender/vendor/human-base-mesh/body-male-realistic-cc0.blend`: trimmed project-local quad body source.
- Create `blender/vendor/human-base-mesh/README.md`: official URL, version, object name, SHA-256, and CC0 provenance.
- Create `blender/scripts/render_character_review.py`: deterministic front/rear/side/action review renders from the generated source scene.
- Regenerate `blender/sanic-source.blend`: high-resolution source character, rig, actions, web collection, and review setup.
- Regenerate `public/models/sanic-runner.glb`: optimized production character and four baked clips.
- Modify `README.md`: document the upgraded asset workflow and canonical personal repository.
- Modify `docs/superpowers/plans/2026-07-15-sanic-runner.md` and `docs/superpowers/specs/2026-07-15-sanic-runner-design.md`: remove obsolete repository restrictions before public release.
- Generated review evidence remains under ignored `test-results/model-review/`.

---

### Task 1: Establish the Blender connection and encode the failing asset contract

**Files:**
- Modify: `blender/scripts/validate_assets.py:19-89`
- Test: `blender/sanic-source.blend`
- Test: `public/models/sanic-runner.glb`

**Interfaces:**
- Consumes: existing `SANIC_SOURCE_HIGH`, `SANIC_WEB`, `SANIC_Armature`, and four action datablocks.
- Produces: `validate_character()` as the executable quality contract for every later task.

- [ ] **Step 1: Start the GUI Blender scene and prove the live connection**

Open `blender/sanic-source.blend` in Blender 5.1 with the installed add-on enabled. The add-on auto-starts on port 9876. Run `get_scene_info` and `get_viewport_screenshot`; require a scene response and visible character image before continuing.

Expected evidence: a live scene named `Scene`, a non-zero object count, and a viewport capture of the pre-upgrade character.

- [ ] **Step 2: Replace the character validator constants with the upgraded contract**

Use these exact contracts:

```python
CHARACTER_OBJECTS = {
    "SANIC_Armature",
    "SANIC_BodySculpt",
    "SANIC_Head",
    "SANIC_Quills",
    "SANIC_Muzzle",
    "SANIC_Eyes",
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
ACTION_FRAME_RANGES = {
    "Idle": (1, 60),
    "Run": (1, 21),
    "Jump": (1, 30),
    "Crash": (1, 42),
}
```

- [ ] **Step 3: Add geometry, rig, animation, and file-budget assertions**

Extend `validate_character()` with:

```python
objects = set(bpy.data.objects.keys())
missing_objects = CHARACTER_OBJECTS - objects
assert not missing_objects, f"Missing objects: {sorted(missing_objects)}"
assert not (BLOCKY_SOURCE_OBJECTS & objects), (
    f"Legacy box footwear remains: {sorted(BLOCKY_SOURCE_OBJECTS & objects)}"
)

rig = bpy.data.objects["SANIC_Armature"]
actual_bones = {bone.name for bone in rig.data.bones}
missing_bones = CHARACTER_BONES - actual_bones
assert not missing_bones, f"Missing deformation bones: {sorted(missing_bones)}"

assert bpy.context.scene.render.fps == 30
for name, expected_range in ACTION_FRAME_RANGES.items():
    action = bpy.data.actions[name]
    actual_range = tuple(int(value) for value in action.frame_range)
    assert actual_range == expected_range, (name, actual_range, expected_range)

source = list(bpy.data.collections["SANIC_SOURCE_HIGH"].all_objects)
web = list(bpy.data.collections["SANIC_WEB"].all_objects)
source_triangles = evaluated_triangle_count(source)
web_triangles = evaluated_triangle_count(web)
assert 350_000 <= source_triangles <= 600_000, source_triangles
assert 100_000 <= web_triangles <= 140_000, web_triangles

glb_path = Path(bpy.data.filepath).parents[1] / "public/models/sanic-runner.glb"
assert glb_path.is_file()
assert 1_000_000 <= glb_path.stat().st_size < 5_000_000, glb_path.stat().st_size
```

- [ ] **Step 4: Run the validator and confirm the old asset fails for the intended reasons**

Run:

```bash
blender --background --python-exit-code 1 blender/sanic-source.blend --python blender/scripts/validate_assets.py -- character
```

Expected: failure names `SANIC_BodySculpt` or `SANIC_ShoeUpper.L`; the old asset must not accidentally satisfy the new contract.

- [ ] **Step 5: Commit the failing contract**

```bash
git add blender/scripts/validate_assets.py
git commit -m "test: specify smooth sanic asset contract"
```

---

### Task 2: Build SANIC on the verified Blender Studio CC0 human base

**Files:**
- Create: `blender/scripts/prepare_human_base.py`
- Create: `blender/vendor/human-base-mesh/body-male-realistic-cc0.blend`
- Create: `blender/vendor/human-base-mesh/README.md`
- Modify: `blender/scripts/build_sanic.py:1-472`
- Modify: `blender/scripts/validate_assets.py:99-145`
- Test: `blender/scripts/validate_assets.py`

**Interfaces:**
- Consumes: Blender Studio Human Base Meshes bundle v1.4.1 from the official Blender download host.
- Produces: `SANIC_CC0_MaleBase` in the vendor blend, `append_cc0_body()`, `reshape_cc0_body()`, and source object `SANIC_BodySculpt` with auditable CC0 properties.

- [ ] **Step 1: Extend the failing contract with provenance checks**

After Task 1's object check, require:

```python
body = bpy.data.objects["SANIC_BodySculpt"]
assert body.get("sanic_base_license") == "CC0-1.0"
assert body.get("sanic_base_source") == "Blender Studio Human Base Meshes v1.4.1"
assert body.get("sanic_base_object") == "GEO-body_male_realistic"
assert all(polygon.use_smooth for polygon in body.data.polygons)
```

Run the character validator with `--python-exit-code 1`. Expected RED: the old source still fails on missing `SANIC_BodySculpt` and cannot satisfy the provenance contract.

- [ ] **Step 2: Download and verify the official CC0 bundle**

Download only:

```text
https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip
```

Save the archive under `/tmp/sanic-human-base/`, compute SHA-256, and extract it. Verify on `https://www.blender.org/download/demo-files/` that the exact Human Base Meshes v1.4.1 entry is marked CC0, then inspect the selected collection's embedded author/description metadata in Blender. Stop if the official page no longer identifies the bundle as CC0 or if the archive redirects to a non-Blender host.

Write `blender/vendor/human-base-mesh/README.md` with the exact observed archive SHA-256, official demo-page and direct archive URLs, version `1.4.1`, selected source object, embedded author `Dan Ulrich`, preparation command, and CC0 1.0 provenance. Do not copy the entire bundle into the repository.

- [ ] **Step 3: Create the deterministic base-isolation script**

`prepare_human_base.py` accepts source `.blend` and output `.blend` paths after `--`. It must inspect the source library, select the verified mesh object whose normalized name equals `geobodymalerealistic`, append it with its mesh and `Multires` modifier, remove unrelated datablocks, apply transforms, rename it `SANIC_CC0_MaleBase`, attach the three provenance properties from Step 1, and save only that trimmed source.

The selection logic is:

```python
def normalized(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())

matches = [name for name in source_objects if normalized(name) == "geobodymalerealistic"]
assert len(matches) == 1, f"Expected one realistic male body, found {matches}"
```

Run the preparation script with `--python-exit-code 1`, reopen the trimmed blend, and assert it contains exactly one mesh object named `SANIC_CC0_MaleBase` plus the multiresolution data needed by the body.

- [ ] **Step 4: Append the project-local base in the character builder**

Add:

```python
VENDOR_BASE_PATH = ROOT / "blender/vendor/human-base-mesh/body-male-realistic-cc0.blend"

def append_cc0_body() -> bpy.types.Object:
    assert VENDOR_BASE_PATH.is_file(), VENDOR_BASE_PATH
    with bpy.data.libraries.load(str(VENDOR_BASE_PATH), link=False) as (source, target):
        assert "SANIC_CC0_MaleBase" in source.objects
        target.objects = ["SANIC_CC0_MaleBase"]
    body = target.objects[0]
    SOURCE_COLLECTION.objects.link(body)
    body.name = "SANIC_BodySculpt"
    return body
```

Remove the old cobalt torso, shoulder, hip, arm, elbow, knee, calf, and abdominal primitive objects. Keep the custom head, muzzle, closed-eye expression, forehead phrase, and quills.

- [ ] **Step 5: Normalize and reshape the coherent body topology**

Scale the imported body uniformly to the existing ground/neck landmarks and apply transforms. The verified source keeps its arms down beside the torso, so rotate each complete arm outward and slightly forward around an anatomical shoulder pivot into the established relaxed runner pose; preserve the shoulder cap and elbow plane with smooth spatial falloffs rather than disconnected parts:

```python
def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)

def gaussian(value: float, center: float, width: float) -> float:
    return math.exp(-((value - center) / width) ** 2)
```

Apply low-frequency proportion fields on the base vertices: shoulder/chest X expansion up to 20%, waist X reduction up to 8%, thigh X/depth expansion up to 10%, and calf expansion up to 5%. Arm cross-sections may change by no more than 8% from the realistic base: preserve a restrained deltoid transition, subtle biceps/triceps contour, narrow elbow plane, long forearm taper, and smaller wrist. Do not generate separate shoulder, elbow, biceps, triceps, or forearm meshes.

Remove the imported human head above the neck loop and cap the hidden boundary inside `SANIC_Head`. Keep hand/foot topology until Task 3 separates glove regions and hides feet inside custom shoes.

- [ ] **Step 6: Preserve multiresolution and smooth shading**

Retain or rebuild a modifier named `SANIC_Multires` with enough levels for the complete source scene to reach 350,000–600,000 evaluated triangles. Keep the deformation base as continuous quads, set every body polygon to smooth shading, assign cobalt, and attach:

```python
body["sanic_source"] = True
body["sanic_material"] = "SANIC_MAT_Cobalt"
body["sanic_base_license"] = "CC0-1.0"
body["sanic_base_source"] = "Blender Studio Human Base Meshes v1.4.1"
body["sanic_base_object"] = "GEO-body_male_realistic"
```

- [ ] **Step 7: Smooth the SANIC head/quill transition and tune materials**

Increase head and face radial resolution to 32×24, use subdivision level 2 for `SANIC_Head`, muzzle, eye masks, and lips, widen quill roots from `0.42` to `0.58`, and add two intermediate quill rings. Keep expression/text positions unchanged.

Set cobalt roughness to `0.34` with coat weight `0.08`, white roughness to `0.46`, red shoe roughness to `0.24` with coat weight `0.18`, midsole roughness to `0.38`, and outsole roughness to `0.76`. Keep all character materials nonmetallic and texture-free.

- [ ] **Step 8: Execute and inspect the neutral build through Blender MCP**

Run preparation/import and `SANIC_BUILD_STAGE = "neutral"` through live Blender in small `execute_blender_code` calls. Capture front, side, rear, and arm-focused three-quarter screenshots.

Expected: coherent human anatomical flow, continuous clavicle-to-wrist arms, no spherical joints or sausage lobes, restrained arm mass, tapered wrists/ankles, strong V-taper, retained sleepy face/quills, and no imported human head visible.

- [ ] **Step 9: Run the fail-closed neutral checks and commit**

```bash
blender --background --python-exit-code 1 --python-expr "from pathlib import Path; path=Path('blender/scripts/build_sanic.py').resolve(); exec(compile(path.read_text(), str(path), 'exec'), {'__file__': str(path), 'SANIC_BUILD_STAGE': 'neutral'})"
```

Expected: `SANIC_NEUTRAL_CHECKPOINT`, verified CC0 properties, and 350,000–600,000 source triangles.

```bash
git add blender/scripts/prepare_human_base.py blender/vendor/human-base-mesh blender/scripts/build_sanic.py blender/scripts/validate_assets.py
git commit -m "feat: sculpt sanic from cc0 human topology"
```

---

### Task 3: Build curved shoes and sculpted gloves

**Files:**
- Modify: `blender/scripts/build_sanic.py:335-435`
- Test: `blender/scripts/validate_assets.py`

**Interfaces:**
- Consumes: `SANIC_BodySculpt` wrist/ankle landmarks, its coherent hand topology, materials, and foot/hand bindings.
- Produces: `build_shoe(side, sign)`, `build_glove(side, sign)`, and the exact source object names required by Task 1.

- [ ] **Step 1: Implement a section-driven shoe shell**

Add:

```python
def shoe_shell(
    name: str,
    side_x: float,
    sections: tuple[tuple[float, float, float, float], ...],
    material_key: str,
    binding: str,
    radial_segments: int = 28,
) -> bpy.types.Object:
    """Loft (y, half_width, center_z, half_height) footwear sections."""
```

Use ring angles around the shoe length axis, soften the upper half with a 0.86 exponent, flatten the bottom 28% for ground contact, and preserve curved toe lift from the supplied section `center_z` values.

- [ ] **Step 2: Build the red upper, white midsole, and rubber outsole**

For each side, use these longitudinal profiles:

```python
UPPER = (
    (0.30, 0.31, 0.33, 0.20),
    (0.08, 0.39, 0.32, 0.23),
    (-0.22, 0.43, 0.31, 0.24),
    (-0.50, 0.45, 0.32, 0.23),
    (-0.72, 0.42, 0.37, 0.21),
    (-0.90, 0.34, 0.44, 0.15),
)
MIDSOLE = tuple((y, width + 0.025, z - 0.17, 0.075) for y, width, z, _ in UPPER)
OUTSOLE = tuple((y, width + 0.045, z - 0.245, 0.055) for y, width, z, _ in UPPER)
```

Name the results `SANIC_ShoeUpper.{side}`, `SANIC_ShoeMidsole.{side}`, and `SANIC_ShoeOutsole.{side}`. Add three shallow tread ribs to the outsole underside and a slightly raised heel edge; all tread pieces inherit `foot.{side}` rigidly.

Add a red heel-counter overlay following the rear two upper sections. It must rise around the back of the padded collar, taper toward both quarters, and share the upper material without creating a hard rectangular edge.

- [ ] **Step 3: Create fitted straps and padded collars**

Build `SANIC_ShoeStrap.{side}` as a beveled curve sampled across the upper at `y=-0.30`, with five control points following the red shell. Convert it to a mesh before export. Build a padded white collar with a 32-segment elliptical torus tilted to the ankle line. The strap may sit no more than 0.018 Blender units above the upper.

- [ ] **Step 4: Turn the imported hand topology into fitted glove shells**

Separate each imported hand at a clean wrist loop into `SANIC_GloveShell.{side}` while preserving the base mesh's quad palm, thumb, and finger edge flow. Remove the separated hand faces from `SANIC_BodySculpt`, cap the hidden body boundary inside the cuff, and retain the hand vertex groups for finger deformation. Inflate the glove shell with a smooth normal displacement of 10–14% around the palm and fingers, soften the knuckle silhouette without erasing finger separation, and taper back to the original wrist circumference beneath the cuff. Do not build fingers from capsules, swept tubes, spheres, or overlapping loose pieces.

Create the cuff from the boundary loop as a short flared quad band with a slightly compressed profile. Add two shallow palm crease curves and restrained knuckle forms whose projection stays below 6% of palm depth. Assign the white material to the complete shell and keep every finger continuous from palm to tip.

- [ ] **Step 5: Inspect footwear through Blender MCP**

Run the neutral stage through `execute_blender_code`, isolate both shoes, and capture side, rear-three-quarter, and outsole screenshots. Then frame a glove and capture the palm/finger silhouette.

Expected: visible toe spring, rounded asymmetrical toe boxes, distinct red/white/dark layers, fitted straps, no rectangular slabs, and no strap/upper intersections.

- [ ] **Step 6: Commit the footwear and glove pass**

```bash
git add blender/scripts/build_sanic.py
git commit -m "feat: model curved sanic footwear and gloves"
```

---

### Task 4: Expand the deformation rig and bake cinematic actions

**Files:**
- Modify: `blender/scripts/build_sanic.py:474-630`
- Test: `blender/scripts/validate_assets.py`

**Interfaces:**
- Consumes: smooth source geometry and `PART_BINDINGS`.
- Produces: expanded `SANIC_Armature` plus 30 FPS `Idle`, `Run`, `Jump`, and `Crash` actions.

- [ ] **Step 1: Add the required deformation bones**

Preserve all existing names. Insert `spine_upper` between `spine` and `chest`; insert `clavicle.{side}` before each upper arm. Add upper/lower twist helpers to arms and legs, `toe.{side}` after each foot, `thumb.{side}` plus four named finger bones after each hand, and three quill-chain bones after the head. Set control-only helpers to `use_deform = False`; every name in `CHARACTER_BONES` must remain deform-enabled.

Use this parenting pattern:

```python
bone("spine_upper", (0.0, 0.0, 3.02), (0.0, 0.0, 3.58), "spine", True)
bone("chest", (0.0, 0.0, 3.58), (0.0, 0.0, 4.30), "spine_upper", True)
bone(f"clavicle.{side}", (0.18 * sign, 0.0, 4.08), (0.76 * sign, 0.0, 4.01), "chest")
bone(f"toe.{side}", (0.51 * sign, -0.66, 0.20), (0.51 * sign, -0.93, 0.22), f"foot.{side}", True)
bone("quill_upper", (0.0, 0.28, 5.45), (0.0, 0.72, 5.72), "head")
bone("quill_mid", (0.0, 0.31, 5.18), (0.0, 0.79, 5.17), "head")
bone("quill_lower", (0.0, 0.29, 4.91), (0.0, 0.72, 4.66), "head")
```

Place twist bones across the middle 45% of their parent segments. Update source bindings so torso, limb, glove, and shoe pieces reference their nearest deform bones.

- [ ] **Step 2: Upgrade pose key support**

Change `key_pose()` to accept per-bone Euler rotation, per-bone location, root translation, and chest scale:

```python
def key_pose(
    frame: int,
    rotations: dict[str, tuple[float, float, float]],
    locations: dict[str, tuple[float, float, float]] | None = None,
    root_location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    chest_scale: float = 1.0,
) -> None:
```

After inserting every action, set all F-curve keyframes to `BEZIER`, `AUTO_CLAMPED`; set planted run-contact root/location curves to `LINEAR`. Set `scene.render.fps = 30` and `scene.render.fps_base = 1.0` during reset.

- [ ] **Step 3: Author the 60-frame idle loop**

Key frames 1, 15, 30, 45, and 60. Frame 1 equals frame 60. Use 2–4 degrees of head drift, 3–5 degrees of shoulder roll, opposing clavicle motion, 2.5% chest breathing, subtle finger flex, 1–3 degrees of delayed quill-chain motion, and less than 0.035 units of root movement.

- [ ] **Step 4: Author the 21-frame run cycle**

Key frames 1 contact-left, 4 compression, 7 passing-left, 11 flight, 12 contact-right, 15 compression, 18 passing-right, and 21 matching frame 1. Use 12–16 degrees of torso lean, 55–70 degrees of arm swing, opposing shoulder/hip rotation, 65–85 degrees of thigh drive, toe-off, heel recovery, delayed quill-chain rotation, and at most 0.11 units vertical root compression. Keep both contact shoes within 0.015 units of their contact-plane height.

- [ ] **Step 5: Author the 30-frame jump action**

Key frame 1 neutral, 5 crouch, 9 extension, 16 tuck, 22 hang, 27 reach, and 30 landing compression. The clip supplies pose dynamics only; root height remains governed by game physics, so animation root Z stays within ±0.12 units.

- [ ] **Step 6: Author the 42-frame crash action**

Key frame 1 running brace, 4 contact, 8 primary impact, 13 recoil, 24 collapse, 34 secondary settle, and 42 final pose. Place the strongest asymmetric chest/head/quill recoil by frame 8 so it occurs within 0.27 seconds. End in a non-neutral collapsed pose and keep the clip non-looping.

- [ ] **Step 7: Build the rig stage through Blender MCP and inspect defining poses**

Execute the script with `SANIC_BUILD_STAGE = "rig"`. Set and capture frames 1/7/12/18 for Run, 5/16/30 for Jump, and 4/8/24/42 for Crash. Inspect shoulder/hip volume, elbows, knees, ankle/toe roll, glove cuffs, and shoe rigidity.

- [ ] **Step 8: Run the animation contract and commit**

Run:

```bash
blender --background --python-exit-code 1 --python blender/scripts/build_sanic.py
blender --background --python-exit-code 1 blender/sanic-source.blend --python blender/scripts/validate_assets.py -- character
```

Expected: all named bones and exact frame ranges pass, 30 FPS is reported, and no action is missing.

```bash
git add blender/scripts/build_sanic.py blender/sanic-source.blend
git commit -m "feat: rig and animate cinematic sanic"
```

---

### Task 5: Optimize, export, and render deterministic review evidence

**Files:**
- Modify: `blender/scripts/build_sanic.py:632-841`
- Create: `blender/scripts/render_character_review.py`
- Regenerate: `blender/sanic-source.blend`
- Regenerate: `public/models/sanic-runner.glb`
- Test: `blender/scripts/validate_assets.py`

**Interfaces:**
- Consumes: generated source geometry, armature, materials, and actions.
- Produces: production GLB, source blend, and ignored PNG review evidence.

- [ ] **Step 1: Raise web geometry while preserving smooth weights**

Change fused cobalt target triangles from 30,000 to 62,000–72,000 and total web budget to 100,000–140,000. Keep four normalized influences per vertex, preserve volume, and require at least 24 deform groups on the fused skin. Apply smooth shading and weighted normals after decimation.

- [ ] **Step 2: Harden the export contract**

Set the source and web assertions to the global budgets and add these exporter flags:

```python
export_frame_range=True,
export_frame_step=1,
export_force_sampling=True,
export_def_bones=True,
export_optimize_animation_size=False,
export_apply=False,
```

After export, assert `GLB_PATH.stat().st_size < 5_000_000` and print bytes, source triangles, web triangles, action names, and FPS in `SANIC_EXPORT_COMPLETE`.

- [ ] **Step 3: Create the deterministic review renderer**

`render_character_review.py` must:

```python
REVIEW_SHOTS = {
    "neutral-front": ("Idle", 1, (0.0, -10.5, 3.1)),
    "neutral-side": ("Idle", 1, (9.0, -1.0, 3.0)),
    "neutral-rear": ("Idle", 1, (0.0, 10.5, 3.1)),
    "run-contact": ("Run", 1, (7.8, -7.8, 3.0)),
    "run-flight": ("Run", 11, (7.8, -7.8, 3.0)),
    "jump-tuck": ("Jump", 16, (7.8, -7.8, 3.2)),
    "crash-impact": ("Crash", 8, (7.8, -7.8, 3.0)),
}
```

Create a 70 mm camera aimed at `(0, 0, 3.0)`, a large soft key, cool fill, warm rim, and neutral floor. Render 900×900 PNGs to `test-results/model-review/` with transparent film disabled. Restore the source scene after rendering.

- [ ] **Step 4: Execute the complete build through Blender MCP**

Run the script in live Blender with `SANIC_BUILD_STAGE = "all"` using multiple `execute_blender_code` calls if a stage takes longer than one MCP response. Require `SANIC_EXPORT_COMPLETE`, then call `get_scene_info`, `get_object_info("SANIC_BodySculpt")`, and `get_viewport_screenshot`.

- [ ] **Step 5: Validate and inspect the exported GLB**

Run:

```bash
blender --background --python-exit-code 1 blender/sanic-source.blend --python blender/scripts/validate_assets.py -- character
npx gltf-transform inspect public/models/sanic-runner.glb
blender --background --python-exit-code 1 blender/sanic-source.blend --python blender/scripts/render_character_review.py
```

Expected: 100,000–140,000 web triangles, four clips, under 5 MB, no missing resources, seven review PNGs, and no validator assertion.

- [ ] **Step 6: Visually inspect every review image**

Open all seven PNGs. Reject the pass if any view shows spherical joint seams, box-shaped shoes, intersecting straps, collapsed shoulders/hips, foot sliding, glove intersections, quill clipping, or an unreadable face. Correct the script and repeat Steps 4–6 until clean.

- [ ] **Step 7: Commit the reproducible asset pass**

```bash
git add blender/scripts/build_sanic.py blender/scripts/render_character_review.py blender/sanic-source.blend public/models/sanic-runner.glb
git commit -m "feat: export smooth animated sanic hero"
```

---

### Task 6: Verify desktop/mobile gameplay with the upgraded asset

**Files:**
- Test: `tests/unit/assetLoader.test.ts`
- Test: `tests/e2e/game.spec.ts`
- Test: `public/models/sanic-runner.glb`

**Interfaces:**
- Consumes: unchanged `ASSET_URLS.character` and the four action names.
- Produces: browser evidence that the new GLB works without runtime changes.

- [ ] **Step 1: Run unit and production-build gates**

```bash
npm test
npm run build
```

Expected: 53 or more passing tests, zero failures, and a successful Vite production build.

- [ ] **Step 2: Run the full local browser suite**

```bash
npx playwright test
```

Expected: every applicable Chromium desktop/mobile case passes; project/capability skips remain documented skips rather than failures.

- [ ] **Step 3: Inspect real gameplay screenshots**

Start `npm run preview`, play long enough to show Run, lane movement, Jump, and Crash on 1440×900 and 390×844 viewports, and save screenshots beneath ignored `.playwright-cli/` or `test-results/`.

Reject if the character clips the ground, leaves the chase framing, becomes visually tiny, shows animation snapping, drops to fallback assets, or obscures mobile controls.

- [ ] **Step 4: Commit only if runtime integration required a correction**

If a camera-scale or crossfade correction is necessary, constrain it to `src/render/worldRenderer.ts`, add a focused Vitest assertion first, and commit:

```bash
git add src/render/worldRenderer.ts tests/unit
git commit -m "fix: frame upgraded sanic animation"
```

If no runtime correction is needed, do not create an empty commit.

---

### Task 7: Redeploy exactly once and verify production

**Files:**
- Deploy: production build from the isolated worktree
- Test: `https://sanic-run.vercel.app`

**Interfaces:**
- Consumes: verified repository HEAD.
- Produces: stable production alias serving the upgraded model.

- [ ] **Step 1: Confirm lineage, cleanliness, and absence of concurrent deploys**

```bash
git status --short --branch
git merge-base feat/sanic-runner main
git rev-parse main
pgrep -af '[v]ercel|[d]eploy'
```

Expected: clean feature worktree, feature merge-base equals current `main`, and no unrelated deployment process.

- [ ] **Step 2: Deploy production once**

```bash
vercel deploy --prod --force --yes
```

Record the unique deployment URL and confirm the stable alias remains `https://sanic-run.vercel.app`.

- [ ] **Step 3: Verify live HTTP and browser behavior**

Require HTTP 200 for `/`, `/models/sanic-runner.glb`, `/models/sanic-ring.glb`, `/models/forest-kit.glb`, and `/media/sanic-og.jpg`. Then run:

```bash
BASE_URL=https://sanic-run.vercel.app npx playwright test tests/e2e/game.spec.ts
```

Expected: all applicable live cases pass, the character is not a fallback, desktop/mobile gameplay works, the exact contract/X/Pump links remain intact, and the browser console has no application errors.

---

### Task 8: Prepare a public-safe single-root release and publish it

**Files:**
- Modify: `README.md:20-41`
- Modify: `docs/superpowers/plans/2026-07-15-sanic-runner.md`
- Modify: `docs/superpowers/specs/2026-07-15-sanic-runner-design.md`
- Create branch: `release/sanic-run-public`
- Create remote repository: `pasekaalex/sanic-run`

**Interfaces:**
- Consumes: production-verified feature HEAD and authenticated `gh` identity `pasekaalex`.
- Produces: public GitHub repository with one clean root commit on `main`.

- [ ] **Step 1: Replace obsolete repository instructions**

Change the README publishing section to:

```markdown
## Deployment

The canonical source repository is `https://github.com/pasekaalex/sanic-run`. Production deploys from the verified `main` tree to `https://sanic-run.vercel.app`.
```

Remove obsolete no-remote wording from both older design/plan documents without naming any client, coworker, employer, or work organization.

- [ ] **Step 2: Document the upgraded model workflow**

Add the review command to README:

```bash
blender --background --python-exit-code 1 blender/sanic-source.blend --python blender/scripts/render_character_review.py
```

Describe the source as a smooth original character with curved footwear, an expanded rig, and four baked 30 FPS actions. Do not claim affiliation or endorsement.

- [ ] **Step 3: Run the complete public tree and local-history audits**

Run the publishing-safety hidden-file scan and full commit-message/author scan from the repository root. Review session-artifact ignore entries as operational exclusions, not attribution. Any legal-name, client/work identifier, generated-with footer, or automated co-author trailer blocks publication.

Expected: only approved operational ignore-path hits; author is `pasekaalex <35618421+pasekaalex@users.noreply.github.com>`.

- [ ] **Step 4: Commit the release documentation**

```bash
git add README.md docs/superpowers/plans/2026-07-15-sanic-runner.md docs/superpowers/specs/2026-07-15-sanic-runner-design.md
git commit -m "docs: prepare sanic public release"
```

- [ ] **Step 5: Create a clean root commit without publishing private history**

Create a root commit from the verified current tree, with author and committer set to the required noreply identity, then point `release/sanic-run-public` at that commit. The root commit message is exactly `feat: launch sanic runner`.

Verify:

```bash
git log release/sanic-run-public --oneline --decorate
git diff HEAD release/sanic-run-public --exit-code
```

Expected: one root commit and byte-identical tree content.

- [ ] **Step 6: Audit the release branch history and tree again**

Run the hidden-file audit against `release/sanic-run-public` and inspect:

```bash
git log release/sanic-run-public --format='%an <%ae>%n%B'
git ls-tree -r --name-only release/sanic-run-public
```

Expected: one clean author/message, no prohibited identifiers, and no session, deployment-link, test-result, or dependency artifacts.

- [ ] **Step 7: Create the public repository and push only the clean branch**

```bash
gh repo create pasekaalex/sanic-run --public --description "Playable Three.js SANIC coin runner with original Blender character, baked animations, and mobile controls."
git remote add origin https://github.com/pasekaalex/sanic-run.git
git push -u origin release/sanic-run-public:main
```

Do not push other local branches or tags.

- [ ] **Step 8: Set and audit public metadata**

Add topics `threejs`, `webgl`, `blender`, `browser-game`, and `solana`. Verify repo visibility, description, default branch, topics, releases, open issues, and open pull requests through `gh`; none may contain a prohibited identifier or attribution footer.

Expected final repository URL: `https://github.com/pasekaalex/sanic-run`.

---

### Task 9: Final cross-system verification

**Files:**
- Test: local feature HEAD
- Test: GitHub `main`
- Test: Vercel production

**Interfaces:**
- Consumes: completed Blender, browser, deployment, and publishing outputs.
- Produces: evidence-backed handoff.

- [ ] **Step 1: Compare all three release identities**

Confirm the local release branch commit equals GitHub `main`, GitHub tree content equals the production-built source tree, and Vercel serves the final GLB byte size and expected immutable cache headers.

- [ ] **Step 2: Repeat the minimum final gates**

```bash
npm test
npm run build
blender --background --python-exit-code 1 blender/sanic-source.blend --python blender/scripts/validate_assets.py -- character
BASE_URL=https://sanic-run.vercel.app npx playwright test tests/e2e/game.spec.ts
```

Expected: all unit, build, asset, and applicable live browser gates pass with fresh output.

- [ ] **Step 3: Request final whole-branch review**

Review the complete diff from `main` to feature HEAD and the exact public release tree. Reject for any critical/important finding, visual regression, missing requirement, unsafe metadata, or mismatched deployment.

- [ ] **Step 4: Hand off exact URLs and evidence**

Report the live game, public repository, source `.blend`, production GLB, test totals, triangle/file budgets, animation clips, and confirmation that no work/client repository received the code.
