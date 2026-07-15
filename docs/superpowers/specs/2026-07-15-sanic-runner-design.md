# $SANIC WebGL Runner — Design Specification

**Date:** 2026-07-15  
**Status:** Approved design, pending implementation  
**Project root:** `/home/alex/projects/sanic-run`  
**Token:** `$SANIC`  
**Contract address:** `CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump`

## Product Summary

Build a single-page, full-screen promotional website whose hero is a genuinely playable third-person WebGL endless runner. The player controls a muscular, deliberately off-model blue meme speedster through a saturated forest, changes among three lanes, jumps obstacles, and collects spinning gold `$SANIC` ring-coins. The experience should feel like an unusually polished playable meme rather than a conventional token landing page.

The site is entertainment and promotion only. It does not connect a wallet, award tokens, display live price data, or imply financial returns.

## Creative Direction

### Character

The supplied artwork at `docs/references/sanic-source.png` is the primary character reference. The 3D interpretation must preserve its recognizable traits without importing or tracing an existing game model:

- Cobalt-blue body with a broad chest, exaggerated shoulders, thick arms, and heroic bodybuilder proportions.
- Large angular quills forming a strong backward-pointing silhouette.
- Sleepy white eye shapes, heavy black lids, dark nose, beige muzzle, and intentionally awkward human-like lips.
- Oversized clean white gloves and oversized glossy red running shoes with white straps and warm off-white soles.
- A small handwritten `I LOVE TO GO FAST` detail across the brow or on a wearable headband, legible only in close views.
- A balance of clean production modeling and intentionally strange meme anatomy. The model should look sculpted and finished, not like a primitive placeholder.

Blender will retain a high-detail master with subdivision and bevel modifiers. The browser receives a separate optimized rigged export that preserves the silhouette and smooth shading.

### World

The runner takes place in a lush, surreal forest at golden hour:

- A three-lane dirt trail with grass borders, rolling terrain, cyan atmospheric haze, oversized trees, ferns, flowers, rocks, and mushrooms.
- Saturated greens, electric cyan shadows, warm sunlight, and bright gold collectibles.
- Layered parallax scenery, drifting pollen, speed streaks, dust puffs, and subtle camera banking create a strong sensation of speed.
- Reusable forest modules are instanced and recycled around the player to create an endless world.
- Meme signs appear as environmental jokes rather than blocking marketing panels: `STIMMY LANE`, `FOR THE TRENCHES`, `SIDELINED & COPING`, and `RETURN TO MEMES`.

The Ansem references are topical parody/background flavor only. The page must not claim or imply endorsement, ownership, partnership, or affiliation.

### Collectible and Obstacles

The collectible is a thick, polished gold ring-coin with beveled edges, a small inset `$` mark, warm emissive highlights, and a rotating glint. Ring-coins appear in readable trails that guide lane changes and jumps.

Obstacle families are visually distinct and readable at speed:

- Fallen logs: jump or change lane.
- Red candle barriers: change lane.
- Wooden `FUD` barricades: change lane.
- Mud gaps: jump.
- Static scenery never intrudes into the valid collision corridor.

Every generated obstacle row must leave at least one safe lane. Early patterns teach one action at a time; later patterns combine lane changes and jumps.

## Player Experience

### Entry

The WebGL world begins loading immediately. A compact loading state shows progress over a moving or poster-like forest composition. Once essential assets are ready, the intro presents:

- `$SANIC` wordmark and `I LOVE TO GO FAST` tagline.
- Primary `GOTTA GO FAST` start button.
- Exact contract address with a copy control.
- Pump.fun link derived from the exact contract address.
- Official project X link: `https://x.com/memesofsanic`.
- Tiny control hints and sound toggle.
- Concise entertainment/not-financial-advice disclaimer.

Starting the game removes most promotional UI and enables audio from the required user gesture.

### Controls

- Desktop: `A`/left arrow and `D`/right arrow change lanes; `W`, up arrow, or space jumps; `P` or escape pauses.
- Touch: swipe left/right changes lanes; swipe up jumps; a visible pause control remains available.
- Lane changes are discrete and eased rather than free steering.
- Input buffering accepts a lane or jump command slightly before the current transition completes, preventing controls from feeling dropped.

### Core Loop

1. Sanic runs forward automatically.
2. The player follows coin trails, changes lane, and jumps obstacles.
3. Speed and pattern complexity increase with distance.
4. Collecting ten consecutive ring-coins raises the score multiplier by one, up to `5x`.
5. A missed collectible resets the consecutive-ring counter but not the run.
6. Colliding with a gameplay obstacle triggers a short impact beat and ends the run.
7. The result screen shows score, distance, rings, best score, and a meme rank, then offers `RUN IT BACK`.

Scoring is deterministic and integer based:

- One point per completed meter.
- Each collected ring-coin awards `100 × current multiplier` points.
- Multiplier starts at `1x` and increases after each uninterrupted group of ten collected ring-coins, capped at `5x`.

The initial forward speed is `18` world units per second. It increases smoothly to a maximum of `36` based on distance. Pattern spacing scales with speed so every obstacle remains physically avoidable.

### HUD and Results

During play, the HUD shows only ring count, multiplier, rounded score, distance, sound, and pause. The contract remains available in a small non-obstructive desktop pill and in the pause sheet on mobile.

The game-over sheet supplies one of five score-based meme ranks: `SIDELINED`, `TRENCH TOURIST`, `STIMMY SPRINTER`, `FULL PORT`, or `TOO FAST FOR THE TIMELINE`. It renders a branded score-card PNG in the browser with score, rings, distance, and rank. When native file sharing is supported, the Share action attaches that PNG; otherwise it opens an X compose intent with prefilled score/site text and offers the card as a separate image. It never claims the score has monetary value and never requests X OAuth credentials.

## Information Architecture

This is a single viewport experience, not a multi-section marketing site:

1. WebGL canvas fills the viewport.
2. Branded DOM shell overlays loading, intro, HUD, pause, and results states.
3. A minimal persistent top bar contains the wordmark, contract copy, Pump.fun link, and `https://x.com/memesofsanic` when space permits.
4. Legal text is accessible from the intro and pause sheet without forcing page scrolling.

The supplied X account `https://x.com/memesofsanic` is the only launch social link. Telegram, DexScreener, and any other URLs remain absent until the project owner supplies exact destinations.

## Technical Architecture

### Stack

- Vite and TypeScript.
- Vanilla Three.js and its official GLTF loading/animation utilities.
- Vitest for deterministic game-logic tests.
- Playwright for browser interaction, responsive, and smoke tests.
- Static Vercel deployment with no server runtime.

React and a physics engine are intentionally omitted. The experience has a small fixed collision model, so a focused TypeScript state machine and analytic bounding volumes provide less bundle weight and more predictable mobile performance.

### Runtime Boundaries

- `GameApp`: owns lifecycle states (`loading`, `intro`, `playing`, `paused`, `gameOver`, `unsupported`) and coordinates the renderer, simulation, and UI.
- `GameSimulation`: fixed-step, renderer-independent rules for forward motion, lane transitions, jump trajectory, scoring, collisions, and difficulty.
- `SpawnDirector`: seeded, deterministic generation of safe coin and obstacle patterns.
- `WorldRenderer`: Three.js scene, camera, lighting, animation mixer, instancing pools, particles, and visual interpolation.
- `AssetLoader`: GLB loading, progress, caching, validation, and fallback meshes.
- `InputController`: keyboard, pointer, and touch gestures normalized to semantic commands.
- `AudioController`: user-gesture-safe synthesized effects and ambience with persisted mute state.
- `GameUI`: DOM state projection, accessible buttons, clipboard/share operations, and live score announcements where appropriate.
- `Storage`: versioned parsing and persistence of high score, mute, and reduced-effects preferences.

The simulation exposes immutable snapshots to rendering and UI. Rendering must not mutate score, collisions, or spawn state.

### Game Loop and Collision

Simulation runs at a fixed `60 Hz` step with an accumulator and a cap on catch-up work after a suspended tab. Rendering uses interpolated snapshots at `requestAnimationFrame` frequency. When hidden, the game pauses rather than advancing in the background.

Collision uses simple character and obstacle bounding volumes defined in model metadata/configuration. The character has grounded and jumping volumes; collectibles use forgiving sphere-distance checks. Visual meshes never determine gameplay collision directly.

### Asset Pipeline

Blender MCP is used to create and inspect the source assets. Expected outputs are:

- `blender/sanic-source.blend`: high-detail master, clean named objects, materials, armature, and source animation actions.
- `public/models/sanic-runner.glb`: optimized browser character with `Idle`, `Run`, `Jump`, and `Crash` clips.
- `public/models/sanic-ring.glb`: gold ring-coin collectible.
- `public/models/forest-kit.glb`: modular tree, grass, fern, rock, mushroom, log, barricade, candle, and sign pieces.

The high-detail master should retain approximately `250k–500k` evaluated triangles. The browser character targets `45k–80k` triangles, one armature, no more than six materials, and a compressed transfer size below `4 MB`. Environment pieces target a combined compressed transfer size below `3 MB`. Exact topology may vary to preserve quality, but initial essential transfer should remain below `10 MB` on the deployed site.

Character animation uses a compact armature and clean deformation or rigid cartoon segment weighting as appropriate. The running animation must read clearly from the rear three-quarter gameplay camera. The web renderer uses Three.js `AnimationMixer` and cross-fades between clips.

### Rendering and Performance

- WebGL 2 is required for the playable renderer; devices without it receive the branded static fallback.
- Trees, grass, rocks, coins, and repeated props use instanced meshes or pooled cloned scenes.
- Device pixel ratio is clamped to `1.75` on desktop and `1.5` on mobile.
- One shadow-casting directional light is used with a bounded shadow area; low-power mode disables dynamic shadows and expensive particles.
- Tone mapping, fog, and lightweight bloom-like emissive treatment provide the final look without a large post-processing chain.
- Resize, orientation change, context loss, and context restoration are handled explicitly.
- Target is stable `60 FPS` on a current desktop and at least `30 FPS` on a representative modern mobile device.

## Audio

All initial audio is synthesized through the Web Audio API to avoid licensed music and large downloads:

- Short gold pickup arpeggio with pitch progression across combos.
- Jump whoosh, lane dash tick, collision thud, button chirp, and subtle wind loop.
- Audio begins only after the start gesture, includes a persistent mute toggle, and releases/resumes cleanly across tab visibility changes.

No music, voice, or sound effects from an existing game franchise are used.

## Resilience and Accessibility

- If WebGL is unsupported, show the supplied art in a branded static composition with contract copy and Pump.fun link.
- If a GLB fails, render a clearly branded procedural fallback for that asset and allow the game to start when possible.
- Clipboard failure reveals/selects the contract text and reports a useful status rather than silently failing.
- Respect `prefers-reduced-motion`: remove camera shake and speed streaks, soften lane/camera easing, and default to low effects.
- All DOM controls are keyboard reachable, have visible focus styles, and use descriptive labels.
- Touch targets are at least `44 × 44` CSS pixels.
- Foreground UI must meet readable contrast over the moving scene using translucent backing plates and text shadows.
- Pause automatically on tab hide or window blur during active play.

## Brand, Safety, and Legal Copy

The project uses `$SANIC`, the exact supplied contract, original custom 3D assets based on the supplied meme artwork, and general speedster parody language. It must not use official franchise logos, models, music, UI art, or copied level assets.

The intro/pause legal copy will state: `$SANIC is a memecoin made for entertainment. No utility, no promises, no financial advice. Verify the contract and only risk what you can afford to lose. Not affiliated with or endorsed by Ansem, SEGA, or Sonic the Hedgehog.`

External links open safely with `noopener,noreferrer`. The site requests no wallet permissions, signatures, personal information, or payments.

## SEO and Sharing

- Page title: `$SANIC — I Love To Go Fast`.
- Description: `Run the trenches. Stack rings. Go irresponsibly fast in the playable $SANIC WebGL runner.`
- The generated launch key art at `public/media/sanic-game-promo.png` is used as the static Open Graph image so social crawlers never need WebGL.
- Theme color is cobalt blue.
- Share copy includes score and site URL only; the contract remains visible on the linked page. A generated 16:9 score-card background keeps a clear stats zone so runtime canvas text remains crisp and exact.

## Verification Strategy

### Unit Tests

Vitest covers:

- Deterministic seeded pattern output and the invariant that each obstacle row has a safe solution.
- Lane bounds, buffered input, and transition timing.
- Jump trajectory and collision immunity over valid jump obstacles.
- Score, combo, multiplier cap, missed-ring reset, and high-score persistence parsing.
- Speed progression and spawn-spacing playability constraints.

### Browser Tests

Playwright covers:

- Intro renders and begins a run from a real click.
- Keyboard lane changes and jump update the simulation.
- Touch swipe gestures work in a mobile viewport.
- Pause/resume and visibility pause preserve state.
- Contract copy displays success and uses the exact address.
- The supplied X account link is exact, and score-card sharing produces a PNG plus a correctly encoded X compose fallback.
- Game-over and restart complete without page reload.
- Unsupported/fallback UI remains useful when WebGL initialization is forced to fail.
- Desktop `1440 × 900` and mobile `390 × 844` screenshots have no clipped critical UI.

### Production Checks

- Type checking, unit tests, browser tests, and `vite build` pass from a clean install.
- Essential deployed transfer is below `10 MB` and no unexpected third-party requests occur.
- Live Vercel URL returns `200`, loads the GLBs, starts a run, copies the exact contract, and reaches the correct Pump.fun contract URL.
- Browser console contains no uncaught errors during one complete run/restart cycle.

## Deployment

Deploy as a Vercel project named `sanic-run` and use its `.vercel.app` production URL until the custom domain is verified. Publish the audited source only to the personal `pasekaalex/sanic-run` repository.

## Non-Goals for Version One

- Wallet connection, token claiming, or on-chain transactions.
- Live charts, market cap, holder counts, or price APIs.
- Online leaderboard, accounts, database, multiplayer, or anti-cheat.
- Multiple levels, character selection, shop, token gating, or downloadable game build.
- Invented community/social links.
- Claims of official affiliation or financial return.

## Acceptance Criteria

The version-one build is complete when:

1. The deployed URL presents a polished full-screen `$SANIC` experience on desktop and mobile.
2. The custom buff Sanic, ring-coin, and forest kit created through Blender are visibly used in gameplay.
3. A user can start, switch among three lanes, jump, collect rings, build a multiplier, collide, receive results, and restart.
4. The exact contract can be copied and the Pump.fun link targets that exact contract.
5. The topical meme signs are visible without claiming Ansem affiliation.
6. The site degrades to a useful branded fallback if WebGL or an asset fails.
7. Automated tests and production checks described above pass.
8. The final Vercel production URL is verified in a real browser.
9. The exact X account is reachable and a completed run produces a branded score-card share image on desktop and mobile.
