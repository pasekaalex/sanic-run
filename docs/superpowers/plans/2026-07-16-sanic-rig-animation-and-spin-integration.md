# SANIC Rig, Animation, and Spin Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rig the corrected 1.70 m SANIC mesh, bake responsive in-place gameplay clips, and integrate the dedicated spin-ball presentation into the deterministic jump without changing jump physics.

**Architecture:** A deterministic Blender script consumes the corrected local `.blend`, creates an original canonical humanoid deformation rig, assigns coordinate-driven weights, bakes `Idle`, `Run`, `Jump`, and `Crash`, downsizes web textures, and exports one animated GLB. The browser loads the small spin-ball GLB as a fourth asset category. During jump progress `0.16–0.82`, rendering switches from the still-advancing `Jump` clip to the rotating ball; the simulation remains the sole owner of player position, collision, apex, and landing time.

**Tech Stack:** Blender 5.1 Python API, bmesh, glTF/Draco, TypeScript, Three.js, Vitest, Playwright.

## Global Constraints

- Generated masters remain in `/home/alex/Downloads/SANIC-Meshy-v1` until all Blender and browser checks pass.
- The public repository receives only the optimized animated runner and lightweight spin-ball after validation.
- No downloaded third-party mesh, skeleton, texture, or animation is copied into production output.
- The rig is in-place: no forward/root-Z travel is baked into any action.
- Run arms move primarily forward/back in the sagittal plane with visible elbow bend.
- Run knees flex and recover under the hips; the first and last frames match exactly.
- Jump frames `1–6` crouch and take off, frames `7–24` tuck/uncurl behind the spin presentation, and frames `25–30` land with bent knees.
- The game simulation remains authoritative for jump height and landing.
- Stable action names remain exactly `Idle`, `Run`, `Jump`, and `Crash`.
- The web character maintains the current rendered height of approximately `4.12` world units through runtime normalization, not an asset-specific magic scale.
- Desktop and narrow mobile gameplay must load without fallback assets or WebGL errors.

---

### Task 1: Define the animated rig contract

**Files:**
- Create: `blender/scripts/validate_meshy_rig.py`
- Read locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.glb`
- Read locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.blend`

**Interfaces:**
- Consumes: `glb <path>` or `source <path>` after `--`.
- Produces: `SANIC_RIG_VALIDATION=PASS` and a JSON report with objects, bones, actions, triangles, bounds, unweighted vertices, and texture sizes.

- [ ] **Step 1: Write the validator before the rig builder**

Require these bones and actions:

```python
EXPECTED_BONES = {
    "root", "hips", "spine", "chest", "neck", "head",
    "shoulder.L", "upper_arm.L", "lower_arm.L", "hand.L",
    "shoulder.R", "upper_arm.R", "lower_arm.R", "hand.R",
    "upper_leg.L", "lower_leg.L", "foot.L", "toe.L",
    "upper_leg.R", "lower_leg.R", "foot.R", "toe.R",
}
EXPECTED_ACTION_RANGES = {
    "Idle": (1, 60),
    "Run": (1, 24),
    "Jump": (1, 30),
    "Crash": (1, 36),
}
```

For GLB mode assert one armature, all expected bones/actions, character height `1.68–1.72 m`, feet at `Z=0` after Blender import, fewer than `150,000` triangles, no unweighted mesh vertices, normalized weight sums within `0.01`, no mesh with more than four non-zero influences per vertex, and embedded images no larger than `2048×2048`. Sample the `Run` action at every frame and assert root forward/lateral translation stays within `0.002 m`; assert frames `1` and `24` have matching bone quaternions within `1e-4`.

- [ ] **Step 2: Verify RED**

```bash
/usr/bin/blender --background --factory-startup \
  --python blender/scripts/validate_meshy_rig.py -- \
  glb /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.glb
```

Expected: `FileNotFoundError` naming the missing rigged GLB.

- [ ] **Step 3: Commit the red contract**

```bash
git add blender/scripts/validate_meshy_rig.py
git commit -m "test: define SANIC rig and animation contract"
```

### Task 2: Build and skin the original humanoid rig

**Files:**
- Create: `blender/scripts/rig_meshy_sanic.py`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.blend`
- Test: `blender/scripts/validate_meshy_rig.py`

**Interfaces:**
- Consumes: `SANIC_CORRECTED_BLEND` and optional `SANIC_RIG_OUTPUT_DIR`.
- Produces: a rigged Blender source with collection `SANIC_RIGGED_EXPORT`, armature `SANIC_Armature`, and the expected actions.

- [ ] **Step 1: Import only the corrected character collection**

Open the corrected `.blend`, duplicate objects from `SANIC_CHARACTER_EXPORT` into a new `SANIC_RIGGED_EXPORT` collection, copy mesh datablocks, remove any stale parents/modifiers/groups, and leave `SANIC_RAW_PRIVATE` excluded. Do not alter the corrected source file.

- [ ] **Step 2: Create the canonical rest rig**

Create the bones at these meter-scale landmarks:

```python
BONE_SEGMENTS = {
    "root": ((0.0, 0.0, 0.00), (0.0, 0.0, 0.18), None),
    "hips": ((0.0, 0.0, 0.58), (0.0, 0.0, 0.74), "root"),
    "spine": ((0.0, 0.0, 0.74), (0.0, 0.0, 0.94), "hips"),
    "chest": ((0.0, 0.0, 0.94), (0.0, 0.0, 1.12), "spine"),
    "neck": ((0.0, 0.0, 1.12), (0.0, 0.0, 1.24), "chest"),
    "head": ((0.0, 0.0, 1.24), (0.0, 0.0, 1.55), "neck"),
}
```

For each side use sign `-1` for `.L` and `+1` for `.R`: shoulder `0.20→0.28` at `Z=1.10`, upper arm `0.28→0.48`, lower arm `0.48→0.69`, hand `0.69→0.84`; upper leg starts at `(0.11*sign,0,0.62)` and ends at the knee `(0.11*sign,0,0.34)`; lower leg ends at `(0.11*sign,0,0.12)`; foot ends at `(0.11*sign,-0.24,0.08)`; toe ends at `(0.11*sign,-0.31,0.07)`.

- [ ] **Step 3: Assign bounded coordinate-driven weights**

Use a helper that retains at most the four largest influences and normalizes them:

```python
def assign_vertex(obj, vertex_index, influences):
    positive = [(name, weight) for name, weight in influences if weight > 1e-5]
    strongest = sorted(positive, key=lambda item: item[1], reverse=True)[:4]
    total = sum(weight for _, weight in strongest)
    assert total > 0.0
    for name, weight in strongest:
        group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        group.add([vertex_index], weight / total, "REPLACE")
```

Classify arm vertices before torso vertices when `abs(X)>0.22` and `0.90<Z<1.25`. Blend upper/lower arms across `0.44–0.52`, lower arm/hand across `0.65–0.72`, upper/lower legs across `0.30–0.38`, lower leg/foot across `0.10–0.18`, hips/spine/chest across their bone landmarks, and neck/head across `1.12–1.27`. Assign back-quill vertices with `Y>0.10` and `Z>0.68` to `head`; assign face overlays to `head` and each glove rigidly to its matching hand.

- [ ] **Step 4: Add armature deformation and verify static pose**

Parent every export mesh to `SANIC_Armature`, add one Armature modifier with preserve volume, and keep transforms at identity. Save the source and run source validation. Expected: no unweighted vertices and every object has the same armature target.

- [ ] **Step 5: Commit the rig builder**

```bash
git add blender/scripts/rig_meshy_sanic.py blender/scripts/validate_meshy_rig.py
git commit -m "feat: build original SANIC humanoid rig"
```

### Task 3: Bake biomechanical gameplay actions and optimized GLB

**Files:**
- Modify: `blender/scripts/rig_meshy_sanic.py`
- Modify: `blender/scripts/validate_meshy_rig.py`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.glb`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/animation-preview/`

**Interfaces:**
- Consumes: the canonical rig and skinned character.
- Produces: four baked actions, a Draco-compressed animated GLB, and selected animation QA frames.

- [ ] **Step 1: Add an absolute world-direction pose solver**

For each sampled integer frame, reset pose matrices, aim torso and limbs from rest in parent-first order, key quaternion rotations for all deform bones, and key only root vertical translation. Enforce quaternion continuity by negating a sample when its dot product with the previous sample is negative. Set all key interpolation to linear after sampling every frame.

- [ ] **Step 2: Bake `Idle` and `Run`**

Use `Idle` anchors at frames `1`, `30`, and `60`. Use `Run` contacts at `1`, `7`, `13`, and `19`, passing poses at `4`, `10`, `16`, and `22`, and repeat frame `1` exactly at frame `24`. Contact poses use opposite arm/leg pairs, `10–12°` forward lean, `±5°` pelvis yaw, counter-rotated chest yaw, knee-flexed down poses, and a maximum root bob of `0.035 m`. Arms use forward/back Y-Z directions with absolute X magnitude at most `0.08`.

- [ ] **Step 3: Bake `Jump` and `Crash`**

`Jump` anchors: entry `1`, crouch `4`, takeoff `6`, tuck `9`, held tuck `20`, uncurl `24`, landing `27`, recovery `30`. Both knees move forward toward the torso during tuck; shins fold under rather than extending backward. `Crash` anchors: run brace `1`, impact `6`, recoil `12`, stagger `22`, held recovery `36`.

- [ ] **Step 4: Optimize textures and export**

Scale every imported image whose maximum dimension exceeds `2048` down proportionally to a maximum of `2048`. Export selected rig plus meshes with animations from all actions, force integer-frame sampling, preserve action names, enable Draco compression level `6`, omit cameras/lights, and keep material textures embedded. Target output size: under `18 MB`.

- [ ] **Step 5: Verify GREEN and render animation checkpoints**

Run GLB and source validators. Render front and side frames `Run:1,4,7,10,13,16,19,22` and `Jump:1,4,6,9,20,24,27,30` into `animation-preview`. Reject if arms move laterally, knees lock, feet cross, the model collapses, or jump legs kick backward.

- [ ] **Step 6: Commit animation/export support**

```bash
git add blender/scripts/rig_meshy_sanic.py blender/scripts/validate_meshy_rig.py
git commit -m "feat: bake SANIC gameplay animations"
```

### Task 4: Load and select the spin presentation with tests first

**Files:**
- Modify: `src/config.ts`
- Modify: `src/render/fallbackAssets.ts`
- Modify: `src/render/assetLoader.ts`
- Modify: `src/render/animationTiming.ts`
- Test: `tests/unit/config.test.ts`
- Test: `tests/unit/assetLoader.test.ts`
- Test: `tests/unit/animationTiming.test.ts`

**Interfaces:**
- Consumes: `/models/sanic-spin-ball.glb` and interpolated jump progress.
- Produces: `LoadedAssets.spinBall: Object3D` and `jumpPresentation(progress): 'character' | 'spin'`.

- [ ] **Step 1: Write RED tests**

Assert `ASSET_URLS.spinBall === '/models/sanic-spin-ball.glb'`; a valid `SANIC_SpinBall` root is returned independently of other categories; failed spin loading returns `SANIC_SpinBall_Fallback`; progress remains monotonic across four categories; and:

```typescript
expect(jumpPresentation(null)).toBe('character');
expect(jumpPresentation(0.15)).toBe('character');
expect(jumpPresentation(0.16)).toBe('spin');
expect(jumpPresentation(0.82)).toBe('spin');
expect(jumpPresentation(0.83)).toBe('character');
```

- [ ] **Step 2: Implement the minimal loader and timing behavior**

Add a lightweight fallback blue sphere with seven swept cones plus red/white flashes. Expand asset categories to `character`, `spinBall`, `ring`, and `forest`; select `SANIC_SpinBall` by semantic name; and expose immutable fallback metadata for all four categories.

Implement:

```typescript
export type JumpPresentation = 'character' | 'spin';

export const jumpPresentation = (progress: number | null): JumpPresentation => {
  if (progress === null || !Number.isFinite(progress)) return 'character';
  return progress >= 0.16 && progress <= 0.82 ? 'spin' : 'character';
};
```

- [ ] **Step 3: Verify focused tests and commit**

```bash
npm test -- tests/unit/config.test.ts tests/unit/assetLoader.test.ts tests/unit/animationTiming.test.ts
git add src/config.ts src/render/fallbackAssets.ts src/render/assetLoader.ts src/render/animationTiming.ts tests/unit/config.test.ts tests/unit/assetLoader.test.ts tests/unit/animationTiming.test.ts
git commit -m "feat: load SANIC spin presentation"
```

### Task 5: Integrate rigged assets and hybrid jump presentation

**Files:**
- Modify: `src/render/worldRenderer.ts`
- Create: `src/render/modelScale.ts`
- Test: `tests/unit/modelScale.test.ts`
- Replace after validation: `public/models/sanic-runner.glb`
- Create after validation: `public/models/sanic-spin-ball.glb`

**Interfaces:**
- Consumes: rigged character, spin ball, `jumpPresentation`, snapshot speed, and render delta.
- Produces: normalized character scale, synchronized visibility, rolling spin, and unchanged simulation behavior.

- [ ] **Step 1: Write RED normalization tests**

Implement the tested pure boundary:

```typescript
export const uniformScaleForHeight = (height: number, targetHeight: number): number => {
  if (!Number.isFinite(height) || height <= 0) return 1;
  if (!Number.isFinite(targetHeight) || targetHeight <= 0) return 1;
  return targetHeight / height;
};
```

Test `uniformScaleForHeight(7.221238, 4.12)` and `uniformScaleForHeight(1.7, 4.12)` as well as invalid dimensions.

- [ ] **Step 2: Add character/spin initialization**

Use a Three.js `Box3` to measure the rest character before scaling and target `4.12` world units. Apply the same uniform scale to the spin ball, rotate both roots by `Math.PI` on Y, hide the ball initially, enable shadows, and add both to the world. Keep the same animation mixer root and actions.

- [ ] **Step 3: Switch presentation without changing physics**

Each render sets character root position to `(playerX, playerY,0)` and spin root position to `(playerX, playerY+1.45,0)`. `jumpPresentation` exclusively controls visibility. Continue sampling the hidden `Jump` action so the rig is already in its uncurl pose when it becomes visible. While spin is visible, advance `spinRotation -= snapshot.speed * dt * 0.42` and assign it to `spinBall.rotation.x`. Reset visibility/rotation on restart and crash.

- [ ] **Step 4: Promote only validated assets**

Copy the locally validated rigged GLB and spin GLB to the two public model paths, then run the existing loader tests and a clean production build. Confirm `git status` contains only the intentional scripts, source, tests, and two model assets.

- [ ] **Step 5: Browser QA desktop and mobile**

Use a real browser to load the local production build at a desktop viewport and a representative narrow mobile viewport. Verify: no fallback asset warning, no console/WebGL error, character size matches the old live silhouette, run arms swing fore/aft, knees visibly flex, jump switches once into the ball and once out, ball follows player X/Y without ground teleport, landing lines up with simulation contact, and restart/crash never leaves both models visible.

- [ ] **Step 6: Full verification and commit**

```bash
npm test
npm run build
git diff --check
```

Run both Blender validators again against the exact public GLBs. Commit only after all commands pass and the desktop/mobile screenshots have been inspected.
