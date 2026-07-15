import { describe, expect, it } from 'vitest';
import { SpawnDirector } from '../../src/game/spawnDirector';

describe('SpawnDirector', () => {
  it('is deterministic for a seed', () => {
    const a = new SpawnDirector(0x5a11c).takeUntil(220);
    const b = new SpawnDirector(0x5a11c).takeUntil(220);
    expect(a).toEqual(b);
  });

  it('leaves a physically safe lane in every obstacle row', () => {
    const rows = new SpawnDirector(42).takeUntil(3_000);
    for (const row of rows.filter((candidate) => candidate.obstacles.length > 0)) {
      const blocked = new Set(row.obstacles.filter((item) => !item.jumpable).map((item) => item.lane));
      expect(blocked.size).toBeLessThan(3);
    }
  });

  it('starts with teaching patterns and increases spacing with required reaction time', () => {
    const rows = new SpawnDirector(7).takeUntil(500);
    expect(rows[0]?.at).toBeGreaterThanOrEqual(24);
    expect(rows.some((row) => row.coins.length >= 3)).toBe(true);
    expect(rows.every((row, index) => index === 0 || row.at > rows[index - 1]!.at)).toBe(true);
  });

  it('gives every multi-coin template distinct ascending offsets and a real jump arc', () => {
    const rows = new SpawnDirector(7).takeUntil(3_000);
    const multiCoinRows = rows.filter((row) => row.coins.length > 1);
    const hasDistinctAscendingOffsets = multiCoinRows.every((row) => {
      const offsets = row.coins.map((coin) => coin.offset);
      return new Set(offsets).size === offsets.length
        && offsets.every((offset, index) => index === 0 || offset > offsets[index - 1]!);
    });
    const hasElevatedJumpArc = multiCoinRows.some((row) => (
      row.coins.some((coin) => coin.height === 2.2)
      && new Set(row.coins.map((coin) => coin.offset)).size === row.coins.length
    ));

    expect(multiCoinRows.length).toBeGreaterThan(0);
    expect({ hasDistinctAscendingOffsets, hasElevatedJumpArc }).toEqual({
      hasDistinctAscendingOffsets: true,
      hasElevatedJumpArc: true,
    });
  });
});
