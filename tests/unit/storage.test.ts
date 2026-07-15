import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  loadPreferences,
  saveBestScore,
  savePreferences,
} from '../../src/platform/storage';

const STORAGE_KEY = 'sanic:v1';
const storedValues = new Map<string, string>();
const testStorage: Storage = {
  get length() {
    return storedValues.size;
  },
  clear: () => storedValues.clear(),
  getItem: (key) => storedValues.get(key) ?? null,
  key: (index) => [...storedValues.keys()][index] ?? null,
  removeItem: (key) => {
    storedValues.delete(key);
  },
  setItem: (key, value) => {
    storedValues.set(key, value);
  },
};

Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: testStorage,
});

const setReducedMotion = (matches: boolean): void => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockReturnValue({ matches } as MediaQueryList),
  });
};

describe('versioned storage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    setReducedMotion(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Reflect.deleteProperty(window, 'matchMedia');
  });

  it('recovers from malformed data', () => {
    window.localStorage.setItem(STORAGE_KEY, '{broken');

    expect(loadPreferences()).toEqual({
      bestScore: 0,
      muted: false,
      lowEffects: false,
    });
  });

  it('validates stored fields independently', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      bestScore: 1250,
      muted: 'yes',
      lowEffects: true,
    }));

    expect(loadPreferences()).toEqual({
      bestScore: 1250,
      muted: false,
      lowEffects: true,
    });
  });

  it('defaults reduced effects from the media query', () => {
    setReducedMotion(true);

    expect(loadPreferences().lowEffects).toBe(true);
  });

  it('round trips preferences through the versioned key', () => {
    savePreferences({ bestScore: 320, muted: true, lowEffects: true });

    expect(loadPreferences()).toEqual({
      bestScore: 320,
      muted: true,
      lowEffects: true,
    });
    expect(window.localStorage.length).toBe(1);
    expect(window.localStorage.key(0)).toBe(STORAGE_KEY);
  });

  it('keeps the higher best score and preserves preferences', () => {
    savePreferences({ bestScore: 100, muted: true, lowEffects: true });
    saveBestScore(900);
    saveBestScore(200);

    expect(loadPreferences()).toEqual({
      bestScore: 900,
      muted: true,
      lowEffects: true,
    });
  });

  it('never throws when browser storage is blocked', () => {
    vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });

    expect(() => loadPreferences()).not.toThrow();
    expect(() => savePreferences({ bestScore: 4, muted: true, lowEffects: false })).not.toThrow();
    expect(() => saveBestScore(10)).not.toThrow();
  });
});
