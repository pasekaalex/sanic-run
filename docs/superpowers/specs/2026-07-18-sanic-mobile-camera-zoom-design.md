# SANIC Mobile Camera Zoom Design

**Date:** 2026-07-18

## Goal

Show more of the runner, lanes, obstacles, and surrounding zone on portrait
mobile screens without changing the established desktop or landscape
composition.

## Approved Framing

- Apply the new framing when the canvas is narrower than `700` CSS pixels and
  its height is at least its width.
- Increase the portrait-mobile vertical field of view from `61` to `66`
  degrees.
- Move the portrait-mobile camera Z position from `9.9` to `11.4`.
- Keep the mobile lateral offset at `2.25`.
- Keep the mobile look-target Z at `-8.5`.
- Keep the camera height, player-follow response, jump tracking, lane-change
  bank, near/far clipping planes, and device-pixel-ratio limits unchanged.
- Preserve the existing narrow-landscape framing at widths below `700` when
  height is less than width: `61`-degree field of view, camera Z `9.9`,
  lateral offset `2.25`, and look-target Z `-8.5`.
- Keep widths of `700` CSS pixels and above on the existing desktop framing:
  `53`-degree field of view, camera Z `9.1`, lateral offset `3.45`, and
  look-target Z `-10.5`.

The combined field-of-view and distance adjustment provides roughly twenty
percent more useful scene context on narrow portrait screens while preserving
the current viewing angle and runner position.

## Architecture

Create a small pure camera-framing module that returns the field of view,
lateral offset, camera Z, and look-target Z for a given canvas width and height.
Both `WorldRenderer.resize()` and `WorldRenderer.updateCamera()` consume the
same framing result so projection and position cannot drift into separate
breakpoint rules.

The helper has no browser or Three.js dependency. This makes the mobile and
desktop contracts directly testable without constructing a WebGL renderer.

## Responsive Behavior

- `390×844` and other narrow portrait layouts use the new zoomed-out framing.
- Narrow landscape layouts below `700` pixels wide retain the existing mobile
  values.
- `700`-pixel and wider layouts use the existing desktop values.
- `844×390` mobile landscape remains unchanged because its canvas width is
  above the existing `700`-pixel breakpoint.
- Runtime resize continues to recompute both projection and camera position
  from the current canvas dimensions.

## Testing

Use test-driven development:

1. Add a pure unit test proving `390×844` and `699×900` return the approved
   portrait values.
2. Prove `667×375` retains the existing narrow-landscape values.
3. Prove `700×900`, `844×390`, and desktop layouts retain the existing desktop
   values.
4. Prove invalid or zero dimensions fall back safely to one pixel and therefore
   use portrait-mobile framing.
5. Run the full unit suite, TypeScript build, production build, and PWA artifact
   gates.

## Non-Goals

- No changes to camera angle, lane banking, player tracking, jump physics,
  model scale, scene geometry, UI layout, or desktop framing.
- No new user-facing camera setting or zoom control.
- No browser automation that opens a visible browser window.
