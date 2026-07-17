import { describe, expect, it } from 'vitest';
import { GAME } from '../../src/config';
import { GameSimulation, type SpawnSource } from '../../src/game/simulation';
import { SpawnDirector } from '../../src/game/spawnDirector';
import type { Lane, SpawnRow } from '../../src/game/types';

const SPEED_CAP_DISTANCE = (GAME.maxSpeed - GAME.startSpeed) * 140;
const EXPECTED_WEAVE_PERMUTATIONS = Object.freeze([
  '-1,0,1',
  '0,-1,1',
  '1,-1,0',
]);

const orderedCoins = (row: SpawnRow) => [...row.coins].sort((a, b) => a.offset - b.offset);

const isLaneWeave = (row: SpawnRow): boolean => (
  row.obstacles.length === 0
  && row.coins.length === 3
  && row.coins.every((coin) => coin.height === 0.9)
  && new Set(row.coins.map((coin) => coin.lane)).size === GAME.lanes.length
);

const weavePermutation = (row: SpawnRow): string => (
  orderedCoins(row).map((coin) => coin.lane).join(',')
);

const fullBlockerSafeLane = (row: SpawnRow): Lane | null => {
  const blocked = new Set(
    row.obstacles
      .filter((obstacle) => !obstacle.jumpable)
      .map((obstacle) => obstacle.lane),
  );
  if (blocked.size !== GAME.lanes.length - 1) return null;
  return GAME.lanes.find((lane) => !blocked.has(lane)) ?? null;
};

const weaveRowsByPermutation = (
  phase: 'opening' | 'maximum',
): ReadonlyMap<string, SpawnRow> => {
  const rowsByPermutation = new Map<string, SpawnRow>();

  for (let seed = 1; seed <= 128 && rowsByPermutation.size < GAME.lanes.length; seed += 1) {
    const rows = new SpawnDirector(seed).takeUntil(3_000);
    for (const row of rows.filter(isLaneWeave)) {
      const firstCoinAt = row.at + Math.min(...row.coins.map((coin) => coin.offset));
      const matchesPhase = phase === 'opening'
        ? row.id === 'row-1'
        : firstCoinAt >= SPEED_CAP_DISTANCE;
      if (matchesPhase) rowsByPermutation.set(weavePermutation(row), row);
    }
  }

  return rowsByPermutation;
};

const collectWithEarliestLegalCommands = (row: SpawnRow): number => {
  const source: SpawnSource = {
    takeUntil: (maxDistance) => (row.at <= maxDistance ? Object.freeze([row]) : Object.freeze([])),
  };
  const game = new GameSimulation(0x5a11c, source);
  const coins = orderedCoins(row);
  const stopDistance = row.at + Math.max(...coins.map((coin) => coin.offset)) + 2;
  game.start();

  for (let frame = 0; frame < 20_000; frame += 1) {
    const snapshot = game.snapshot();
    const target = coins[snapshot.rings];
    if (target !== undefined) {
      if (snapshot.lane > target.lane) game.command('left');
      if (snapshot.lane < target.lane) game.command('right');
    }

    game.step(GAME.fixedStep);
    const stepped = game.snapshot();
    if (stepped.rings === coins.length || stepped.distance > stopDistance) {
      return stepped.rings;
    }
  }

  throw new Error(`Fixed-step collection schedule did not reach row ${row.id}`);
};

describe('SpawnDirector', () => {
  it('is deterministic for a seed', () => {
    const resettable = new SpawnDirector(0x5a11c);
    const a = resettable.takeUntil(220);
    const b = new SpawnDirector(0x5a11c).takeUntil(220);
    expect(a).toEqual(b);
    resettable.reset(0x5a11c);
    expect(resettable.takeUntil(220)).toEqual(a);
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

  it('constrains the audited seed-1 adjacent full blockers without changing separated rows', () => {
    const rows = new SpawnDirector(1).takeUntil(2_600);
    expect(rows[122]?.at).toBeCloseTo(2_527.417552, 5);
    expect(rows[123]?.at).toBeCloseTo(2_550.937552, 5);
    expect([
      fullBlockerSafeLane(rows[122]!),
      fullBlockerSafeLane(rows[123]!),
    ]).toEqual([-1, 0]);

    expect([
      fullBlockerSafeLane(rows[22]!),
      fullBlockerSafeLane(rows[24]!),
    ]).toEqual([-1, 1]);
  });

  it('keeps adjacent full-blocker routes within one lane through the speed cap for 128 seeds', () => {
    const violations: string[] = [];

    for (let seed = 1; seed <= 128; seed += 1) {
      const rows = new SpawnDirector(seed).takeUntil(3_000);
      for (let index = 1; index < rows.length; index += 1) {
        const previousLane = fullBlockerSafeLane(rows[index - 1]!);
        const lane = fullBlockerSafeLane(rows[index]!);
        if (previousLane !== null && lane !== null && Math.abs(lane - previousLane) > 1) {
          violations.push(`${seed}:${rows[index - 1]!.id}->${rows[index]!.id}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it('scales only weave offsets with speed and keeps each weave inside its row budget', () => {
    const rows = new SpawnDirector(7).takeUntil(3_000);
    const weaveRows = rows.filter(isLaneWeave);
    const openingWeave = weaveRows.find((row) => row.id === 'row-1');
    const maximumWeaves = weaveRows.filter((row) => (
      row.at + Math.min(...row.coins.map((coin) => coin.offset)) >= SPEED_CAP_DISTANCE
    ));

    expect(openingWeave).toBeDefined();
    expect(maximumWeaves.length).toBeGreaterThan(0);
    const openingHalfSpan = Math.max(...openingWeave!.coins.map((coin) => Math.abs(coin.offset)));
    const maximumHalfSpans = maximumWeaves.map((row) => (
      Math.max(...row.coins.map((coin) => Math.abs(coin.offset)))
    ));
    expect(Math.min(...maximumHalfSpans)).toBeGreaterThan(openingHalfSpan);
    expect(Math.min(...maximumHalfSpans)).toBeGreaterThanOrEqual(4.2);

    for (const row of weaveRows) {
      const rowIndex = rows.indexOf(row);
      const adjacentGaps = [
        rows[rowIndex - 1] === undefined ? Number.POSITIVE_INFINITY : row.at - rows[rowIndex - 1]!.at,
        rows[rowIndex + 1] === undefined ? Number.POSITIVE_INFINITY : rows[rowIndex + 1]!.at - row.at,
      ];
      const halfSpan = Math.max(...row.coins.map((coin) => Math.abs(coin.offset)));
      expect(halfSpan * 2).toBeLessThan(Math.min(...adjacentGaps));
    }

    for (const row of rows.filter((candidate) => candidate.coins.length === 3 && !isLaneWeave(candidate))) {
      expect(row.coins.map((coin) => coin.offset)).toEqual([-2.4, 0, 2.4]);
    }
  });

  it('lets fixed-step earliest commands collect every weave permutation at opening and max speed', () => {
    const openingRows = weaveRowsByPermutation('opening');
    const maximumRows = weaveRowsByPermutation('maximum');

    expect([...openingRows.keys()].sort()).toEqual(EXPECTED_WEAVE_PERMUTATIONS);
    expect([...maximumRows.keys()].sort()).toEqual(EXPECTED_WEAVE_PERMUTATIONS);

    const results = [...openingRows, ...maximumRows].map(([permutation, row]) => ({
      phase: row.id === 'row-1' ? 'opening' : 'maximum',
      permutation,
      rings: collectWithEarliestLegalCommands(row),
    }));
    expect(results).toEqual(results.map((result) => ({ ...result, rings: 3 })));
  });
});
