import { describe, expect, it } from 'vitest';
import { uniformScaleForHeight } from '../../src/render/modelScale';

describe('uniformScaleForHeight', () => {
  it('normalizes both the legacy and corrected SANIC models to one world height', () => {
    expect(uniformScaleForHeight(7.221238, 4.12)).toBeCloseTo(0.570539, 6);
    expect(uniformScaleForHeight(1.7, 4.12)).toBeCloseTo(2.423529, 6);
  });

  it('returns a safe neutral scale for invalid dimensions', () => {
    expect(uniformScaleForHeight(Number.NaN, 4.12)).toBe(1);
    expect(uniformScaleForHeight(0, 4.12)).toBe(1);
    expect(uniformScaleForHeight(-1, 4.12)).toBe(1);
    expect(uniformScaleForHeight(1.7, Number.POSITIVE_INFINITY)).toBe(1);
    expect(uniformScaleForHeight(1.7, 0)).toBe(1);
  });
});
