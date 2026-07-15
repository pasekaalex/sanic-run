import { describe, expect, it } from 'vitest';
import { GAME } from '../../src/config';
import { GameSimulation, type SpawnSource } from '../../src/game/simulation';
import type { CoinSpawn, ObstacleSpawn, SpawnRow } from '../../src/game/types';

const advance = (game: GameSimulation, seconds: number): void => {
  for (let elapsed = 0; elapsed < seconds; elapsed += GAME.fixedStep) {
    game.step(GAME.fixedStep);
  }
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
    const game = new GameSimulation(2);
    game.start();
    game.command('jump');
    advance(game, 0.35);
    expect(game.snapshot().playerY).toBeGreaterThan(1.2);
    advance(game, 0.6);
    expect(game.snapshot().playerY).toBe(0);
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
      impactKind: null,
    });
  });
});
