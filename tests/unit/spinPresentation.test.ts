import { describe, expect, it } from 'vitest';
import { nextSpinRotation } from '../../src/render/spinPresentation';

describe('nextSpinRotation', () => {
  it('advances only while the jump ball is presented', () => {
    expect(nextSpinRotation(0, true, 12, 0.25)).toBeCloseTo(-1.26, 6);
    expect(nextSpinRotation(-1.26, true, 12, 0.25)).toBeCloseTo(-2.52, 6);
  });

  it('resets as soon as the presentation returns to the character', () => {
    expect(nextSpinRotation(-4.5, false, 12, 0.25)).toBe(0);
  });
});
