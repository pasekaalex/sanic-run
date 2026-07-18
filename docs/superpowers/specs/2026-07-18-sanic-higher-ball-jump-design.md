# SANIC Higher Ball Jump Design

**Date:** 2026-07-18

## Goal

Make the existing ball-spin jump visibly higher and let SANIC travel slightly
farther forward while airborne, without making the landing feel floaty.

## Approved Gameplay Tuning

- Raise the deterministic jump apex from `3.1` to `4.3` world units.
- Increase ascent time from `0.31` to `0.35` seconds.
- Increase descent time from `0.25` to `0.28` seconds.
- Keep the `0.07`-second anticipation and `0.05`-second landing recovery.
- Increase total airborne time from `0.56` to `0.63` seconds and total jump
  state time from `0.68` to `0.75` seconds.
- Retain stronger descent gravity than ascent gravity so the landing remains
  quick and decisive.

## Architecture

The deterministic simulation remains the sole owner of vertical position,
collision clearance, jump progress, and landing time. The renderer continues
to derive the ball-spin presentation from simulation progress, so no model,
animation clip, or renderer-specific vertical offset changes are needed.

The existing equations derive launch velocity and rise/fall gravity from the
apex and phase durations. Updating the three approved constants therefore
preserves coarse/fine timestep determinism and exact ground snapping at
touchdown.

## Collision and Presentation

- The physical `playerY` value and the rendered character height remain aligned.
- Jumpable obstacle clearance continues to use the simulation height.
- Coin collection continues to use the simulation height.
- The existing ball-spin progress window remains unchanged and naturally lasts
  slightly longer because the jump itself lasts slightly longer.
- Forward speed and zone difficulty remain unchanged; the longer airborne phase
  produces the requested modest increase in forward travel.

## Testing

Use test-driven development:

1. Change the apex regression expectation to require a peak near `4.3`.
2. Add timing assertions that the character remains airborne through the new
   longer flight and lands exactly at the approved touchdown time.
3. Run the focused simulation tests and then the complete JavaScript, Python,
   PWA artifact, and production build gates.

## Non-Goals

- No changes to the SANIC mesh, rig, GLB animation clips, or spin-ball asset.
- No changes to obstacle dimensions, spawn spacing, coin layouts, forward
  speed, input handling, or camera behavior.
- No double jump, variable-height jump, or new control.

## Release

Publish the tested change to the public `pasekaalex/sanic-run` main branch,
perform one production deployment, and verify the live `www.sanic.fun`
response and production commit.
