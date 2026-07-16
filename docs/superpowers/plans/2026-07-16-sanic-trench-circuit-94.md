# SANIC Trench Circuit '94 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current pixel-decorated landing-card shell with an original, cohesive 1990s 16-bit cartridge title screen and arcade HUD without filtering or changing the Three.js runner.

**Architecture:** `GameUI` adds a small reusable stage-marquee fragment, stable arcade-shell data hooks, accessible loading progress, title/menu structure, and phase-specific dialog copy. `pixel-ui.css` remains the sole themed visual layer and turns those hooks into the cabinet frame, stepped title, parallax attract scene, menu selection, HUD, dialogs, responsive pruning, and reduced-motion behavior. Playwright locks every semantic, visual, phase, and viewport contract before implementation.

**Tech Stack:** TypeScript 7, DOM/native dialogs, CSS, Vite 8, Playwright 1.61, Vitest 4.

## Global Constraints

- Preserve `#game-canvas` as a direct `body` child with `image-rendering: auto`, `filter: none`, and `transform: none`.
- Preserve `data-ui-theme="pixel-16"` and add `data-arcade-shell="trench-circuit-94"`.
- Use only original CSS geometry and text; add no copied logo, sprite, texture, SVG, bitmap, font, or third-party asset.
- Keep the contract value, Copy action, Pump.fun link, X link, disclosure, Sound controls, keyboard input, swipe input, share flow, and context-recovery behavior.
- Keep every decorative element `aria-hidden="true"` and pointer-transparent.
- Use `Press Start 2P` for stage/menu/HUD display copy and `Space Mono` for instructions, contract, and legal text.
- Keep interactive targets at least `44x44px` and normal text at `4.5:1` contrast.
- Disable every new animation and transition under `prefers-reduced-motion: reduce` while keeping a static selected-row cue.
- Support desktop, `390x844`, `320x568`, and `844x390` without horizontal page overflow or hidden required actions.
- Do not modify Three.js, simulation, models, audio synthesis, score-card PNG rendering, or deployment CSP.

---

### Task 1: Define the semantic arcade-shell contract

**Files:**
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/ui/gameUI.ts`

**Interfaces:**
- Consumes: existing `GameUI` phase markup and `setLoading(progress)`.
- Produces: `stageMarqueeMarkup(): string`, `data-arcade-shell="trench-circuit-94"`, `[data-stage-marquee]`, `[data-stage-label]`, `[data-arcade-bezel]`, a real `PRESS START` control, and synchronized loading progressbar attributes.

- [ ] **Step 1: Write the failing intro and loading tests**

Add a helper that gates model requests so the loading state is deterministic:

```ts
const withHeldModels = async (
  page: Page,
  assertion: () => Promise<void>,
): Promise<void> => {
  let release = (): void => undefined;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/models/*.glb', async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto('/?seed=7&e2e=1');
  try {
    await assertion();
  } finally {
    release();
  }
};
```

Add assertions:

```ts
test('boots as a stage-aware cartridge screen with accessible progress', async ({ page }) => {
  await withHeldModels(page, async () => {
    const ui = page.locator('#app-ui');
    await expect(ui).toHaveAttribute('data-ui-theme', 'pixel-16');
    await expect(ui).toHaveAttribute('data-arcade-shell', 'trench-circuit-94');
    await expect(ui).toHaveAttribute('data-phase', 'loading');
    await expect(page.locator('[data-view="loading"] [data-stage-label]')).toHaveText('STAGE 01');
    const progress = page.getByRole('progressbar', { name: 'Loading STAGE 01' });
    await expect(progress).toHaveAttribute('aria-valuemin', '0');
    await expect(progress).toHaveAttribute('aria-valuemax', '100');
    await expect(progress).toHaveAttribute('aria-valuenow', /\d+/);
    await expect(progress).toHaveAttribute('aria-valuetext', /\d+% loaded/);
  });
});

test('presents one selected PRESS START action and complete stage identity', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('[data-view="intro"] [data-stage-label]')).toHaveText('STAGE 01');
  await expect(page.locator('[data-view="intro"] [data-zone-label]')).toHaveText('TRENCH ZONE');
  await expect(page.locator('[data-view="intro"] [data-act-label]')).toHaveText('ACT 1');
  const start = page.getByRole('button', { name: 'PRESS START' });
  await expect(start).toBeVisible();
  await expect(start).toHaveAttribute('data-action', 'start');
  await expect(page.getByText('GOTTA GO FAST', { exact: true })).toBeVisible();
});
```

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
npx playwright test tests/e2e/game.spec.ts \
  --project=desktop-chromium \
  --grep "boots as a stage-aware|presents one selected"
```

Expected: failures for missing `data-arcade-shell`, stage hooks, progressbar role, and `PRESS START` button.

- [ ] **Step 3: Add the reusable marquee and semantic markup**

In `gameUI.ts`, add:

```ts
const stageMarqueeMarkup = (): string => `
  <div class="stage-marquee" data-stage-marquee>
    <span class="stage-marquee__checker" aria-hidden="true"></span>
    <span class="stage-marquee__chrome" aria-hidden="true"></span>
    <span class="stage-marquee__ring" aria-hidden="true"></span>
    <span data-stage-label>STAGE 01</span>
    <strong data-zone-label>TRENCH ZONE</strong>
    <span data-act-label>ACT 1</span>
  </div>
`;
```

Set `root.dataset.arcadeShell = 'trench-circuit-94'`. Insert the marquee into loading, intro, Pause, Results, and Unsupported content. Add this attract decoration before the existing clouds:

```html
<div class="arcade-bezel" data-arcade-bezel aria-hidden="true">
  <span class="arcade-bezel__top"></span>
  <span class="arcade-bezel__right"></span>
  <span class="arcade-bezel__bottom"></span>
  <span class="arcade-bezel__left"></span>
</div>
<div class="arcade-score-strip" data-arcade-score-strip aria-hidden="true">
  <span>1 PLAYER</span><span>HI 000000</span><span>1994 MODE</span>
</div>
```

Change the intro primary button to:

```html
<div class="arcade-menu" data-arcade-menu>
  <span class="arcade-menu__cursor" aria-hidden="true">▶</span>
  <button class="primary-button" type="button" data-action="start">PRESS START</button>
  <small>GOTTA GO FAST</small>
</div>
```

Change dialog headings to `PAUSED` and `GAME OVER`. Keep their ids and `aria-labelledby` connections.

- [ ] **Step 4: Make loading progress accessible**

Change the meter to:

```html
<div class="loading-meter" role="progressbar" aria-label="Loading STAGE 01"
  aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"
  aria-valuetext="0% loaded"><span data-loading-bar></span></div>
```

Add `private readonly loadingMeter: HTMLElement`, select it in the constructor, and update `setLoading`:

```ts
this.loadingMeter.setAttribute('aria-valuenow', String(percent));
this.loadingMeter.setAttribute('aria-valuetext', `${percent}% loaded`);
```

- [ ] **Step 5: Update existing accessible-name assertions and verify GREEN**

Replace existing dialog locators named `Paused`/`Run complete` with `PAUSED`/`GAME OVER`. Replace the intro heading's old primary-action expectation only where it identifies the start button.

```bash
npx playwright test tests/e2e/game.spec.ts --project=desktop-chromium \
  --grep "stage-aware|selected PRESS START|starts, responds|pause dialog|short landscape"
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the semantic shell**

```bash
git add src/ui/gameUI.ts tests/e2e/game.spec.ts
git commit -m "feat: define SANIC cartridge screen"
```

### Task 2: Build the title screen, cabinet frame, and stepped motion

**Files:**
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/ui/gameUI.ts`
- Modify: `src/pixel-ui.css`

**Interfaces:**
- Consumes: Task 1 arcade data hooks and marquee markup.
- Produces: hard-edged bezel/raster/checker/chrome/title/menu/status visuals whose animations stop during play.

- [ ] **Step 1: Write failing computed-style and phase tests**

Extend the attract-mode test with:

```ts
const shell = await page.evaluate(() => {
  const style = (selector: string, pseudo?: string): CSSStyleDeclaration =>
    getComputedStyle(document.querySelector<HTMLElement>(selector)!, pseudo);
  return {
    rootRaster: style('#app-ui', '::before').backgroundImage,
    bezelChecker: style('.arcade-bezel__bottom').backgroundImage,
    bezelPointerEvents: style('[data-arcade-bezel]').pointerEvents,
    chrome: style('.stage-marquee__chrome').backgroundImage,
    checker: style('.stage-marquee__checker').backgroundImage,
    ringRadius: style('.stage-marquee__ring').borderRadius,
    titleFill: style('.title-word').backgroundImage,
    cursorAnimation: style('.arcade-menu__cursor').animationName,
    titleAnimation: style('.title-lockup').animationName,
  };
});
expect(shell.rootRaster).toContain('repeating-linear-gradient');
expect(shell.bezelChecker).toContain('repeating-conic-gradient');
expect(shell.bezelPointerEvents).toBe('none');
expect(shell.chrome).toContain('linear-gradient');
expect(shell.checker).toContain('repeating-conic-gradient');
expect(shell.ringRadius).toBe('50%');
expect(shell.titleFill).toContain('linear-gradient');
expect(shell.cursorAnimation).not.toBe('none');
expect(shell.titleAnimation).not.toBe('none');
```

After starting the run, assert bezel opacity `0`, visibility `hidden`, and the title/cursor/checker animations have `animationPlayState === 'paused'`.

- [ ] **Step 2: Verify RED**

```bash
npx playwright test tests/e2e/game.spec.ts --project=desktop-chromium \
  --grep "original animated 16-bit attract mode"
```

Expected: missing title hooks and absent chrome/bezel/raster styling.

- [ ] **Step 3: Add the stepped title and service deck markup**

Replace the intro heading body while preserving its accessible name:

```html
<div class="title-lockup" data-title-lockup>
  <h1 id="intro-title" aria-label="$SANIC">
    <span class="title-coin" aria-hidden="true">$</span>
    <span class="title-word" aria-hidden="true">SANIC</span>
  </h1>
  <p class="title-subtitle" aria-hidden="true">RING RUNNER</p>
</div>
```

Wrap contract, links, controls, mute, and disclosure in `<div class="service-deck" data-service-deck>`. Keep every existing class, data attribute, label, and element inside the wrapper.

Add `.attract-stage__raster`, `.attract-stage__ridge--far`, and `.attract-stage__ridge--near` as decorative children. Keep the existing grid/checker/ring hooks so old tests and lifecycle behavior remain stable, but restyle them into horizontal parallax bands.

- [ ] **Step 4: Implement the visual primitives in `pixel-ui.css`**

Add tokens:

```css
--arcade-ink: #07092b;
--arcade-indigo: #102b70;
--arcade-cobalt: #1740b8;
--arcade-aqua: #62eadb;
--arcade-gold: #ffd43b;
--arcade-orange: #ef7d2c;
--arcade-cream: #fff4d0;
--arcade-coral: #ed4b4f;
--chrome-dark: #61709a;
--chrome-light: #f4fbff;
```

Implement:

```css
#app-ui[data-arcade-shell='trench-circuit-94']::before {
  position: fixed;
  z-index: -1;
  inset: 0;
  background: repeating-linear-gradient(0deg, transparent 0 3px, rgb(7 9 43 / 14%) 3px 4px);
  content: '';
  opacity: .45;
  pointer-events: none;
}

.stage-marquee__chrome {
  background: linear-gradient(180deg,
    var(--chrome-light) 0 20%, var(--chrome-dark) 20% 42%,
    var(--arcade-ink) 42% 55%, var(--chrome-light) 55% 72%,
    var(--chrome-dark) 72% 100%);
}

.stage-marquee__checker,
.arcade-bezel__bottom {
  background-image: repeating-conic-gradient(
    var(--arcade-cream) 0 25%, var(--arcade-ink) 0 50%
  );
}

.title-word {
  color: var(--arcade-cream);
  background-image: linear-gradient(180deg,
    var(--arcade-cream) 0 32%, var(--arcade-aqua) 32% 58%,
    var(--arcade-cobalt) 58% 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

Use opaque indigo/ink backgrounds, cream keylines, cobalt insets, and hard shadows. Style the title with `Press Start 2P`, an upright layout, and stepped extrusion. Style `.arcade-menu` as one selected inverse-gold row; keep the real button at least `44px` high. Convert `.meme-reel` into a single narrow status strip without changing its six-line deterministic transform.

Define `arcade-title-enter`, `arcade-cursor-nudge`, `arcade-ridge-far`, `arcade-ridge-near`, and stepped checker/ring animation keyframes. Apply `steps(...)` timing only.

- [ ] **Step 5: Verify GREEN and commit**

```bash
npx playwright test tests/e2e/game.spec.ts --project=desktop-chromium \
  --grep "pixel UI shell|animated 16-bit attract|hard-edged pixel panels"
git add src/ui/gameUI.ts src/pixel-ui.css tests/e2e/game.spec.ts
git commit -m "feat: build Trench Circuit title screen"
```

### Task 3: Unify the gameplay HUD, Pause, and Game Over

**Files:**
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/ui/gameUI.ts`
- Modify: `src/pixel-ui.css`

**Interfaces:**
- Consumes: live HUD values/actions and Task 1 marquee.
- Produces: stage-aware cartridge HUD plus phase-specific native dialogs above a quiet attract background.

- [ ] **Step 1: Write failing HUD/dialog assertions**

Add a decorative desktop stage plaque to the expected DOM:

```ts
await beginRun(page);
await expect(page.locator('[data-hud-stage]')).toHaveText(/P1\s+TRENCH ZONE\s+ACT 1/);
expect(await page.locator('.hud').evaluate((element) => getComputedStyle(element).backgroundImage))
  .toContain('linear-gradient');
```

In the phase-flow test, assert:

```ts
await expect(page.getByRole('dialog', { name: 'PAUSED' })).toBeVisible();
await expect(page.locator('.pause-dialog [data-stage-label]')).toHaveText('STAGE 01');
await expect(page.getByRole('button', { name: 'RESUME' })).toBeFocused();

await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
await expect(page.getByRole('dialog', { name: 'GAME OVER' })).toBeVisible();
await expect(page.locator('.results-dialog [data-stage-label]')).toHaveText('STAGE 01');
await expect(page.getByRole('button', { name: 'RUN IT BACK' })).toBeFocused();
```

Assert `.results-grid div` has `borderLeftWidth === '0px'` for the non-first rows and an opaque shared background on `.results-grid`.

- [ ] **Step 2: Verify RED**

```bash
npx playwright test tests/e2e/game.spec.ts --project=desktop-chromium \
  --grep "starts, responds|cartridge HUD"
```

Expected: missing HUD stage hook and old individually boxed result rows.

- [ ] **Step 3: Add stage plaque markup and phase CSS**

Insert as the first HUD child:

```html
<p class="hud__stage" data-hud-stage aria-hidden="true">
  <span>P1</span><strong>TRENCH ZONE</strong><span>ACT 1</span>
</p>
```

Style `.hud` as one opaque cartridge strip with a cream keyline and hard shadow.
Keep the existing four `.hud__metric` elements and both `.hud-button` actions.
Use dividers rather than six independent identical boxes. Preserve current mobile
grid geometry and the existing no-overlap test.

Pause and Results reuse the same marquee and cabinet frame. Set Pause accent to
aqua, Game Over accent to coral, and selection to gold. Freeze every attract
animation under both `data-phase='paused'` and `data-phase='gameOver'`.

- [ ] **Step 4: Verify GREEN and commit**

```bash
npx playwright test tests/e2e/game.spec.ts --project=desktop-chromium \
  --grep "cartridge HUD|starts, responds|context loss"
git add src/ui/gameUI.ts src/pixel-ui.css tests/e2e/game.spec.ts
git commit -m "feat: unify SANIC arcade HUD and dialogs"
```

### Task 4: Lock responsive and reduced-motion behavior

**Files:**
- Modify: `tests/e2e/game.spec.ts`
- Modify: `src/pixel-ui.css`
- Modify only if geometry cannot be expressed in the theme: `src/styles.css`

**Interfaces:**
- Consumes: Tasks 1–3 title, menu, bezel, HUD, and dialogs.
- Produces: bounded title/menu/dialog layouts at `390x844`, `320x568`, and `844x390`, plus zero active arcade animation under reduced motion.

- [ ] **Step 1: Write the failing viewport regression**

Add:

```ts
test('keeps the cartridge title action reachable at 320x568', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  for (const locator of [
    page.locator('[data-view="intro"] [data-stage-marquee]'),
    page.getByRole('button', { name: 'PRESS START' }),
  ]) {
    const box = await locator.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(320);
  }
});
```

Extend short-landscape coverage so the stage marquee, Press Start, Copy,
Pump.fun, X, and disclosure can each be scrolled into view.

- [ ] **Step 2: Write the failing reduced-motion regression**

After `page.emulateMedia({ reducedMotion: 'reduce' })` and intro load:

```ts
expect(await page.locator('#app-ui').evaluate((ui) =>
  ui.getAnimations({ subtree: true }).filter((animation) =>
    animation.playState === 'running'
  ).length
)).toBe(0);
await expect(page.locator('.arcade-menu__cursor')).toBeVisible();
await expect(page.getByRole('button', { name: 'PRESS START' })).toBeVisible();
```

- [ ] **Step 3: Verify RED**

```bash
npx playwright test tests/e2e/game.spec.ts --project=mobile-chromium \
  --grep "320x568|short landscape|reduced motion|HUD controls"
```

Expected: new ornament overflows or remains animated before responsive rules are added.

- [ ] **Step 4: Implement responsive pruning**

At `max-width: 600px`, reduce the pixel unit, title size, frame shadow, and
marquee columns; hide the decorative score strip, extra rings, and far ridge.
Keep Press Start above the service deck. Preserve the existing intro/dialog
bounded scroller for service and legal copy.

At `max-width: 360px`, hide `.hud__stage` and the existing distance metric,
reduce title extrusion, and keep service-deck children full width.

At short landscape, hide title subtitle, decorative score strip, far ridge,
and nonessential attract tokens before shrinking text. Do not hide contract,
launch links, disclosure, Sound, Pause, Resume, Restart, or Share.

Under reduced motion, explicitly include every new pseudo-element and child in
the existing `animation: none !important; transition: none !important` rule.

- [ ] **Step 5: Verify GREEN and commit**

```bash
npx playwright test tests/e2e/game.spec.ts --project=mobile-chromium \
  --grep "320x568|short landscape|reduced motion|HUD controls"
git add src/pixel-ui.css src/styles.css tests/e2e/game.spec.ts
git commit -m "fix: harden SANIC arcade shell on mobile"
```

### Task 5: Visual QA and regression review

**Files:**
- Review: `src/ui/gameUI.ts`
- Review: `src/pixel-ui.css`
- Review: `src/styles.css`
- Review: `tests/e2e/game.spec.ts`

**Interfaces:**
- Consumes: completed UI implementation.
- Produces: inspected screenshots and a reviewer verdict with no unfixed Critical or Important findings.

- [ ] **Step 1: Run the local production build**

```bash
npm test
npm run build
npm run preview -- --host 127.0.0.1
```

Expected: `96` or more unit tests pass, Vite build succeeds with only the known chunk-size advisory, and the preview serves successfully.

- [ ] **Step 2: Capture and inspect phase screenshots**

With Playwright and the real bundled Chromium, capture at `1440x900`,
`390x844`, `320x568`, and `844x390`:

- loading held before model release;
- intro with Press Start and service deck;
- playing with real GLBs and HUD;
- paused dialog;
- Game Over dialog.

Reject if the result still reads as a rounded marketing card, title/menu/service
hierarchy is unclear, legal or links disappear, the runner is obscured, pixel
motifs use fractional scaling, or small text lacks an opaque backing.

- [ ] **Step 3: Run the complete automated gate**

```bash
npm test
npm run build
BASE_URL=http://127.0.0.1:4173 npx playwright test
git diff --check
```

Expected: every unit test passes; all applicable desktop/mobile Playwright tests pass with only intentional project skips; no diff whitespace errors.

- [ ] **Step 4: Request independent review**

Dispatch one read-only reviewer over the full base-to-working-tree delta. Require
file-and-line findings for semantic regressions, pointer interception, mobile
overflow, reduced-motion leaks, contrast, brittle tests, and canvas changes.
Fix every Critical and Important issue test-first, then re-run the full gate.

### Task 6: Publish and verify production

**Files:**
- Commit: completed source, tests, spec, and plan only.
- Do not commit: `dist/`, `.playwright-cli/`, `output/`, screenshots, traces, or local Vercel state.

**Interfaces:**
- Consumes: clean reviewed release branch.
- Produces: `pasekaalex/sanic-run` main and one Ready Vercel production deployment aliased to `sanic.fun`/`www.sanic.fun`.

- [ ] **Step 1: Run the public-repo safety audit**

Use the repository's public-publishing safety workflow to audit the complete
working tree, hidden files, commit history, authorship, messages, and remote
metadata. Review every match and block the push on any private identity,
client/infrastructure, or automated-authorship leak. Keep the workflow's private
pattern list out of public source and documentation.

- [ ] **Step 2: Verify lineage and push once**

```bash
git fetch origin --prune
git rev-list --left-right --count origin/main...HEAD
git push origin HEAD:main
```

Expected: a fast-forward push to `github.com/pasekaalex/sanic-run.git`.

- [ ] **Step 3: Deploy once and verify the live edge**

After confirming no Vercel/deploy process is active:

```bash
npx vercel deploy --prod --force --yes
curl -sS -I https://www.sanic.fun/
```

Expected: one Ready production deployment, aliases for apex and `www`, HTTP 200,
and the existing narrow CSP with blob worker/model support.

- [ ] **Step 4: Run live browser proof**

Open `https://www.sanic.fun/?seed=7&e2e=1` in a fresh browser session at desktop
and `390x844`. Assert every asset diagnostic is `glb`, Press Start launches the
run, the new shell disappears during play, and the console reports zero errors
and zero warnings. Capture final intro and gameplay screenshots for inspection,
then close local browser/server processes.
