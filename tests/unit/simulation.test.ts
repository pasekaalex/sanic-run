import { describe, expect, it } from 'vitest';
import { GAME } from '../../src/config';
import { GameSimulation, type SpawnSource } from '../../src/game/simulation';
import type { CoinSpawn, ObstacleSpawn, SpawnRow } from '../../src/game/types';

const advance = (game: GameSimulation, seconds: number): void => {
  for (let elapsed = 0; elapsed < seconds; elapsed += GAME.fixedStep) {
    game.step(GAME.fixedStep);
  }
};

const sampleJump = (game: GameSimulation, step: number, samples: number): number[] => {
  const heights = [game.snapshot().playerY];
  for (let index = 0; index < samples; index += 1) {
    game.step(step);
    heights.push(game.snapshot().playerY);
  }
  return heights;
};

const scriptedSource = (rows: readonly SpawnRow[]): SpawnSource => ({
  takeUntil: (maxDistance) => rows.filter((row) => row.at <= maxDistance),
});

const scriptedRingSource = (count: number): SpawnSource => {
  const coins = Object.freeze(Array.from({ length: count }, (_, index): CoinSpawn => Object.freeze({
    id: `ring-${index}`,
    lane: 0,
    height: 0.9,
    offset: 0.75 + index * 1.1,
  })));

  return scriptedSource([Object.freeze({
    id: 'rings',
    at: 0,
    coins,
    obstacles: Object.freeze([]),
  })]);
};

const scriptedObstacleSource = (obstacle: ObstacleSpawn, at: number): SpawnSource => scriptedSource([
  Object.freeze({
    id: `obstacle-${obstacle.id}`,
    at,
    coins: Object.freeze([]),
    obstacles: Object.freeze([Object.freeze({ ...obstacle })]),
  }),
]);

describe('GameSimulation', () => {
  it('clamps lane commands and eases to the selected lane', () => {
    const game = new GameSimulation(1);
    game.start();
    game.command('left');
    game.command('left');
    advance(game, 0.3);
    expect(game.snapshot().lane).toBe(-1);
    expect(game.snapshot().playerX).toBeCloseTo(-GAME.laneWidth, 1);
  });

  it('uses a repeatable jump arc and returns to ground', () => {
    const game = new GameSimulation(2, scriptedSource([]));
    game.start();
    game.command('jump');
    advance(game, 0.35);
    expect(game.snapshot().playerY).toBeGreaterThan(1.2);
    advance(game, 0.7);
    expect(game.snapshot().playerY).toBe(0);
  });

  it('uses constant rise gravity and a stronger fast-fall gravity after the apex', () => {
    const game = new GameSimulation(20, scriptedSource([]));
    game.start();
    game.command('jump');
    game.step(0.07);

    const step = 0.04;
    const heights = sampleJump(game, step, 5);
    const velocities = heights.slice(1).map((height, index) => (
      height - heights[index]!
    ) / step);
    const riseAccelerations = velocities.slice(1).map((velocity, index) => (
      velocity - velocities[index]!
    ) / step);

    expect(velocities[0]).toBeGreaterThan(15);
    expect(velocities[0]).toBeLessThan(22);
    expect(Math.max(...riseAccelerations)).toBeLessThan(-50);
    expect(Math.max(...riseAccelerations) - Math.min(...riseAccelerations)).toBeLessThan(0.05);

    game.step(0.11);
    const fallingHeights = sampleJump(game, step, 4);
    const fallingVelocities = fallingHeights.slice(1).map((height, index) => (
      height - fallingHeights[index]!
    ) / step);
    const fallAccelerations = fallingVelocities.slice(1).map((velocity, index) => (
      velocity - fallingVelocities[index]!
    ) / step);
    expect(Math.max(...fallAccelerations)).toBeLessThan(-80);
    expect(Math.max(...fallAccelerations) - Math.min(...fallAccelerations)).toBeLessThan(0.05);
    expect(Math.max(...fallAccelerations)).toBeLessThan(Math.min(...riseAccelerations));
  });

  it('reports simulation-timed anticipation, flight, and landing recovery', () => {
    const game = new GameSimulation(24, scriptedSource([]));
    game.start();
    game.command('jump');

    expect(game.snapshot()).toMatchObject({ playerY: 0, jumpProgress: 0 });
    game.step(0.05);
    expect(game.snapshot().playerY).toBe(0);
    expect(game.snapshot().jumpProgress).toBeGreaterThan(0);
    game.step(0.1);
    expect(game.snapshot().playerY).toBeGreaterThan(0);
    expect(game.snapshot().jumpProgress).toBeGreaterThan(0.1);

    game.step(0.49);
    expect(game.snapshot().playerY).toBe(0);
    expect(game.snapshot().jumpProgress).not.toBeNull();
    game.step(0.03);
    expect(game.snapshot().jumpProgress).toBe(1);
    game.step(0.02);
    expect(game.snapshot().jumpProgress).toBeNull();
  });

  it('has one readable apex followed by a monotonic descent and exact landing', () => {
    const game = new GameSimulation(21, scriptedSource([]));
    game.start();
    game.command('jump');

    const heights = sampleJump(game, GAME.fixedStep, 75);
    const peak = Math.max(...heights);
    const peakIndex = heights.indexOf(peak);
    expect(peak).toBeGreaterThan(3.0);
    expect(peak).toBeLessThan(3.2);
    expect(peakIndex).toBeGreaterThan(20);
    expect(peakIndex).toBeLessThan(26);
    for (let index = 1; index <= peakIndex; index += 1) {
      expect(heights[index]).toBeGreaterThanOrEqual(heights[index - 1]!);
    }
    for (let index = peakIndex + 1; index < heights.length; index += 1) {
      expect(heights[index]).toBeLessThanOrEqual(heights[index - 1]!);
    }
    expect(heights.at(-1)).toBe(0);
  });

  it('produces the same airborne height with coarse and fine integration steps', () => {
    const coarse = new GameSimulation(22, scriptedSource([]));
    const fine = new GameSimulation(22, scriptedSource([]));
    coarse.start();
    fine.start();
    coarse.command('jump');
    fine.command('jump');

    coarse.step(0.3);
    for (let index = 0; index < 18; index += 1) fine.step(GAME.fixedStep);

    expect(coarse.snapshot().playerY).toBeCloseTo(fine.snapshot().playerY, 8);

    coarse.step(0.4);
    for (let index = 0; index < 24; index += 1) fine.step(GAME.fixedStep);
    expect(coarse.snapshot()).toMatchObject({ playerY: 0, jumpProgress: null });
    expect(fine.snapshot()).toMatchObject({ playerY: 0, jumpProgress: null });
  });

  it('ignores another jump command while airborne', () => {
    const game = new GameSimulation(23, scriptedSource([]));
    game.start();
    game.command('jump');
    advance(game, 0.2);
    game.command('jump');
    advance(game, 1);

    expect(game.snapshot().playerY).toBe(0);
    advance(game, 0.2);
    expect(game.snapshot().playerY).toBe(0);
  });

  it('reports a queued jump start after an active lane transition completes', () => {
    const game = new GameSimulation(27, scriptedSource([]));
    game.start();
    game.command('left');
    game.command('jump');
    expect(game.snapshot().jumpProgress).toBeNull();

    game.step(0.2);
    expect(game.snapshot().jumpProgress).not.toBeNull();
  });

  it('preserves queued movement timing across coarse and fine step partitions', () => {
    const coarseJump = new GameSimulation(28, scriptedSource([]));
    const fineJump = new GameSimulation(28, scriptedSource([]));
    for (const game of [coarseJump, fineJump]) {
      game.start();
      game.command('left');
      game.command('jump');
    }
    coarseJump.step(0.7);
    for (let index = 0; index < 42; index += 1) fineJump.step(GAME.fixedStep);
    expect(coarseJump.snapshot().playerY).toBeCloseTo(fineJump.snapshot().playerY, 8);
    expect(coarseJump.snapshot().jumpProgress).toBeCloseTo(
      fineJump.snapshot().jumpProgress!,
      8,
    );

    const coarseLane = new GameSimulation(29, scriptedSource([]));
    const fineLane = new GameSimulation(29, scriptedSource([]));
    for (const game of [coarseLane, fineLane]) {
      game.start();
      game.command('jump');
      game.command('left');
    }
    coarseLane.step(0.8);
    for (let index = 0; index < 48; index += 1) fineLane.step(GAME.fixedStep);
    expect(coarseLane.snapshot().playerX).toBeCloseTo(fineLane.snapshot().playerX, 8);
    expect(coarseLane.snapshot().jumpProgress).toBe(fineLane.snapshot().jumpProgress);
  });

  it('awards one multiplier step per ten uninterrupted rings and caps at five', () => {
    const game = new GameSimulation(3, scriptedRingSource(50));
    game.start();
    advance(game, 3.2);
    expect(game.snapshot()).toMatchObject({ rings: 50, multiplier: 5, ringStreak: 50 });
    expect(game.snapshot().score - Math.floor(game.snapshot().distance)).toBe(15_000);
  });

  it('ends the run on an occupied grounded obstacle lane', () => {
    const game = new GameSimulation(4, scriptedObstacleSource({
      id: 'impact',
      lane: 0,
      kind: 'fud',
      jumpable: false,
    }, 0.5));
    game.start();
    advance(game, 0.1);
    expect(game.snapshot().phase).toBe('gameOver');
  });

  it('collides using physical lateral position while a lane change is beginning', () => {
    const game = new GameSimulation(25, scriptedObstacleSource({
      id: 'center-during-transition',
      lane: 0,
      kind: 'fud',
      jumpable: false,
    }, 0.1));
    game.start();
    game.command('left');
    game.step(0.005);

    expect(game.snapshot().playerX).toBeGreaterThan(-GAME.laneWidth / 2);
    expect(game.snapshot().phase).toBe('gameOver');
  });

  it('cannot evade a landing obstacle with a queued airborne lane command', () => {
    const game = new GameSimulation(26, scriptedObstacleSource({
      id: 'landing-log',
      lane: 0,
      kind: 'log',
      jumpable: true,
    }, 12.3));
    game.start();
    game.command('jump');
    advance(game, 0.2);
    game.command('left');
    advance(game, 0.6);

    expect(game.snapshot().phase).toBe('gameOver');
  });

  it('freezes forward progress while paused and resumes from the same distance', () => {
    const game = new GameSimulation(5, scriptedSource([]));
    game.start();
    advance(game, 0.2);
    game.pause();
    const pausedDistance = game.snapshot().distance;

    advance(game, 1);
    expect(game.snapshot()).toMatchObject({ phase: 'paused', distance: pausedDistance });

    game.resume();
    advance(game, 0.1);
    expect(game.snapshot().phase).toBe('playing');
    expect(game.snapshot().distance).toBeGreaterThan(pausedDistance);
  });

  it('never exceeds the maximum speed', () => {
    const game = new GameSimulation(6, scriptedSource([]));
    game.start();
    advance(game, 120);
    expect(game.snapshot().speed).toBe(GAME.maxSpeed);
  });

  it('clears a jumpable log above the clearance height', () => {
    const game = new GameSimulation(7, scriptedObstacleSource({
      id: 'jump-log',
      lane: 0,
      kind: 'log',
      jumpable: true,
    }, 5));
    game.start();
    game.command('jump');
    advance(game, 0.5);
    expect(game.snapshot().phase).toBe('playing');
    expect(game.snapshot().distance).toBeGreaterThan(5);
  });

  it('resets the uninterrupted streak when a ring is missed', () => {
    const game = new GameSimulation(8, scriptedSource([Object.freeze({
      id: 'hit-then-miss',
      at: 0,
      coins: Object.freeze([
        Object.freeze({ id: 'hit', lane: 0, height: 0.9, offset: 0.75 }),
        Object.freeze({ id: 'miss', lane: 1, height: 0.9, offset: 2 }),
      ]),
      obstacles: Object.freeze([]),
    })]));
    game.start();
    advance(game, 0.3);
    expect(game.snapshot()).toMatchObject({ rings: 1, multiplier: 1, ringStreak: 0 });
  });

  it('returns all run counters and movement state to their initial values on restart', () => {
    const game = new GameSimulation(9, scriptedRingSource(12));
    game.start();
    advance(game, 1);
    game.command('left');
    advance(game, 0.1);
    expect(game.snapshot().rings).toBeGreaterThan(0);

    game.restart();
    expect(game.snapshot()).toMatchObject({
      phase: 'playing',
      elapsed: 0,
      distance: 0,
      speed: GAME.startSpeed,
      score: 0,
      rings: 0,
      multiplier: 1,
      ringStreak: 0,
      lane: 0,
      playerX: 0,
      playerY: 0,
      jumpProgress: null,
      impactKind: null,
    });
  });
});
