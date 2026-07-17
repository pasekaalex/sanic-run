# SANIC PWA + Multi-Zone Expansion Design

**Status:** Approved by the user's repeated “go / continue / autonomous” direction after the design proposal.

## Outcome

Turn the current endless runner into a replayable three-zone arcade run while preserving its audited controls, deterministic simulation, v3 character, rollback model, and safe meme-coin disclosure. The release must work on desktop and mobile, remain playable when optional media fails, and become installable/offline-safe after one successful online load.

## Experience

The run advances continuously through three authored zones:

| Distance | Stage identity | Speed | Music | Visual language |
| --- | --- | --- | --- | --- |
| 0–839.999 m | Stage 01 — Ringwood Rush | 18 → 24 m/s | 148 BPM | bright grass, palms, checker cliffs |
| 840–1,959.999 m | Stage 02 — Liquidity Loop | 24 → 32 m/s | 164 BPM | sunset purple, neon water, ticker signs |
| 1,960 m+ | Stage 03 — Ansem After Dark | 32 → 36 m/s | 178 BPM | moonlit cyan, magenta haze, meme billboards |

Transitions use a short pixel stage card and palette shift without pausing or hiding hazards. The HUD always exposes the current stage and zone to assistive technology. Zone changes are deterministic from distance and never reset score, rings, combo, animation, or input.

Difficulty rises by changing safe template weights and speed, not by shrinking the audited reaction window below 200 ms. Teaching rows remain at the opening. Consecutive forced-jump routes remain forbidden, adjacent full-blocker routes remain within one lane, and every generated row retains a physically safe route.

## Audio

Ship three original, locally authored, mono compressed tracks—no SEGA/Sonic samples and no copied melody:

- `ringwood-rush.mp3`: 148 BPM, bright PSG lead, syncopated bass, restrained drums.
- `liquidity-loop.mp3`: 164 BPM, minor/suspended lead, denser arpeggio, stronger backbeat.
- `ansem-after-dark.mp3`: 178 BPM, urgent lead, octave bass, fuller percussion.

The browser decodes tracks after the Start gesture. A two-slot buffer player loops the active track and crossfades equal-power over 1.2 seconds at zone changes. Only the active and next tracks stay resident. A failed fetch/decode silences music while effects and gameplay continue; it does not fall back to the old oscillator texture. Mute, pause, visibility, game-over, restart, interruption recovery, and destroy semantics remain intact.

## PWA

Provide a standards-based web app manifest, 192 px and 512 px icons, maskable icon, standalone display, theme/background colors, and canonical start URL. A generated service worker precaches the versioned app shell and runtime-caches same-origin successful GET requests for scripts, styles, fonts, models, media, and music.

Navigation is network-first with cached shell fallback, including non-OK network responses. Immutable hashed assets are cache-first. Large game assets are cached as the successful first load requests them, avoiding a fragile all-or-nothing install. Updates use a new cache version, reload an already-controlled page once when the new worker takes over to prevent mixed-version sessions, and delete old SANIC caches. No service worker is registered in the explicit E2E build mode.

## Pixel UI and accessibility

Keep the existing 16-bit cartridge shell and enhance it with:

- stage/zone text projected everywhere the fixed “Trench Zone” label currently appears;
- a brief non-blocking stage-transition overlay;
- per-zone CSS variables for sky, chrome, accent, and scanline colors;
- reduced-motion behavior that removes transition movement but preserves the information;
- live-region announcement once per zone transition.

The game remains fully operable by keyboard, pointer/swipe, and touch. Dialog focus, copy-contract fallback, X link, score-card sharing, disclosures, and unsupported-WebGL fallback remain unchanged.

## Validation

- Unit-test distance boundaries, monotonic speed, deterministic weighted spawns, all fairness invariants, zone UI projection, music crossfade/lifecycle, manifest, service worker generation, and registration gates.
- Validate generated audio duration, sample rate, channel count, bitrate, peak, and total payload.
- Run all existing unit/Python/model validators and both normal/adversarial production builds.
- Use only headless/no-browser-window checks for production smoke.
- Publish only a fast-forward to `pasekaalex/sanic-run` and deploy only the linked Vercel `sanic-run` project at `sanic.fun`.
