export const BASE_BPM = 120;
export const MAX_BPM = 132;
export const BEATS_PER_BAR = 4;
export const BARS = 16;
export const LOOP_BEATS = BARS * BEATS_PER_BAR;
export const STEPS_PER_BEAT = 4;
export const LOOP_STEPS = LOOP_BEATS * STEPS_PER_BEAT;

export interface NoteEvent {
  readonly beat: number;
  readonly midi: number;
  readonly duration: number;
  readonly velocity: number;
}

export type DrumKind = 'kick' | 'snare' | 'hat' | 'openHat';

export interface DrumEvent {
  readonly beat: number;
  readonly kind: DrumKind;
  readonly velocity: number;
}

const freezeNotes = (events: readonly NoteEvent[]): readonly NoteEvent[] => Object.freeze(
  events.map((event) => Object.freeze(event)),
);

const freezeDrums = (events: readonly DrumEvent[]): readonly DrumEvent[] => Object.freeze(
  events.map((event) => Object.freeze(event)),
);

// Eight eighth-note slots per bar. Rests give the square lead room to read as a tune
// instead of becoming another continuous buzz.
const LEAD_BARS: readonly (readonly (number | null)[])[] = Object.freeze([
  [74, null, 77, 81, 79, null, 77, 76],
  [74, 74, 77, 79, 81, null, 84, 81],
  [70, null, 74, 77, 76, 74, 69, 72],
  [74, 77, 76, 72, 74, null, 69, null],
  [74, null, 79, 81, 82, 81, 79, 74],
  [77, 77, 81, 84, 82, null, 81, 79],
  [72, null, 76, 79, 81, 79, 76, 72],
  [73, 76, 79, 76, 74, null, 69, 73],
  [81, null, 79, 77, 74, 77, 81, null],
  [82, 81, 77, 74, 70, null, 74, 77],
  [79, null, 81, 84, 83, 79, 76, 72],
  [76, 79, 81, 79, 76, null, 72, 69],
  [74, 77, 81, 86, 84, 81, 79, 77],
  [70, 74, 77, 82, 81, 77, 74, 70],
  [74, 81, 84, 86, 84, 81, 77, 76],
  [74, 77, 81, 84, 81, 77, 76, 69],
]);

export const LEAD_EVENTS: readonly NoteEvent[] = freezeNotes(
  LEAD_BARS.flatMap((bar, barIndex) => bar.flatMap((midi, slot) => {
    if (midi === null) return [];
    return [{
      beat: barIndex * BEATS_PER_BAR + slot / 2,
      midi,
      duration: slot === 7 ? 0.32 : 0.38,
      velocity: slot === 0 || slot === 4 ? 1 : 0.82,
    }];
  })),
);

// Each bar uses a deliberately compact four-note color. The sequence is original;
// it favors added tones and suspended colors over a copied game progression.
const ARP_CHORDS: readonly (readonly number[])[] = Object.freeze([
  [62, 65, 69, 76], [58, 62, 65, 69], [60, 65, 67, 69], [60, 62, 67, 69],
  [55, 58, 62, 65], [58, 62, 65, 70], [60, 64, 67, 74], [57, 61, 64, 67],
  [62, 65, 69, 72], [58, 62, 65, 69], [60, 64, 69, 74], [55, 60, 64, 67],
  [62, 67, 69, 76], [58, 65, 69, 74], [60, 64, 67, 74], [57, 62, 64, 73],
]);

export const ARPEGGIO_EVENTS: readonly NoteEvent[] = freezeNotes(
  ARP_CHORDS.flatMap((chord, barIndex) => Array.from({ length: 16 }, (_, step) => ({
    beat: barIndex * BEATS_PER_BAR + step / STEPS_PER_BEAT,
    midi: chord[step % chord.length]! + (step % 8 >= 4 ? 12 : 0),
    duration: 0.19,
    velocity: step % 4 === 0 ? 0.72 : 0.5,
  }))),
);

const BASS_ROOTS: readonly number[] = Object.freeze([
  38, 46, 41, 36,
  43, 46, 36, 45,
  38, 46, 41, 36,
  38, 46, 36, 45,
]);

export const BASS_EVENTS: readonly NoteEvent[] = freezeNotes(
  BASS_ROOTS.flatMap((root, barIndex) => [0, 1, 2, 3].map((beatInBar) => ({
    beat: barIndex * BEATS_PER_BAR + beatInBar,
    midi: root + ([0, 7, 12, 7][beatInBar] ?? 0),
    duration: 0.72,
    velocity: beatInBar === 0 ? 0.9 : 0.7,
  }))),
);

export const DRUM_EVENTS: readonly DrumEvent[] = freezeDrums(
  Array.from({ length: BARS }, (_, barIndex) => Array.from({ length: 16 }, (_, step) => {
    const beat = barIndex * BEATS_PER_BAR + step / STEPS_PER_BEAT;
    const events: DrumEvent[] = [];
    if (step % 2 === 0) events.push({ beat, kind: 'hat', velocity: step % 4 === 0 ? 0.58 : 0.4 });
    if (step === 0 || step === 8) events.push({ beat, kind: 'kick', velocity: step === 0 ? 1 : 0.84 });
    if (step === 4 || step === 12) events.push({ beat, kind: 'snare', velocity: 0.82 });
    if (step === 14) events.push({ beat, kind: 'openHat', velocity: barIndex % 4 === 3 ? 0.72 : 0.48 });
    return events;
  }).flat()).flat(),
);

export const loopDurationSeconds = (bpm: number): number => {
  const safeBpm = Number.isFinite(bpm) && bpm > 0 ? bpm : BASE_BPM;
  return LOOP_BEATS * 60 / safeBpm;
};

export const midiToFrequency = (midi: number): number => 440 * 2 ** ((midi - 69) / 12);
