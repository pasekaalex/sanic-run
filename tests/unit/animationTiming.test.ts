import { describe, expect, it } from 'vitest';
import {
  animationCrossfadeSeconds,
  characterActionFor,
  interpolateJumpProgress,
  jumpPresentation,
  jumpClipTime,
  jumpStarted,
  runTimeScale,
} from '../../src/render/animationTiming';

describe('animationTiming', () => {
  it('selects Jump during grounded anticipation and landing recovery', () => {
    expect(characterActionFor('playing', 0)).toBe('Jump');
    expect(characterActionFor('playing', 0.99)).toBe('Jump');
    expect(characterActionFor('playing', null)).toBe('Run');
    expect(characterActionFor('gameOver', null)).toBe('Crash');
    expect(characterActionFor('intro', null)).toBe('Idle');
  });

  it('samples jump clips from deterministic simulation progress', () => {
    expect(jumpClipTime(0.966, 0)).toBe(0);
    expect(jumpClipTime(0.966, 0.5)).toBeCloseTo(0.483, 8);
    expect(jumpClipTime(0.966, 1)).toBeCloseTo(0.966, 8);
    expect(jumpClipTime(0.966, -1)).toBe(0);
    expect(jumpClipTime(0.966, 2)).toBeCloseTo(0.966, 8);
  });

  it('only reports a jump start on the grounded-to-active transition', () => {
    expect(jumpStarted(null, 0)).toBe(true);
    expect(jumpStarted(null, 0.02)).toBe(true);
    expect(jumpStarted(0, 0)).toBe(false);
    expect(jumpStarted(0.5, 0.5)).toBe(false);
    expect(jumpStarted(0.99, null)).toBe(false);
  });

  it('crossfades into Jump before the short anticipation finishes', () => {
    expect(animationCrossfadeSeconds('Jump')).toBeLessThanOrEqual(0.04);
    expect(animationCrossfadeSeconds('Crash')).toBe(0.08);
    expect(animationCrossfadeSeconds('Run')).toBeGreaterThan(0.08);
  });

  it('plays the Run clip at sprint cadence from the opening pace onward', () => {
    expect(runTimeScale(18, 18)).toBeCloseTo(1, 8);
    expect(runTimeScale(27, 18)).toBeCloseTo(1.5, 8);
    expect(runTimeScale(36, 18)).toBeCloseTo(1.55, 8);
    expect(runTimeScale(0, 18)).toBeCloseTo(0.95, 8);
    expect(runTimeScale(Number.NaN, 18)).toBeCloseTo(1, 8);
  });

  it('holds the final jump pose across the active-to-grounded interpolation edge', () => {
    expect(interpolateJumpProgress(null, 0, 0.5)).toBe(0);
    expect(interpolateJumpProgress(0.4, 0.6, 0.25)).toBeCloseTo(0.45, 8);
    expect(interpolateJumpProgress(1, null, 0)).toBe(1);
    expect(interpolateJumpProgress(1, null, 1)).toBe(1);
    expect(interpolateJumpProgress(null, null, 0.5)).toBeNull();
  });

  it('shows the curled spin ball only through the airborne tuck window', () => {
    expect(jumpPresentation(null)).toBe('character');
    expect(jumpPresentation(Number.NaN)).toBe('character');
    expect(jumpPresentation(0.15)).toBe('character');
    expect(jumpPresentation(0.16)).toBe('spin');
    expect(jumpPresentation(0.82)).toBe('spin');
    expect(jumpPresentation(0.83)).toBe('character');
  });
});
