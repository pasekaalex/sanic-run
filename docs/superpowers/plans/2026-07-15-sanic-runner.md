# $SANIC WebGL Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a polished, playable three-lane `$SANIC` WebGL runner with original Blender-made assets, responsive controls, exact contract links, and a static fallback.

**Architecture:** A backend-free Vite/TypeScript application keeps deterministic runner rules in a renderer-independent fixed-step simulation and projects immutable snapshots into a Three.js renderer plus an accessible DOM UI. Blender MCP creates high-detail source assets and optimized GLBs; Vercel serves the resulting static build directly from the local checkout.

**Tech Stack:** Node 26, npm 11, TypeScript 7.0.2, Vite 8.1.4, Three.js 0.185.1, Vitest 4.1.10, Playwright 1.61.1, Blender 5.1.2, Vercel CLI 54.13.0.

## Global Constraints

- Token name is `$SANIC`; contract address is exactly `CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump`.
- The production link for buying is `https://pump.fun/coin/CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump`.
- Version one has no wallet connection, signatures, live prices, backend, accounts, leaderboard, or invented social links.
- The game uses three discrete lanes, automatic forward motion, jumping, ring collection, a `1x–5x` combo multiplier, collision game-over, and restart.
- The Blender master retains approximately `250k–500k` evaluated triangles; the browser character targets `45k–80k` triangles and less than `4 MB` compressed transfer.
- Initial essential deployed transfer stays below `10 MB`; target frame rate is `60 FPS` on a current desktop and at least `30 FPS` on a representative modern mobile device.
- WebGL 2 runs the game; unsupported devices receive the branded static fallback.
- Use only original custom assets based on `docs/references/sanic-source.png`; do not use official franchise models, logos, music, UI, or level assets.
- Include the approved entertainment/not-financial-advice and non-affiliation disclosure.
- Deploy the audited release to Vercel and publish its clean-root source only to the personal `pasekaalex/sanic-run` repository.
- Do not persist or use the GitHub PAT shared in chat.
- The only launch social account is exactly `https://x.com/memesofsanic`; results produce a branded PNG score card and an encoded X compose fallback without OAuth.

## File Map

```text
index.html                         Static semantic shell and SEO metadata
package.json                       Exact scripts and dependency versions
playwright.config.ts               Desktop/mobile browser projects
tsconfig.json                      Strict TypeScript settings
vite.config.ts                     Vite and Vitest configuration
src/main.ts                        Browser entry point
src/config.ts                      Immutable brand/game constants
src/styles.css                     Responsive visual system and overlays
src/game/types.ts                  Shared simulation contracts
src/game/random.ts                 Deterministic seeded PRNG
src/game/spawnDirector.ts          Solvable obstacle/coin pattern generation
src/game/simulation.ts             Fixed-step game rules and snapshots
src/platform/storage.ts            Versioned local settings/high score
src/platform/inputController.ts    Keyboard and swipe command normalization
src/platform/audioController.ts    Web Audio effects and wind loop
src/render/assetLoader.ts          GLB loading, progress, validation, fallbacks
src/render/fallbackAssets.ts       Procedural emergency meshes
src/render/worldRenderer.ts        Three.js world, pools, animation, camera
src/ui/gameUI.ts                   Accessible DOM state projection and actions
src/ui/scoreCard.ts                Runtime score-card PNG rendering and share payload
src/app/gameApp.ts                 Lifecycle orchestration and RAF accumulator
tests/unit/*.test.ts               Deterministic unit coverage
tests/e2e/game.spec.ts             Browser gameplay and responsive coverage
blender/scripts/build_sanic.py     Reproducible high-detail character build
blender/scripts/build_world.py     Reproducible ring and forest-kit build
blender/scripts/validate_assets.py Blender object/action/poly validation
blender/sanic-source.blend         High-detail source scene
blender/world-source.blend         Reproducible ring and forest source scene
public/models/sanic-runner.glb     Optimized animated web character
public/models/sanic-ring.glb       Collectible model
public/models/forest-kit.glb       Modular environment and obstacle kit
public/media/sanic-game-promo.png  Approved launch key art
public/media/sanic-score-card-bg.png Generated score-card background with clear stats zone
public/media/sanic-og.jpg          Optimized 1200×630 social image
vercel.json                        Static deployment headers and SPA fallback
```

---

### Task 1: Scaffold the Static App and Lock Brand Constants

**Files:**
- Create: `.gitignore`
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `index.html`
- Create: `src/config.ts`
- Create: `src/main.ts`
- Create: `src/styles.css`
- Create: `tests/unit/config.test.ts`

**Interfaces:**
- Consumes: approved copy and exact contract from the design specification.
- Produces: `BRAND`, `GAME`, and `ASSET_URLS` constants used by every later task.

- [ ] **Step 1: Create package metadata and install the exact toolchain**

Use this `package.json`:

```json
{
  "name": "sanic-run",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "check": "npm run test && npm run build && npm run test:e2e"
  },
  "dependencies": {
    "@fontsource/bangers": "5.2.8",
    "@fontsource/space-mono": "5.2.9",
    "three": "0.185.1"
  },
  "devDependencies": {
    "@gltf-transform/cli": "4.4.1",
    "@playwright/test": "1.61.1",
    "@types/node": "26.1.1",
    "jsdom": "29.1.1",
    "typescript": "7.0.2",
    "vite": "8.1.4",
    "vitest": "4.1.10"
  }
}
```

Run: `npm install`  
Expected: `package-lock.json` is created and npm exits `0`.

- [ ] **Step 2: Write the brand-constant test before its module exists**

```ts
// tests/unit/config.test.ts
import { describe, expect, it } from 'vitest';
import { ASSET_URLS, BRAND, GAME } from '../../src/config';

describe('immutable launch configuration', () => {
  it('uses the exact contract in copy and Pump.fun URL', () => {
    expect(BRAND.contract).toBe('CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump');
    expect(BRAND.pumpUrl).toBe(`https://pump.fun/coin/${BRAND.contract}`);
  });

  it('locks the three-lane scoring rules and asset URLs', () => {
    expect(GAME.lanes).toEqual([-1, 0, 1]);
    expect(GAME.maxMultiplier).toBe(5);
    expect(GAME.ringsPerMultiplier).toBe(10);
    expect(ASSET_URLS.character).toBe('/models/sanic-runner.glb');
  });
});
```

Run: `npm test -- tests/unit/config.test.ts`  
Expected: FAIL because `src/config.ts` does not exist.

- [ ] **Step 3: Add strict configuration and the minimal semantic shell**

Implement `src/config.ts` with frozen literal values:

```ts
export const BRAND = Object.freeze({
  name: '$SANIC',
  tagline: 'I LOVE TO GO FAST',
  contract: 'CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump',
  pumpUrl: 'https://pump.fun/coin/CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump',
  disclosure: '$SANIC is a memecoin made for entertainment. No utility, no promises, no financial advice. Verify the contract and only risk what you can afford to lose. Not affiliated with or endorsed by Ansem, SEGA, or Sonic the Hedgehog.',
});

export const GAME = Object.freeze({
  lanes: [-1, 0, 1] as const,
  laneWidth: 3.2,
  fixedStep: 1 / 60,
  startSpeed: 18,
  maxSpeed: 36,
  ringScore: 100,
  ringsPerMultiplier: 10,
  maxMultiplier: 5,
  spawnAhead: 190,
});

export const ASSET_URLS = Object.freeze({
  character: '/models/sanic-runner.glb',
  ring: '/models/sanic-ring.glb',
  forest: '/models/forest-kit.glb',
  promo: '/media/sanic-game-promo.png',
});
```

Create `index.html` with `#game-canvas`, `#app-ui`, a static `<noscript>` fallback, exact title/description/theme metadata, and no remote scripts. `src/main.ts` should import both bundled fonts and `src/styles.css`, then render a temporary intro card using `BRAND`; later tasks replace only the bootstrap body, not the metadata.

Use strict `tsconfig.json` settings: `target: ES2023`, `module: ESNext`, `moduleResolution: Bundler`, `strict: true`, `noUncheckedIndexedAccess: true`, `noImplicitOverride: true`, `useDefineForClassFields: true`, and `types: ["vitest/globals", "node"]`. Configure Vite tests with `environment: "jsdom"` and include `tests/unit/**/*.test.ts`.

- [ ] **Step 4: Verify the scaffold**

Run: `npm test -- tests/unit/config.test.ts && npm run build`  
Expected: two tests pass and Vite emits `dist/index.html` with no TypeScript errors.

- [ ] **Step 5: Commit the scaffold**

```bash
git add .gitignore package.json package-lock.json tsconfig.json vite.config.ts index.html src tests/unit/config.test.ts
git commit -m "feat: scaffold sanic runner shell"
```

---

### Task 2: Build a Deterministic, Solvable Spawn Director

**Files:**
- Create: `src/game/types.ts`
- Create: `src/game/random.ts`
- Create: `src/game/spawnDirector.ts`
- Create: `tests/unit/spawnDirector.test.ts`

**Interfaces:**
- Consumes: `GAME.lanes` and `GAME.spawnAhead`.
- Produces: `SpawnDirector`, `SpawnRow`, `CoinSpawn`, `ObstacleSpawn`, `Lane`, and `ObstacleKind`.

- [ ] **Step 1: Write failing generator tests**

```ts
// tests/unit/spawnDirector.test.ts
import { describe, expect, it } from 'vitest';
import { SpawnDirector } from '../../src/game/spawnDirector';

describe('SpawnDirector', () => {
  it('is deterministic for a seed', () => {
    const a = new SpawnDirector(0x5a11c).takeUntil(220);
    const b = new SpawnDirector(0x5a11c).takeUntil(220);
    expect(a).toEqual(b);
  });

  it('leaves a physically safe lane in every obstacle row', () => {
    const rows = new SpawnDirector(42).takeUntil(3_000);
    for (const row of rows.filter((candidate) => candidate.obstacles.length > 0)) {
      const blocked = new Set(row.obstacles.filter((item) => !item.jumpable).map((item) => item.lane));
      expect(blocked.size).toBeLessThan(3);
    }
  });

  it('starts with teaching patterns and increases spacing with required reaction time', () => {
    const rows = new SpawnDirector(7).takeUntil(500);
    expect(rows[0]?.at).toBeGreaterThanOrEqual(24);
    expect(rows.some((row) => row.coins.length >= 3)).toBe(true);
    expect(rows.every((row, index) => index === 0 || row.at > rows[index - 1]!.at)).toBe(true);
  });
});
```

Run: `npm test -- tests/unit/spawnDirector.test.ts`  
Expected: FAIL because the generator modules do not exist.

- [ ] **Step 2: Define exact spawn contracts**

```ts
// src/game/types.ts
export type Lane = -1 | 0 | 1;
export type ObstacleKind = 'log' | 'candle' | 'fud' | 'gap';
export type GameCommand = 'left' | 'right' | 'jump' | 'pause';
export type GamePhase = 'intro' | 'playing' | 'paused' | 'gameOver';

export interface CoinSpawn { readonly id: string; readonly lane: Lane; readonly height: 0.9 | 2.2; }
export interface ObstacleSpawn { readonly id: string; readonly lane: Lane; readonly kind: ObstacleKind; readonly jumpable: boolean; }
export interface SpawnRow { readonly id: string; readonly at: number; readonly coins: readonly CoinSpawn[]; readonly obstacles: readonly ObstacleSpawn[]; }
```

Implement `src/game/random.ts` as a nonzero `xorshift32` generator exposing `next(): number` in `[0, 1)` and `pick<T>(items: readonly T[]): T`.

- [ ] **Step 3: Implement config-driven safe patterns**

`SpawnDirector` must expose:

```ts
export class SpawnDirector {
  constructor(seed: number);
  reset(seed: number): void;
  takeUntil(maxDistance: number): readonly SpawnRow[];
}
```

Use immutable templates for: straight coin line, lane-weave coin line, single log with jump arc, two hard blockers with one safe lane, and log-plus-hard-blocker with one lane/jump solution. Start at distance `24`; use spacing `12 + speedAtDistance(distance) * 0.32`; assign stable IDs from row and item counters. The director may randomize lanes and template choice, but it must never place three non-jumpable blockers in one row.

- [ ] **Step 4: Verify determinism and long-run safety**

Run: `npm test -- tests/unit/spawnDirector.test.ts`  
Expected: all three tests pass for 3,000 world units of generated rows.

- [ ] **Step 5: Commit the spawn system**

```bash
git add src/game tests/unit/spawnDirector.test.ts
git commit -m "feat: add solvable runner patterns"
```

---

### Task 3: Implement the Fixed-Step Runner Simulation

**Files:**
- Create: `src/game/simulation.ts`
- Create: `tests/unit/simulation.test.ts`
- Modify: `src/game/types.ts`

**Interfaces:**
- Consumes: `SpawnDirector`, `GameCommand`, `SpawnRow`, and `GAME`.
- Produces: `GameSimulation.command(command)`, `GameSimulation.step(dt)`, `GameSimulation.snapshot()`, and immutable `SimulationSnapshot`.

- [ ] **Step 1: Write failing movement, scoring, and collision tests**

```ts
// tests/unit/simulation.test.ts
import { describe, expect, it } from 'vitest';
import { GAME } from '../../src/config';
import { GameSimulation } from '../../src/game/simulation';

const advance = (game: GameSimulation, seconds: number) => {
  for (let elapsed = 0; elapsed < seconds; elapsed += GAME.fixedStep) game.step(GAME.fixedStep);
};

describe('GameSimulation', () => {
  it('clamps lane commands and eases to the selected lane', () => {
    const game = new GameSimulation(1);
    game.start();
    game.command('left'); game.command('left');
    advance(game, 0.3);
    expect(game.snapshot().lane).toBe(-1);
    expect(game.snapshot().playerX).toBeCloseTo(-GAME.laneWidth, 1);
  });

  it('uses a repeatable jump arc and returns to ground', () => {
    const game = new GameSimulation(2);
    game.start(); game.command('jump');
    advance(game, 0.35);
    expect(game.snapshot().playerY).toBeGreaterThan(1.2);
    advance(game, 0.6);
    expect(game.snapshot().playerY).toBe(0);
  });

  it('awards one multiplier step per ten uninterrupted rings and caps at five', () => {
    const game = new GameSimulation(3, scriptedRingSource(50));
    game.start();
    advance(game, 3.2);
    expect(game.snapshot()).toMatchObject({ rings: 50, multiplier: 5, ringStreak: 50 });
    expect(game.snapshot().score - Math.floor(game.snapshot().distance)).toBe(15_000);
  });

  it('ends the run on an occupied grounded obstacle lane', () => {
    const game = new GameSimulation(4, scriptedObstacleSource({ id: 'impact', lane: 0, kind: 'fud', jumpable: false }, 0.5));
    game.start();
    advance(game, 0.1);
    expect(game.snapshot().phase).toBe('gameOver');
  });
});
```

Run: `npm test -- tests/unit/simulation.test.ts`  
Expected: FAIL because `GameSimulation` does not exist.

- [ ] **Step 2: Extend snapshot contracts**

Add `ActiveCoin`, `ActiveObstacle`, and this immutable snapshot shape:

```ts
export interface SimulationSnapshot {
  readonly phase: GamePhase;
  readonly elapsed: number;
  readonly distance: number;
  readonly speed: number;
  readonly score: number;
  readonly rings: number;
  readonly multiplier: number;
  readonly ringStreak: number;
  readonly lane: Lane;
  readonly playerX: number;
  readonly playerY: number;
  readonly coins: readonly ActiveCoin[];
  readonly obstacles: readonly ActiveObstacle[];
  readonly impactKind: ObstacleKind | null;
}
```

- [ ] **Step 3: Implement deterministic game rules**

Implement a `GameSimulation` with public API:

```ts
export class GameSimulation {
  constructor(seed: number, source?: SpawnSource);
  start(): void;
  restart(seed?: number): void;
  pause(): void;
  resume(): void;
  command(command: GameCommand): void;
  step(dt: number): void;
  snapshot(): Readonly<SimulationSnapshot>;
}
```

Define `SpawnSource` as the minimal production interface `{ takeUntil(maxDistance: number): readonly SpawnRow[] }`; `SpawnDirector` is the default implementation. Put `scriptedRingSource` and `scriptedObstacleSource` in the test file as small real data sources that implement this interface. This keeps test-only controls out of production while allowing exact deterministic scenarios.

Use a `0.18 s` cubic-eased lane transition, a `0.82 s` sine jump peaking at `2.35` units, speed `min(36, 18 + distance / 140)`, distance score `floor(distance)`, collectible radius `1.15`, obstacle collision window `±0.85`, and jump clearance at `playerY >= 1.05`. Queue one semantic input while a lane transition or jump is active. When a ring passes `-1.2` relative units uncollected, reset only `ringStreak`; collision sets `phase = 'gameOver'` and freezes forward progress.

Implement multiplier advancement after each completed group of ten so the first ten rings award `1,000`, the next ten `2,000`, then `3,000`, `4,000`, and `5,000`, for an exact 50-ring total of `15,000`.

- [ ] **Step 4: Add playability invariants and run all simulation tests**

Add tests that pausing freezes distance, speed never exceeds `36`, a jump clears a log, a missed ring resets the streak, and `restart()` returns all counters to their initial values.

Run: `npm test -- tests/unit/spawnDirector.test.ts tests/unit/simulation.test.ts`  
Expected: all generator and simulation tests pass.

- [ ] **Step 5: Commit the simulation**

```bash
git add src/game tests/unit/simulation.test.ts
git commit -m "feat: implement runner simulation"
```

---

### Task 4: Normalize Input, Persist Preferences, and Synthesize Audio

**Files:**
- Create: `src/platform/inputController.ts`
- Create: `src/platform/storage.ts`
- Create: `src/platform/audioController.ts`
- Create: `tests/unit/inputController.test.ts`
- Create: `tests/unit/storage.test.ts`

**Interfaces:**
- Consumes: `GameCommand` and browser keyboard/pointer events.
- Produces: `InputController`, `AudioController`, `loadPreferences`, `savePreferences`, `saveBestScore`.

- [ ] **Step 1: Write failing storage and gesture tests**

```ts
// tests/unit/storage.test.ts
import { beforeEach, describe, expect, it } from 'vitest';
import { loadPreferences, saveBestScore } from '../../src/platform/storage';

describe('versioned storage', () => {
  beforeEach(() => localStorage.clear());
  it('recovers from malformed data', () => {
    localStorage.setItem('sanic:v1', '{broken');
    expect(loadPreferences()).toEqual({ bestScore: 0, muted: false, lowEffects: false });
  });
  it('keeps the higher best score', () => {
    saveBestScore(900); saveBestScore(200);
    expect(loadPreferences().bestScore).toBe(900);
  });
});
```

```ts
// tests/unit/inputController.test.ts
import { describe, expect, it, vi } from 'vitest';
import { InputController } from '../../src/platform/inputController';

describe('InputController', () => {
  it('maps arrows and a horizontal swipe to semantic commands', () => {
    const onCommand = vi.fn();
    const target = document.createElement('div');
    document.body.append(target);
    const input = new InputController(target, onCommand);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));
    target.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientX: 100, clientY: 100 }));
    target.dispatchEvent(new PointerEvent('pointerup', { pointerId: 1, clientX: 170, clientY: 104 }));
    expect(onCommand.mock.calls.map(([command]) => command)).toEqual(['left', 'right']);
    input.destroy();
  });
});
```

Run: `npm test -- tests/unit/storage.test.ts tests/unit/inputController.test.ts`  
Expected: FAIL because the platform modules do not exist.

- [ ] **Step 2: Implement the small browser adapters**

`InputController` accepts `(target: HTMLElement, onCommand: (command: GameCommand) => void)`, uses non-repeating keyboard events, pointer capture, a `42 px` swipe threshold, horizontal/vertical dominance, and exposes `destroy(): void` that removes every listener.

`storage.ts` uses only key `sanic:v1`, validates each parsed field, defaults to `{ bestScore: 0, muted: false, lowEffects: matchMedia('(prefers-reduced-motion: reduce)').matches }`, and never throws for blocked storage.

`AudioController` exposes `start()`, `setMuted(boolean)`, `pickup(multiplier)`, `jump()`, `lane()`, `impact()`, `pause()`, and `destroy()`. Build oscillators/gain nodes only after `start()`; cap master gain at `0.16`; use short envelopes and a filtered-noise wind source; do not fetch audio files.

- [ ] **Step 3: Verify adapters and listener cleanup**

Run: `npm test -- tests/unit/storage.test.ts tests/unit/inputController.test.ts`  
Expected: all adapter tests pass and no event fires after `destroy()`.

- [ ] **Step 4: Commit platform adapters**

```bash
git add src/platform tests/unit/inputController.test.ts tests/unit/storage.test.ts
git commit -m "feat: add controls storage and synth audio"
```

---

### Task 5: Create the High-Detail Buff Sanic in Blender MCP

**Files:**
- Create: `blender/scripts/build_sanic.py`
- Create: `blender/scripts/validate_assets.py`
- Create: `blender/sanic-source.blend`
- Create: `public/models/sanic-runner.glb`

**Interfaces:**
- Consumes: `docs/references/sanic-source.png` and the exact asset limits in the design.
- Produces: named Blender source objects plus GLB actions `Idle`, `Run`, `Jump`, and `Crash` consumed by `AssetLoader`/`WorldRenderer`.

- [ ] **Step 1: Write the Blender validation script first**

```py
# blender/scripts/validate_assets.py
import bpy
from pathlib import Path

required_objects = {
    'SANIC_Armature', 'SANIC_Body', 'SANIC_Head', 'SANIC_Quills',
    'SANIC_Muzzle', 'SANIC_Eyes', 'SANIC_Glove.L', 'SANIC_Glove.R',
    'SANIC_Shoe.L', 'SANIC_Shoe.R',
}
required_actions = {'Idle', 'Run', 'Jump', 'Crash'}
missing_objects = required_objects - set(bpy.data.objects.keys())
missing_actions = required_actions - set(bpy.data.actions.keys())
assert not missing_objects, f'Missing objects: {sorted(missing_objects)}'
assert not missing_actions, f'Missing actions: {sorted(missing_actions)}'
depsgraph = bpy.context.evaluated_depsgraph_get()
triangles = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    triangles += len(mesh.loop_triangles)
    evaluated.to_mesh_clear()
assert 250_000 <= triangles <= 500_000, f'High-detail triangle count is {triangles}'
assert Path(bpy.data.filepath).name == 'sanic-source.blend'
print({'objects': len(bpy.data.objects), 'actions': sorted(required_actions), 'triangles': triangles})
```

Run it against the empty Blender scene through `mcp__blender__execute_blender_code`.  
Expected: assertion failure listing all required objects. This proves the validator is active.

- [ ] **Step 2: Build materials and the muscular silhouette through Blender MCP**

Create reusable helpers in `build_sanic.py`: `material(name, color, metallic, roughness)`, `uv_sphere(name, location, scale, material)`, `capsule_between(name, start, end, radius, material)`, `rounded_box(...)`, and `quill(name, root, tip, width)`. Use smooth shading, bevel modifiers, weighted normals where available, and subdivision levels that evaluate inside the high-detail budget.

Execute the script through Blender MCP in small checkpoints:

1. Reset scene, set meters, create cobalt/white/red/sole/beige/black materials.
2. Create broad torso, separated pectorals, abdominal masses, deltoids, biceps, forearms, thighs, and calves.
3. Create the head, backward quill fan, drooping eye plates, lids, nose, muzzle, sculpted lips, brow text curve, gloves with five readable fingers, and strapped red shoes.
4. Capture a viewport screenshot after the neutral model and correct silhouette/material issues before rigging.

Every object must use the exact `SANIC_*` naming prefix; left/right suffixes use `.L`/`.R`.

- [ ] **Step 3: Add armature, rigid-cartoon weights, and four actions**

Create an armature with root, hips, spine, chest, neck, head, upper/lower arm, hand, upper/lower leg, and foot bones. Bind torso/head/quills rigidly and use smooth automatic weights only at shoulder, elbow, hip, and knee transitions. Define:

- `Idle`: 48 frames, subtle chest breathing and quill bob.
- `Run`: 24-frame loop, exaggerated opposing limbs, vertical body compression, shoe follow-through.
- `Jump`: 36 frames, anticipation, tucked airborne pose, landing extension.
- `Crash`: 30 frames, chest recoil, arms forward, head/quill lag.

Set action frame ranges explicitly and mark each action for export. Capture front and rear-three-quarter viewport screenshots; the rear angle must read clearly at gameplay distance.

- [ ] **Step 4: Save the high-detail source and export the optimized GLB**

Save `/home/alex/projects/sanic-run/blender/sanic-source.blend`. Duplicate the export collection, apply a lower subdivision level, remove unseen internal geometry, join compatible material sections, and target `45k–80k` evaluated triangles. Export only the armature and web collection to `public/models/sanic-runner.glb` with animation, materials, tangents, and Y-up conversion.

Run `npx gltf-transform optimize public/models/sanic-runner.glb public/models/sanic-runner.optimized.glb --compress meshopt`, verify the optimized file in Three.js, then replace the unoptimized export only if animation clips and materials survive.

- [ ] **Step 5: Validate and visually inspect the character**

Run the validator inside Blender MCP, query scene/object info, and capture a final viewport screenshot. Then run:

```bash
du -h public/models/sanic-runner.glb
npx gltf-transform inspect public/models/sanic-runner.glb
```

Expected: source scene `250k–500k` evaluated triangles; web GLB `45k–80k` triangles, under `4 MB`, exactly four named actions, no missing textures.

- [ ] **Step 6: Commit the character source and export**

```bash
git add blender/scripts/build_sanic.py blender/scripts/validate_assets.py blender/sanic-source.blend public/models/sanic-runner.glb
git commit -m "feat: model and rig buff sanic"
```

---

### Task 6: Create the Ring-Coin and Modular Forest Kit in Blender MCP

**Files:**
- Create: `blender/scripts/build_world.py`
- Create: `blender/world-source.blend`
- Create: `public/models/sanic-ring.glb`
- Create: `public/models/forest-kit.glb`
- Modify: `blender/scripts/validate_assets.py`

**Interfaces:**
- Consumes: renderer naming contract documented below.
- Produces: `SANIC_Ring` and named `KIT_*` nodes discoverable by `AssetLoader`.

- [ ] **Step 1: Extend the validator with the web-kit contract**

Refactor the validator to accept a `character` or `world` mode from Blender's arguments so character validation remains independent. In `world` mode, require these exported node names: `SANIC_Ring`, `KIT_Tree_A`, `KIT_Tree_B`, `KIT_Grass`, `KIT_Fern`, `KIT_Rock`, `KIT_Mushroom`, `KIT_Log`, `KIT_Candle`, `KIT_FUD`, `KIT_Gap`, `KIT_Sign_Stimmy`, `KIT_Sign_Trenches`, `KIT_Sign_Coping`, and `KIT_Sign_Memes`. Assert all meshes have UVs, no object has negative scale, and the combined web-kit source stays below `120k` evaluated triangles before instancing.

Run the extended validator before building.  
Expected: failure listing the missing kit nodes.

- [ ] **Step 2: Build and export the gold ring-coin**

Through Blender MCP, create a thick beveled torus in warm metallic gold, add an inset central `$` plaque that remains readable from the game camera, use a subtle emissive inner rim, triangulate, and export only `SANIC_Ring` to `public/models/sanic-ring.glb`. Target below `12k` triangles and `500 KB`.

- [ ] **Step 3: Build a clean stylized forest kit**

Use shared atlas-friendly materials and create:

- Two tapered tree variants with separate leaf crowns.
- One grass clump and one fern silhouette suitable for instancing.
- Rock and mushroom variants.
- Fallen log, red candle barrier, `FUD` barricade, and shallow gap rim.
- Four wooden sign variants with exact readable phrases: `STIMMY LANE`, `FOR THE TRENCHES`, `SIDELINED & COPING`, and `RETURN TO MEMES`.

Keep pivot points at ground center, forward direction `-Z`, dimensions in meters, and collision props within their configured lane envelope. Save the reproducible source scene as `blender/world-source.blend`. Capture a viewport screenshot showing the entire kit on a neutral ground plane.

- [ ] **Step 4: Export, optimize, and validate both GLBs**

Export the kit to `public/models/forest-kit.glb`, optimize with meshopt, and run `gltf-transform inspect` on both files. Expected combined compressed transfer is below `3 MB`; materials remain embedded; every required node name is present.

- [ ] **Step 5: Commit the world assets**

```bash
git add blender/scripts/build_world.py blender/scripts/validate_assets.py blender/world-source.blend public/models/sanic-ring.glb public/models/forest-kit.glb
git commit -m "feat: build sanic forest asset kit"
```

---

### Task 7: Load Assets and Render the Endless Forest

**Files:**
- Create: `src/render/fallbackAssets.ts`
- Create: `src/render/assetLoader.ts`
- Create: `src/render/worldRenderer.ts`
- Create: `tests/unit/assetLoader.test.ts`

**Interfaces:**
- Consumes: `ASSET_URLS`, `SimulationSnapshot`, and the exact GLB node/action names from Tasks 5–6.
- Produces: `AssetLoader.load(onProgress)`, `WorldRenderer.render(previous, current, alpha)`, `resize()`, `setLowEffects()`, and `destroy()`.

- [ ] **Step 1: Write failing asset fallback tests**

```ts
// tests/unit/assetLoader.test.ts
import { describe, expect, it, vi } from 'vitest';
import { AssetLoader } from '../../src/render/assetLoader';

describe('AssetLoader', () => {
  it('returns branded fallback assets when all GLBs reject', async () => {
    const loader = new AssetLoader({ loadAsync: vi.fn().mockRejectedValue(new Error('offline')) });
    const assets = await loader.load(() => undefined);
    expect(assets.usingFallback).toBe(true);
    expect(assets.character.name).toBe('SANIC_Fallback');
    expect(assets.ring.name).toBe('SANIC_Ring_Fallback');
  });
});
```

Run: `npm test -- tests/unit/assetLoader.test.ts`  
Expected: FAIL because renderer modules do not exist.

- [ ] **Step 2: Implement visible procedural fallbacks and resilient loading**

`fallbackAssets.ts` creates a cobalt capsule body with quill cones, white glove spheres, red shoe boxes, a gold torus, trees, logs, and signs from basic Three.js geometry. `AssetLoader` accepts a structural loader dependency for tests, loads all three URLs concurrently, reports progress in `[0,1]`, validates the four character actions and kit node names, and replaces only failed categories with fallback assets.

- [ ] **Step 3: Implement the renderer and object pools**

Create a WebGL renderer with antialiasing, ACES tone mapping, sRGB output, DPR clamps, transparent cyan-to-forest fog, hemisphere light, one bounded shadow-casting directional light, and a low rear-three-quarter perspective camera.

`WorldRenderer` must:

- Keep the character near world origin and move/recycle road/scenery relative to simulation distance.
- Use `InstancedMesh` pools for `180` rings, `120` trees, `360` grass/fern clusters, `80` rocks/mushrooms, and pooled obstacle clones.
- Resolve `KIT_*` nodes once and never traverse the GLB during each frame.
- Cross-fade `Idle`, `Run`, `Jump`, and `Crash` clips through one `AnimationMixer`.
- Interpolate player position between fixed snapshots.
- Rotate/pulse ring instances, emit pickup sparkles and dust, bank the camera during lane changes, and omit shake/streaks in low-effects mode.
- Handle resize, context loss/restoration, and full disposal of geometries/materials/listeners.

- [ ] **Step 4: Verify loading and compile the renderer**

Run: `npm test -- tests/unit/assetLoader.test.ts && npm run build`  
Expected: fallback test passes and strict TypeScript build reports no renderer errors.

- [ ] **Step 5: Commit the rendering layer**

```bash
git add src/render tests/unit/assetLoader.test.ts
git commit -m "feat: render the endless sanic forest"
```

---

### Task 8: Build the Accessible UI and Application Lifecycle

**Files:**
- Existing: `public/media/sanic-score-card-bg.png` generated through the built-in `imagegen` workflow before this task.
- Create: `src/ui/gameUI.ts`
- Create: `src/ui/scoreCard.ts`
- Create: `src/app/gameApp.ts`
- Create: `tests/unit/scoreCard.test.ts`
- Create: `tests/e2e/game.spec.ts`
- Create: `playwright.config.ts`
- Modify: `index.html`
- Modify: `src/main.ts`
- Modify: `src/config.ts`
- Modify: `src/styles.css`

**Interfaces:**
- Consumes: simulation, renderer, platform adapters, brand constants, and semantic DOM slots.
- Produces: the complete loading → intro → playing → paused → game-over/fallback user flow.

- [ ] **Step 1: Write browser tests against the unfinished shell**

```ts
// tests/e2e/game.spec.ts
import { expect, test } from '@playwright/test';

test('starts, responds to controls, pauses, crashes, and restarts', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.getByRole('heading', { name: '$SANIC' })).toBeVisible();
  await page.getByRole('button', { name: 'GOTTA GO FAST' }).click();
  await expect(page.locator('[data-phase="playing"]')).toBeVisible();
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('[data-player-lane]')).toHaveAttribute('data-player-lane', '-1');
  await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Pause' }).click();
  await expect(page.getByRole('dialog', { name: 'Paused' })).toBeVisible();
  await page.getByRole('button', { name: 'Resume' }).click();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await expect(page.getByRole('dialog', { name: 'Run complete' })).toBeVisible();
  await page.getByRole('button', { name: 'RUN IT BACK' }).click();
  await expect(page.locator('[data-phase="playing"]')).toBeVisible();
});

test('copies the exact contract and reaches the exact Pump.fun URL', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/');
  await page.getByRole('button', { name: 'Copy contract' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump');
  await expect(page.getByRole('link', { name: 'View on Pump.fun' })).toHaveAttribute('href', 'https://pump.fun/coin/CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump');
  await expect(page.getByRole('link', { name: 'Follow $SANIC on X' })).toHaveAttribute('href', 'https://x.com/memesofsanic');
});
```

Configure Playwright `webServer.command = 'npm run dev -- --host 127.0.0.1'`, `baseURL = 'http://127.0.0.1:5173'`, and projects for desktop Chromium `1440×900` plus mobile Chromium `390×844` with touch.

Run: `npx playwright test tests/e2e/game.spec.ts`  
Expected: FAIL because the lifecycle UI is incomplete.

- [ ] **Step 2: Implement semantic overlays and exact state projection**

`GameUI` must cache DOM references once and expose:

```ts
export interface UIActions {
  start(): void; pause(): void; resume(): void; restart(): void;
  mute(muted: boolean): void; copyContract(): Promise<void>; share(): Promise<void>;
}

export class GameUI {
  constructor(root: HTMLElement, actions: UIActions);
  setLoading(progress: number): void;
  showIntro(): void;
  showPlaying(snapshot: SimulationSnapshot, bestScore: number): void;
  showPaused(snapshot: SimulationSnapshot): void;
  showGameOver(snapshot: SimulationSnapshot, bestScore: number): void;
  showUnsupported(reason: string): void;
  announce(message: string): void;
  destroy(): void;
}
```

Use real buttons/links/dialog semantics, visible focus, `aria-live` status, `44 px` targets, exact disclosure, and score ranks from the approved spec. Clipboard failure must select/reveal the contract and announce `COPY MANUALLY`.

Add `BRAND.xUrl = 'https://x.com/memesofsanic'`. Implement `renderScoreCard(snapshot, rank, siteUrl): Promise<Blob>` in `src/ui/scoreCard.ts`: load `/media/sanic-score-card-bg.png`, draw it to a `1200×675` canvas, then draw exact runtime score, rings, rounded distance, rank, `$SANIC`, and site URL with high-contrast bundled/system fonts. Unit-test the formatted values and PNG blob contract with a small canvas/image adapter injection rather than a test-only production method.

`share()` first builds the PNG file. If `navigator.canShare({ files: [file] })` is true, call native share with the file, score text, and URL. Otherwise open `https://twitter.com/intent/tweet?text=<encoded score text>&url=<encoded site URL>` in a safe new tab and expose a separate `SAVE SCORE CARD` image action. Never request X login tokens or silently post.

- [ ] **Step 3: Implement the lifecycle and fixed-step RAF accumulator**

`GameApp` constructs dependencies, loads assets with progress, shows intro, and on start unlocks audio plus simulation. In `requestAnimationFrame`, accumulate at most `0.25 s`, run fixed `1/60 s` steps, render interpolation alpha, and update UI at no more than `20 Hz`. Pause on hidden/blur, resume only from an explicit action, store best score at game-over, and dispose every resource.

When `?e2e=1`, construct the simulation with a deterministic scripted spawn source that includes an early center-lane blocker; the `sanic:e2e-crash` event advances that existing scenario to impact without mutating simulation internals. Reflect phase/lane in data attributes for non-visual assertions.

- [ ] **Step 4: Finish the responsive visual system**

Use local Bangers for display and Space Mono for metrics. Style the canvas full viewport, cobalt glass/ink panels, yellow brush title, a contract pill, loading speedometer, compact HUD, swipe hint, pause/results sheet, static promo fallback, safe-area insets, landscape-short-height rules, and reduced-motion overrides. Keep promotional chrome outside the center gameplay corridor.

- [ ] **Step 5: Make the browser flows pass**

Run: `npx playwright test tests/e2e/game.spec.ts`  
Expected: desktop and mobile projects pass start/control/pause/crash/restart and exact-contract tests.

- [ ] **Step 6: Commit the complete user flow**

```bash
git add index.html src/main.ts src/styles.css src/ui src/app tests/e2e playwright.config.ts
git commit -m "feat: ship the playable sanic flow"
```

---

### Task 9: Add Fallback, Responsive, SEO, and Performance Verification

**Files:**
- Create: `public/media/sanic-og.jpg`
- Create: `vercel.json`
- Modify: `index.html`
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/app/gameApp.ts`
- Modify: `src/styles.css`

**Interfaces:**
- Consumes: complete local app and generated promo image.
- Produces: crawler-safe metadata, explicit WebGL failure experience, screenshot evidence, and deployment-ready headers.

- [ ] **Step 1: Add failing fallback and mobile-layout tests**

Extend Playwright tests to load `/?forceFallback=1`, assert the promo image, contract copy, Pump.fun link, X link, and disclosure remain usable, and capture `test-results/sanic-fallback.png`. Add a mobile test that performs touch swipes, verifies lane changes, opens pause, and asserts the dialog bounding box fits inside `390×844`. Add a completed-run share test that verifies a nonempty PNG blob and the encoded X compose fallback when file sharing is unavailable.

Run: `npx playwright test tests/e2e/game.spec.ts`  
Expected: new fallback/mobile assertions fail before implementation.

- [ ] **Step 2: Implement explicit WebGL/static fallback and context-loss messaging**

Before creating `WorldRenderer`, attempt a WebGL 2 context unless `forceFallback=1`. If unavailable, use `GameUI.showUnsupported('YOUR BROWSER IS TOO SLOW FOR SANIC')` with the approved promo art and fully functional contract/link controls. On context loss, pause and display `SANIC HIT A DIMENSIONAL WALL`; on restoration, rebuild pools and offer resume.

- [ ] **Step 3: Produce social metadata and deployment headers**

Run:

```bash
magick public/media/sanic-game-promo.png -resize '1200x630^' -gravity center -extent 1200x630 -strip -quality 88 public/media/sanic-og.jpg
```

Add canonical-relative Open Graph/Twitter tags for title, description, image, and theme color. Create `vercel.json` with immutable one-year cache headers for `/models/*` and `/media/*`, while `index.html` uses `Cache-Control: public, max-age=0, must-revalidate`.

- [ ] **Step 4: Measure transfer and rendering behavior**

Run:

```bash
npm run build
du -ch dist/models/*.glb dist/media/sanic-og.jpg dist/assets/* | tail -n 1
npx playwright test
```

Expected: build succeeds; essential assets total under `10 MB`; all desktop/mobile/fallback tests pass. Inspect desktop and mobile screenshots for clipped UI, unreadable text, wrong character silhouette, missing rings, and scenery crossing gameplay lanes.

- [ ] **Step 5: Commit deployment polish**

```bash
git add public/media/sanic-og.jpg vercel.json index.html src/app/gameApp.ts src/styles.css tests/e2e/game.spec.ts
git commit -m "feat: harden sanic launch experience"
```

---

### Task 10: Final Verification and Direct Vercel Deployment

**Files:**
- Create: `README.md`
- Generated and ignored: `.vercel/` project linkage.

**Interfaces:**
- Consumes: clean committed production build.
- Produces: verified `.vercel.app` production URL with no GitHub remote.

- [ ] **Step 1: Run the complete clean verification gate**

Run:

```bash
npm ci
npm run test
npm run build
npx playwright test
git diff --check
git status --short
git remote -v
```

Expected: all unit and browser tests pass, build succeeds, no whitespace errors, worktree contains only intentional generated test artifacts or is clean, and `git remote -v` prints nothing.

- [ ] **Step 2: Perform a real-browser quality pass against the production build**

Run `npm run preview`, then use Playwright to inspect `1440×900` and `390×844`: start, change lanes, jump, collect a ring, pause/resume, trigger game-over, restart, mute/unmute, copy contract, and open the Pump.fun link in a captured new tab. Check the console for uncaught errors and the network log for unexpected third-party requests.

Expected: one full cycle works on both viewports with no uncaught console errors and only same-origin asset requests plus the user-initiated Pump.fun navigation.

- [ ] **Step 3: Deploy directly from the local checkout**

Run: `vercel --prod --yes`  
Expected: Vercel links a new `sanic-run` project and prints a nonempty HTTPS production URL. Do not run `gh`, do not add a Git remote, and do not use the PAT from chat.

- [ ] **Step 4: Verify the exact deployed artifact**

Against the printed production URL, verify HTTP `200`, OG image `200`, all three GLBs `200`, exact contract copy, exact Pump.fun href, start/play/crash/restart, desktop/mobile layout, and no console errors. Re-run the Playwright smoke test with `BASE_URL` set to the production URL.

- [ ] **Step 5: Record the handoff**

Add a concise `README.md` containing local commands, asset regeneration commands, direct Vercel deploy command, production URL, contract address, and canonical personal repository. Commit only if the README changed:

```bash
git add README.md
git commit -m "docs: add sanic launch handoff"
```

Final report must include the production URL, verification commands and results, asset sizes, the saved Blender source path, the promo path, and confirmation that the repo still has no Git remote.
