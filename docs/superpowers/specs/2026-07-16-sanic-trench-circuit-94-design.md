# SANIC Trench Circuit '94 UI Design

## Objective

Turn the website shell into an original 1990s 16-bit cartridge title screen and
arcade HUD while leaving the Three.js runner visually untouched. The result
should feel like a complete game from boot through title, play, pause, and
results rather than a modern crypto landing card with pixel decoration.

## Creative direction

The theme is **Trench Circuit '94**. It uses a compact console-screen grammar:
dark indigo cabinet framing, stepped cobalt panels, cream keylines, restrained
chrome highlights, gold selection states, one asymmetric checker rail, and
integer-stepped motion. All visuals are original CSS and text treatments. No
franchise logo geometry, character silhouette, landscape copy, traced sprite,
third-party texture, or protected game asset enters the UI.

The shell must avoid nostalgia clutter. It will not use global CRT curvature,
chromatic aberration, VHS noise, bloom, continuous title bobbing, or a smooth
neon synthwave grid. Scanline texture, where present, stays faint and is hidden
during active play so it never degrades the WebGL canvas.

## Visual system

The UI palette is deliberately narrow:

- cabinet ink: `#07092b`
- panel indigo: `#102b70`
- game cobalt: `#1740b8`
- aqua highlight: `#62eadb`
- selection gold: `#ffd43b`
- stepped orange shadow: `#ef7d2c`
- cream keyline: `#fff4d0`
- coral alert: `#ed4b4f`

Indigo and ink carry most of the screen. Gold identifies the selected action,
rings, and rewards; it is not used as a generic fill on every control. The
standard frame is a dark outer keyline, cream inner keyline, cobalt inset, and
hard down-right shadow on a four-pixel desktop unit and a two-to-three-pixel
mobile unit. Blur, glass, translucent utility cards, and rounded corners remain
absent.

`Press Start 2P` owns display headings, stage labels, menu selection, HUD labels,
and values. `Space Mono` owns contract text, instructions, and legal copy. The
title becomes an upright stepped slab: a separate gold coin-slot `$` tile beside
cream/aqua `SANIC` letters with cobalt and ink extrusion. It must not reproduce
the italic yellow sweep or surrounding geometry of an existing franchise logo.

## Title-screen structure

`GameUI` keeps the canvas and UI as body siblings. The canvas receives no wrapper,
filter, transform, or pixelated image-rendering mode. The UI root retains
`data-ui-theme="pixel-16"` and adds
`data-arcade-shell="trench-circuit-94"` as the stable enhancement hook.

The attract layer gains a pointer-transparent viewport bezel, faint raster sky,
two horizontal parallax ridge bands, a single foreground checker rail, and a
compact decorative score strip reading `1 PLAYER`, `HI 000000`, and `1994 MODE`.
Existing CSS clouds, rings, hills, and perspective grid are either restyled into
this grammar or removed; they are not stacked on top as unrelated effects.

Loading, intro, pause, and results each receive the same reusable stage marquee:

- `STAGE 01`
- `TRENCH ZONE`
- `ACT 1`
- a cream-and-ink checker strip
- a stepped chrome bar
- one decorative gold ring

The intro hierarchy is title first, selected action second, status ticker third,
and service information last. The real start button is labeled `PRESS START`,
contains the persistent selection cursor, and keeps `data-action="start"`. Its
supporting line may still say `GOTTA GO FAST`, but there is only one primary
start affordance.

The contract, Copy action, Pump.fun link, X account link, sound control, game
controls, and disclosure all remain available. They are grouped into a compact
opaque service deck below the start row rather than presented as many equal
marketing cards. The meme reel becomes a narrow status channel with one line at
a time and keeps all current meme copy, including the Ansem line.

## Gameplay HUD and phase treatment

During play the attract artwork, viewport bezel, and non-game scanline texture
are hidden and their animations are paused. The HUD becomes a coherent cartridge
strip: rings and score are primary, combo and distance are secondary, and Sound
and Pause remain reachable. Existing live values, actions, and accessible labels
do not change. On desktop the stage identity can occupy a small non-interactive
plaque; on narrow mobile the metrics and actions remain one compact safe-area row
without overlapping the runner.

Pause and results use native dialogs and repeat the marquee inside the dialog so
it remains above the native backdrop. Pause is titled `PAUSED` and behaves as a
console menu with Resume as the selected action. Results are titled `GAME OVER`
and present score rows with dividers rather than four unrelated cards. Contract
and external links remain in Pause; results keep Restart, Share Score, and Save
Card behavior.

Attract animations remain paused behind Pause and Game Over. Dialog content is
opaque enough for small text and does not depend on motion to communicate state.

## Motion

Motion uses integer steps only:

- the title enters once through three or four stepped frames and then holds;
- far, middle, and near scenery bands move at approximately `24s`, `14s`, and
  `8s` respectively;
- the selected menu cursor performs a restrained two-frame four-pixel nudge;
- the status ticker changes every `3.6s` using the existing six deterministic
  lines;
- the checker rail advances in discrete cells;
- decorative rings rotate in a low-frame-count stepped loop.

No essential text begins hidden or waits for an animation to become usable.
`prefers-reduced-motion: reduce` disables all parallax, title, ticker, checker,
cursor, ring, hover, and transition motion. The selected action remains clear
through a static cursor and inverse gold fill.

## Responsive behavior

Desktop keeps the title/menu composition on the left and lets the live game
world remain visible on the right. The cabinet frame stays within safe areas and
never captures pointer input.

At `390x844`, the title, stage marquee, status line, and Press Start action are
visible without horizontal scrolling. Decorative depth is reduced before text
size or controls are reduced. Contract, links, controls, and disclosure remain
reachable in the intro's existing bounded vertical scroll region when required.
The live HUD keeps all four metric values and two controls collision-free at
`390px`, preserving the current regression contract.

At `320x568` and `844x390`, essential actions remain within the viewport or the
existing bounded panel/dialog scroller. Tertiary scenery, extra rings, the
decorative score strip, and nonessential title copy may hide; contract, launch
links, disclosure, Sound, Pause, Resume, Restart, and Share do not hide.

## Accessibility and interaction

- All decorative shell elements use `aria-hidden="true"` and
  `pointer-events: none`.
- The real start button has accessible name `PRESS START` and a minimum
  `44x44px` target.
- Loading exposes a named progressbar with `aria-valuemin="0"`,
  `aria-valuemax="100"`, and synchronized `aria-valuenow` and
  `aria-valuetext`.
- Normal text reaches `4.5:1` contrast; large display text and focus indicators
  reach `3:1`.
- Pixel labels remain at least `8.32px` at the existing mobile baseline, while
  body and legal copy use the more readable `Space Mono` sizes already present.
- Native dialog focus, Escape behavior, keyboard controls, swipe controls,
  clipboard fallback, share flow, and WebGL context recovery remain unchanged.

## Implementation boundaries

`src/ui/gameUI.ts` owns the small semantic markup additions and loading progress
attributes. `src/pixel-ui.css` owns the arcade-shell visual system and responsive
behavior; `src/styles.css` changes only if base geometry or overflow needs a
targeted adjustment. No new runtime dependency, bitmap, SVG, font, audio asset,
WebGL material, simulation rule, or model is needed.

The score-card PNG renderer is outside this pass. The 3D world, camera, runner,
spin ball, obstacle spawning, collision, music, contract value, Pump.fun URL, and
X URL remain untouched.

## Test contract

Playwright tests are written before UI implementation and must prove:

1. The root advertises the new arcade-shell hook while retaining `pixel-16`.
2. Intro exposes the stage marquee and a real `PRESS START` button.
3. Checker, chrome, ring, bezel, raster, title, menu, and ticker treatments have
   their intended hard-edged CSS primitives and stepped animations.
4. The canvas remains a direct body child with `image-rendering: auto`, no
   filter, and no transform.
5. Entering play hides and pauses every attract/cabinet layer.
6. Loading progress attributes stay synchronized with the visible percentage.
7. Pause and Game Over show phase-specific headings and in-dialog marquees while
   preserving focus and actions.
8. Reduced-motion mode leaves no active arcade-shell animation while keeping
   selection and text visible.
9. `390x844`, `320x568`, and `844x390` retain legal controls, avoid horizontal
   overflow, and keep required actions reachable.
10. Existing real-GLB, audio, input, clipboard, share, context-loss, and gameplay
    tests continue to pass on desktop and mobile.

## Acceptance criteria

- A first glance reads as a complete original 16-bit console title screen, not a
  generic pixel-styled website.
- `STAGE 01 / TRENCH ZONE / ACT 1`, the stepped title, and the selected Press
  Start row establish a clear title-screen hierarchy.
- The game canvas remains crisp, smooth, full-viewport, and unfiltered.
- Every required crypto link and disclosure remains accessible.
- Desktop, portrait mobile, short mobile, and short landscape remain usable.
- Reduced-motion and keyboard-only use preserve all state and selection cues.
- No protected game asset or recognizable franchise-logo construction is used.
