# Meshy SANIC Character Generation Design

## Objective

Generate one production-quality, rig-ready SANIC character from the approved
front and back references. This phase ends with inspected GLB and FBX files; it
does not replace the live game model or begin animation work.

The character must preserve the approved humanlike proportions, sleepy parody
face, swept blue quills, small round tail, single left-ear gold hoop, white
five-finger gloves, compact red shoes, and blue/tan color layout. The result
must be suitable for a standard humanoid skeleton and responsive on desktop and
mobile once optimized for the game.

## Inputs and handling

- Use the two approved reference images supplied for this production pass.
- Keep the source images and generated masters outside the public repository
  until visual and rights review is complete.
- Treat the front and back images as one identity, not as separate concepts.
- Enforce a T-pose during reconstruction even though the references show the
  arms lowered.
- Add the forehead phrase later as a controlled Blender decal. Image-generated
  lettering is not an acceptance criterion.
- Keep service credentials in the operating-system keyring. Never write them
  into the repository, task metadata, prompts, or generated filenames.

## Selected approach

Use one direct Meshy 6 multi-image generation. This is the best first pass
because it preserves the approved artwork without spending extra credits on an
intermediate image transformation that may alter the face or proportions.

The alternatives are deliberately deferred:

1. A generated T-pose turnaround before 3D reconstruction would improve pose
   separation but adds cost and identity drift.
2. Multiple simultaneous 3D variants would provide an A/B comparison but spend
   credits before the first result reveals what actually needs correction.

## Generation contract

The first paid call uses the following fixed parameters:

| Parameter | Value |
| --- | --- |
| Model | `meshy-6` |
| Model type | `standard` |
| Pose | `t-pose` |
| Topology | `quad` |
| Target face count | `60000` |
| Remesh | enabled |
| Preserve pre-remesh master | enabled |
| Textures | enabled |
| PBR maps | enabled |
| Base-color resolution | 4K |
| Image enhancement | enabled |
| Lighting removal | enabled |
| Auto size | enabled |
| Origin | bottom center |
| Formats | GLB and FBX |
| Inspection renders | alpha thumbnail plus four cardinal views |
| Response | structured JSON |

Expected generation cost: 30 Meshy API credits: 20 for Meshy 6 geometry and
10 for texturing. Status polling and balance checks must not create additional
generation tasks.

Texture guidance should preserve the reference artwork: deep royal-blue body,
warm tan muzzle and circular belly patch, sleepy humanlike eyes and eyebrows,
compact black nose, understated mouth, clean white gloves and cuffs, compact red
athletic shoes with gray soles and small gold buckles, layered swept-back blue
quills, one gold hoop on the character's left ear, and a small centered blue
tail. It must not introduce logos, extra jewelry, extra limbs, or background
geometry.

## Output flow

1. Submit one Meshy 6 multi-image task using the approved local references.
2. Record only the task identifier and non-secret generation metadata.
3. Poll until the task succeeds, fails, or reaches a documented timeout.
4. Download exactly one textured GLB and one textured FBX into a local handoff
   directory outside the repository.
5. Preserve the pre-remeshed master when Meshy makes it available.
6. Inspect the geometry and textures before any rigging or animation call.

No result is promoted merely because the API task reports success.

## Acceptance checks

### Character identity

- Front and rear proportions agree with the references.
- The face remains humanlike and intentionally sleepy rather than becoming a
  conventional mascot face.
- Both hands have five recognizable fingers and do not fuse into the thighs.
- Shoes remain compact, symmetrical, and clearly separated from the sock cuffs.
- Quills read as intentional swept layers without hiding or joining the arms.
- The gold hoop remains on the character's left side.
- The small tail is centered and does not create an extra limb.

### Rigging readiness

- Character is in a symmetrical T-pose with visible shoulder, elbow, wrist,
  hip, knee, and ankle landmarks.
- Mesh contains no accidental duplicate body parts or major self-intersections.
- Face count is at or below the 300,000-face rigging limit and near the requested
  60,000-face production target.
- Character scale is approximately 1.7 meters with the origin at ground level.
- Materials and embedded textures survive clean Blender imports from both GLB
  and FBX.

### Web readiness

- GLB loads without parser errors.
- Skinning-critical silhouettes remain clean when triangulated.
- Materials use a bounded texture set suitable for later compression.
- The model can be reduced further without losing the face, gloves, shoes, or
  quill silhouette if mobile profiling requires it.

## Failure handling

- If the task fails at the service level, inspect the returned error and retry
  only when the same parameters are safe; do not create blind duplicate tasks.
- If identity is correct but color or surface detail is wrong, prefer a texture
  correction over a full regeneration.
- If hands, arms, or quills are fused, stop and prepare a consistent T-pose
  multi-view reference set before requesting another 3D generation.
- If only small shoe, glove, or facial details are weak, prefer corrective
  Blender work over another paid generation.
- Any second paid generation requires a new visual review and explicit approval.

## Downstream rigging boundary

After the model passes inspection, prepare it for the approved Mixamo workflow:
normalize transforms, remove non-character scene objects, verify connected
humanoid geometry, and export the clean static character as FBX. Mixamo will be
the canonical shipped skeleton and primary motion source. Existing downloaded
character packages remain local motion references and are never copied into the
public repository or production model.

Game physics will own forward motion and jump height. Animation clips will be
baked in place and exported later as `Idle`, `Run`, `Jump`, and `Crash` actions.
The jump uses a hybrid curl-and-spin treatment: a short rigged takeoff/tuck,
a crossfade to a dedicated spinning ball model during flight, then an uncurl
and landing pose during descent. This preserves a clean spherical silhouette
without forcing the humanoid mesh into destructive deformation.

## Non-goals for this phase

- No live-site model replacement or deployment.
- No automatic rigging or custom animation task.
- No use of downloaded character meshes, textures, or source skeletons.
- No additional paid variant without reviewing the first result.
- No public commit of source references or raw service downloads.
