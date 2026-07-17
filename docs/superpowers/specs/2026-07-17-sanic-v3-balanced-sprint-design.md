# SANIC v3 Balanced Sprint Design

## Objective

Replace the remaining jog-like qualities in SANIC's current `Run` action with a
balanced sprint that combines believable human biomechanics with exaggerated
speed-game readability. The current production model and deployment remain the
rollback baseline until the v3 candidate passes Blender, browser, desktop, and
mobile review.

This phase changes only the `Run` action and its validation/preview pipeline.
The approved `Jump` action, character mesh, materials, face, gloves, shoes,
spin-ball presentation, game physics, and world speed remain unchanged.

## Current findings

The v2 cadence and broad poses are sound, but three motion defects remain
visible from the chase camera:

1. The root rises 44.5 mm in one frame at takeoff and drops 39.0 mm in one
   frame at landing. This reads as a vertical pop rather than continuous
   sprint compression.
2. The support shoe stays nearly flat through stance. Its pitch changes by
   only about 2.4 degrees, so the planted foot appears to skate instead of
   progressing through strike, midstance, and toe-off.
3. Both elbows stay at exactly 90 degrees while shoulder poses hold and then
   change abruptly. The large rear quill silhouette hides much of this motion,
   making the gloves appear frozen from the gameplay camera.

The v3 work is successful only if it corrects those defects without damaging
the model or weakening the existing jump.

## Selected approach

Use a Blender-first production pass with one tightly bounded Meshy reference
experiment.

Blender remains authoritative because the existing armature, skin weights,
action names, runtime integration, and jump preservation checks are already
proven. The run will be rebuilt on the current skeleton with continuous root
motion, an articulated strike-to-toe-off foot roll, variable elbow flexion,
stronger contralateral arm drive, and a clearer forward body axis.

Meshy may supply a motion reference or retargeting source, but never a direct
production replacement. This limits credit use and prevents a new automatic
rig from changing the approved mesh, face, gloves, shoes, or jump.

## Alternatives considered

### Blender-only refinement

This is the lowest-risk and lowest-cost option. It provides complete control
over foot contact and gameplay-camera readability, but all timing must be
authored and tuned manually.

### Meshy-assisted reference and retargeting

Meshy can auto-rig the corrected humanoid and return a basic running animation.
If that rig preserves the silhouette, a dedicated in-place forward sprint can
be requested and retargeted onto the existing armature. This may provide more
natural secondary motion, but retarget cleanup is still required.

### Full Meshy rig replacement

This is rejected. Replacing the current skeleton and skinning could damage the
custom character details, invalidate the jump, change action contracts, and
introduce a much larger regression surface than the run animation warrants.

## Sprint motion contract

The v3 action uses frames 1 through 17 at 24 fps: frames 1 through 16 form the
period and frame 17 exactly duplicates frame 1 for the seam. Opening cadence
remains approximately 180 steps per minute, and the runtime speed multiplier
remains capped at the existing 1.55 value. Game physics owns forward
translation; the animation must have no accumulated root drift.

All motion measurements use rig-world coordinates after dependency-graph
evaluation: `FORWARD = (0, -1, 0)`, `LATERAL = (1, 0, 0)`, and
`UP = (0, 0, 1)`. Validators sample every integer frame from 1 through 17.

### Root and torso

- Body-axis lean is the sagittal-plane angle between `hips.head` and
  `chest.tail` relative to `UP`; it stays between 11 and 14 degrees.
- The root-bone head is the center-of-mass proxy. Its total vertical travel is
  35 to 50 mm.
- Maximum root-height change between adjacent 24 fps frames: 18 mm.
- Maximum absolute second finite difference of root height: 20 mm per frame
  squared.
- Root X and Y positions stay within 1 mm of their frame-1 values.
- Takeoff and landing arcs must remain continuous with no single-frame pop.

### Legs and feet

- Every knee retains at least 15 degrees of flexion.
- Passing recovery knee remains at least 120 mm above the support knee.
- Stance foot progresses through visible forefoot/midfoot strike, controlled
  full-sole loading, and heel-lift/toe-off rather than remaining a flat paddle.
- Total stance-foot pitch progression: at least 22 degrees.
- Strike forefoot clearance: at most 6 mm while heel clearance remains between
  15 and 45 mm.
- Midstance sole clearance: at most 8 mm.
- Toe-off toe clearance: at most 8 mm while heel height reaches at least
  60 mm.
- V2 maximum evaluated fore-aft toe separation is 0.50434 m. V3 reaches at
  least 0.68086 m, a 35 percent increase, without knee hyperextension or mesh
  tearing.
- Both flight phases keep every evaluated shoe-region vertex at least 25 mm
  above the road.

### Arms and upper body

- Elbow angles stay between 75 and 105 degrees and vary by at least 18 degrees
  over the cycle.
- Shoulder motion changes continuously; no identical shoulder pose may persist
  for more than one frame.
- Adjacent shoulder-angle changes stay at or below 20 degrees.
- Arms remain contralateral to the lead leg and primarily sagittal.
- Rear-view glove-height separation, measured between the two hand-bone heads
  on `UP`, reaches at least 120 mm.
- Each hand-bone head's root-relative `LATERAL` range stays at or below 50 mm.
- Pelvis and chest counter-rotation support the stride without side-to-side
  arm flailing.

## Meshy reference experiment

The experiment has a hard maximum of one auto-rig task and one custom animation
task:

1. Preflight the corrected source as a textured humanoid GLB below 300,000
   faces, approximately 1.7 meters tall, and facing glTF `+Z`. Submit it by
   Data URI or an unlisted temporary public URL to one Meshy auto-rig task.
2. Inspect the basic running output when the rig task provides one. The
   auto-rig task is expected to consume 5 credits.
3. Stop if the face, quills, gloves, shoes, topology, or limb deformation is
   damaged.
4. Only when the rig passes inspection, request animation action `644`,
   `Lean_Forward_Sprint_inplace`, with
   `post_process: { operation_type: "change_fps", fps: 24 }`. This task is
   expected to consume 3 additional credits.
5. Import the processed 24-fps FBX into an isolated Blender file and retarget
   only useful bone rotations onto the existing SANIC armature.
6. Discard all Meshy mesh, material, skin, root translation, and jump data.

The maximum Meshy spend for this pass is 8 credits. A failed or unsuitable
result does not authorize retries or additional animation variants.

## Preview and validation flow

The build produces front, side, and rear gameplay-camera checkpoint renders.
The rear camera is placed on the character's `+Y` side, aimed toward the torso
along `FORWARD`, with framing matched to the in-game chase view. This view is
mandatory because it reveals glove occlusion, foot skating, and vertical
popping that front and side renders can hide.

Validation runs against both the source `.blend` and re-imported production
GLB. It measures:

- root position, first finite difference, and second finite difference;
- evaluated shoe-region contact heights and pitch progression;
- knee height, flexion, stride, and flight clearance;
- evaluated torso lean;
- elbow variation, shoulder continuity, wrist travel, and lateral drift;
- exact first/last-frame loop continuity; and
- absence of horizontal root drift.

The existing jump comparison remains a release gate: all 10,560 sampled values
must match the v1 baseline with maximum delta `0.0`. A browser test also
exercises the existing 0.035-second Run-to-Jump crossfade and rejects visible
root, shoe, or torso snapping at the transition boundary.

## Browser acceptance

- The production GLB loads with `Run`, `Jump`, `Idle`, and `Crash` actions.
- The model remains the selected character asset without silent fallback.
- Run cadence scales correctly at opening, mid-game, and maximum speeds.
- Desktop and mobile gameplay recordings show alternating foot strike,
  midstance, toe-off, and flight from the chase camera.
- No shoe clipping, glove/quill intersection, new console error, WebGL context
  failure, or material regression is introduced.
- Existing unit, build, and end-to-end suites pass before deployment.

## Rollout and failure handling

- Build v3 under a new local basename and Downloads directory.
- Keep the current v2 GLB and Blender source byte-for-byte unchanged. The
  rollback hashes are:
  - v2 GLB:
    `3567547081fb191a73562b306bea3dba299e717d89152ae42dd03e5a69a03333`
  - v2 Blend:
    `80960279c1e08a3c130bca92027a53bc9958bd9010cb891a777d2da2ee0236d7`
- Do not replace the repository asset until the candidate passes independent
  visual review and all source/GLB validators.
- Push and deploy only after verifying that the remote main branch has not
  advanced unexpectedly.
- Confirm the live GLB hash matches the approved candidate and repeat focused
  desktop/mobile gameplay checks on the production domain.
- If any v3 gate fails, leave v2 live and continue locally.

## Credential and public-repository handling

- The Meshy credential stays in the environment or operating-system keyring.
- Task responses, signed asset URLs, service payloads, generated masters, and
  temporary upload locations remain untracked.
- Public source contains only reproducible scripts, validators, and the
  approved optimized production GLB.
- Hidden-tree, staged-diff, commit-message, and full-history safety scans run
  before any push.

## Non-goals

- No change to jump height, timing, curl, or spin-ball behavior.
- No regeneration or replacement of the SANIC character mesh.
- No new facial, shoe, glove, texture, or environment modeling.
- No additional Meshy task beyond the 8-credit cap.
- No zone progression, reward economy, difficulty system, or world expansion
  in this phase. Those form the linked
  `2026-07-17-sanic-zone-progression-design.md` design cycle, which must be
  approved before the user's combined animation-and-gameplay request is
  considered complete.
