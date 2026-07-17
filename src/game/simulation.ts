import { GAME } from '../config';
import { SPAWN_ROW_RETURN_BEHIND_DISTANCE, SpawnDirector } from './spawnDirector';
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
const JUMP_HEIGHT = 3.1;
const JUMP_ANTICIPATION_SECONDS = 0.07;
const JUMP_ASCENT_SECONDS = 0.31;
const JUMP_DESCENT_SECONDS = 0.25;
const JUMP_RECOVERY_SECONDS = 0.05;
const JUMP_ASCENT_END = JUMP_ANTICIPATION_SECONDS + JUMP_ASCENT_SECONDS;
const JUMP_DESCENT_END = JUMP_ASCENT_END + JUMP_DESCENT_SECONDS;
const JUMP_TOTAL_SECONDS = JUMP_DESCENT_END + JUMP_RECOVERY_SECONDS;
const JUMP_LAUNCH_VELOCITY = (2 * JUMP_HEIGHT) / JUMP_ASCENT_SECONDS;
const JUMP_RISE_GRAVITY = JUMP_LAUNCH_VELOCITY / JUMP_ASCENT_SECONDS;
const JUMP_FALL_GRAVITY = (2 * JUMP_HEIGHT) / JUMP_DESCENT_SECONDS ** 2;
const COLLECTIBLE_RADIUS = 1.15;
const OBSTACLE_COLLISION_WINDOW = 0.85;
const OBSTACLE_LATERAL_RADIUS = GAME.laneWidth * 0.44;
const JUMP_CLEARANCE_HEIGHT = 1.05;
const MISSED_COIN_DISTANCE = -1.2;
const PHYSICS_EPSILON = 1e-9;

const easeOutCubic = (progress: number): number => 1 - (1 - progress) ** 3;

const clampLane = (lane: number): Lane => Math.max(-1, Math.min(1, lane)) as Lane;

const jumpProgressForElapsed = (elapsed: number): number => {
  const touchdownProgress = JUMP_DESCENT_END / JUMP_TOTAL_SECONDS;
  if (elapsed <= JUMP_DESCENT_END) return elapsed / JUMP_TOTAL_SECONDS;
  const recovery = (elapsed - JUMP_DESCENT_END) / (JUMP_RECOVERY_SECONDS * 0.65);
  return touchdownProgress + (1 - touchdownProgress) * Math.min(1, recovery);
};

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
  private jumpVelocity = 0;
  private queuedCommand: ActionCommand | null = null;
  private loadedRows = new Map<string, number>();
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
    this.jumpVelocity = 0;
    this.queuedCommand = null;
    this.loadedRows = new Map<string, number>();
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

    if (command === 'jump' && this.jumpElapsed !== null) return;

    if (this.laneTransition !== null || this.jumpElapsed !== null) {
      this.queuedCommand ??= command;
      return;
    }

    this.beginCommand(command);
  }

  step(dt: number): void {
    if (this.phaseValue !== 'playing' || !Number.isFinite(dt) || dt <= 0) return;

    this.elapsedValue += dt;
    this.updatePlayerMotion(dt);
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
      jumpProgress: this.jumpElapsed === null
        ? null
        : jumpProgressForElapsed(this.jumpElapsed),
      coins,
      obstacles,
      impactKind: this.impactKindValue,
    });
  }

  private beginCommand(command: ActionCommand): void {
    if (command === 'jump') {
      this.jumpElapsed = 0;
      this.jumpVelocity = 0;
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

  private updatePlayerMotion(dt: number): void {
    let remaining = dt;
    let boundaries = 0;
    while (remaining > PHYSICS_EPSILON) {
      if (boundaries > 4) throw new Error('Movement state crossed too many boundaries in one step');
      boundaries += 1;
      if (this.laneTransition !== null) {
        remaining = this.updateLaneTransition(remaining);
      } else if (this.jumpElapsed !== null) {
        remaining = this.updateJump(remaining);
      } else {
        return;
      }
    }
  }

  private updateLaneTransition(dt: number): number {
    if (this.laneTransition === null) return dt;

    const slice = Math.min(dt, LANE_TRANSITION_SECONDS - this.laneTransition.elapsed);
    this.laneTransition.elapsed += slice;
    const progress = Math.min(1, this.laneTransition.elapsed / LANE_TRANSITION_SECONDS);
    const eased = easeOutCubic(progress);
    this.playerXValue = this.laneTransition.from
      + (this.laneTransition.to - this.laneTransition.from) * eased;

    if (progress < 1) return 0;
    this.playerXValue = this.laneTransition.to;
    this.laneTransition = null;
    this.consumeQueuedCommand();
    return dt - slice;
  }

  private updateJump(dt: number): number {
    if (this.jumpElapsed === null) return dt;

    let remaining = dt;
    while (remaining > PHYSICS_EPSILON && this.jumpElapsed !== null) {
      const elapsed: number = this.jumpElapsed;

      if (elapsed < JUMP_ANTICIPATION_SECONDS - PHYSICS_EPSILON) {
        const slice = Math.min(remaining, JUMP_ANTICIPATION_SECONDS - elapsed);
        const nextElapsed = elapsed + slice;
        this.jumpElapsed = nextElapsed;
        remaining -= slice;
        if (nextElapsed >= JUMP_ANTICIPATION_SECONDS - PHYSICS_EPSILON) {
          this.jumpElapsed = JUMP_ANTICIPATION_SECONDS;
          this.jumpVelocity = JUMP_LAUNCH_VELOCITY;
        }
        continue;
      }

      if (elapsed < JUMP_ASCENT_END - PHYSICS_EPSILON) {
        const slice = Math.min(remaining, JUMP_ASCENT_END - elapsed);
        this.playerYValue += this.jumpVelocity * slice
          - 0.5 * JUMP_RISE_GRAVITY * slice ** 2;
        this.jumpVelocity -= JUMP_RISE_GRAVITY * slice;
        const nextElapsed = elapsed + slice;
        this.jumpElapsed = nextElapsed;
        remaining -= slice;
        if (nextElapsed >= JUMP_ASCENT_END - PHYSICS_EPSILON) {
          this.jumpElapsed = JUMP_ASCENT_END;
          this.playerYValue = JUMP_HEIGHT;
          this.jumpVelocity = 0;
        }
        continue;
      }

      if (elapsed < JUMP_DESCENT_END - PHYSICS_EPSILON) {
        const slice = Math.min(remaining, JUMP_DESCENT_END - elapsed);
        this.playerYValue += this.jumpVelocity * slice
          - 0.5 * JUMP_FALL_GRAVITY * slice ** 2;
        this.jumpVelocity -= JUMP_FALL_GRAVITY * slice;
        const nextElapsed = elapsed + slice;
        this.jumpElapsed = nextElapsed;
        remaining -= slice;
        if (nextElapsed >= JUMP_DESCENT_END - PHYSICS_EPSILON) {
          this.jumpElapsed = JUMP_DESCENT_END;
          this.playerYValue = 0;
          this.jumpVelocity = 0;
        }
        continue;
      }

      const slice = Math.min(remaining, JUMP_TOTAL_SECONDS - elapsed);
      const nextElapsed = elapsed + slice;
      this.jumpElapsed = nextElapsed;
      remaining -= slice;
      if (nextElapsed >= JUMP_TOTAL_SECONDS - PHYSICS_EPSILON) {
        this.jumpElapsed = null;
        this.consumeQueuedCommand();
      }
    }
    return remaining;
  }

  private consumeQueuedCommand(): void {
    if (this.queuedCommand === null) return;
    const command = this.queuedCommand;
    this.queuedCommand = null;
    this.beginCommand(command);
  }

  private loadSpawns(): void {
    const rows = this.source.takeUntil(this.distanceValue + GAME.spawnAhead);
    if (this.injectedSource === undefined) {
      const minimumReturnableDistance = this.distanceValue - SPAWN_ROW_RETURN_BEHIND_DISTANCE;
      for (const [id, distance] of this.loadedRows) {
        if (distance < minimumReturnableDistance) this.loadedRows.delete(id);
      }
    }

    for (const row of rows) {
      if (this.loadedRows.has(row.id)) continue;
      this.loadedRows.set(row.id, row.at);

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
        this.multiplierValue = 1;
      }
    }

    this.activeCoins = remaining;
  }

  private collideWithObstacles(): void {
    for (const obstacle of this.activeObstacles) {
      const forward = obstacle.at - this.distanceValue;
      const lateral = obstacle.lane * GAME.laneWidth - this.playerXValue;
      if (Math.abs(lateral) > OBSTACLE_LATERAL_RADIUS
        || Math.abs(forward) > OBSTACLE_COLLISION_WINDOW) continue;
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
