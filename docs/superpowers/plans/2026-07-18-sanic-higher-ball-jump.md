# SANIC Higher Ball Jump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the ball-spin jump to a 4.3-unit apex and extend airborne time to 0.63 seconds while preserving the decisive fast-fall landing.

**Architecture:** Keep `GameSimulation` as the single source of truth for vertical position and jump progress. Update only its apex, ascent, and descent constants; the existing derived velocity/gravity equations, collision system, and renderer-driven spin presentation continue unchanged.

**Tech Stack:** TypeScript, Vitest, Vite, Three.js, Vercel

## Global Constraints

- The jump apex is exactly `4.3` world units.
- Ascent lasts `0.35` seconds and descent lasts `0.28` seconds.
- Anticipation remains `0.07` seconds and recovery remains `0.05` seconds.
- The ball-spin progress window, models, animation clips, controls, forward speed, spawn spacing, and camera behavior remain unchanged.
- Use test-driven development and verify the regression test fails for the old `3.1`-unit jump before modifying production code.
- Publish only to `pasekaalex/sanic-run` and run exactly one production deployment.

---

### Task 1: Raise and Lengthen the Deterministic Ball Jump

**Files:**
- Modify: `tests/unit/simulation.test.ts:65-169`
- Modify: `src/game/simulation.ts:27-39`

**Interfaces:**
- Consumes: `GameSimulation.command('jump')`, `GameSimulation.step(dt)`, and `GameSimulation.snapshot()`.
- Produces: the existing `SimulationSnapshot.playerY` and `SimulationSnapshot.jumpProgress` interfaces with a 4.3-unit apex and 0.63-second airborne phase.

- [ ] **Step 1: Write the failing apex and flight-duration tests**

Change the apex bounds in the existing monotonic-arc test:

```ts
expect(peak).toBeGreaterThan(4.2);
expect(peak).toBeLessThan(4.4);
```

Add this focused test beside the other jump-timing tests:

```ts
it('stays airborne slightly longer before an exact fast-fall landing', () => {
  const game = new GameSimulation(30, scriptedSource([]));
  game.start();
  game.command('jump');

  game.step(0.69);
  expect(game.snapshot().playerY).toBeGreaterThan(0);
  expect(game.snapshot().jumpProgress).not.toBeNull();

  game.step(0.01);
  expect(game.snapshot().playerY).toBe(0);
  expect(game.snapshot().jumpProgress).not.toBeNull();

  game.step(0.05);
  expect(game.snapshot()).toMatchObject({ playerY: 0, jumpProgress: null });
});
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```bash
npx vitest run tests/unit/simulation.test.ts
```

Expected: FAIL because the old jump peaks near `3.1` and has already completed by `0.69` seconds.

- [ ] **Step 3: Apply the minimal physics tuning**

Change only these constants in `src/game/simulation.ts`:

```ts
const JUMP_HEIGHT = 4.3;
const JUMP_ASCENT_SECONDS = 0.35;
const JUMP_DESCENT_SECONDS = 0.28;
```

Leave anticipation, recovery, progress mapping, collision thresholds, and all rendering code unchanged.

- [ ] **Step 4: Run the focused test to verify GREEN**

Run:

```bash
npx vitest run tests/unit/simulation.test.ts
```

Expected: all simulation tests PASS, including a peak between `4.2` and `4.4`, positive height at `0.69` seconds, exact touchdown at `0.70` seconds, and jump completion at `0.75` seconds.

- [ ] **Step 5: Run complete local verification**

Run:

```bash
npm test -- --run
python3 -m unittest discover -s tests/python -p 'test_*.py'
npm run build
npm run test:pwa:artifacts
git diff --check
```

Expected: 214 or more JavaScript tests pass, 39 Python tests pass, the production and PWA artifact builds succeed, and `git diff --check` prints nothing.

- [ ] **Step 6: Commit the gameplay change**

```bash
git add src/game/simulation.ts tests/unit/simulation.test.ts
git commit -m "feat: raise SANIC ball jump"
```

Expected: one feature commit containing only the simulation constants and regression tests.

### Task 2: Publish and Verify Production

**Files:**
- No source files are created or modified.

**Interfaces:**
- Consumes: the verified feature branch and the existing Vercel project linkage.
- Produces: `pasekaalex/sanic-run` `main` and `www.sanic.fun` serving the same verified commit.

- [ ] **Step 1: Run the public-repository safety audit**

Audit the tracked tree, history, staged delta, author identity, credentials, remote, and current branch. Review false positives from documentation explicitly.

Expected: no legal-name, client, AI-attribution, or credential leak; author is `pasekaalex <35618421+pasekaalex@users.noreply.github.com>`; origin is `https://github.com/pasekaalex/sanic-run.git`.

- [ ] **Step 2: Verify branch lineage and push**

Confirm `origin/main` is an ancestor of `HEAD`, review the complete `origin/main..HEAD` delta, and push `HEAD` to `origin/main`.

Expected: one fast-forward push with only the approved design, plan, tests, and physics tuning.

- [ ] **Step 3: Deploy production exactly once**

Confirm no other deploy process is running, then run:

```bash
vercel deploy --prod --force --yes
```

Expected: one `READY` production deployment aliased to `www.sanic.fun`.

- [ ] **Step 4: Verify the live release**

Confirm the deployment metadata references the pushed commit, `https://www.sanic.fun/` returns HTTP 200, and the served production JavaScript contains the new jump constants after minification/build.

Expected: GitHub `main`, the Vercel production deployment, and the live domain all identify the same release.
