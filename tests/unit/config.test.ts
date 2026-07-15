import { describe, expect, it } from 'vitest';
import { ASSET_URLS, BRAND, GAME } from '../../src/config';

describe('immutable launch configuration', () => {
  it('uses the exact contract in copy and Pump.fun URL', () => {
    expect(BRAND.contract).toBe('CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump');
    expect(BRAND.pumpUrl).toBe(`https://pump.fun/coin/${BRAND.contract}`);
    expect(BRAND.xUrl).toBe('https://x.com/memesofsanic');
  });

  it('locks the three-lane scoring rules and asset URLs', () => {
    expect(GAME.lanes).toEqual([-1, 0, 1]);
    expect(GAME.maxMultiplier).toBe(5);
    expect(GAME.ringsPerMultiplier).toBe(10);
    expect(ASSET_URLS.character).toBe('/models/sanic-runner.glb');
  });
});
