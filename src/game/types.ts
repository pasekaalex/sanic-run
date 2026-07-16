export type Lane = -1 | 0 | 1;
export type ObstacleKind = 'log' | 'candle' | 'fud' | 'gap';
export type GameCommand = 'left' | 'right' | 'jump' | 'pause';
export type GamePhase = 'intro' | 'playing' | 'paused' | 'gameOver';

export interface CoinSpawn { readonly id: string; readonly lane: Lane; readonly height: 0.9 | 2.2; readonly offset: number; }
export interface ObstacleSpawn { readonly id: string; readonly lane: Lane; readonly kind: ObstacleKind; readonly jumpable: boolean; }
export interface SpawnRow { readonly id: string; readonly at: number; readonly coins: readonly CoinSpawn[]; readonly obstacles: readonly ObstacleSpawn[]; }

export interface ActiveCoin extends CoinSpawn {
  readonly at: number;
}

export interface ActiveObstacle extends ObstacleSpawn {
  readonly at: number;
}

export interface SimulationSnapshot {
  readonly phase: GamePhase;
  readonly elapsed: number;
  readonly distance: number;
  readonly speed: number;
  readonly score: number;
  readonly rings: number;
  readonly multiplier: number;
  readonly ringStreak: number;
  readonly lane: Lane;
  readonly playerX: number;
  readonly playerY: number;
  readonly jumpProgress: number | null;
  readonly coins: readonly ActiveCoin[];
  readonly obstacles: readonly ActiveObstacle[];
  readonly impactKind: ObstacleKind | null;
}
