export interface Preferences {
  readonly bestScore: number;
  readonly muted: boolean;
  readonly lowEffects: boolean;
}

const STORAGE_KEY = 'sanic:v1';
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

const prefersReducedMotion = (): boolean => {
  try {
    return typeof window.matchMedia === 'function'
      && window.matchMedia(REDUCED_MOTION_QUERY).matches;
  } catch {
    return false;
  }
};

const defaults = (): Preferences => ({
  bestScore: 0,
  muted: false,
  lowEffects: prefersReducedMotion(),
});

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const isScore = (value: unknown): value is number => (
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
);

const normalizePreferences = (value: unknown): Preferences => {
  const fallback = defaults();
  if (!isRecord(value)) return fallback;

  return {
    bestScore: isScore(value.bestScore) ? value.bestScore : fallback.bestScore,
    muted: typeof value.muted === 'boolean' ? value.muted : fallback.muted,
    lowEffects: typeof value.lowEffects === 'boolean'
      ? value.lowEffects
      : fallback.lowEffects,
  };
};

export const loadPreferences = (): Preferences => {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === null ? defaults() : normalizePreferences(JSON.parse(stored));
  } catch {
    return defaults();
  }
};

export const savePreferences = (preferences: Preferences): void => {
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(normalizePreferences(preferences)),
    );
  } catch {
    // Storage may be disabled or full; preferences remain usable in memory.
  }
};

export const saveBestScore = (score: number): void => {
  const normalizedScore = Math.floor(score);
  if (!isScore(normalizedScore)) return;

  const current = loadPreferences();
  savePreferences({
    ...current,
    bestScore: Math.max(current.bestScore, normalizedScore),
  });
};
