# SANIC Audit Remediation Implementation Plan

> Execute test-first. Reproduce each defect before changing production code, keep commits narrow, and re-run the complete unit/browser suite after integration.

**Goal:** Remove the confirmed correctness, fairness, audio-lifecycle, loading, long-run, and crawler defects found in the July 17 desktop/mobile audit without changing the approved v3 animation contract.

**Architecture:** Keep `GameSimulation` authoritative for scoring and motion, `SpawnDirector` authoritative for authored rows, `AudioController` as a non-throwing platform boundary, and `AssetLoader` as a fail-soft boundary. Add only the state and policies required to make those boundaries explicit and bounded.

**Tech stack:** TypeScript 7, Vitest 4, Playwright 1.61, Three.js 0.185, Vite 8, Vercel static hosting.

---

## Task 1: Restore combo and audio lifecycle correctness

**Files:**

- Modify: `tests/unit/simulation.test.ts`
- Modify: `src/game/simulation.ts`
- Modify: `tests/unit/audioController.test.ts`
- Modify: `src/platform/audioController.ts`

1. Add a simulation regression that collects ten rings, misses one, then collects one. Assert the miss resets both streak and multiplier and the final ring total is 1,100 points.
2. Run the focused simulation test and record RED: the multiplier remains `2`.
3. Reset `multiplierValue` to `1` in the same miss branch that resets `ringStreakValue`.
4. Extend the audio fake with `statechange` listeners and configurable failures after successful startup.
5. Add RED tests proving:
   - `pickup`, `jump`, `lane`, and `impact` never throw when oscillator, gain, filter, buffer-source, `start`, or `stop` fails after startup;
   - every locally created partial node is stopped/disconnected where possible;
   - an externally suspended context triggers one serialized recovery attempt while the controller still desires playback;
   - app-requested pause does not auto-resume;
   - `destroy()` removes the state listener and prevents later recovery.
6. Put a local allocation/cleanup boundary around every effect graph. Register one context-state listener that delegates to the existing serialized state synchronizer.
7. Run:

   ```bash
   npm test -- tests/unit/simulation.test.ts tests/unit/audioController.test.ts
   npm test
   ```

8. Commit only the four scoped files.

---

## Task 2: Make startup fail-soft and remove the wasted promo transfer

**Files:**

- Modify: `tests/unit/assetLoader.test.ts`
- Modify: `src/render/assetLoader.ts`
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/ui/gameUI.ts`

1. Add a fake-timer asset test with one loader promise that never settles. Assert all four categories complete within a documented 20-second ceiling and the stalled category uses its branded fallback.
2. Record RED: the existing `Promise.all` never settles.
3. Race each category against one finite deadline. Resolve a timeout as `undefined`, mark progress complete once, and safely ignore a late resolution/rejection.
4. Add browser RED tests:
   - ordinary WebGL intro makes zero requests for `/media/sanic-game-promo.png`;
   - `?forceFallback=1` requests it exactly once and exposes the promo image with its existing alt text.
5. Store the promo URL in a data attribute and assign `src` only inside `showUnsupported()`.
6. Run:

   ```bash
   npm test -- tests/unit/assetLoader.test.ts
   npx playwright test tests/e2e/game.spec.ts --grep "promo|fallback|loading"
   npm test
   ```

7. Commit only the four scoped files.

---

## Task 3: Restore collectible and obstacle-sequence fairness

**Files:**

- Modify: `tests/unit/spawnDirector.test.ts`
- Modify: `src/game/spawnDirector.ts`

1. Add a deterministic regression for the seed-1 late-game full-blocker pair. Assert consecutive full-lane rows never require opposite outer lanes.
2. Add a fixed-step collection regression for every lane permutation of the weave at opening and maximum speed. Assert an earliest legal command schedule can collect all three rings.
3. Record RED:
   - the seed-1 pair requires `-1` then `+1`;
   - the current 2.4 m weave span yields at most two rings at maximum speed.
4. Track the last full-blocker safe lane and constrain only the next adjacent full-blocker focus lane so its route is reachable with margin. Preserve seeded determinism.
5. Scale only lane-weave offsets with speed, with a maximum half-span of at least 4.2 m, while keeping the complete row inside the existing row-spacing budget.
6. Add a multi-seed invariant covering at least 100 seeds through the speed cap.
7. Run:

   ```bash
   npm test -- tests/unit/spawnDirector.test.ts tests/unit/simulation.test.ts
   npm test
   ```

8. Commit only the two scoped files.

---

## Task 4: Bound endless-run bookkeeping

**Files:**

- Modify: `tests/unit/spawnDirector.test.ts`
- Modify: `src/game/spawnDirector.ts`
- Modify: `tests/unit/simulation.test.ts`
- Modify: `src/game/simulation.ts`
- Modify: `tests/unit/worldRendererPools.test.ts`
- Modify: `src/render/worldRenderer.ts`

1. Add a one-hour simulation benchmark/invariant that asserts generated-row returns and internal bookkeeping remain proportional to the lookahead window, not total distance.
2. Record RED with the current cumulative `rows`, `loadedRows`, and `emittedCoins` behavior.
3. Keep only a bounded recent row window inside `SpawnDirector`; prune rows permanently behind the player before filtering the next lookahead result.
4. Track loaded-row distance in production and prune identifiers only after the corresponding row is no longer returnable. Preserve the current injected-source behavior used by deterministic tests.
5. Store emitted coin distance alongside its identifier and prune entries once that distance is permanently behind the render window.
6. Preserve deterministic restart output for the same seed.
7. Run focused tests, then the complete unit suite.
8. Commit only the six scoped files.

---

## Task 5: Correct static crawler routes and the dialog compatibility branch

**Files:**

- Modify: `tests/unit/deploymentConfig.test.ts`
- Modify: `vercel.json`
- Create: `public/robots.txt`
- Create: `public/sitemap.xml`
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/ui/gameUI.ts`

1. Add RED deployment tests asserting:
   - `robots.txt` has plain-text directives and the sitemap URL;
   - `sitemap.xml` is parseable and contains only the canonical site URL;
   - no unconditional SPA rewrite masks an unknown static path.
2. Add the two crawler files and remove the unnecessary catch-all rewrite.
3. Add a browser RED test that forces `showModal()` to throw, then verifies background content is inert and Tab/Shift+Tab stay within the open dialog.
4. Implement a small internal compatibility branch: inert the non-dialog UI, apply modal semantics, contain focus, and restore the prior state when closing.
5. Run:

   ```bash
   npm test -- tests/unit/deploymentConfig.test.ts
   npx playwright test tests/e2e/game.spec.ts --grep "dialog|fallback"
   npm run build
   ```

6. Commit only the six scoped paths.

---

## Task 6: Integrated verification

1. Run:

   ```bash
   npm test
   npm run build
   npm run test:e2e
   python3 -m unittest tests/python/test_meshy_sprint_reference.py
   git diff --check origin/main...HEAD
   ```

2. Repeat cold-cache desktop, 390×844 mobile, 320×568 short-phone, and short-landscape browser passes.
3. Confirm:
   - zero application console errors;
   - no horizontal document overflow;
   - all visible touch controls remain at least 44×44 CSS px;
   - ordinary WebGL boot does not request the fallback promo;
   - a stalled GLB reaches branded fallback before the deadline;
   - combo resets on a miss;
   - audio interruption recovers without duplicate schedulers;
   - the audited seed pair and max-speed weave satisfy the new fairness tests;
   - unknown static routes are 404 while robots and sitemap return correct types.
4. Run the repository/public-history safety gates from the v3 release plan before any push or deployment.
