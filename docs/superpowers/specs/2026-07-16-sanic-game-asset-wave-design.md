# SANIC Game Asset Wave Design

## Objective

Upgrade the runner with a coherent first production asset wave: the accepted
SANIC character, a recognizable gold-ring collectible, several readable
obstacles, realistic sprinting, and a curl-and-spin jump. The result must remain
responsive on desktop and mobile and preserve the game's original parody style.

## Work order

The work is split by dependency:

1. Generate and inspect the static T-pose character.
2. Build lightweight collectibles and obstacles while the character is being
   prepared for rigging.
3. Fit the canonical humanoid skeleton and clean skin weights.
4. Bake the run, takeoff, landing, and crash poses.
5. Integrate the dedicated spin-ball model between takeoff and landing.
6. Profile and deploy only after the complete asset wave passes desktop and
   mobile gameplay checks.

## Gameplay models

Simple gameplay props use deterministic Blender geometry rather than paid 3D
generation. Their silhouettes, colliders, and polygon budgets matter more than
sculptural complexity.

### Gold ring collectible

- Rounded torus with a thick, readable silhouette at mobile size.
- Gold base color, restrained metallic response, and warm emissive rim.
- Rotation and collection burst are driven by the game, not skeletal clips.
- One shared mesh and material instance across all visible rings.
- Target budget: at most 2,000 triangles and one compact material.

### Obstacle starter kit

- Low wooden hurdle: requires a normal jump.
- Fallen forest log: wider organic jump obstacle.
- Red spike barricade: visually dangerous, with a forgiving gameplay collider.
- Mossy boulder: lane-change obstacle with a broad silhouette.
- Original crypto-meme sign: a lightweight roadside prop using editable game
  copy rather than a baked portrait or third-party artwork.

Each obstacle receives a simple explicit collider independent of the rendered
mesh. Repeated obstacles share geometry and materials. Individual obstacle
budgets should remain below 8,000 triangles, with the hurdle and sign well below
that ceiling.

## Character animation

### Sprint

- In-place animation; game code owns forward speed.
- Arms swing primarily forward and backward in the sagittal plane, not sideways.
- Elbows remain bent and hands clear the hips.
- Hips rotate subtly while shoulders counter-rotate.
- Knees flex visibly, feet recover underneath the body, and planted feet do not
  slide during their contact phase.
- Export at 30 FPS as a seamless `Run` action.

### Curl-and-spin jump

The jump is a hybrid animation and model transition:

1. Anticipation crouch and takeoff over approximately four to six frames.
2. Arms and legs tuck toward the torso as the character leaves the ground.
3. Crossfade to a dedicated compact blue spin-ball model before the silhouette
   becomes visibly distorted.
4. Rotate the ball according to horizontal running speed while gameplay physics
   controls vertical position, apex, and fall speed.
5. Crossfade back to the rigged character during descent.
6. Uncurl into a short knee-bent landing pose and return to `Run`.

The spin ball should read as the same character through swept blue quill forms
and controlled flashes of red shoes and white gloves. It is a lightweight game
model, not a second full character generation.

### Collision and state behavior

- Jumping suppresses the standing character collider only when the ball state is
  active; it does not change the physics trajectory.
- Obstacles use authored clearance heights so the visual and collider agree.
- Landing transitions are time-warped to the actual physics landing event.
- A failed collision exits the spin state cleanly before `Crash` begins.

## Asset interface

Character actions keep the stable names `Idle`, `Run`, `Jump`, and `Crash`.
The spin ball is loaded once and toggled by the character presentation layer.
Gameplay code references obstacles by semantic kind rather than asset filename.
This keeps model replacements from changing collision rules or scoring.

## Acceptance checks

- New character identity matches the approved references from front, side, and
  gameplay-camera views.
- Run cycle has natural arm direction, knee bend, foot contact, and no root drift.
- Jump reaches the existing higher/faster gameplay arc and visibly curls into a
  smooth spinning ball before uncurling for landing.
- Ring remains recognizable and bright on a narrow mobile viewport.
- Every obstacle reads early enough for a player to react at maximum game speed.
- Render meshes and colliders remain aligned through repeated spawning.
- Repeated props do not change shape or material unexpectedly while running.
- Desktop and representative mobile profiles maintain the existing frame-rate
  target without increasing draw calls unnecessarily.

## Scope controls

- No copied franchise models, textures, logos, or animation files enter the
  repository.
- Downloaded character packages remain private motion references only.
- No paid prop generations are needed for this starter wave.
- The live model is replaced only after the new character and animation state
  machine pass local browser gameplay testing.
