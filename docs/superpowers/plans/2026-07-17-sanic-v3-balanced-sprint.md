# SANIC v3 Balanced Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a visibly human, fast, smoothly grounded 17-frame SANIC sprint cycle while preserving the approved character, jump, spin-ball behavior, runtime cadence, and current v2 production rollback.

**Architecture:** Blender remains the production authority. A new `v3-run` branch in the existing deterministic rig builder authors only the `Run` action, and a new evaluated-geometry validator enforces the approved motion contract against both `.blend` and re-imported GLB. One guarded Meshy rig task and, only after inspection, one guarded Meshy sprint task may provide reference motion; their skeleton, skin, mesh, root translation, and jump never enter production. The browser exposes minimal action/pose diagnostics so Playwright can exercise the actual 0.035-second Run-to-Jump transition before the validated GLB replaces the current asset.

**Tech Stack:** Blender 5.1 Python API, Meshy Rigging/Animation REST APIs, Python 3 standard library, Three.js 0.185.1, TypeScript 7, Vitest 4, Playwright 1.61, Vite 8, Git/GitHub, Vercel.

## Global Constraints

- Work only in `/home/alex/projects/sanic-run-v2` on `feature/sanic-run-v2`.
- Publish only to `github.com/pasekaalex/sanic-run`; do not touch any other repository, remote, credential, deployment, or service.
- Use public author identity `pasekaalex <35618421+pasekaalex@users.noreply.github.com>` for every commit.
- Keep these v2 rollback artifacts byte-for-byte unchanged:
  - `/home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.glb` — `3567547081fb191a73562b306bea3dba299e717d89152ae42dd03e5a69a03333`
  - `/home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.blend` — `80960279c1e08a3c130bca92027a53bc9958bd9010cb891a777d2da2ee0236d7`
- Keep the current v1 and v2 builder branches behaviorally unchanged. Add `v3-run` as a separate conditional branch. The only permitted shared refactor is extracting the existing quaternion/root key insertion statements into `insert_pose_keys()` so v3 does not duplicate them; the all-action v1/v2 rebuild comparison must prove maximum delta `0.0`. Do not otherwise refactor shared rigging, skinning, non-Run action, or export code during this sprint.
- Preserve `Jump` exactly: 10,560 sampled matrix-basis values, maximum delta `0.0`, identical SHA-256 snapshot.
- Do not change the mesh, face, quills, gloves, shoes, materials, spin-ball, jump physics, world speed, or `runTimeScale` cap.
- Meshy spend is capped at one 5-credit auto-rig plus one 3-credit animation. No automatic retry, alternate action, or additional generation is authorized.
- Keep execution usage lean: use at most one implementation worker and one independent reviewer per task, and do not launch duplicate explorations or speculative asset generations.
- Never put the Meshy key, GitHub token, authorization header, Data URI, task response, signed URL, task ID, generated master, or temporary upload location in Git, terminal output, documentation, screenshots, or commit messages.
- Store Meshy state and generated reference files only below `/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/`. That directory is never copied into the repository.
- Use `/home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend` and `.glb` for the production candidate. Replace `public/models/sanic-runner.glb` only after every source, GLB, visual, unit, browser, and jump-preservation gate passes.
- Remove any temporary `node_modules` symlink before staging. Never commit `dist/`, `.vercel/`, test output, preview renders, Meshy state, or Downloads artifacts.
- If a required gate fails, keep v2 live, record the exact failing metric, and continue locally. Do not weaken a numeric gate without revising and re-approving the design specification.

---

## V3 validator checklist used inside Task 3

**Files:**

- Create: `blender/scripts/validate_meshy_run_v3.py`
- Reference: `blender/scripts/validate_meshy_run_v2.py`
- Reference: `docs/superpowers/specs/2026-07-17-sanic-v3-balanced-sprint-design.md`

### Create the v3 validator shell and exact coordinate/frame contract

Copy only the proven loading, dependency-graph evaluation, joint-angle, and weighted-vertex traversal helpers from `validate_meshy_run_v2.py`. Declare the v3 contract explicitly:

```python
FORWARD = Vector((0.0, -1.0, 0.0))
LATERAL = Vector((1.0, 0.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
ALL_RUN_FRAMES = tuple(range(1, 18))
STRIKE = ((1, "L"), (9, "R"))
LOAD = ((3, "L"), (11, "R"))
TOE_OFF = ((5, "L"), (13, "R"))
FLIGHT = (7, 15)
RECOVERY = ((5, "R", "L"), (13, "L", "R"))
V2_STRIDE_METERS = 0.504341721534729
MINIMUM_V3_STRIDE_METERS = V2_STRIDE_METERS * 1.35
```

Require `Run` frames `(1, 17)`, `Jump` frames `(1, 30)`, exactly one armature, and all expected SANIC bones. Source and GLB modes must share the same `validate()` path.

### Partition each shoe once in rest space, then sample evaluated vertices

For each side, collect vertices influenced by `foot.<side>` or `toe.<side>`. Transform their rest coordinates into rig world space and partition them by the `FORWARD` projection:

```python
ordered = sorted(weighted_vertices, key=lambda item: item.rest_world.dot(FORWARD))
quarter = max(1, len(ordered) // 4)
heel_vertices = {(item.object_name, item.index) for item in ordered[:quarter]}
forefoot_vertices = {(item.object_name, item.index) for item in ordered[-quarter:]}
shoe_vertices = {(item.object_name, item.index) for item in ordered}
```

At every sampled frame, evaluate the skinned mesh through the dependency graph and report:

- minimum whole-shoe Z;
- minimum heel Z;
- minimum forefoot Z;
- foot pitch from `foot.<side>.head` to `toe.<side>.tail`;
- toe world position;
- knee/hip/ankle positions and knee flexion.

Fail loudly if any region has no weighted vertices. Do not infer contact from bone endpoints alone.

### Implement all approved numeric gates

The validator must append named problems and exit non-zero unless all of these hold:

```python
assert 11.0 <= torso_lean_degrees <= 14.0
assert 0.035 <= root_vertical_range <= 0.050
assert max_adjacent_root_delta <= 0.018
assert max_second_root_delta <= 0.020
assert root_horizontal_range_x <= 0.001
assert root_horizontal_range_y <= 0.001
assert minimum_knee_flexion >= 15.0
assert recovery_knee_height_delta >= 0.120
assert stance_pitch_progression >= 22.0
assert strike_forefoot_z <= 0.006
assert 0.015 <= strike_heel_z <= 0.045
assert load_whole_shoe_z <= 0.008
assert toe_off_forefoot_z <= 0.008
assert toe_off_heel_z >= 0.060
assert maximum_toe_separation >= 0.6808613240718842
assert minimum_flight_shoe_z >= 0.025
assert 75.0 <= elbow_angle <= 105.0
assert elbow_angle_range >= 18.0
assert maximum_adjacent_shoulder_delta <= 20.0
assert maximum_identical_shoulder_run <= 1
assert rear_glove_height_separation >= 0.120
assert hand_root_relative_lateral_range <= 0.050
assert first_last_pose_error <= 1e-4
```

The torso check must use the evaluated sagittal angle from `hips.head` to `chest.tail` in degrees.

Measure shoulder continuity from the angle between adjacent normalized world-space upper-arm directions. Count two frames as identical when that angle is below `0.05°`; use the same angular measurement for the `20°` adjacent-change ceiling.

Print a compact JSON report containing every measured maximum/minimum and a final `SANIC_V3_RUN_VALIDATION=PASS` marker. On failure, print named metrics without dumping mesh data.

### Prove the validator is red against the current v2 source

Run:

```bash
if /usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  source /home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.blend
then
  echo "ERROR: v3 validator unexpectedly accepted v2" >&2
  exit 1
fi
```

Expected: failure names include root adjacent delta, stance pitch progression, torso lean, elbow-angle range, and stride. The measured v2 evidence should remain approximately 44.5 mm takeoff rise, 39.0 mm landing drop, 2.4° foot progression, 6.9–8.4° evaluated lean, 0° elbow variation, and 0.50434 m stride.

### Self-review the validator

Confirm:

- every design-spec threshold appears once in executable validation;
- both left and right limbs are checked symmetrically;
- all 17 integer frames are sampled;
- source and re-imported GLB use the same measurements;
- no hard-coded vertex index depends on one export ordering;
- every evaluated lookup is keyed by both mesh-object name and vertex index;
- JSON output cannot contain credentials, paths outside the named input, or signed URLs.

This checklist is reference material, not a standalone execution task. Task 3 creates the validator, proves the intended RED result, implements v3, makes source and GLB GREEN, and commits test plus implementation together.

---

## Task 1: Build a safe Meshy input and a one-shot spend guard

**Files:**

- Create: `blender/scripts/prepare_meshy_reference.py`
- Create: `blender/scripts/validate_meshy_reference.py`
- Create: `blender/scripts/meshy_sprint_reference.py`
- Create: `tests/python/test_meshy_sprint_reference.py`
- Read locally: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/SANIC-meshy6-v3-meshy-input.glb`

- [ ] **Step 1: Write a failing Meshy-input validator**

`validate_meshy_reference.py` imports a GLB and requires:

- exactly zero armatures;
- one or more visible textured meshes;
- fewer than 300,000 evaluated triangles;
- height between 1.55 m and 1.85 m;
- feet near Z=0;
- named eyelid/brow mesh centroids remain on the character's Blender `-Y` face side, which exports as glTF `+Z`;
- every packed image at or below 1,024 px;
- file size at or below 20 MiB.

Check orientation from the semantic meshes rather than guessing from the overall bounds: all four `SANIC_Face_Eyelid.*` / `SANIC_Face_Brow.*` centroids must have world Y below `-0.20 m`, and each left/right pair must remain mirrored within `0.03 m` on X and `0.03 m` on Y.

Run it against the existing 36,139,736-byte corrected GLB and expect a non-zero size/image preflight failure:

```bash
if /usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_reference.py -- \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.glb
then
  echo "ERROR: unoptimized Meshy input unexpectedly passed" >&2
  exit 1
fi
```

- [ ] **Step 2: Implement the local-only Meshy input exporter**

`prepare_meshy_reference.py` opens the corrected `.blend`, selects only `SANIC_CHARACTER_EXPORT` (explicitly excluding `SANIC_RAW_PRIVATE` and `SANIC_SPIN_EXPORT`), removes no source data, scales image copies in memory to a maximum dimension of 1,024 px, packs those image buffers, and exports an unrigged Draco-compressed GLB with materials and tangents. It must never save over the corrected `.blend`.

Use the same glTF coordinate options as the production exporter:

```python
result = bpy.ops.export_scene.gltf(
    filepath=str(output_path),
    export_format="GLB",
    use_selection=True,
    export_animations=False,
    export_materials="EXPORT",
    export_tangents=True,
    export_yup=True,
    export_draco_mesh_compression_enable=True,
    export_draco_mesh_compression_level=6,
    export_draco_position_quantization=14,
    export_draco_normal_quantization=10,
    export_draco_texcoord_quantization=12,
)
assert result == {"FINISHED"}, result
```

The script accepts exactly `SOURCE_BLEND OUTPUT_GLB`, refuses to write inside the repository, and prints only the output path, byte size, triangle count, dimensions, and image dimensions.

- [ ] **Step 3: Write unit tests for the spend guard before its implementation**

First create an importable zero-behavior skeleton in `meshy_sprint_reference.py` containing only `API_BASE`, the command parser, typed function signatures, and `raise NotImplementedError("spend guard not implemented")` bodies. It must make no network request and read no environment variable at import time.

Using `unittest.mock`, specify that the Meshy client:

- reads only `MESHY_API_KEY` and raises if absent;
- never returns or logs an authorization header;
- performs `GET /openapi/v1/balance` before a paid call;
- refuses a rig call when balance is below 8 credits;
- atomically writes `rig_attempted_at` before the rig POST;
- refuses any second rig POST once that marker exists, even if the first call errored;
- requires a successful stored `rig_task_id` and explicit `--approve-rig` for animation;
- atomically writes `animation_attempted_at` before the animation POST;
- refuses any second animation POST;
- sends only action `644` with 24-fps post-processing.

The exact animation payload is:

```python
{
    "rig_task_id": rig_task_id,
    "action_id": 644,
    "post_process": {
        "operation_type": "change_fps",
        "fps": 24,
    },
}
```

Run and expect RED assertions from `NotImplementedError` or unmet guard behavior—not `ImportError`, syntax error, collection failure, or a real network request:

```bash
python3 -m unittest tests/python/test_meshy_sprint_reference.py
```

- [ ] **Step 4: Implement the one-shot Meshy client**

Use only Python standard-library `urllib.request`; no dependency changes. Provide these subcommands:

```text
balance
rig INPUT_GLB STATE_JSON
poll-rig STATE_JSON OUTPUT_DIR
approve-rig STATE_JSON
animate STATE_JSON
poll-animation STATE_JSON OUTPUT_DIR
```

Rules:

- API base is fixed to `https://api.meshy.ai/openapi/v1`.
- `rig` converts the optimized GLB to a `data:model/gltf-binary;base64,...` Data URI in memory and posts `{"model_url": data_uri, "height_meters": 1.7}`.
- Before either paid POST, persist the attempt marker with an atomic temporary-file rename. This intentionally prefers stopping over accidental duplicate spend.
- Never persist the encoded GLB, Data URI, authorization header, or request body in the state file.
- Poll only the exact stored task ID. Polling and downloading do not create tasks.
- A failed/canceled task ends that branch; no client command clears attempt markers.
- `approve-rig` records a local boolean only after human/agent visual inspection; it performs no network request.
- Download only allow-listed result fields into the local output directory. Never print a signed URL, Data URI, API response, or authorization value.
- Console output is restricted to task type, redacted ID suffix, status, progress, consumed credits, local filenames, and error message.
- Raw state JSON lives outside the repo and is mode `0600`.

- [ ] **Step 5: Make the tests green and validate the optimized input**

```bash
python3 -m unittest tests/python/test_meshy_sprint_reference.py
mkdir -p /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/prepare_meshy_reference.py -- \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/SANIC-meshy6-v3-meshy-input.glb
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_reference.py -- \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/SANIC-meshy6-v3-meshy-input.glb
```

Expected: unit tests pass; the local GLB is textured, unrigged, below 300,000 faces, below 20 MiB, approximately 1.7 m tall, and faces the Meshy-required glTF `+Z` direction.

- [ ] **Step 6: Self-review and commit only reproducible code**

Confirm no response fixtures contain a real task ID, signed URL, Data URI, or key. Fixtures use obvious values such as `rig-task-example`.

```bash
git add \
  blender/scripts/prepare_meshy_reference.py \
  blender/scripts/validate_meshy_reference.py \
  blender/scripts/meshy_sprint_reference.py \
  tests/python/test_meshy_sprint_reference.py
git diff --cached --check
git -c user.name=pasekaalex \
  -c user.email=35618421+pasekaalex@users.noreply.github.com \
  commit -m "feat: guard Meshy sprint references"
```

---

## Task 2: Run the bounded Meshy motion-reference experiment

**Files:**

- Use locally: `/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/SANIC-meshy6-v3-meshy-input.glb`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/state.json`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/rig/`
- Create locally only after approval: `/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/sprint-644/`
- Modify in Git: none

- [ ] **Step 1: Load the already-authorized key without displaying it**

Use the operating-system keyring or a process-scoped `MESHY_API_KEY`. If the key is not yet in the keyring, store the already-authorized session value through `secret-tool` standard input; never put it in a command argument, shell history, plan, file, or output.

Verify only presence:

```bash
test -n "$(secret-tool lookup service meshy api_key)" &&
  echo "Meshy credential available"
```

Do not print the lookup value.

- [ ] **Step 2: Check balance and submit exactly one rig task**

```bash
MESHY_API_KEY="$(secret-tool lookup service meshy api_key)" \
python3 blender/scripts/meshy_sprint_reference.py balance

MESHY_API_KEY="$(secret-tool lookup service meshy api_key)" \
python3 blender/scripts/meshy_sprint_reference.py rig \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/SANIC-meshy6-v3-meshy-input.glb \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/state.json
```

Expected: balance is at least 8 credits and one rig task is stored. If the POST fails, stop; do not delete/edit state or retry.

- [ ] **Step 3: Poll and download the one rig result**

```bash
MESHY_API_KEY="$(secret-tool lookup service meshy api_key)" \
python3 blender/scripts/meshy_sprint_reference.py poll-rig \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/state.json \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/rig
```

Repeat only this read-only poll command until terminal status. Download the rigged GLB/FBX and supplied basic-running files immediately after success because Meshy output URLs expire.

- [ ] **Step 4: Inspect the auto-rig from front, side, and rear**

Open/import the rig result in an isolated Blender process. Reject it if any of these occur:

- face, quills, ring earring, gloves, or shoes are missing or materially reshaped;
- left/right limbs are crossed or assigned to the wrong bones;
- shoulder, elbow, wrist, hip, knee, ankle, or toe bends collapse the mesh;
- rest pose is rotated away from the expected forward axis;
- basic run has foot skating, locked knees, lateral arm flailing, or worse rear-view readability than v2.

If rejected, record `rig_approved: false` locally and skip every remaining Meshy animation step. Blender v3 implementation still proceeds.

- [ ] **Step 5: Only after a clean rig, request action 644 once**

```bash
MESHY_API_KEY="$(secret-tool lookup service meshy api_key)" \
python3 blender/scripts/meshy_sprint_reference.py approve-rig \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/state.json

MESHY_API_KEY="$(secret-tool lookup service meshy api_key)" \
python3 blender/scripts/meshy_sprint_reference.py animate \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/state.json

MESHY_API_KEY="$(secret-tool lookup service meshy api_key)" \
python3 blender/scripts/meshy_sprint_reference.py poll-animation \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/state.json \
  /home/alex/Downloads/SANIC-Meshy-v3/meshy-reference/sprint-644
```

Use the processed 24-fps FBX only as a timing/pose reference. Discard its mesh, skin, materials, root translation, and non-Run clips. Do not perform another generation if it is poor.

- [ ] **Step 6: Confirm repository isolation**

```bash
git status --short
if git ls-files | rg -q 'meshy-reference|state\.json|sprint-644'
then
  echo "ERROR: local Meshy artifact is tracked" >&2
  exit 1
fi
```

Expected: Task 2 creates no tracked or untracked repository file.

---

## Task 3: Define and author the v3 Blender sprint

**Files:**

- Modify: `blender/scripts/rig_meshy_sanic.py`
- Create: `blender/scripts/validate_meshy_run_v3.py`
- Create: `blender/scripts/compare_meshy_actions.py`
- Test: `blender/scripts/compare_meshy_jump.py`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v3/animation-preview/`

- [ ] **Step 1: Create the complete v3 validator and prove RED**

Implement every item in the “V3 validator checklist used inside Task 3” above, including object-qualified shoe vertex keys of `(mesh_object.name, vertex.index)` so equal vertex indices from different meshes cannot collide.

Run it against both current v2 artifacts:

```bash
if /usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  source /home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.blend
then
  echo "ERROR: v3 validator unexpectedly accepted v2 source" >&2
  exit 1
fi
if /usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  glb /home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.glb
then
  echo "ERROR: v3 validator unexpectedly accepted v2 GLB" >&2
  exit 1
fi
```

Expected: both fail on the intended root, foot-roll, lean, elbow-range, and stride metrics—not on import, missing bones, empty shoe regions, exceptions, or malformed output. Keep this RED state uncommitted and continue directly to Step 2.

- [ ] **Step 2: Add v3 identity without changing v1/v2 behavior**

Make the smallest top-level additions:

```python
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
```

Set `sanic_rig_version` to `1`, `2`, or `3` by exact variant and set `sanic_run_variant = "v3-run"` for v3. Keep `Run` at 24 frames only for v1 and 17 frames for both sprint variants.

Change the current broad `else` into `elif RIG_VARIANT == "v2-run"` and leave every v2 constant and statement byte-for-byte in that branch. Add the new v3 code only in the final `else`.

- [ ] **Step 3: Add distinct v3 anchor poses**

Use frames `1, 3, 5, 7, 9, 11, 13, 15, 17`:

```text
1  left forefoot/midfoot strike, right trail, right glove forward
3  left full-sole load/compression, right recovery
5  left toe-off, right knee drive, arms passing
7  flight, right leg opening, left heel recovery
9  mirrored right strike
11 mirrored right load/compression
13 mirrored right toe-off
15 mirrored flight
17 exact duplicate of frame 1
```

Start with this complete v3 pose table. Each direction is `(lateral, forward, up)` and is normalized by the existing `side_direction()` helper:

```python
v3_arm_forward_strike = (
    (0.025, 0.500, -0.866),
    (0.020, 0.788, 0.616),
    (0.015, 0.820, 0.572),
)
v3_arm_forward_load = (
    (0.025, 0.350, -0.937),
    (0.020, 0.930, 0.368),
    (0.015, 0.954, 0.300),
)
v3_arm_forward_pass = (
    (0.025, 0.174, -0.985),
    (0.020, 1.000, 0.000),
    (0.015, 0.940, -0.342),
)
v3_arm_forward_flight = (
    (0.025, 0.620, -0.785),
    (0.020, 0.720, 0.694),
    (0.015, 0.800, 0.600),
)
v3_arm_back_strike = (
    (0.025, -0.906, -0.423),
    (0.020, 0.600, -0.800),
    (0.015, 0.480, -0.877),
)
v3_arm_back_load = (
    (0.025, -0.820, -0.572),
    (0.020, 0.650, -0.760),
    (0.015, 0.450, -0.893),
)
v3_arm_back_pass = (
    (0.025, -0.643, -0.766),
    (0.020, 0.695, -0.719),
    (0.015, 0.500, -0.866),
)
v3_arm_back_flight = (
    (0.025, -0.950, -0.312),
    (0.020, 0.530, -0.848),
    (0.015, 0.400, -0.916),
)

v3_leg_strike = (
    (0.025, 0.520, -0.854),
    (0.020, 0.100, -0.995),
    (0.015, 0.966, -0.259),
    (0.010, 0.999, -0.040),
)
v3_leg_trail = (
    (0.025, -0.450, -0.893),
    (0.020, -0.800, -0.600),
    (0.015, 0.820, -0.572),
    (0.010, 0.985, -0.174),
)
v3_leg_load = (
    (0.025, 0.180, -0.984),
    (0.020, -0.550, -0.835),
    (0.015, 1.000, -0.020),
    (0.010, 1.000, 0.000),
)
v3_leg_recovery = (
    (0.025, -0.100, -0.995),
    (0.020, -0.980, -0.200),
    (0.015, 0.980, 0.200),
    (0.010, 0.995, 0.100),
)
v3_leg_toe_off = (
    (0.025, -0.250, -0.968),
    (0.020, -0.700, -0.714),
    (0.015, 0.866, -0.500),
    (0.010, 0.985, -0.174),
)
v3_leg_knee_drive = (
    (0.025, 0.720, -0.694),
    (0.020, -0.550, -0.835),
    (0.015, 0.940, 0.342),
    (0.010, 0.985, 0.174),
)
v3_leg_flight_lead = (
    (0.025, 0.820, -0.572),
    (0.020, -0.120, -0.993),
    (0.015, 0.980, -0.200),
    (0.010, 0.995, -0.100),
)
v3_leg_flight_recovery = (
    (0.025, -0.600, -0.800),
    (0.020, -0.940, 0.342),
    (0.015, 0.900, 0.435),
    (0.010, 0.980, 0.200),
)

v3_contact_a = pose(
    root_up=0.006, lean=24.0, pelvis_yaw=-5.0, chest_yaw=7.0,
    arms={"L": v3_arm_back_strike, "R": v3_arm_forward_strike},
    legs={"L": v3_leg_strike, "R": v3_leg_trail},
)
v3_load_a = pose(
    root_up=-0.014, lean=26.0, pelvis_yaw=-3.0, chest_yaw=4.0,
    arms={"L": v3_arm_back_load, "R": v3_arm_forward_load},
    legs={"L": v3_leg_load, "R": v3_leg_recovery},
)
v3_toe_a = pose(
    root_up=0.006, lean=27.0, pelvis_yaw=1.0, chest_yaw=-2.0,
    arms={"L": v3_arm_forward_pass, "R": v3_arm_back_pass},
    legs={"L": v3_leg_toe_off, "R": v3_leg_knee_drive},
)
v3_flight_a = pose(
    root_up=0.0, lean=26.0, pelvis_yaw=4.0, chest_yaw=-6.0,
    arms={"L": v3_arm_forward_flight, "R": v3_arm_back_flight},
    legs={"L": v3_leg_flight_recovery, "R": v3_leg_flight_lead},
)
v3_contact_b = pose(
    root_up=0.006, lean=24.0, pelvis_yaw=5.0, chest_yaw=-7.0,
    arms={"L": v3_arm_forward_strike, "R": v3_arm_back_strike},
    legs={"L": v3_leg_trail, "R": v3_leg_strike},
)
v3_load_b = pose(
    root_up=-0.014, lean=26.0, pelvis_yaw=3.0, chest_yaw=-4.0,
    arms={"L": v3_arm_forward_load, "R": v3_arm_back_load},
    legs={"L": v3_leg_recovery, "R": v3_leg_load},
)
v3_toe_b = pose(
    root_up=0.006, lean=27.0, pelvis_yaw=-1.0, chest_yaw=2.0,
    arms={"L": v3_arm_back_pass, "R": v3_arm_forward_pass},
    legs={"L": v3_leg_knee_drive, "R": v3_leg_toe_off},
)
v3_flight_b = pose(
    root_up=0.0, lean=26.0, pelvis_yaw=-4.0, chest_yaw=6.0,
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
```

The values are a deterministic starting implementation, not alternate acceptance criteria. If a numeric validator identifies a miss, adjust only the v3 constant responsible for that named metric and record the before/after measurement. Do not substitute vague visual tuning for a validator result.

- [ ] **Step 4: Replace frame-local flight grounding with a continuous root bridge**

For v3 only, solve the grounded root correction at every stance frame first. Bridge frame 5 to 9 and frame 13 to 17 with smooth interpolation plus a 24 mm parabola:

```python
def flight_root_offset(
    start: Vector,
    end: Vector,
    frame: int,
    first: int,
    last: int,
) -> Vector:
    t = (frame - first) / (last - first)
    smooth = t * t * (3.0 - 2.0 * t)
    arc = 0.024 * 4.0 * t * (1.0 - t)
    return start.lerp(end, smooth) + up * arc
```

Implement the two-pass solve completely:

```python
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

def make_v3_run(
    anchors: dict[int, dict[str, object]],
) -> bpy.types.Action:
    poses = {frame: pose_between(anchors, frame) for frame in range(1, 18)}
    stance_sides = {
        **{frame: "L" for frame in range(1, 6)},
        **{frame: "R" for frame in range(9, 14)},
        17: "L",
    }
    root_offsets: dict[int, Vector] = {}

    for frame, side in stance_sides.items():
        scene.frame_set(frame)
        solve_pose(poses[frame])
        base = poses[frame]["root_offset"]
        assert isinstance(base, Vector)
        correction = 0.002 - deformed_foot_minimum_z(side)
        root_offsets[frame] = base + up * correction

    root_offsets[17] = root_offsets[1].copy()
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
        solved = {**poses[frame], "root_offset": root_offsets[frame]}
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

run = make_v3_run(v3_anchors)
```

Frames 1 and 17 must use the same pose and solved root offset. The validator, not visual guesswork, decides whether the 24 mm arc needs adjustment within the approved 35–50 mm total COM range.

Implement this as a separate `make_v3_run()` helper beside the existing `make()`/`key_pose()` path. Extract the current key-insertion statements exactly into `insert_pose_keys()` and call it from both `key_pose()` and v3. Do not change existing grounding behavior or the `make()` call sites for v1, v2, Idle, Jump, or Crash.

- [ ] **Step 5: Add the mandatory rear gameplay-camera preview**

For v3 preview only:

```python
views = {
    "front": Vector((0.0, -4.2, 0.86)),
    "side": Vector((-4.2, 0.0, 0.86)),
    "rear": Vector((0.0, 4.2, 0.86)),
}
```

The rear camera points toward `(0, 0, 0.84)`. Keep the nine checkpoints for front and side, but render every integer Run frame `1..17` from the rear. Preserve current front/side filenames and create the complete sequence `run-rear-01.png` through `run-rear-17.png`.

After the Blender build, create a local-only three-cycle 24-fps review video:

```bash
ffmpeg -y -framerate 24 \
  -i /home/alex/Downloads/SANIC-Meshy-v3/animation-preview/run-rear-%02d.png \
  -vf 'loop=loop=2:size=17:start=0' \
  -frames:v 51 -c:v libx264 -pix_fmt yuv420p \
  /home/alex/Downloads/SANIC-Meshy-v3/animation-preview/run-rear-3cycles.mp4
```

Expected: exactly 51 frames. The movie is mandatory for temporal review and remains untracked.

- [ ] **Step 6: Build the isolated candidate**

```bash
mkdir -p /home/alex/Downloads/SANIC-Meshy-v3
SANIC_CORRECTED_BLEND=/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend \
SANIC_RIG_OUTPUT_DIR=/home/alex/Downloads/SANIC-Meshy-v3 \
SANIC_RIG_VARIANT=v3-run \
SANIC_RIG_BASENAME=SANIC-meshy6-v3-run \
SANIC_RUN_ONLY_PREVIEW=1 \
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/rig_meshy_sanic.py
```

- [ ] **Step 7: Make the v3 contract green on source and GLB**

```bash
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  source /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  glb /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb
```

When a metric fails, adjust only the v3 pose/root constants tied to that metric, rebuild once, and rerun both modes. Never alter validator thresholds, v2 code, jump anchors, skinning, or the mesh to force a pass.

- [ ] **Step 8: Rebuild and semantically compare the untouched v1/v2 paths**

Create `compare_meshy_actions.py` to snapshot all four actions—`Idle`, `Run`, `Jump`, and `Crash`—at every integer frame. It only compares the same variant to a rebuild of itself, so Run ranges match. For every sorted pose bone, serialize all 16 `matrix_basis` components and compare baseline/candidate lengths, per-action SHA-256, and maximum absolute delta. It also compares:

- armature name and bone-name set;
- `sanic_rig_version` and `sanic_run_variant`;
- action frame ranges;
- scene FPS;
- mesh names and material-slot names.

Build v1 and v2 into a newly allocated temporary directory, then compare and validate them in the same shell so no pre-existing directory is deleted or reused:

```bash
regression_root="$(mktemp -d /tmp/sanic-v3-regression.XXXXXX)"
mkdir "$regression_root/v1" "$regression_root/v2"
SANIC_CORRECTED_BLEND=/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend \
SANIC_RIG_OUTPUT_DIR="$regression_root/v1" \
SANIC_RIG_VARIANT=v1 \
SANIC_RUN_ONLY_PREVIEW=1 \
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/rig_meshy_sanic.py
SANIC_CORRECTED_BLEND=/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-corrected.blend \
SANIC_RIG_OUTPUT_DIR="$regression_root/v2" \
SANIC_RIG_VARIANT=v2-run \
SANIC_RUN_ONLY_PREVIEW=1 \
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/rig_meshy_sanic.py
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/compare_meshy_actions.py -- \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.blend \
  "$regression_root/v1/SANIC-meshy6-v1-rigged.blend"
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/compare_meshy_actions.py -- \
  /home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.blend \
  "$regression_root/v2/SANIC-meshy6-v2-run.blend"
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_rig.py -- \
  glb "$regression_root/v1/SANIC-meshy6-v1-rigged.glb"
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_rig.py -- \
  glb "$regression_root/v2/SANIC-meshy6-v2-run.glb"
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v2.py -- \
  glb "$regression_root/v2/SANIC-meshy6-v2-run.glb"
```

Expected: every v1 and v2 action, including both legacy Run cycles, is byte-for-byte numeric-identical with maximum delta `0.0`; metadata and semantic validators pass. A regression blocks v3 regardless of whether the original rollback files still hash correctly.

- [ ] **Step 9: Prove v3 jump preservation immediately**

```bash
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/compare_meshy_jump.py -- \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.blend \
  /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend
```

Expected: `samples: 10560`, `maximum_delta: 0.0`, identical snapshot SHA.

- [ ] **Step 10: Self-review and commit the GREEN validator with the builder**

Review the diff to confirm only v3 identity, v3 run construction, the continuous v3 root solver, and the v3 rear preview were added.

```bash
git diff -- \
  blender/scripts/rig_meshy_sanic.py \
  blender/scripts/validate_meshy_run_v3.py \
  blender/scripts/compare_meshy_actions.py
git add \
  blender/scripts/rig_meshy_sanic.py \
  blender/scripts/validate_meshy_run_v3.py \
  blender/scripts/compare_meshy_actions.py
git diff --cached --check
git -c user.name=pasekaalex \
  -c user.email=35618421+pasekaalex@users.noreply.github.com \
  commit -m "feat: build SANIC v3 balanced sprint"
```

---

## Task 4: Prove the runtime Run-to-Jump transition

**Files:**

- Modify: `blender/scripts/validate_meshy_rig.py`
- Modify: `src/render/worldRenderer.ts`
- Modify: `tests/unit/animationTiming.test.ts`
- Modify: `tests/e2e/game.spec.ts`
- Test: `src/render/animationTiming.ts`

- [ ] **Step 1: Write failing generic-rig and runtime assertions**

Update `validate_meshy_rig.py` expectations so rig versions 2 and 3 both require `Run: (1, 17)`, but version 3 additionally requires `sanic_run_variant == "v3-run"`.

Tighten the existing unit assertion to the exact approved transition:

```typescript
expect(animationCrossfadeSeconds('Jump')).toBe(0.035);
```

Add an E2E test named `crossfades the v3 sprint into jump without a pose snap`. Before runtime implementation, it must fail because `data-character-action` and `data-pose-probe` are absent.

- [ ] **Step 2: Add minimal action and pose diagnostics to the renderer**

Inside `updateAnimation()`, immediately after selecting `desired`, set:

```typescript
this.canvas.dataset.characterAction = desired;
```

In `?e2e=1` mode only, resolve `root`, `hips`, `chest`, `foot.L`, and `foot.R` once from the loaded character. After `character.updateMatrixWorld(true)`, transform each bone's world position back through `character.worldToLocal()`. Record Three.js-up Y, sagittal Z, and the sagittal body-axis lean from hips to chest:

```typescript
this.canvas.dataset.poseProbe = [
  rootY,
  rootZ,
  chestY,
  chestZ,
  leftFootY,
  leftFootZ,
  rightFootY,
  rightFootZ,
  bodyLeanDegrees,
].map((value) => value.toFixed(5)).join(',');
```

Do not expose the skeleton, renderer, mixer, or asset object on `window`. Production without `?e2e=1` gets only `data-character-action`.

- [ ] **Step 3: Exercise the real transition in Playwright**

The new test:

1. calls `beginRun(page)`;
2. waits for `data-character-asset="glb"` and `data-character-action="Run"`;
3. samples `data-pose-probe` on `requestAnimationFrame`;
4. dispatches Space;
5. samples through `Run -> Jump -> Run`;
6. ignores adjacent samples separated by more than 80 ms;
7. rejects non-finite/missing values;
8. enforces maximum adjacent deltas:
   - root Y: `<= 0.080 m`;
   - root Z: `<= 0.080 m`;
   - chest Y: `<= 0.100 m`;
   - chest Z: `<= 0.120 m`;
   - either foot Y: `<= 0.180 m`;
   - either foot Z: `<= 0.220 m`;
   - body-axis lean: `<= 12°`;
9. confirms the spin presentation still appears during the middle of the jump and returns to character presentation on landing.

These are transition safety limits, not replacements for the stricter 24-fps Blender biomechanical gates.

- [ ] **Step 4: Run focused tests**

If needed for this worktree only:

```bash
ln -s /home/alex/projects/sanic-run-public/node_modules node_modules
```

Then:

```bash
npx vitest run tests/unit/animationTiming.test.ts
npx playwright test tests/e2e/game.spec.ts \
  --project=desktop-chromium \
  --grep "crossfades the v3 sprint into jump without a pose snap"
npx playwright test tests/e2e/game.spec.ts \
  --project=mobile-chromium \
  --grep "crossfades the v3 sprint into jump without a pose snap"
```

Expected: unit, desktop, and mobile focused tests pass against the tracked v2 rollback asset, proving the diagnostic and transition-test plumbing without changing the model. Task 5 reruns the same test against v3 after the promotion gate.

- [ ] **Step 5: Self-review and commit diagnostics/tests**

Check that runtime gameplay behavior did not change: `src/render/animationTiming.ts` remains unchanged, diagnostics do not run outside E2E except for the action name, and no object is exposed globally.

```bash
git add \
  blender/scripts/validate_meshy_rig.py \
  src/render/worldRenderer.ts \
  tests/unit/animationTiming.test.ts \
  tests/e2e/game.spec.ts
git diff --cached --check
git -c user.name=pasekaalex \
  -c user.email=35618421+pasekaalex@users.noreply.github.com \
  commit -m "test: prove SANIC sprint jump transitions"
```

---

## Task 5: Independently review and promote the candidate

**Files:**

- Replace only after approval: `public/models/sanic-runner.glb`
- Read locally: `/home/alex/Downloads/SANIC-Meshy-v3/animation-preview/`
- Read locally: `/home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend`
- Read locally: `/home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb`

- [ ] **Step 1: Run all Blender gates before looking at aesthetics**

```bash
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  source /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_run_v3.py -- \
  glb /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_rig.py -- \
  source /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/validate_meshy_rig.py -- \
  glb /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb
/usr/bin/blender --background --factory-startup --python-exit-code 1 \
  --python blender/scripts/compare_meshy_jump.py -- \
  /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1-rigged.blend \
  /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.blend
```

- [ ] **Step 2: Obtain an independent visual review**

Give a reviewer the nine front/side checkpoint sets, all 17 rear frames, and the 51-frame three-cycle rear video without telling them which metric was most recently adjusted. Require explicit review of:

- continuous vertical COM without pogo takeoff/landing;
- alternating strike, load, toe-off, and flight;
- heel lift and visible toe-off rather than a flat sliding sole;
- bent knees with believable recovery;
- arms driving fore/aft, not side-to-side;
- visibly changing elbow flexion and glove-height separation;
- no glove/quill, thigh/crotch, shoe/ground, or limb/torso intersection;
- exact loop seam from frame 17 back to frame 1.

Static frames establish pose quality; the uninterrupted three-cycle video is the release gate for temporal popping, foot skating, shoulder holds, easing discontinuities, and the frame-17/frame-1 seam.

Any Critical or Important finding returns to Task 3. A subjective preference that conflicts with a numeric gate requires a design revision, not an ad hoc validator change.

- [ ] **Step 3: Promote the exact approved GLB**

```bash
cp \
  /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb \
  public/models/sanic-runner.glb
test "$(sha256sum /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb | cut -d' ' -f1)" = \
     "$(sha256sum public/models/sanic-runner.glb | cut -d' ' -f1)"
```

Record the candidate SHA-256 in the final handoff, not in source code.

- [ ] **Step 4: Run focused browser transition tests on the promoted asset**

```bash
npx vitest run tests/unit/animationTiming.test.ts
npx playwright test tests/e2e/game.spec.ts \
  --project=desktop-chromium \
  --grep "crossfades the v3 sprint into jump without a pose snap"
npx playwright test tests/e2e/game.spec.ts \
  --project=mobile-chromium \
  --grep "crossfades the v3 sprint into jump without a pose snap"
```

- [ ] **Step 5: Run the complete local release suite**

```bash
npm run test
npm run build
npx playwright test
```

Expected: all unit tests, build, and every non-skipped desktop/mobile E2E pass; only the known Vite chunk-size advisory is allowed.

- [ ] **Step 6: Recheck rollback artifacts and repository hygiene**

```bash
test "$(sha256sum /home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.glb | cut -d' ' -f1)" = \
  "3567547081fb191a73562b306bea3dba299e717d89152ae42dd03e5a69a03333"
test "$(sha256sum /home/alex/Downloads/SANIC-Meshy-v2/SANIC-meshy6-v2-run.blend | cut -d' ' -f1)" = \
  "80960279c1e08a3c130bca92027a53bc9958bd9010cb891a777d2da2ee0236d7"
if [ -L node_modules ]; then rm node_modules; fi
git status --short
```

- [ ] **Step 7: Commit the approved production asset**

```bash
git add public/models/sanic-runner.glb
git diff --cached --check
git -c user.name=pasekaalex \
  -c user.email=35618421+pasekaalex@users.noreply.github.com \
  commit -m "feat: ship SANIC v3 balanced sprint"
test -z "$(git status --porcelain)"
```

---

## Task 6: Public-safety audit, push, deploy, and live verification

**Files:**

- Push: current branch `HEAD` to `origin/main`
- Deploy: linked Vercel project `sanic-run`
- Verify: `https://www.sanic.fun`

- [ ] **Step 1: Run public-repository safety scans**

List filenames only when looking for secrets:

```bash
git status --short
git diff origin/main...HEAD --check
git diff --stat origin/main...HEAD
credential_pattern='ghp_[[:alnum:]]{20,}|msy_[[:alnum:]]{20,}|Authorization:[[:space:]]+Bearer[[:space:]]+[[:alnum:]_.-]{12,}'
if credential_files="$(
  git grep -IlE "$credential_pattern" -- ':!public/models/*.glb'
)"
then
  printf 'Potential credential-bearing tracked files:\n%s\n' "$credential_files" >&2
  exit 1
fi
working_files="$(
  rg -Il --hidden \
    --glob '!.git/**' \
    --glob '!node_modules/**' \
    --glob '!public/models/*.glb' \
    "$credential_pattern" . || true
)"
if [ -n "$working_files" ]
then
  printf 'Potential credential-bearing working-tree files:\n%s\n' "$working_files" >&2
  exit 1
fi
suspicious_names="$(
  find . \
    -path './.git' -prune -o \
    -path './node_modules' -prune -o \
    -type f \
    \( -name '.env*' -o -iname '*credential*' -o -iname '*secret*' -o -iname '*token*' \) \
    -print
)"
if [ -n "$suspicious_names" ]
then
  printf 'Suspicious public-tree filenames:\n%s\n' "$suspicious_names" >&2
  exit 1
fi
history_matches="$(git log --all --format='%H %s' -G "$credential_pattern")"
if [ -n "$history_matches" ]
then
  printf 'Credential pattern found in Git history:\n%s\n' "$history_matches" >&2
  exit 1
fi

# Construct the public-identity/client/AI-attribution policy at runtime so
# this audit recipe does not itself contain a prohibited contiguous string.
robot_mark="$(printf '\360\237\244\226')"
public_pattern='alex[ ._-]pa''seka|pa''seka[ ,._-]+alex|ja''cob|p''cg|pre''stigious|co-authored-by:[[:space:]]*(cl''aude|co''dex|chat''gpt)|gen''erated[[:space:]]+w''ith[[:space:]]+(cl''aude([[:space:]]+code)?|co''dex|chat''gpt|open''ai)|cl''aude\.com/cl''aude-code|noreply@anth''ropic\.com|'"$robot_mark"
public_tree_hits="$(
  rg --hidden -il \
    --glob '!.git/**' \
    --glob '!node_modules/**' \
    --glob '!public/models/*.glb' \
    -e "$public_pattern" . || true
)"
if [ -n "$public_tree_hits" ]
then
  printf 'Public-policy working-tree match:\n%s\n' "$public_tree_hits" >&2
  exit 1
fi
if git diff --cached | rg -qi -e "$public_pattern"
then
  echo "Public-policy match in staged diff" >&2
  exit 1
fi
if git diff origin/main...HEAD | rg -qi -e "$public_pattern"
then
  echo "Public-policy match in branch diff" >&2
  exit 1
fi
if git log origin/main..HEAD --format='%an %ae%n%B' | rg -qi -e "$public_pattern"
then
  echo "Public-policy match in branch author or commit message" >&2
  exit 1
fi
if git log --all --format='%an %ae%n%B' | rg -qi -e "$public_pattern"
then
  echo "Public-policy match in full-history author or commit message" >&2
  exit 1
fi
public_history_hits="$(
  git log --all --format='%H %s' -i -G "$public_pattern" -- .
)"
if [ -n "$public_history_hits" ]
then
  echo "Public-policy content found in Git history" >&2
  exit 1
fi

repo_metadata="$(
  gh repo view pasekaalex/sanic-run \
    --json name,description,homepageUrl,repositoryTopics
)"
issue_metadata="$(
  gh api --paginate 'repos/pasekaalex/sanic-run/issues?state=all&per_page=100' \
    --jq '.[] | [.title, (.body // "")] | @tsv'
)"
release_metadata="$(
  gh api --paginate 'repos/pasekaalex/sanic-run/releases?per_page=100' \
    --jq '.[] | [.name, .tag_name, (.body // "")] | @tsv'
)"
if printf '%s\n%s\n%s\n' \
  "$repo_metadata" "$issue_metadata" "$release_metadata" |
  rg -qi -e "$public_pattern"
then
  echo "Public-policy match in GitHub-side metadata" >&2
  exit 1
fi
```

Expected: no credential-bearing file and no matching commit. Inspect `git diff --name-status origin/main...HEAD` and confirm every path belongs to the SANIC v3 sprint/spec/plan.

- [ ] **Step 2: Verify authorship and remote-main precondition**

```bash
git log --format='%h %an <%ae> %s' origin/main..HEAD
git fetch origin
test "$(git rev-parse origin/main)" = \
  "3df53e7e90f12d96473ec6c5de2e8084b0b9e336"
test -z "$(git status --porcelain)"
```

If remote main advanced, stop and inspect/rebase safely; do not force-push or overwrite it.

- [ ] **Step 3: Push once**

```bash
git push origin HEAD:main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

- [ ] **Step 4: Deploy the tested commit once**

First confirm no local deploy is already running:

```bash
if pgrep -af '[v]ercel.*(deploy|build)'
then
  echo "A Vercel deploy/build is already active; inspect and wait instead of launching another." >&2
  exit 1
fi
```

Read the project’s actual Git-link state and query deployments by the exact pushed SHA:

```bash
release_sha="$(git rev-parse HEAD)"
project_id="$(jq -r '.projectId' .vercel/project.json)"
team_id="$(jq -r '.orgId' .vercel/project.json)"
project_json="$(
  vercel api \
    "/v9/projects/$project_id?teamId=$team_id" \
    --raw 2>/dev/null
)"
git_link_state="$(
  printf '%s' "$project_json" |
  jq -r 'if (.link == null and .gitRepository == null) then "none" else "connected" end'
)"
deployment_json="$(
  vercel api \
    "/v7/deployments?projectId=$project_id&sha=$release_sha&target=production&teamId=$team_id&limit=20" \
    --raw 2>/dev/null
)"
deployment_count="$(printf '%s' "$deployment_json" | jq '.deployments | length')"
```

Decision is exact and has no timing fallback:

- If `deployment_count > 0`, select the one whose metadata SHA equals `release_sha`, wait for it, and never launch another.
- If `git_link_state == "connected"` and `deployment_count == 0`, monitor the same SHA-filtered Vercel query until Git creates the deployment or reports a terminal integration failure. Never fall back to CLI for a linked project.
- If `git_link_state == "none"` and `deployment_count == 0`, an automatic Git deployment cannot appear. Reassert the clean committed tree and deploy once:

```bash
test "$git_link_state" = "none"
test "$deployment_count" = "0"
test -z "$(git status --porcelain)"
vercel deploy --prod --yes
```

After either path, rerun the exact SHA-filtered `/v7/deployments` query and require one production deployment with `readyState == "READY"`. Record its deployment ID, source commit SHA, and production URL; never launch a second deployment while one for the same commit is pending or building.

- [ ] **Step 5: Verify the live asset is byte-identical**

```bash
candidate_sha="$(
  sha256sum /home/alex/Downloads/SANIC-Meshy-v3/SANIC-meshy6-v3-run.glb |
  cut -d' ' -f1
)"
live_sha="$(curl -fsSL https://www.sanic.fun/models/sanic-runner.glb | sha256sum | cut -d' ' -f1)"
test "$candidate_sha" = "$live_sha"
```

- [ ] **Step 6: Run focused live desktop/mobile checks**

```bash
BASE_URL=https://www.sanic.fun \
npx playwright test tests/e2e/game.spec.ts \
  --project=desktop-chromium \
  --grep "crossfades the v3 sprint into jump without a pose snap|starts, responds to controls"
BASE_URL=https://www.sanic.fun \
npx playwright test tests/e2e/game.spec.ts \
  --project=mobile-chromium \
  --grep "crossfades the v3 sprint into jump without a pose snap|starts, responds to controls"
```

Also confirm manually from the chase camera that the new run, existing curl/spin jump, chiptune, fixed scenery species, copy-contract button, and X link remain functional.

- [ ] **Step 7: Handle failure without losing the rollback**

If deployment or live verification fails:

1. leave the v2 files in Downloads untouched;
2. restore `public/models/sanic-runner.glb` from the known v2 GLB in a new corrective commit;
3. rerun build and focused E2E;
4. deploy that tested rollback commit;
5. report the failed v3 gate and keep further v3 work local.

- [ ] **Step 8: Close v3 and begin the separate game-expansion design**

After live verification, record:

- final Git commit;
- Vercel deployment ID/URL;
- candidate/live GLB SHA-256;
- v3 source and GLB validator summaries;
- exact Jump preservation result;
- unit/E2E counts;
- Meshy credits actually consumed (`0`, `5`, or `8`) without task IDs.

Then start a new brainstorming/design cycle for `docs/superpowers/specs/2026-07-17-sanic-zone-progression-design.md`, covering biome progression, obstacle/ring pattern language, difficulty ramp, missions/combos, replay hooks, scenery stability, performance budgets, and mobile controls. Do not mix that world/gameplay expansion into the v3 animation commits or deployment.
