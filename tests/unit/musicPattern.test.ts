import { describe, expect, it } from 'vitest';
import {
  ARPEGGIO_EVENTS,
  BASE_BPM,
  BARS,
  BASS_EVENTS,
  BEATS_PER_BAR,
  DRUM_EVENTS,
  LEAD_EVENTS,
  LOOP_BEATS,
  MAX_BPM,
  loopDurationSeconds,
} from '../../src/platform/musicPattern';

describe('original $SANIC music pattern', () => {
  it('defines a deterministic 16-bar, 64-beat loop lasting 32 seconds at base tempo', () => {
    expect(BARS).toBe(16);
    expect(BEATS_PER_BAR).toBe(4);
    expect(LOOP_BEATS).toBe(64);
    expect(BASE_BPM).toBe(120);
    expect(MAX_BPM).toBe(132);
    expect(loopDurationSeconds(BASE_BPM)).toBe(32);
  });

  it('keeps every melodic event finite, audible, and inside the loop', () => {
    for (const event of [...LEAD_EVENTS, ...ARPEGGIO_EVENTS, ...BASS_EVENTS]) {
      expect(Number.isFinite(event.beat)).toBe(true);
      expect(event.beat).toBeGreaterThanOrEqual(0);
      expect(event.beat).toBeLessThan(LOOP_BEATS);
      expect(event.duration).toBeGreaterThan(0);
      expect(event.duration).toBeLessThanOrEqual(BEATS_PER_BAR);
      expect(event.midi).toBeGreaterThanOrEqual(36);
      expect(event.midi).toBeLessThanOrEqual(88);
      expect(event.velocity).toBeGreaterThan(0);
      expect(event.velocity).toBeLessThanOrEqual(1);
    }
  });

  it('supplies melody, forward arpeggiation, bass, and percussion across the full phrase', () => {
    expect(LEAD_EVENTS.length).toBeGreaterThan(60);
    expect(ARPEGGIO_EVENTS).toHaveLength(256);
    expect(BASS_EVENTS).toHaveLength(64);
    expect(DRUM_EVENTS.length).toBeGreaterThan(150);

    for (let bar = 0; bar < BARS; bar += 1) {
      const start = bar * BEATS_PER_BAR;
      const end = start + BEATS_PER_BAR;
      expect(LEAD_EVENTS.some(({ beat }) => beat >= start && beat < end)).toBe(true);
      expect(BASS_EVENTS.some(({ beat }) => beat >= start && beat < end)).toBe(true);
      expect(DRUM_EVENTS.some(({ beat }) => beat >= start && beat < end)).toBe(true);
    }
  });

  it('uses a distinct final-bar turnaround instead of cloning the opening bar', () => {
    const notesForBar = (bar: number): readonly number[] => {
      const start = bar * BEATS_PER_BAR;
      return LEAD_EVENTS
        .filter(({ beat }) => beat >= start && beat < start + BEATS_PER_BAR)
        .map(({ midi }) => midi);
    };

    expect(notesForBar(15)).not.toEqual(notesForBar(0));
    expect(new Set(notesForBar(15)).size).toBeGreaterThanOrEqual(5);
  });
});
