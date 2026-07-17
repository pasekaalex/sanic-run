import { GAME } from '../config';
import { XorShift32 } from './random';
import type { CoinSpawn, Lane, ObstacleKind, ObstacleSpawn, SpawnRow } from './types';

type LaneRole = 0 | 1 | 2;

interface CoinTemplate {
  readonly lane: LaneRole;
  readonly height: CoinSpawn['height'];
  readonly offset: number;
}

interface ObstacleTemplate {
  readonly lane: LaneRole;
  readonly kind: ObstacleKind;
  readonly jumpable: boolean;
}

interface SpawnTemplate {
  readonly name: string;
  readonly coins: readonly CoinTemplate[];
  readonly obstacles: readonly ObstacleTemplate[];
}

const freezeTemplate = (
  name: string,
  coins: readonly CoinTemplate[],
  obstacles: readonly ObstacleTemplate[],
): SpawnTemplate => Object.freeze({
  name,
  coins: Object.freeze(coins.map((coin) => Object.freeze({ ...coin }))),
  obstacles: Object.freeze(obstacles.map((obstacle) => Object.freeze({ ...obstacle }))),
});

const STRAIGHT_COIN_LINE = freezeTemplate('straight-coin-line', [
  { lane: 0, height: 0.9, offset: -2.4 },
  { lane: 0, height: 0.9, offset: 0 },
  { lane: 0, height: 0.9, offset: 2.4 },
], []);

const LANE_WEAVE_COIN_LINE = freezeTemplate('lane-weave-coin-line', [
  { lane: 0, height: 0.9, offset: -2.4 },
  { lane: 1, height: 0.9, offset: 0 },
  { lane: 2, height: 0.9, offset: 2.4 },
], []);

const SINGLE_LOG_WITH_JUMP_ARC = freezeTemplate('single-log-with-jump-arc', [
  { lane: 0, height: 0.9, offset: -2.4 },
  { lane: 0, height: 2.2, offset: 0 },
  { lane: 0, height: 0.9, offset: 2.4 },
], [
  { lane: 0, kind: 'log', jumpable: true },
]);

const TWO_HARD_BLOCKERS = freezeTemplate('two-hard-blockers', [
  { lane: 0, height: 0.9, offset: -2.4 },
  { lane: 0, height: 0.9, offset: 0 },
  { lane: 0, height: 0.9, offset: 2.4 },
], [
  { lane: 1, kind: 'candle', jumpable: false },
  { lane: 2, kind: 'fud', jumpable: false },
]);

const LOG_PLUS_HARD_BLOCKERS = freezeTemplate('log-plus-hard-blocker', [
  { lane: 0, height: 0.9, offset: -2.4 },
  { lane: 0, height: 2.2, offset: 0 },
  { lane: 0, height: 0.9, offset: 2.4 },
], [
  { lane: 0, kind: 'log', jumpable: true },
  { lane: 1, kind: 'candle', jumpable: false },
  { lane: 2, kind: 'fud', jumpable: false },
]);

const TEACHING_TEMPLATES = Object.freeze([
  STRAIGHT_COIN_LINE,
  LANE_WEAVE_COIN_LINE,
  SINGLE_LOG_WITH_JUMP_ARC,
] as const);

const ALL_TEMPLATES = Object.freeze([
  ...TEACHING_TEMPLATES,
  TWO_HARD_BLOCKERS,
  LOG_PLUS_HARD_BLOCKERS,
] as const);

const START_DISTANCE = 24;
const WEAVE_LANE_CHANGE_SECONDS = 0.29;

const speedAtDistance = (distance: number): number => (
  Math.min(GAME.maxSpeed, GAME.startSpeed + distance / 140)
);

const weaveHalfSpanAtDistance = (distance: number): number => (
  speedAtDistance(distance) * WEAVE_LANE_CHANGE_SECONDS
);

const spacingAtDistance = (distance: number): number => (
  12 + speedAtDistance(distance) * 0.32
);

const isFullBlockerTemplate = (template: SpawnTemplate): boolean => (
  new Set(
    template.obstacles
      .filter((obstacle) => !obstacle.jumpable)
      .map((obstacle) => obstacle.lane),
  ).size === GAME.lanes.length - 1
);

export class SpawnDirector {
  private random: XorShift32;
  private rows: SpawnRow[] = [];
  private nextDistance = START_DISTANCE;
  private rowCounter = 0;
  private previousFullBlockerLane: Lane | null = null;

  constructor(seed: number) {
    this.random = new XorShift32(seed);
  }

  reset(seed: number): void {
    this.random = new XorShift32(seed);
    this.rows = [];
    this.nextDistance = START_DISTANCE;
    this.rowCounter = 0;
    this.previousFullBlockerLane = null;
  }

  takeUntil(maxDistance: number): readonly SpawnRow[] {
    if (!Number.isFinite(maxDistance)) throw new RangeError('maxDistance must be finite');

    while (this.nextDistance <= maxDistance) {
      const distance = this.nextDistance;
      this.rows.push(this.createRow(distance));
      this.nextDistance = distance + spacingAtDistance(distance);
    }

    return Object.freeze(this.rows.filter((row) => row.at <= maxDistance));
  }

  private createRow(distance: number): SpawnRow {
    const template = this.chooseTemplate(distance);
    const proposedFocusLane = this.random.pick(GAME.lanes);
    const fullBlocker = isFullBlockerTemplate(template);
    const focusLane = fullBlocker
      && this.previousFullBlockerLane !== null
      && Math.abs(proposedFocusLane - this.previousFullBlockerLane) > 1
      ? 0
      : proposedFocusLane;
    const lanes = Object.freeze([
      focusLane,
      ...GAME.lanes.filter((lane) => lane !== focusLane),
    ] satisfies readonly Lane[]);
    const rowIndex = this.rowCounter;
    let itemCounter = 0;

    const coins = Object.freeze(template.coins.map((coin): CoinSpawn => Object.freeze({
      id: `row-${rowIndex}-coin-${itemCounter++}`,
      lane: lanes[coin.lane]!,
      height: coin.height,
      offset: template === LANE_WEAVE_COIN_LINE && coin.offset !== 0
        ? Math.sign(coin.offset) * weaveHalfSpanAtDistance(distance)
        : coin.offset,
    })));
    const obstacles = Object.freeze(template.obstacles.map((obstacle): ObstacleSpawn => Object.freeze({
      id: `row-${rowIndex}-obstacle-${itemCounter++}`,
      lane: lanes[obstacle.lane]!,
      kind: obstacle.kind,
      jumpable: obstacle.jumpable,
    })));

    this.rowCounter += 1;
    this.previousFullBlockerLane = fullBlocker ? focusLane : null;
    return Object.freeze({
      id: `row-${rowIndex}`,
      at: distance,
      coins,
      obstacles,
    });
  }

  private chooseTemplate(distance: number): SpawnTemplate {
    if (this.rowCounter < TEACHING_TEMPLATES.length) {
      return TEACHING_TEMPLATES[this.rowCounter]!;
    }

    const availableTemplates = distance < GAME.spawnAhead ? TEACHING_TEMPLATES : ALL_TEMPLATES;
    return this.random.pick(availableTemplates);
  }
}
