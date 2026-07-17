# SANIC PWA + Multi-Zone Expansion Implementation Plan

> Execute with tests first, isolated task branches, review before integration, and exact-artifact verification before publishing.

**Goal:** Ship an installable offline-safe SANIC runner with three escalating zones, original zone music, dynamic 90s pixel presentation, and preserved audited fairness.

**Baseline:** `beb4778d89a02639ed9dfbe7d8697bc19b7d6c0e`

## Task 1: Zone model and progression

**Files:** `src/game/zones.ts`, `src/config.ts`, `src/game/simulation.ts`, `src/game/spawnDirector.ts`, associated unit tests.

1. Write failing boundary, speed, deterministic weighting, and fairness tests.
2. Add immutable zone definitions and `zoneAtDistance` / `speedAtDistance`.
3. Make simulation and spawn spacing share the same speed curve.
4. Add deterministic per-zone template weights without weakening safety constraints.
5. Run spawn/simulation tests and the long-run fairness probes.

## Task 2: Zone-aware rendering and pixel UI

**Files:** `src/ui/gameUI.ts`, `src/app/gameApp.ts`, `src/render/worldRenderer.ts`, `src/pixel-ui.css`, `src/styles.css`, associated tests.

1. Write failing tests for boundary projection and one-shot transition announcements.
2. Project current stage/zone into loading, intro, HUD, pause, results, and root data attributes.
3. Add a non-blocking transition banner and per-zone CSS variables.
4. Vary deterministic scenery/palette/sign copy by zone without model flicker.
5. Honor reduced motion and verify compact/mobile HUD behavior.

## Task 3: Authored music and zone player

**Files:** `scripts/render-zone-music.mjs`, `public/music/*.mp3`, `src/platform/zoneMusicPlayer.ts`, `src/platform/audioController.ts`, `src/app/gameApp.ts`, associated tests.

1. Write failing lifecycle/crossfade tests.
2. Author three original loop-safe PCM arrangements and render reproducibly.
3. Encode mono MP3 assets and validate duration, channels, bitrate, peak, and combined size.
4. Implement a two-slot decoded-buffer player with equal-power 1.2 s crossfades and fail-soft fetch/decode.
5. Replace runtime oscillator music while preserving effects, mute, pause, restart, interruption, game-over, and destroy behavior.

## Task 4: Installable offline-safe PWA

**Files:** `public/manifest.webmanifest`, `public/icons/*`, `src/platform/pwa.ts`, `src/main.ts`, `vite.config.ts`, `vercel.json`, associated tests.

1. Write failing manifest and registration-gate tests.
2. Generate 192 px, 512 px, and maskable icons from the existing original SANIC art.
3. Add manifest metadata and document head links.
4. Generate a versioned service worker from the production bundle and implement runtime cache policies.
5. Register only in normal production, fail soft, and keep E2E builds hook-free.

## Task 5: Integrated verification and release

1. Review every task branch against the design and baseline.
2. Integrate only reviewed commits onto the feature branch; do not merge through unrelated local `main`.
3. Run `git diff --check`, all unit tests, Python/model validators, audio validation, normal/adversarial builds, and serial production E2E.
4. Scan reachable history for secrets and confirm the sole remote is `pasekaalex/sanic-run`.
5. Fetch/revalidate remote `main`, push by strict fast-forward, deploy the exact clean source to the linked `sanic-run` Vercel project, then verify `sanic.fun` and live asset hashes without opening a visible browser.
