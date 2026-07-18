# SANIC Mobile Camera Zoom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Zoom the runner camera out on narrow portrait mobile screens without changing desktop or narrow-landscape framing.

**Architecture:** Add a pure viewport-to-camera-framing helper and use it from both renderer resize and per-frame camera updates. Keep the existing width-only mobile DPR rule independent from framing.

**Tech Stack:** TypeScript, Three.js, Vitest, Vite

## Global Constraints

- Portrait mobile is width below 700 CSS pixels with height greater than or equal to width.
- Portrait mobile uses FOV 66 and camera Z 11.4.
- Narrow landscape and desktop retain their existing values.
- Do not change camera follow, jump tracking, lane bank, near/far planes, or DPR limits.
- Do not open an interactive browser.

### Task 1: Add and integrate deterministic camera framing

**Files:**

- Create: `src/render/cameraFraming.ts`
- Create: `tests/unit/cameraFraming.test.ts`
- Modify: `src/render/worldRenderer.ts`

1. Write focused tests for portrait mobile, narrow landscape, desktop, the 700-pixel boundary, and invalid dimensions.
2. Run the focused test and confirm it fails because the helper does not exist.
3. Implement the smallest pure framing helper that satisfies the tests.
4. Use the helper for renderer FOV, lateral offset, camera Z, and look-target Z while preserving DPR behavior.
5. Run the focused test, full JavaScript and Python suites, production build, PWA artifact checks, and `git diff --check`.
6. Review the final diff, commit, push to `pasekaalex/sanic-run`, deploy production once, and verify `sanic.fun`.
