import { GAME } from '../config';
import { SpawnDirector } from './spawnDirector';
import type {
  ActiveCoin,
  ActiveObstacle,
  GameCommand,
  GamePhase,
  Lane,
  ObstacleKind,
  SimulationSnapshot,
  SpawnRow,
} from './types';

export interface SpawnSource {
  takeUntil(maxDistance: number): readonly SpawnRow[];
}

interface LaneTransition {
  readonly from: number;
  readonly to: number;
  elapsed: number;
}

type ActionCommand = Exclude<GameCommand, 'pause'>;

const LANE_TRANSITION_SECONDS = 0.18;
const JUMP_SECONDS = 0.82;
const JUMP_HEIGHT = 2.35;
const COLLECTIBLE_RADIUS = 1.15;
const OBSTACLE_COLLISION_WINDOW = 0.85;
const JUMP_CLEARANCE_HEIGHT = 1.05;
const MISSED_COIN_DISTANCE = -1.2;

const easeOutCubic = (progress: number): number => 1 - (1 - progress) ** 3;

const clampLane = (lane: number): Lane => Math.max(-1, Math.min(1, lane)) as Lane;

export class GameSimulation {
  private readonly injectedSource: SpawnSource | undefined;
  private seed: number;
  private source: SpawnSource;
  private phaseValue: GamePhase = 'intro';
  private elapsedValue = 0;
  private distanceValue = 0;
  private speedValue: number = GAME.startSpeed;
  private ringScore = 0;
  private ringsValue = 0;
  private multiplierValue = 1;
  private ringStreakValue = 0;
  private laneValue: Lane = 0;
  private playerXValue = 0;
  private playerYValue = 0;
  private impactKindValue: ObstacleKind | null = null;
  private laneTransition: LaneTransition | null = null;
  private jumpElapsed: number | null = null;
  private queuedCommand: ActionCommand | null = null;
  private loadedRows = new Set<string>();
  private activeCoins: ActiveCoin[] = [];
  private activeObstacles: ActiveObstacle[] = [];

  constructor(seed: number, source?: SpawnSource) {
    this.seed = seed;
    this.injectedSource = source;
    this.source = source ?? new SpawnDirector(seed);
  }

  start(): void {
    if (this.phaseValue !== 'intro') return;
    this.phaseValue = 'playing';
    this.loadSpawns();
  }

  restart(seed = this.seed): void {
    this.seed = seed;
    this.source = this.injectedSource ?? new SpawnDirector(seed);
    this.phaseValue = 'playing';
    this.elapsedValue = 0;
    this.distanceValue = 0;
    this.speedValue = GAME.startSpeed;
    this.ringScore = 0;
    this.ringsValue = 0;
    this.multiplierValue = 1;
    this.ringStreakValue = 0;
    this.laneValue = 0;
    this.playerXValue = 0;
    this.playerYValue = 0;
    this.impactKindValue = null;
    this.laneTransition = null;
    this.jumpElapsed = null;
    this.queuedCommand = null;
    this.loadedRows = new Set<string>();
    this.activeCoins = [];
    this.activeObstacles = [];
    this.loadSpawns();
  }

  pause(): void {
    if (this.phaseValue === 'playing') this.phaseValue = 'paused';
  }

  resume(): void {
    if (this.phaseValue === 'paused') this.phaseValue = 'playing';
  }

  command(command: GameCommand): void {
    if (command === 'pause') {
      if (this.phaseValue === 'playing') this.pause();
      else if (this.phaseValue === 'paused') this.resume();
      return;
    }
    if (this.phaseValue !== 'playing') return;

    if (this.laneTransition !== null || this.jumpElapsed !== null) {
      this.queuedCommand ??= command;
      return;
    }

    this.beginCommand(command);
  }

  step(dt: number): void {
    if (this.phaseValue !== 'playing' || !Number.isFinite(dt) || dt <= 0) return;

    this.elapsedValue += dt;
    this.updateLaneTransition(dt);
    this.updateJump(dt);
    this.distanceValue += this.speedValue * dt;
    this.speedValue = Math.min(GAME.maxSpeed, GAME.startSpeed + this.distanceValue / 140);
    this.loadSpawns();
    this.collectCoins();
    this.collideWithObstacles();
  }

  snapshot(): Readonly<SimulationSnapshot> {
    const coins = Object.freeze(this.activeCoins.map((coin) => Object.freeze({ ...coin })));
    const obstacles = Object.freeze(this.activeObstacles.map((obstacle) => Object.freeze({ ...obstacle })));

    return Object.freeze({
      phase: this.phaseValue,
      elapsed: this.elapsedValue,
      distance: this.distanceValue,
      speed: this.speedValue,
      score: Math.floor(this.distanceValue) + this.ringScore,
      rings: this.ringsValue,
      multiplier: this.multiplierValue,
      ringStreak: this.ringStreakValue,
      lane: this.laneValue,
      playerX: this.playerXValue,
      playerY: this.playerYValue,
      coins,
      obstacles,
      impactKind: this.impactKindValue,
    });
  }

  private beginCommand(command: ActionCommand): void {
    if (command === 'jump') {
      this.jumpElapsed = 0;
      return;
    }

    const direction = command === 'left' ? -1 : 1;
    const nextLane = clampLane(this.laneValue + direction);
    if (nextLane === this.laneValue) return;

    this.laneValue = nextLane;
    this.laneTransition = {
      from: this.playerXValue,
      to: nextLane * GAME.laneWidth,
      elapsed: 0,
    };
  }

  private updateLaneTransition(dt: number): void {
    if (this.laneTransition === null) return;

    this.laneTransition.elapsed += dt;
    const progress = Math.min(1, this.laneTransition.elapsed / LANE_TRANSITION_SECONDS);
    const eased = easeOutCubic(progress);
    this.playerXValue = this.laneTransition.from
      + (this.laneTransition.to - this.laneTransition.from) * eased;

    if (progress < 1) return;
    this.playerXValue = this.laneTransition.to;
    this.laneTransition = null;
    this.consumeQueuedCommand();
  }

  private updateJump(dt: number): void {
    if (this.jumpElapsed === null) return;

    this.jumpElapsed += dt;
    const progress = Math.min(1, this.jumpElapsed / JUMP_SECONDS);
    this.playerYValue = JUMP_HEIGHT * Math.sin(Math.PI * progress);

    if (progress < 1) return;
    this.playerYValue = 0;
    this.jumpElapsed = null;
    this.consumeQueuedCommand();
  }

  private consumeQueuedCommand(): void {
    if (this.queuedCommand === null) return;
    const command = this.queuedCommand;
    this.queuedCommand = null;
    this.beginCommand(command);
  }

  private loadSpawns(): void {
    const rows = this.source.takeUntil(this.distanceValue + GAME.spawnAhead);
    for (const row of rows) {
      if (this.loadedRows.has(row.id)) continue;
      this.loadedRows.add(row.id);

      for (const coin of row.coins) {
        this.activeCoins.push(Object.freeze({ ...coin, at: row.at + coin.offset }));
      }
      for (const obstacle of row.obstacles) {
        this.activeObstacles.push(Object.freeze({ ...obstacle, at: row.at }));
      }
    }

    this.activeCoins.sort((a, b) => a.at - b.at);
    this.activeObstacles.sort((a, b) => a.at - b.at);
  }

  private collectCoins(): void {
    const remaining: ActiveCoin[] = [];
    const radiusSquared = COLLECTIBLE_RADIUS ** 2;

    for (const coin of this.activeCoins) {
      const forward = coin.at - this.distanceValue;
      const lateral = coin.lane * GAME.laneWidth - this.playerXValue;
      const vertical = coin.height - this.playerYValue;
      if (forward ** 2 + lateral ** 2 + vertical ** 2 <= radiusSquared) {
        this.ringScore += GAME.ringScore * this.multiplierValue;
        this.ringsValue += 1;
        this.ringStreakValue += 1;
        if (this.ringStreakValue % GAME.ringsPerMultiplier === 0) {
          this.multiplierValue = Math.min(GAME.maxMultiplier, this.multiplierValue + 1);
        }
        continue;
      }

      if (forward >= MISSED_COIN_DISTANCE) {
        remaining.push(coin);
      } else {
        this.ringStreakValue = 0;
      }
    }

    this.activeCoins = remaining;
  }

  private collideWithObstacles(): void {
    for (const obstacle of this.activeObstacles) {
      const forward = obstacle.at - this.distanceValue;
      if (obstacle.lane !== this.laneValue || Math.abs(forward) > OBSTACLE_COLLISION_WINDOW) continue;
      if (obstacle.jumpable && this.playerYValue >= JUMP_CLEARANCE_HEIGHT) continue;

      this.phaseValue = 'gameOver';
      this.impactKindValue = obstacle.kind;
      return;
    }

    this.activeObstacles = this.activeObstacles.filter((obstacle) => (
      obstacle.at - this.distanceValue >= -OBSTACLE_COLLISION_WINDOW
    ));
  }
}
