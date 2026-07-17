#!/usr/bin/env node

/**
 * Deterministic original chiptune renderer for SANIC's three zones.
 *
 * Every melody, bass line, arpeggio, and drum hit below was composed for this
 * project. The renderer uses mathematical oscillators and seeded noise only:
 * there are no samples or interpolated third-party recordings.
 */

import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawnSync } from 'node:child_process';

const SAMPLE_RATE = 44_100;
const CHANNELS = 1;
const BARS = 16;
const BEATS_PER_BAR = 4;
const TOTAL_BEATS = BARS * BEATS_PER_BAR;
const MP3_BITRATE = 96_000;
const PAYLOAD_LIMIT_BYTES = 950_000;
const TARGET_PCM_PEAK = 0.52;
const BOUNDARY_FADE_SECONDS = 0.012;
const VALID_DURATION_TOLERANCE_SECONDS = 0.08;
const MAX_ALLOWED_PEAK_DBFS = -1;

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outputDirectory = join(projectRoot, 'public', 'music');

const note = (offset, midi, duration = 0.45, velocity = 1) =>
  Object.freeze({ offset, midi, duration, velocity });

const ARRANGEMENTS = Object.freeze([
  Object.freeze({
    id: 'ringwood-rush',
    title: 'Ringwood Rush',
    bpm: 148,
    leadWave: 'pulse',
    leadDuty: 0.25,
    arpDivision: 0.5,
    chords: Object.freeze([
      [62, 66, 69, 73], [67, 71, 74, 78], [59, 62, 66, 71], [57, 61, 64, 69],
      [62, 66, 69, 73], [66, 69, 73, 76], [67, 71, 74, 78], [57, 61, 64, 71],
      [59, 62, 66, 71], [67, 71, 74, 78], [62, 66, 69, 73], [57, 61, 64, 69],
      [67, 71, 74, 78], [57, 61, 64, 71], [62, 66, 69, 73], [57, 61, 64, 69],
    ]),
    leadBars: Object.freeze([
      [note(0, 74, .65), note(.75, 78, .2, .82), note(1, 81, .45), note(1.75, 76, .45), note(2.5, 78, .7), note(3.35, 73, .45)],
      [note(0, 71, .45), note(.5, 74, .45), note(1.25, 78, .7), note(2.25, 76, .2), note(2.5, 74, .45), note(3, 71, .8)],
      [note(.25, 71, .45), note(.75, 74, .2), note(1, 78, .7), note(2, 76, .45), note(2.75, 74, .2), note(3, 69, .8)],
      [note(0, 73, .2), note(.25, 76, .45), note(1, 81, .45), note(1.75, 78, .2), note(2, 76, .7), note(3, 73, .7)],
      [note(0, 74, .45), note(.5, 76, .2), note(.75, 78, .45), note(1.5, 81, .45), note(2.25, 83, .2), note(2.5, 81, .45), note(3.25, 78, .65)],
      [note(0, 76, .7), note(1, 73, .45), note(1.75, 69, .45), note(2.5, 73, .2), note(2.75, 76, .8)],
      [note(.25, 74, .2), note(.5, 78, .45), note(1.25, 83, .45), note(2, 81, .7), note(3, 78, .7)],
      [note(0, 76, .45), note(.5, 73, .45), note(1.25, 71, .7), note(2.25, 73, .2), note(2.5, 76, .45), note(3.25, 69, .6)],
      [note(0, 71, .2), note(.25, 74, .2), note(.5, 78, .7), note(1.5, 74, .45), note(2.25, 83, .45), note(3, 81, .7)],
      [note(0, 78, .45), note(.75, 74, .2), note(1, 71, .45), note(1.75, 74, .7), note(2.75, 78, .8)],
      [note(.25, 81, .45), note(1, 78, .45), note(1.75, 76, .2), note(2, 74, .7), note(3, 73, .7)],
      [note(0, 69, .45), note(.75, 73, .45), note(1.5, 76, .7), note(2.5, 78, .2), note(2.75, 76, .8)],
      [note(0, 71, .45), note(.5, 74, .2), note(.75, 78, .45), note(1.5, 83, .7), note(2.75, 81, .7)],
      [note(0, 81, .2), note(.25, 78, .45), note(1, 76, .2), note(1.25, 73, .7), note(2.5, 76, .45), note(3.25, 78, .5)],
      [note(0, 74, .45), note(.5, 78, .45), note(1, 81, .7), note(2, 78, .2), note(2.25, 76, .45), note(3, 73, .75)],
      [note(0, 69, .2), note(.25, 73, .45), note(1, 76, .45), note(1.75, 78, .2), note(2, 74, .7), note(3, 73, .2), note(3.25, 74, .55)],
    ]),
    bassPattern: 'syncopated',
    drums: 'restrained',
  }),
  Object.freeze({
    id: 'liquidity-loop',
    title: 'Liquidity Loop',
    bpm: 164,
    leadWave: 'pulse',
    leadDuty: 0.375,
    arpDivision: 0.25,
    chords: Object.freeze([
      [61, 64, 68, 75], [57, 61, 64, 68], [64, 66, 71, 76], [59, 64, 66, 71],
      [61, 64, 68, 73], [56, 61, 64, 68], [57, 61, 64, 71], [59, 63, 66, 73],
      [61, 64, 68, 75], [64, 68, 71, 78], [57, 61, 64, 68], [59, 64, 66, 71],
      [56, 61, 64, 68], [57, 61, 64, 71], [59, 63, 66, 73], [61, 64, 68, 75],
    ]),
    leadBars: Object.freeze([
      [note(.5, 68, .2), note(.75, 73, .45), note(1.5, 75, .2), note(1.75, 76, .7), note(2.75, 71, .2), note(3, 73, .65)],
      [note(0, 69, .45), note(.75, 73, .2), note(1, 76, .45), note(1.75, 80, .45), note(2.5, 76, .7), note(3.5, 73, .35)],
      [note(.25, 71, .45), note(1, 76, .7), note(2, 78, .2), note(2.25, 76, .2), note(2.5, 71, .45), note(3.25, 68, .55)],
      [note(0, 66, .2), note(.25, 71, .45), note(1, 73, .45), note(1.75, 75, .7), note(2.75, 71, .7)],
      [note(0, 68, .2), note(.25, 73, .2), note(.5, 76, .45), note(1.25, 80, .45), note(2, 83, .2), note(2.25, 80, .45), note(3, 76, .7)],
      [note(.5, 73, .45), note(1.25, 76, .2), note(1.5, 80, .45), note(2.25, 76, .7), note(3.25, 73, .5)],
      [note(0, 69, .45), note(.75, 71, .2), note(1, 76, .7), note(2, 73, .45), note(2.75, 71, .2), note(3, 68, .7)],
      [note(.25, 66, .2), note(.5, 71, .2), note(.75, 75, .45), note(1.5, 78, .45), note(2.25, 75, .2), note(2.5, 73, .7), note(3.5, 71, .35)],
      [note(0, 80, .2), note(.25, 76, .45), note(1, 73, .2), note(1.25, 68, .7), note(2.5, 73, .2), note(2.75, 75, .7)],
      [note(0, 76, .45), note(.75, 80, .45), note(1.5, 83, .2), note(1.75, 80, .45), note(2.5, 78, .2), note(2.75, 76, .7)],
      [note(.25, 73, .45), note(1, 76, .2), note(1.25, 80, .7), note(2.5, 76, .45), note(3.25, 73, .55)],
      [note(0, 71, .2), note(.25, 75, .45), note(1, 78, .7), note(2.25, 75, .45), note(3, 71, .7)],
      [note(.5, 68, .2), note(.75, 73, .45), note(1.5, 76, .7), note(2.75, 80, .45), note(3.5, 76, .35)],
      [note(0, 69, .45), note(.75, 73, .45), note(1.5, 76, .2), note(1.75, 80, .7), note(3, 76, .7)],
      [note(.25, 71, .2), note(.5, 75, .45), note(1.25, 78, .2), note(1.5, 80, .45), note(2.25, 78, .7), note(3.25, 73, .5)],
      [note(0, 68, .2), note(.25, 71, .2), note(.5, 73, .45), note(1.25, 76, .45), note(2, 75, .2), note(2.25, 73, .45), note(3, 68, .8)],
    ]),
    bassPattern: 'suspended',
    drums: 'backbeat',
  }),
  Object.freeze({
    id: 'ansem-after-dark',
    title: 'Ansem After Dark',
    bpm: 178,
    leadWave: 'pulse',
    leadDuty: 0.2,
    arpDivision: 0.25,
    chords: Object.freeze([
      [64, 67, 71, 76], [60, 64, 67, 71], [67, 71, 74, 78], [62, 66, 69, 74],
      [64, 67, 71, 76], [60, 64, 67, 72], [57, 60, 64, 69], [62, 66, 69, 74],
      [64, 67, 71, 76], [67, 71, 74, 79], [60, 64, 67, 71], [62, 66, 69, 74],
      [57, 60, 64, 69], [60, 64, 67, 72], [62, 66, 69, 74], [64, 67, 71, 76],
    ]),
    leadBars: Object.freeze([
      [note(0, 76, .2), note(.25, 79, .2), note(.5, 83, .45), note(1.25, 81, .2), note(1.5, 79, .45), note(2.25, 86, .2), note(2.5, 83, .7)],
      [note(0, 79, .45), note(.75, 76, .2), note(1, 72, .45), note(1.75, 76, .2), note(2, 79, .45), note(2.75, 81, .7)],
      [note(.25, 83, .2), note(.5, 86, .45), note(1.25, 83, .2), note(1.5, 79, .7), note(2.75, 78, .2), note(3, 74, .7)],
      [note(0, 81, .2), note(.25, 78, .45), note(1, 74, .2), note(1.25, 78, .45), note(2, 81, .7), note(3.25, 78, .5)],
      [note(0, 76, .2), note(.25, 79, .2), note(.5, 83, .2), note(.75, 86, .45), note(1.5, 88, .2), note(1.75, 86, .45), note(2.5, 83, .2), note(2.75, 81, .7)],
      [note(.25, 84, .45), note(1, 79, .2), note(1.25, 76, .7), note(2.5, 79, .45), note(3.25, 84, .5)],
      [note(0, 81, .2), note(.25, 84, .45), note(1, 88, .2), note(1.25, 84, .45), note(2, 81, .2), note(2.25, 79, .7), note(3.5, 76, .3)],
      [note(0, 78, .45), note(.75, 81, .2), note(1, 86, .45), note(1.75, 83, .2), note(2, 81, .45), note(2.75, 78, .7)],
      [note(.25, 83, .2), note(.5, 86, .2), note(.75, 88, .45), note(1.5, 86, .2), note(1.75, 83, .45), note(2.5, 79, .2), note(2.75, 76, .7)],
      [note(0, 79, .2), note(.25, 83, .45), note(1, 86, .2), note(1.25, 91, .45), note(2, 88, .7), note(3, 86, .7)],
      [note(.25, 84, .45), note(1, 79, .2), note(1.25, 76, .45), note(2, 79, .2), note(2.25, 83, .45), note(3, 81, .7)],
      [note(0, 78, .2), note(.25, 81, .2), note(.5, 86, .7), note(1.75, 83, .45), note(2.5, 81, .2), note(2.75, 78, .7)],
      [note(0, 81, .2), note(.25, 84, .45), note(1, 88, .2), note(1.25, 84, .7), note(2.5, 81, .2), note(2.75, 79, .7)],
      [note(.25, 84, .2), note(.5, 88, .45), note(1.25, 91, .2), note(1.5, 88, .45), note(2.25, 84, .7), note(3.25, 81, .5)],
      [note(0, 78, .2), note(.25, 81, .45), note(1, 86, .2), note(1.25, 83, .45), note(2, 81, .2), note(2.25, 78, .7), note(3.5, 74, .3)],
      [note(0, 76, .2), note(.25, 79, .2), note(.5, 83, .45), note(1.25, 81, .2), note(1.5, 79, .45), note(2.25, 76, .2), note(2.5, 74, .45), note(3.25, 76, .55)],
    ]),
    bassPattern: 'octaves',
    drums: 'full',
  }),
]);

const midiFrequency = (midi) => 440 * 2 ** ((midi - 69) / 12);

const polyBlep = (phase, increment) => {
  if (phase < increment) {
    const position = phase / increment;
    return position + position - position * position - 1;
  }
  if (phase > 1 - increment) {
    const position = (phase - 1) / increment;
    return position * position + position + position + 1;
  }
  return 0;
};

const oscillatorSample = (phase, increment, wave, duty) => {
  if (wave === 'triangle') return (2 / Math.PI) * Math.asin(Math.sin(phase * Math.PI * 2));
  if (wave === 'sine') return Math.sin(phase * Math.PI * 2);
  const shifted = (phase - duty + 1) % 1;
  return (phase < duty ? 1 : -1) + polyBlep(phase, increment) - polyBlep(shifted, increment);
};

const renderTone = (mix, secondsPerBeat, event) => {
  const start = Math.max(0, Math.round(event.beat * secondsPerBeat * SAMPLE_RATE));
  const durationSeconds = event.duration * secondsPerBeat;
  const length = Math.max(2, Math.round(durationSeconds * SAMPLE_RATE));
  const end = Math.min(mix.length, start + length);
  const attackSamples = Math.max(2, Math.min(Math.round(SAMPLE_RATE * 0.006), Math.floor(length * .18)));
  const releaseSamples = Math.max(2, Math.min(Math.round(SAMPLE_RATE * 0.045), Math.floor(length * .34)));
  const frequency = midiFrequency(event.midi);
  let phase = 0;

  for (let index = start; index < end; index += 1) {
    const local = index - start;
    const progress = local / Math.max(1, length - 1);
    const vibrato = event.vibrato === 0
      ? 0
      : Math.sin(Math.PI * 2 * 5.3 * local / SAMPLE_RATE) * (event.vibrato ?? .002);
    const increment = frequency * (1 + vibrato) / SAMPLE_RATE;
    phase = (phase + increment) % 1;
    const attack = local < attackSamples
      ? Math.sin((local / attackSamples) * Math.PI * .5)
      : 1;
    const releaseStart = length - releaseSamples;
    const release = local >= releaseStart
      ? Math.cos(((local - releaseStart) / releaseSamples) * Math.PI * .5)
      : 1;
    const contour = 1 - progress * (event.decay ?? .12);
    mix[index] += oscillatorSample(phase, increment, event.wave, event.duty ?? .5)
      * attack * release * contour * event.volume;
  }
};

const seededNoise = (seed) => {
  let state = seed >>> 0;
  return () => {
    state = (state * 1_664_525 + 1_013_904_223) >>> 0;
    return state / 0x80000000 - 1;
  };
};

const renderDrum = (mix, secondsPerBeat, beat, kind, velocity, seed) => {
  const start = Math.round(beat * secondsPerBeat * SAMPLE_RATE);
  const duration = kind === 'kick' ? .16 : kind === 'snare' ? .13 : kind === 'openHat' ? .12 : .038;
  const length = Math.min(mix.length - start, Math.round(duration * SAMPLE_RATE));
  const random = seededNoise(seed);
  let priorNoise = 0;
  let phase = 0;

  for (let local = 0; local < length; local += 1) {
    const progress = local / Math.max(1, length - 1);
    const attack = Math.sin(Math.min(1, local / Math.max(1, SAMPLE_RATE * .002)) * Math.PI * .5);
    let sample;
    if (kind === 'kick') {
      const frequency = 118 * (1 - progress) + 43;
      phase = (phase + frequency / SAMPLE_RATE) % 1;
      sample = Math.sin(phase * Math.PI * 2) * Math.exp(-progress * 6.4);
    } else {
      const noise = random();
      const highpassed = noise - priorNoise * .88;
      priorNoise = noise;
      const decay = kind === 'snare' ? 7.8 : kind === 'openHat' ? 11 : 24;
      const tone = kind === 'snare' ? Math.sin(progress * Math.PI * 2 * 22) * .18 : 0;
      sample = (highpassed + tone) * Math.exp(-progress * decay);
    }
    const release = Math.sin(progress * Math.PI);
    mix[start + local] += sample * attack * release * velocity;
  }
};

const chordRoot = (chord) => chord[0] - 24;

const addArrangementEvents = (mix, arrangement) => {
  const secondsPerBeat = 60 / arrangement.bpm;

  for (let bar = 0; bar < BARS; bar += 1) {
    const barBeat = bar * BEATS_PER_BAR;
    const chord = arrangement.chords[bar];
    const leadEvents = arrangement.leadBars[bar];

    for (const event of leadEvents) {
      renderTone(mix, secondsPerBeat, {
        beat: barBeat + event.offset,
        midi: event.midi,
        duration: event.duration,
        volume: .175 * event.velocity,
        wave: arrangement.leadWave,
        duty: arrangement.leadDuty,
        vibrato: .0024,
        decay: .1,
      });
      const echoBeat = barBeat + event.offset + .75;
      if (echoBeat + event.duration * .55 < TOTAL_BEATS) {
        renderTone(mix, secondsPerBeat, {
          beat: echoBeat,
          midi: event.midi,
          duration: event.duration * .55,
          volume: .031 * event.velocity,
          wave: arrangement.leadWave,
          duty: arrangement.leadDuty,
          vibrato: .0015,
          decay: .25,
        });
      }
    }

    const arpSteps = Math.round(BEATS_PER_BAR / arrangement.arpDivision);
    for (let step = 0; step < arpSteps; step += 1) {
      if (arrangement.id === 'ringwood-rush' && (step + bar) % 7 === 5) continue;
      const direction = bar % 4 >= 2 ? -1 : 1;
      const chordIndex = direction > 0
        ? (step + bar) % chord.length
        : (chord.length - 1 - ((step + bar) % chord.length));
      const octave = arrangement.id === 'ansem-after-dark' && step % 8 >= 6 ? 12 : 0;
      renderTone(mix, secondsPerBeat, {
        beat: barBeat + step * arrangement.arpDivision,
        midi: chord[chordIndex] + octave,
        duration: arrangement.arpDivision * .68,
        volume: arrangement.id === 'ringwood-rush' ? .036 : .043,
        wave: 'pulse',
        duty: arrangement.id === 'liquidity-loop' ? .125 : .5,
        vibrato: 0,
        decay: .36,
      });
    }

    for (const beatOffset of [0, 2]) {
      for (const midi of chord.slice(0, 3)) {
        renderTone(mix, secondsPerBeat, {
          beat: barBeat + beatOffset,
          midi: midi - 12,
          duration: .19,
          volume: .026,
          wave: 'pulse',
          duty: .5,
          vibrato: 0,
          decay: .5,
        });
      }
    }

    const root = chordRoot(chord);
    const bassEvents = arrangement.bassPattern === 'octaves'
      ? [[0, root, .42], [.5, root + 12, .36], [1, root, .42], [1.5, root + 7, .36], [2, root, .42], [2.5, root + 12, .36], [3, root + 7, .42], [3.5, root + 12, .34]]
      : arrangement.bassPattern === 'suspended'
        ? [[0, root, .72], [1.25, root + 7, .46], [2, root + 12, .46], [2.75, root + 5, .22], [3, root + 7, .72]]
        : [[0, root, .7], [1.5, root + 7, .42], [2.25, root + 12, .22], [2.5, root, .7], [3.5, root + 7, .35]];
    for (const [offset, midi, duration] of bassEvents) {
      renderTone(mix, secondsPerBeat, {
        beat: barBeat + offset,
        midi,
        duration,
        volume: arrangement.id === 'ansem-after-dark' ? .16 : .145,
        wave: 'triangle',
        duty: .5,
        vibrato: 0,
        decay: .18,
      });
    }

    const kickOffsets = arrangement.drums === 'restrained'
      ? [0, 2.5]
      : arrangement.drums === 'backbeat'
        ? [0, 1.75, 2.5]
        : [0, 1.5, 2, 2.75, 3.5];
    const snareOffsets = arrangement.drums === 'full' ? [1, 2.75, 3] : [1, 3];
    for (const offset of kickOffsets) {
      renderDrum(mix, secondsPerBeat, barBeat + offset, 'kick', .22, bar * 101 + offset * 32 + arrangement.bpm);
    }
    for (const offset of snareOffsets) {
      renderDrum(mix, secondsPerBeat, barBeat + offset, 'snare', arrangement.drums === 'restrained' ? .085 : .13, bar * 211 + offset * 64 + arrangement.bpm);
    }
    const hatDivision = arrangement.drums === 'restrained' ? .5 : .25;
    for (let offset = 0; offset < BEATS_PER_BAR; offset += hatDivision) {
      const open = arrangement.drums !== 'restrained' && Math.abs(offset - 3.5) < .01;
      renderDrum(
        mix,
        secondsPerBeat,
        barBeat + offset,
        open ? 'openHat' : 'hat',
        (offset % 1 === 0 ? .034 : .022) * (arrangement.drums === 'full' ? 1.2 : 1),
        bar * 307 + Math.round(offset * 64) + arrangement.bpm,
      );
    }
  }
};

const sealAndNormalize = (mix) => {
  for (let index = 0; index < mix.length; index += 1) {
    mix[index] = Math.tanh(mix[index] * .92);
  }

  const fadeSamples = Math.min(
    Math.round(BOUNDARY_FADE_SECONDS * SAMPLE_RATE),
    Math.floor(mix.length / 4),
  );
  for (let index = 0; index < fadeSamples; index += 1) {
    const gain = Math.sin((index / Math.max(1, fadeSamples - 1)) * Math.PI * .5);
    mix[index] *= gain;
    mix[mix.length - 1 - index] *= gain;
  }
  mix[0] = 0;
  mix[mix.length - 1] = 0;

  let peak = 0;
  for (const sample of mix) peak = Math.max(peak, Math.abs(sample));
  const scale = peak > 0 ? TARGET_PCM_PEAK / peak : 1;
  const pcm = new Int16Array(mix.length);
  for (let index = 0; index < mix.length; index += 1) {
    pcm[index] = Math.round(Math.max(-1, Math.min(1, mix[index] * scale)) * 32_767);
  }
  pcm[0] = 0;
  pcm[pcm.length - 1] = 0;
  return pcm;
};

const renderArrangement = (arrangement) => {
  const duration = TOTAL_BEATS * 60 / arrangement.bpm;
  const frameCount = Math.round(duration * SAMPLE_RATE);
  const mix = new Float64Array(frameCount);
  addArrangementEvents(mix, arrangement);
  return {
    duration: frameCount / SAMPLE_RATE,
    pcm: sealAndNormalize(mix),
  };
};

const writeWav = (path, pcm) => {
  const dataBytes = pcm.length * 2;
  const wav = Buffer.allocUnsafe(44 + dataBytes);
  wav.write('RIFF', 0, 'ascii');
  wav.writeUInt32LE(36 + dataBytes, 4);
  wav.write('WAVE', 8, 'ascii');
  wav.write('fmt ', 12, 'ascii');
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(CHANNELS, 22);
  wav.writeUInt32LE(SAMPLE_RATE, 24);
  wav.writeUInt32LE(SAMPLE_RATE * CHANNELS * 2, 28);
  wav.writeUInt16LE(CHANNELS * 2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write('data', 36, 'ascii');
  wav.writeUInt32LE(dataBytes, 40);
  for (let index = 0; index < pcm.length; index += 1) {
    wav.writeInt16LE(pcm[index], 44 + index * 2);
  }
  writeFileSync(path, wav);
};

const encodeMp3 = (wavPath, outputPath, arrangement) => {
  execFileSync('ffmpeg', [
    '-y',
    '-hide_banner',
    '-loglevel', 'error',
    '-i', wavPath,
    '-map_metadata', '-1',
    '-ac', String(CHANNELS),
    '-ar', String(SAMPLE_RATE),
    '-codec:a', 'libmp3lame',
    '-b:a', '96k',
    '-compression_level', '2',
    '-write_xing', '1',
    '-id3v2_version', '3',
    '-metadata', `title=${arrangement.title}`,
    '-metadata', 'artist=SANIC Original Audio',
    '-metadata', 'album=SANIC Zone Loops',
    '-metadata', `TBPM=${arrangement.bpm}`,
    outputPath,
  ], { stdio: 'inherit' });
};

const ffprobe = (path) => JSON.parse(execFileSync('ffprobe', [
  '-v', 'error',
  '-show_entries',
  'stream=codec_name,sample_rate,channels,bit_rate,duration:format=duration,size:format_tags=title,artist,album,TBPM',
  '-of', 'json',
  path,
], { encoding: 'utf8' }));

const readPeaks = (path) => {
  const sampleResult = spawnSync('ffmpeg', [
    '-hide_banner',
    '-nostats',
    '-i', path,
    '-filter:a', 'volumedetect',
    '-f', 'null',
    '-',
  ], { encoding: 'utf8' });
  if (sampleResult.status !== 0) throw new Error(sampleResult.stderr);
  const sampleMatches = [...sampleResult.stderr.matchAll(/max_volume:\s*(-?(?:inf|\d+(?:\.\d+)?)) dB/g)];
  const samplePeak = Number(sampleMatches.at(-1)?.[1]);

  const trueResult = spawnSync('ffmpeg', [
    '-hide_banner',
    '-nostats',
    '-i', path,
    '-filter:a', 'ebur128=peak=true',
    '-f', 'null',
    '-',
  ], { encoding: 'utf8' });
  if (trueResult.status !== 0) throw new Error(trueResult.stderr);
  const trueMatches = [...trueResult.stderr.matchAll(/Peak:\s*(-?(?:inf|\d+(?:\.\d+)?)) dBFS/g)];
  const truePeak = Number(trueMatches.at(-1)?.[1]);
  return { samplePeak, truePeak };
};

const readBoundary = (path) => {
  const decoded = spawnSync('ffmpeg', [
    '-v', 'error',
    '-i', path,
    '-f', 'f32le',
    '-acodec', 'pcm_f32le',
    '-ac', '1',
    '-ar', String(SAMPLE_RATE),
    '-',
  ], { maxBuffer: 16 * 1024 * 1024 });
  if (decoded.status !== 0) throw new Error(decoded.stderr.toString());
  const bytes = decoded.stdout;
  const samples = bytes.length / 4;
  const first = bytes.readFloatLE(0);
  const last = bytes.readFloatLE(bytes.length - 4);
  return {
    decodedSamples: samples,
    first,
    last,
    seamDelta: Math.abs(first - last),
  };
};

const invariant = (condition, message) => {
  if (!condition) throw new Error(message);
};

const validateAssets = () => {
  const metadata = [];
  let combinedBytes = 0;

  for (const arrangement of ARRANGEMENTS) {
    const path = join(outputDirectory, `${arrangement.id}.mp3`);
    const probe = ffprobe(path);
    const stream = probe.streams?.[0];
    const duration = Number(stream?.duration ?? probe.format?.duration);
    const expectedDuration = TOTAL_BEATS * 60 / arrangement.bpm;
    const bytes = statSync(path).size;
    const sampleRate = Number(stream?.sample_rate);
    const channels = Number(stream?.channels);
    const bitrate = Number(stream?.bit_rate);
    const peaks = readPeaks(path);
    const boundary = readBoundary(path);
    const tags = probe.format?.tags ?? {};

    invariant(stream?.codec_name === 'mp3', `${arrangement.id}: codec is not MP3`);
    invariant(tags.title === arrangement.title, `${arrangement.id}: title metadata is missing`);
    invariant(tags.TBPM === String(arrangement.bpm), `${arrangement.id}: BPM metadata is missing`);
    invariant(channels === CHANNELS, `${arrangement.id}: expected mono, got ${channels} channels`);
    invariant(sampleRate === SAMPLE_RATE, `${arrangement.id}: expected ${SAMPLE_RATE} Hz, got ${sampleRate}`);
    invariant(
      bitrate >= MP3_BITRATE - 2_000 && bitrate <= MP3_BITRATE + 2_000,
      `${arrangement.id}: bitrate ${bitrate} is outside the 96 kbps gate`,
    );
    invariant(
      Math.abs(duration - expectedDuration) <= VALID_DURATION_TOLERANCE_SECONDS,
      `${arrangement.id}: duration ${duration} differs from ${expectedDuration}`,
    );
    invariant(
      Number.isFinite(peaks.samplePeak) && peaks.samplePeak <= MAX_ALLOWED_PEAK_DBFS,
      `${arrangement.id}: sample peak ${peaks.samplePeak} dBFS exceeds ${MAX_ALLOWED_PEAK_DBFS} dBFS`,
    );
    invariant(
      Number.isFinite(peaks.truePeak) && peaks.truePeak <= MAX_ALLOWED_PEAK_DBFS,
      `${arrangement.id}: true peak ${peaks.truePeak} dBFS exceeds ${MAX_ALLOWED_PEAK_DBFS} dBFS`,
    );
    invariant(Math.abs(boundary.first) <= .02, `${arrangement.id}: decoded first sample is not seam-safe`);
    invariant(Math.abs(boundary.last) <= .02, `${arrangement.id}: decoded last sample is not seam-safe`);
    invariant(boundary.seamDelta <= .025, `${arrangement.id}: decoded seam delta is too high`);
    invariant(
      Math.abs(boundary.decodedSamples / SAMPLE_RATE - expectedDuration) <= VALID_DURATION_TOLERANCE_SECONDS,
      `${arrangement.id}: decoded duration is outside the loop gate`,
    );

    combinedBytes += bytes;
    metadata.push(Object.freeze({
      id: arrangement.id,
      bpm: arrangement.bpm,
      duration,
      sampleRate,
      channels,
      bitrate,
      samplePeakDbfs: peaks.samplePeak,
      truePeakDbfs: peaks.truePeak,
      seamDelta: boundary.seamDelta,
      bytes,
    }));
  }

  invariant(
    combinedBytes <= PAYLOAD_LIMIT_BYTES,
    `Combined music payload ${combinedBytes} exceeds ${PAYLOAD_LIMIT_BYTES} bytes`,
  );
  return Object.freeze({ combinedBytes, tracks: Object.freeze(metadata) });
};

const renderAssets = () => {
  mkdirSync(outputDirectory, { recursive: true });
  const scratch = mkdtempSync(join(tmpdir(), 'sanic-zone-music-'));
  try {
    for (const arrangement of ARRANGEMENTS) {
      const { pcm } = renderArrangement(arrangement);
      const wavPath = join(scratch, `${arrangement.id}.wav`);
      const mp3Path = join(outputDirectory, `${arrangement.id}.mp3`);
      writeWav(wavPath, pcm);
      encodeMp3(wavPath, mp3Path, arrangement);
    }
  } finally {
    rmSync(scratch, { force: true, recursive: true });
  }
};

const main = () => {
  if (!process.argv.includes('--validate')) renderAssets();
  const report = validateAssets();
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
};

const invokedPath = process.argv[1] === undefined ? '' : resolve(process.argv[1]);
if (invokedPath === fileURLToPath(import.meta.url)) main();
