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
const ONE_HOUR_SECONDS = 60 * 60;
const ROW_RENDER_BEHIND_DISTANCE = 12;
const MINIMUM_ROW_SPACING = 12 + GAME.startSpeed * 0.32;
const MAXIMUM_RETAINED_ROWS = Math.ceil(
  (GAME.spawnAhead + ROW_RENDER_BEHIND_DISTANCE) / MINIMUM_ROW_SPACING,
) + 1;
// Twelve fixed steps leave one 200 ms touch/input-scheduling budget.
const MOBILE_INPUT_BUFFER_SECONDS = 0.2;
const MAX_JUMP_LEAD_FRAMES = 50;

type LaneResponse = 'empty' | 'jump-required' | 'blocked';

const orderedCoins = (row: SpawnRow) => [...row.coins].sort((a, b) => a.offset - b.offset);

const rowsThrough = (seed: number, maxDistance: number): readonly SpawnRow[] => {
  const director = new SpawnDirector(seed);
  const rows = new Map<string, SpawnRow>();
  const batchDistance = GAME.spawnAhead / 2;

  for (let distance = batchDistance; distance < maxDistance; distance += batchDistance) {
    for (const row of director.takeUntil(distance)) rows.set(row.id, row);
  }
  for (const row of director.takeUntil(maxDistance)) rows.set(row.id, row);

  return [...rows.values()].sort((left, right) => left.at - right.at);
};

const isLaneWeave = (row: SpawnRow): boolean => (
  row.obstacles.length === 0
  && row.coins.length === 3
  && row.coins.every((coin) => coin.height === 0.9)
  && new Set(row.coins.map((coin) => coin.lane)).size === GAME.lanes.length
);

const weavePermutation = (row: SpawnRow): string => (
  orderedCoins(row).map((coin) => coin.lane).join(',')
);

const laneResponseFromObstacles = (row: SpawnRow, lane: Lane): LaneResponse => {
  const obstacles = row.obstacles.filter((obstacle) => obstacle.lane === lane);
  if (obstacles.length === 0) return 'empty';
  return obstacles.some((obstacle) => !obstacle.jumpable) ? 'blocked' : 'jump-required';
};

const fullBlockerRouteLane = (row: SpawnRow): Lane | null => {
  const blocked = new Set(
    row.obstacles
      .filter((obstacle) => !obstacle.jumpable)
      .map((obstacle) => obstacle.lane),
  );
  if (blocked.size !== GAME.lanes.length - 1) return null;
  return GAME.lanes.find((lane) => !blocked.has(lane)) ?? null;
};

const survivesRowInLane = (
  row: SpawnRow,
  lane: Lane,
  jumpLeadFrames: number | null,
): boolean => {
  const source: SpawnSource = {
    takeUntil: (maxDistance) => (row.at <= maxDistance ? Object.freeze([row]) : Object.freeze([])),
  };
  const game = new GameSimulation(0x5a11c, source);
  game.start();
  if (lane === -1) game.command('left');
  if (lane === 1) game.command('right');

  const jumpAt = jumpLeadFrames === null
    ? Number.NEGATIVE_INFINITY
    : row.at - jumpLeadFrames * GAME.fixedStep * GAME.maxSpeed;
  let jumped = jumpLeadFrames === null;

  for (let frame = 0; frame < 20_000; frame += 1) {
    const snapshot = game.snapshot();
    if (!jumped && snapshot.distance >= jumpAt) {
      game.command('jump');
      jumped = true;
    }

    game.step(GAME.fixedStep);
    const stepped = game.snapshot();
    if (stepped.phase === 'gameOver') return false;
    if (stepped.distance > row.at + 2) return true;
  }

  throw new Error(`Fixed-step lane probe did not reach row ${row.id}`);
};

const laneResponseFromSimulation = (row: SpawnRow, lane: Lane): LaneResponse => {
  if (survivesRowInLane(row, lane, null)) return 'empty';
  for (let leadFrames = 1; leadFrames <= MAX_JUMP_LEAD_FRAMES; leadFrames += 1) {
    if (survivesRowInLane(row, lane, leadFrames)) return 'jump-required';
  }
  return 'blocked';
};

const rowRequiresJump = (row: SpawnRow): boolean => {
  const responses = GAME.lanes.map((lane) => laneResponseFromObstacles(row, lane));
  return !responses.includes('empty') && responses.includes('jump-required');
};

const survivesAuditedRoutePair = (
  first: SpawnRow,
  second: SpawnRow,
  firstJumpLeadFrames: number,
): boolean => {
  const rows = Object.freeze([first, second]);
  const source: SpawnSource = {
    takeUntil: (maxDistance) => rows.filter((row) => row.at <= maxDistance),
  };
  const game = new GameSimulation(0x5a11c, source);
  const firstJumpAt = first.at - firstJumpLeadFrames * GAME.fixedStep * GAME.maxSpeed;
  let firstJumpStarted = false;
  let rightQueued = false;
  let secondJumpQueued = false;
  game.start();
  game.command('left');

  for (let frame = 0; frame < 20_000; frame += 1) {
    const snapshot = game.snapshot();
    if (!firstJumpStarted && snapshot.distance >= firstJumpAt) {
      game.command('jump');
      firstJumpStarted = true;
    } else if (firstJumpStarted && !rightQueued && snapshot.jumpProgress !== null) {
      game.command('right');
      rightQueued = true;
    } else if (
      rightQueued
      && !secondJumpQueued
      && snapshot.jumpProgress === null
      && snapshot.lane === 0
      && snapshot.playerX < -0.01
    ) {
      game.command('jump');
      secondJumpQueued = true;
    }

    game.step(GAME.fixedStep);
    const stepped = game.snapshot();
    if (stepped.phase === 'gameOver') return false;
    if (stepped.distance > second.at + 2) return true;
  }

  throw new Error(`Fixed-step response probe did not reach ${first.id}->${second.id}`);
};

const longestConsecutiveFrameSpan = (frames: readonly number[]): number => {
  let longest = 0;
  let spanStart = frames[0] ?? 0;
  let previous = frames[0] ?? 0;

  for (const frame of frames.slice(1)) {
    if (frame !== previous + 1) spanStart = frame;
    previous = frame;
    longest = Math.max(longest, previous - spanStart);
  }

  return longest;
};

const weaveRowsByPermutation = (
  phase: 'opening' | 'maximum',
): ReadonlyMap<string, SpawnRow> => {
  const rowsByPermutation = new Map<string, SpawnRow>();

  for (let seed = 1; seed <= 128 && rowsByPermutation.size < GAME.lanes.length; seed += 1) {
    const rows = rowsThrough(seed, 3_000);
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

  it('returns a row through its behind-player safety margin and prunes it immediately after', () => {
    const director = new SpawnDirector(0x5a11c);
    const firstRow = director.takeUntil(GAME.spawnAhead)[0]!;

    expect(
      director.takeUntil(firstRow.at + GAME.spawnAhead + ROW_RENDER_BEHIND_DISTANCE - 0.01)
        .some((row) => row.id === firstRow.id),
    ).toBe(true);
    expect(
      director.takeUntil(firstRow.at + GAME.spawnAhead + ROW_RENDER_BEHIND_DISTANCE + 0.01)
        .some((row) => row.id === firstRow.id),
    ).toBe(false);
  });

  it('leaves a physically safe lane in every obstacle row', () => {
    const rows = rowsThrough(42, 3_000);
    for (const row of rows.filter((candidate) => candidate.obstacles.length > 0)) {
      const blocked = new Set(row.obstacles.filter((item) => !item.jumpable).map((item) => item.lane));
      expect(blocked.size).toBeLessThan(3);
    }
  });

  it('starts with teaching patterns and increases spacing with required reaction time', () => {
    const rows = rowsThrough(7, 500);
    expect(rows[0]?.at).toBeGreaterThanOrEqual(24);
    expect(rows.some((row) => row.coins.length >= 3)).toBe(true);
    expect(rows.every((row, index) => index === 0 || row.at > rows[index - 1]!.at)).toBe(true);
  });

  it('gives every multi-coin template distinct ascending offsets and a real jump arc', () => {
    const rows = rowsThrough(7, 3_000);
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
    const rows = rowsThrough(1, 2_600);
    expect(rows[122]?.at).toBeCloseTo(2_527.417552, 5);
    expect(rows[123]?.at).toBeCloseTo(2_550.937552, 5);
    expect([
      fullBlockerRouteLane(rows[122]!),
      fullBlockerRouteLane(rows[123]!),
    ]).toEqual([-1, 0]);

    expect([
      fullBlockerRouteLane(rows[22]!),
      fullBlockerRouteLane(rows[24]!),
    ]).toEqual([-1, 1]);
  });

  it('gives the audited max-speed route at least 200 ms of real input latitude', () => {
    const rows = rowsThrough(1, 2_600);
    expect({
      empty: laneResponseFromSimulation(rows[121]!, 0),
      jumpRequired: laneResponseFromSimulation(rows[121]!, 1),
      blocked: laneResponseFromSimulation(rows[122]!, 0),
    }).toEqual({
      empty: 'empty',
      jumpRequired: 'jump-required',
      blocked: 'blocked',
    });

    const successfulLeadFrames = Array.from(
      { length: MAX_JUMP_LEAD_FRAMES },
      (_, index) => index + 1,
    ).filter((leadFrames) => survivesAuditedRoutePair(
      rows[122]!,
      rows[123]!,
      leadFrames,
    ));
    expect(successfulLeadFrames.length).toBeGreaterThan(0);

    const inputLatitude = longestConsecutiveFrameSpan(successfulLeadFrames) * GAME.fixedStep;
    expect(inputLatitude).toBeGreaterThanOrEqual(MOBILE_INPUT_BUFFER_SECONDS);
  });

  it('never generates consecutive forced-jump routes through the speed cap for 128 seeds', () => {
    const violations: string[] = [];

    for (let seed = 1; seed <= 128; seed += 1) {
      const rows = rowsThrough(seed, 3_000);
      for (let index = 1; index < rows.length; index += 1) {
        if (rowRequiresJump(rows[index - 1]!) && rowRequiresJump(rows[index]!)) {
          violations.push(`${seed}:${rows[index - 1]!.id}->${rows[index]!.id}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it('keeps adjacent full-blocker routes within one lane through the speed cap for 128 seeds', () => {
    const violations: string[] = [];

    for (let seed = 1; seed <= 128; seed += 1) {
      const rows = rowsThrough(seed, 3_000);
      for (let index = 1; index < rows.length; index += 1) {
        const previousLane = fullBlockerRouteLane(rows[index - 1]!);
        const lane = fullBlockerRouteLane(rows[index]!);
        if (previousLane !== null && lane !== null && Math.abs(lane - previousLane) > 1) {
          violations.push(`${seed}:${rows[index - 1]!.id}->${rows[index]!.id}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it('scales only weave offsets with speed and keeps each weave inside its row budget', () => {
    const rows = rowsThrough(7, 3_000);
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

  it('keeps one hour of generated-row returns and retained rows bounded to lookahead', () => {
    const seed = 0x5a11c;
    const director = new SpawnDirector(seed);
    const baseline = new SpawnDirector(seed).takeUntil(GAME.spawnAhead);
    const generatedIds = new Set<string>();
    let maximumReturned = 0;
    let maximumRetained = 0;

    for (let second = 0; second <= ONE_HOUR_SECONDS; second += 1) {
      const playerDistance = second * GAME.maxSpeed;
      const returned = director.takeUntil(playerDistance + GAME.spawnAhead);
      maximumReturned = Math.max(maximumReturned, returned.length);
      for (const row of returned) generatedIds.add(row.id);
      const retained = (director as unknown as { rows: readonly SpawnRow[] }).rows;
      maximumRetained = Math.max(maximumRetained, retained.length);
    }

    expect(generatedIds.size).toBeGreaterThan(5_000);
    expect(maximumReturned).toBeLessThanOrEqual(MAXIMUM_RETAINED_ROWS);
    expect(maximumRetained).toBeLessThanOrEqual(MAXIMUM_RETAINED_ROWS);

    director.reset(seed);
    expect(director.takeUntil(GAME.spawnAhead)).toEqual(baseline);
  });
});
