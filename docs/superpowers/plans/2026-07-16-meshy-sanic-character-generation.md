# Meshy SANIC Character Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and validate one textured, rig-ready Meshy 6 SANIC character from the approved front and rear references without creating duplicate paid tasks.

**Architecture:** Submit one 30-credit multi-image task through the authenticated Meshy MCP server, monitor the immutable task identifier to completion, and download only GLB and FBX. Keep all generated artifacts outside the public repository, then audit geometry, materials, scale, pose, and appearance before any rigging or live-site integration.

**Tech Stack:** Meshy MCP Server 0.4.0, Meshy 6 multi-image API, Blender 5.1, GLB/FBX, shell-based MCP JSON-RPC validation.

## Global Constraints

- Use exactly the two approved reference images from the working session.
- Use `meshy-6`, `standard`, `t-pose`, quad topology, and a 60,000-face target.
- Enable remesh, pre-remesh preservation, 4K textures, PBR, image enhancement, lighting removal, auto sizing, and a bottom origin.
- Generate only GLB and FBX plus alpha and cardinal-view inspection thumbnails.
- The authorized maximum for the first generation is 30 Meshy API credits.
- Never write the service credential into files, logs, prompts, filenames, or the repository.
- Do not submit a second paid generation without a new visual review.
- Do not rig, animate, deploy, or commit generated assets during this plan.

---

### Task 1: Preflight references and account state

**Files:**
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/references/front.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/references/back.png`
- Create locally: `/home/alex/Downloads/SANIC-Meshy-v1/`

**Interfaces:**
- Consumes: the approved front and rear PNG references and the keyring-backed Meshy MCP configuration.
- Produces: verified input paths, image dimensions and hashes, a clean output directory, and a confirmed balance of at least 30 credits.

- [ ] **Step 1: Stage both approved references outside the repository**

Run:

```bash
mkdir -p /home/alex/Downloads/SANIC-Meshy-v1/references
install -m 0600 /tmp/*-udBiu5.png \
  /home/alex/Downloads/SANIC-Meshy-v1/references/front.png
install -m 0600 /tmp/*-porSUJ.png \
  /home/alex/Downloads/SANIC-Meshy-v1/references/back.png
```

Expected: stable private copies exist in the local handoff directory.

- [ ] **Step 2: Verify both local references**

Run:

```bash
file \
  /home/alex/Downloads/SANIC-Meshy-v1/references/front.png \
  /home/alex/Downloads/SANIC-Meshy-v1/references/back.png
identify -format '%f %m %wx%h\n' \
  /home/alex/Downloads/SANIC-Meshy-v1/references/front.png \
  /home/alex/Downloads/SANIC-Meshy-v1/references/back.png
sha256sum \
  /home/alex/Downloads/SANIC-Meshy-v1/references/front.png \
  /home/alex/Downloads/SANIC-Meshy-v1/references/back.png
```

Expected: both inputs are readable PNG files at 1280×853 with distinct hashes.

- [ ] **Step 3: Create the local handoff directory**

Run:

```bash
mkdir -p /home/alex/Downloads/SANIC-Meshy-v1
```

Expected: the directory exists outside the Git working tree.

- [ ] **Step 4: Confirm authentication and balance**

Call `meshy_check_balance` through the configured MCP server.

Expected: authentication succeeds and the reported balance is at least 30 credits.

- [ ] **Step 5: Check recent task history for an identical in-progress task**

Call `meshy_list_tasks` and compare recent multi-image tasks with the two input hashes and selected parameters.

Expected: no identical pending or in-progress task exists. If one exists, reuse its identifier instead of submitting another task.

### Task 2: Submit the single Meshy 6 task

**Files:**
- Read: the two approved PNG files.
- Write remotely: one Meshy multi-image task.

**Interfaces:**
- Consumes: verified reference paths and the generation contract.
- Produces: one immutable multi-image task identifier stored in the execution
  variable `MESHY_TASK_ID`.

- [ ] **Step 1: Submit the generation call**

Call `meshy_multi_image_to_3d` with this exact argument object:

```json
{
  "file_paths": [
    "/home/alex/Downloads/SANIC-Meshy-v1/references/front.png",
    "/home/alex/Downloads/SANIC-Meshy-v1/references/back.png"
  ],
  "ai_model": "meshy-6",
  "model_type": "standard",
  "pose_mode": "t-pose",
  "enable_pbr": true,
  "topology": "quad",
  "target_polycount": 60000,
  "should_remesh": true,
  "should_texture": true,
  "texture_prompt": "Preserve the approved SANIC parody character: deep royal-blue humanlike body, warm tan muzzle and circular belly patch, sleepy humanlike eyes and eyebrows, compact black nose, understated mouth, clean white five-finger gloves and cuffs, compact red athletic shoes with gray soles and small gold buckles, layered swept-back blue quills, one gold hoop on the character's left ear, and a small centered blue tail. No logos, background geometry, extra jewelry, extra limbs, or added props.",
  "hd_texture": true,
  "image_enhancement": true,
  "remove_lighting": true,
  "save_pre_remeshed_model": true,
  "target_formats": ["glb", "fbx"],
  "alpha_thumbnail": true,
  "multi_view_thumbnails": true,
  "auto_size": true,
  "origin_at": "bottom",
  "response_format": "json"
}
```

Expected: one response containing a non-empty task identifier with `PENDING` or `IN_PROGRESS` status.

- [ ] **Step 2: Record the task identifier in the execution notes**

Assign the returned UUID to the execution variable `MESHY_TASK_ID` and record it
in the active task log, not in the repository or filename.

Expected: every later status and download call uses the same identifier.

### Task 3: Monitor without duplicate spending

**Files:**
- No repository files.

**Interfaces:**
- Consumes: the multi-image task identifier.
- Produces: a terminal task result with consumed credits, model URLs, and inspection thumbnail URLs.

- [ ] **Step 1: Poll the existing task**

Call `meshy_get_task_status` with:

```json
{
  "task_id": "${MESHY_TASK_ID}",
  "task_type": "multi-image-to-3d",
  "response_format": "json"
}
```

Poll no faster than once every ten seconds.

Expected: status progresses from `PENDING` or `IN_PROGRESS` to `SUCCEEDED`. A reported failure stops execution without a replacement generation.

- [ ] **Step 2: Verify charged credits and required outputs**

Inspect the successful task response.

Expected: `consumed_credits` is at most 30, GLB and FBX URLs are present, and alpha/cardinal thumbnails are present. Stop if the charge or outputs differ materially.

### Task 4: Download the two handoff formats

**Files:**
- Create: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.glb`
- Create: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.fbx`

**Interfaces:**
- Consumes: the successful multi-image task identifier.
- Produces: one textured GLB and one textured FBX with stable local names.

- [ ] **Step 1: Download GLB**

Call `meshy_download_model` with:

```json
{
  "task_id": "${MESHY_TASK_ID}",
  "task_type": "multi-image-to-3d",
  "format": "glb",
  "include_textures": true,
  "save_to": "/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.glb"
}
```

Expected: a non-empty GLB is saved at the exact path.

- [ ] **Step 2: Download FBX**

Call `meshy_download_model` with the same task identifier and:

```json
{
  "task_id": "${MESHY_TASK_ID}",
  "task_type": "multi-image-to-3d",
  "format": "fbx",
  "include_textures": true,
  "save_to": "/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.fbx"
}
```

Expected: a non-empty FBX is saved at the exact path.

- [ ] **Step 3: Hash and identify both files**

Run:

```bash
file /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.{glb,fbx}
sha256sum /home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.{glb,fbx}
```

Expected: both formats are recognized, non-empty, and have recorded hashes.

### Task 5: Audit static model quality

**Files:**
- Read: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.glb`
- Read: `/home/alex/Downloads/SANIC-Meshy-v1/SANIC-meshy6-v1.fbx`

**Interfaces:**
- Consumes: downloaded assets and task thumbnails.
- Produces: geometry/material statistics and an accept-or-correct recommendation.

- [ ] **Step 1: Import the GLB into an empty Blender process**

Use Blender background mode to report object types, mesh/triangle counts,
materials, images, bounds, transforms, armatures, actions, and non-manifold edge
counts without saving the scene.

Expected: a static T-pose character near 1.7 meters tall, no accidental armature
or animation, at most 300,000 faces, bounded materials, and no parser errors.

- [ ] **Step 2: Import the FBX independently**

Repeat the same empty-scene audit using the FBX importer.

Expected: matching character scale and material assignments with no unrelated
cameras, lights, helpers, or scene geometry.

- [ ] **Step 3: Inspect all supplied thumbnails**

Inspect the alpha, front, rear, left, and right thumbnails at full detail.

Expected: recognizable sleepy face; five-finger gloves; compact separated shoes;
clean T-pose arms; intentional quills; left-side hoop; centered tail; no fused,
duplicated, or missing body parts.

- [ ] **Step 4: Classify the result**

Use exactly one disposition:

- `ACCEPT`: identity and topology meet the specification.
- `BLENDER_CORRECTION`: only localized face, glove, shoe, or material changes are needed.
- `REFERENCE_REBUILD`: fused anatomy, major identity drift, or unusable pose requires a new reference set.

Expected: no live integration or rigging begins until the disposition and evidence are recorded.

### Task 6: Close the generation phase

**Files:**
- No repository asset changes.

**Interfaces:**
- Consumes: final audit evidence and file hashes.
- Produces: a local handoff ready for the next rigging or corrective-modeling plan.

- [ ] **Step 1: Recheck balance**

Call `meshy_check_balance`.

Expected: balance decreased by no more than 30 credits from the verified preflight balance.

- [ ] **Step 2: Verify the public repository stayed asset-clean**

Run:

```bash
git status --short
```

Expected: no generated GLB, FBX, texture, reference, credential, or task metadata appears in the repository.

- [ ] **Step 3: Report the handoff**

Report the task disposition, exact local paths, sizes, hashes, charged credits,
geometry statistics, and the next approved production step.
