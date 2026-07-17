import { GAME } from '../config';
import { GameSimulation, type SpawnSource } from '../game/simulation';
import type { SimulationSnapshot, SpawnRow } from '../game/types';

const E2E_CRASH_EVENT = 'sanic:e2e-crash';
const E2E_GUARD_STEPS = 4_000;
const DEFAULT_SEED = 0x5a11c;

const freezeRow = (row: SpawnRow): SpawnRow => Object.freeze({
  ...row,
  coins: Object.freeze([...row.coins]),
  obstacles: Object.freeze([...row.obstacles]),
});

const createE2ERows = (): readonly SpawnRow[] => Object.freeze([
  freezeRow({
    id: 'e2e-center',
    at: 300,
    coins: [],
    obstacles: [Object.freeze({
      id: 'e2e-obstacle-center',
      lane: 0,
      kind: 'fud',
      jumpable: false,
    })],
  }),
  freezeRow({
    id: 'e2e-left',
    at: 306,
    coins: [],
    obstacles: [Object.freeze({
      id: 'e2e-obstacle-left',
      lane: -1,
      kind: 'candle',
      jumpable: false,
    })],
  }),
  freezeRow({
    id: 'e2e-right',
    at: 312,
    coins: [],
    obstacles: [Object.freeze({
      id: 'e2e-obstacle-right',
      lane: 1,
      kind: 'log',
      jumpable: false,
    })],
  }),
]);

class E2ESpawnSource implements SpawnSource {
  private readonly rows = createE2ERows();

  public takeUntil(maxDistance: number): readonly SpawnRow[] {
    return this.rows.filter(({ at }) => at <= maxDistance);
  }
}

export interface E2EHarness {
  readonly seed: number;
  readonly source: SpawnSource | undefined;
  readonly simulateUnsupported: boolean;
  readonly lowEffects: boolean;
  readonly testProbes: boolean;
  attachCrashHandler(
    simulation: GameSimulation,
    afterStep: (
      previous: Readonly<SimulationSnapshot>,
      current: Readonly<SimulationSnapshot>,
    ) => void,
  ): void;
  destroy(): void;
}

const readSeed = (parameters: URLSearchParams): number => {
  const value = Number(parameters.get('seed'));
  return Number.isSafeInteger(value) ? value : DEFAULT_SEED;
};

export const createE2EHarness = (parameters: URLSearchParams): E2EHarness => {
  const testMode = parameters.get('e2e') === '1';
  let removeCrashHandler = (): void => undefined;

  return {
    seed: readSeed(parameters),
    source: testMode ? new E2ESpawnSource() : undefined,
    simulateUnsupported: parameters.get('forceFallback') === '1',
    lowEffects: testMode,
    testProbes: testMode,
    attachCrashHandler(simulation, afterStep): void {
      if (!testMode) return;
      const handleCrash = (): void => {
        let steps = 0;
        while (simulation.snapshot().phase === 'playing' && steps < E2E_GUARD_STEPS) {
          const previous = simulation.snapshot();
          simulation.step(GAME.fixedStep);
          const current = simulation.snapshot();
          afterStep(previous, current);
          steps += 1;
        }
      };
      window.addEventListener(E2E_CRASH_EVENT, handleCrash);
      removeCrashHandler = () => window.removeEventListener(E2E_CRASH_EVENT, handleCrash);
    },
    destroy(): void {
      removeCrashHandler();
      removeCrashHandler = (): void => undefined;
    },
  };
};
