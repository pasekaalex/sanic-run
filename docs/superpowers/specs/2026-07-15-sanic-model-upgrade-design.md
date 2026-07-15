# SANIC Player Model Upgrade Design

## Goal

Replace the current primitive-built player silhouette with a smooth, Blender-native character that matches the heroic realism of the launch artwork while remaining readable, animated, and performant in the Three.js runner.

The upgraded model must retain SANIC's sleepy meme face, cobalt body, white gloves, red shoes, backward quills, and exaggerated muscular proportions. It must not resemble a stack of spheres, capsules, or rounded boxes during gameplay.

## Chosen approach

Use Blender Studio's official CC0 realistic male Human Base Mesh as the deformation-ready body foundation. Preserve its continuous quad edge flow, UVs, and multiresolution structure while reshaping it into SANIC's exaggerated heroic proportions. Build the custom head, muzzle, quills, gloves, and footwear in the project scene, then produce a controlled game export from the same source. This replaces primitive-generated anatomy with a proven character topology while retaining an original final silhouette.

The referenced Pepsiman download is visual workflow inspiration only. Its noncommercial license and third-party character identity make it ineligible for import, modification, redistribution, or inclusion in this project.

The existing character armature and action names remain the animation contract. The visible body and footwear may be rebuilt, but the exported GLB must continue to provide `Idle`, `Run`, `Jump`, and `Crash` actions without frontend changes.

## Character geometry

- Use the CC0 realistic male base from neck to ankles/wrists so the torso, shoulders, arms, hips, and legs retain coherent anatomical edge flow.
- Reshape broad proportions at low multiresolution levels before adding muscle definition at higher levels; do not create anatomy by intersecting spheres, capsules, or lofted limb pieces.
- Remove visible ball joints, capsule seams, flat limb ends, and abrupt changes in cross-section.
- Use broad heroic anatomy rather than fine human realism: strong V-taper, large shoulders and arms, defined chest and abdomen, powerful thighs, and narrower ankles.
- Keep arms athletic and continuous rather than bulbous: restrained deltoid transitions, subtle biceps/triceps contour, a narrow readable elbow plane, long forearm taper, and smaller wrists.
- Refine the head, muzzle, ears, eyelids, nose, lips, and quill roots so their transitions read as one designed character from front, side, and rear gameplay angles.
- Keep the sleepy closed-eye expression and forehead phrase as the defining meme cues.
- Shape the gloves with a rounded palm, separated fingers, softened knuckles, cuff compression, and shallow fold forms.

## Shoe construction

Each shoe will be a dedicated curved footwear assembly rather than a rounded box. It includes:

- an asymmetrical foot last with a broad rounded toe box;
- visible toe spring and a smooth tapered instep;
- a formed heel counter and padded collar;
- a fitted white strap that follows the upper instead of intersecting it;
- a separate white midsole with a clean sidewall;
- a dark rubber outsole with a beveled edge and shallow tread relief;
- smooth transitions at the ankle and sock cuff.

The red upper, white strap and midsole, and dark outsole remain readable at the normal chase-camera distance. The shoes must also hold up in close promotional screenshots.

## Rigging and animation

Use a cinematic-athletic animation style: believable sprint mechanics and weight transfer, amplified with strong poses, fast anticipation, broad arcs, and readable impact. Preserve the current deform-bone and action names so the runtime animation loader remains unchanged, then extend the Blender source rig with clavicle, upper-spine, limb-twist, toe, and finger controls where they improve silhouette or deformation.

The source scene may use IK targets, pole controls, foot roll, hand controls, and corrective constraints. The web export must bake their result onto the deform skeleton so Three.js receives deterministic keyframes with no dependency on Blender-only controls.

- Rebind the rebuilt body with smooth weights, concentrating review on shoulders, elbows, hips, knees, ankles, wrists, glove cuffs, and quill/head motion.
- Preserve volume through the shoulders and hips while twist helpers prevent forearm and thigh collapse.
- Keep shoes sufficiently rigid to read as footwear while allowing clean ankle and toe-roll motion.
- Preserve the established character scale, origin, forward direction, ground contact, and chase-camera framing.
- Check all four actions for mesh collapse, foot sliding, glove intersections, shoe deformation, knee popping, arm snapping, and quill clipping.

### Baked action direction

- `Idle`: two-second loop with grounded weight, broad breathing through the chest and abdomen, subtle shoulder roll, glove flex, head drift, and a small quill follow-through. The first and final poses must match exactly.
- `Run`: powerful cyclic sprint with a deep but stable forward lean, forceful arm drive, shoulder/hip counter-rotation, clear contact and passing poses, toe-off, heel recovery, controlled vertical compression, and planted contacts without visible sliding. Runtime speed scaling remains supported.
- `Jump`: a non-looping action with a fast anticipatory crouch, arm load, explosive extension, airborne tuck, readable hang pose, leg reach, and heavy landing compression. Its timing must follow the existing gameplay jump arc.
- `Crash`: a non-looping, front-loaded impact with a sharp brace, asymmetric torso recoil, limb follow-through, head/quill lag, and a heavy collapsed finish. The defining impact pose must occur during the first 0.3 seconds so it remains visible before the results treatment settles.

All four actions will be sampled and baked at 30 frames per second. Exported clips must contain complete transform curves for their deform bones, stable first/last loop boundaries where applicable, and no live IK or unsupported constraint dependencies.

## Materials and finish

Use restrained physically based materials: saturated cobalt skin with moderate roughness, soft off-white gloves and sock cuffs, glossy red shoe uppers, clean white midsoles and straps, and dark rubber outsoles. Smooth normals and controlled bevels provide the finish; noisy surface textures are out of scope.

Lighting and environment remain unchanged so before-and-after comparisons measure the player asset rather than a scene redesign.

## Asset provenance

The only external geometry permitted for this character pass is `GEO-body_male_realistic` from Blender Studio's Human Base Meshes bundle v1.4.1. Preserve a trimmed project-local source plus a provenance record containing the official Blender demo-page URL and CC0 statement, direct Blender Foundation archive URL, bundle version, SHA-256 checksum, original asset name, and embedded asset author/description metadata. No attribution is legally required, but the record makes the public build reproducible and auditable.

Do not import Pepsiman, Sonic, commercial marketplace characters, noncommercial models, or generated third-party character meshes. Existing SANIC artwork remains a visual target rather than mesh source data.

## Blender workflow and export

Scene construction, CC0 base import, multiresolution shaping, inspection, posing, and corrective edits will be performed through the connected Blender tooling and the reproducible `blender/scripts/build_sanic.py` pipeline. Viewport captures will cover front, rear, side, three-quarter, contact, airborne, and impact poses. The scripted build must reproduce the final geometry, rig, weights, materials, actions, and export from a clean Blender session using the project-local trimmed base source.

The Blender source may use approximately 350,000–600,000 triangles. The final `public/models/sanic-runner.glb` should target 100,000–140,000 triangles, remain under 5 MB, contain no missing external textures, and retain the required four animation clips. The existing asset URL and frontend loader contract do not change.

## Validation

1. Run the Blender asset validator against the rebuilt source and export.
2. Confirm triangle count, material assignments, skeleton, animation names, 30 FPS baked curves, bounds, scale, and embedded resources.
3. Inspect static front, rear, side, and three-quarter viewport captures.
4. Inspect `Idle`, `Run`, `Jump`, and `Crash` deformation in Blender at their defining poses and through full playback.
5. Run the local unit suite and production build.
6. Exercise gameplay in desktop and mobile browser viewports, including lane changes and jumping.
7. Compare chase-camera screenshots against the current production model, focusing on anatomical continuity and shoe readability.
8. Redeploy once, then repeat the live browser smoke test before publishing the repository.

## Acceptance criteria

- The player reads as a continuous sculpted character rather than assembled primitives.
- No rectangular shoe upper or slab-like sole is visible from gameplay or promotional angles.
- The face and overall silhouette are recognizably SANIC and retain the approved meme expression.
- All four existing animations play with cinematic-athletic timing, stable planted contacts, and no visible rigging failures.
- Desktop and mobile maintain their existing gameplay behavior and responsive layout.
- The final GLB stays within the stated geometry and file-size budgets.

## Non-goals

This upgrade does not change gameplay rules, controls, environment geometry, score sharing, UI, camera behavior, contract links, or token copy. It does not add noncommercial, attribution-restricted, proprietary, or third-party character meshes; the verified Blender Studio CC0 human base is the sole external geometry exception.
