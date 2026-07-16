import {
  ARPEGGIO_EVENTS,
  BASE_BPM,
  BASS_EVENTS,
  BEATS_PER_BAR,
  DRUM_EVENTS,
  LEAD_EVENTS,
  LOOP_STEPS,
  MAX_BPM,
  STEPS_PER_BEAT,
  midiToFrequency,
  type DrumEvent,
  type NoteEvent,
} from './musicPattern';

const SILENCE = 0.0001;
const DEFAULT_LOOK_AHEAD_SECONDS = 0.12;
const DEFAULT_INTERVAL_MS = 25;
const DEFAULT_START_DELAY_SECONDS = 0.045;
const DEFAULT_MAX_ACTIVE_SOURCES = 28;
const MAX_SCHEDULE_LATENESS_SECONDS = 0.04;
const MAX_SKIPPED_STEPS_PER_TICK = LOOP_STEPS * 32;

export interface MusicSchedulerTimers {
  setInterval(callback: () => void, intervalMs: number): number;
  clearInterval(id: number): void;
}

interface MusicSequencerOptions {
  readonly timers?: MusicSchedulerTimers;
  readonly lookAheadSeconds?: number;
  readonly intervalMs?: number;
  readonly startDelaySeconds?: number;
  readonly maxActiveSources?: number;
}

export interface MusicSequencerSnapshot {
  readonly running: boolean;
  readonly destroyed: boolean;
  readonly patternStep: number;
  readonly completedLoops: number;
  readonly bpm: number;
  readonly targetIntensity: number;
  readonly appliedIntensity: number;
  readonly activeSources: number;
  readonly timerActive: boolean;
}

interface ActiveVoice {
  readonly source: AudioScheduledSourceNode;
  readonly nodes: readonly AudioNode[];
}

const browserTimers: MusicSchedulerTimers = {
  setInterval: (callback, intervalMs) => window.setInterval(callback, intervalMs),
  clearInterval: (id) => window.clearInterval(id),
};

const eventsByStep = <EventType extends { readonly beat: number }>(
  events: readonly EventType[],
): ReadonlyMap<number, readonly EventType[]> => {
  const result = new Map<number, EventType[]>();
  for (const event of events) {
    const step = Math.round(event.beat * STEPS_PER_BEAT) % LOOP_STEPS;
    const bucket = result.get(step) ?? [];
    bucket.push(event);
    result.set(step, bucket);
  }
  return result;
};

const LEAD_BY_STEP = eventsByStep(LEAD_EVENTS);
const ARPEGGIO_BY_STEP = eventsByStep(ARPEGGIO_EVENTS);
const BASS_BY_STEP = eventsByStep(BASS_EVENTS);
const DRUMS_BY_STEP = eventsByStep(DRUM_EVENTS);
const STEPS_PER_BAR = BEATS_PER_BAR * STEPS_PER_BEAT;

const finiteOr = (value: number | undefined, fallback: number): number =>
  value !== undefined && Number.isFinite(value) ? value : fallback;

export class MusicSequencer {
  private readonly timers: MusicSchedulerTimers;
  private readonly lookAheadSeconds: number;
  private readonly intervalMs: number;
  private readonly startDelaySeconds: number;
  private readonly maxActiveSources: number;
  private readonly activeVoices = new Map<AudioScheduledSourceNode, ActiveVoice>();
  private noiseBuffer: AudioBuffer | null = null;
  private timerId: number | null = null;
  private running = false;
  private destroyed = false;
  private nextStep = 0;
  private nextStepTime = 0;
  private completedLoops = 0;
  private bpm = BASE_BPM;
  private targetIntensity = 0;
  private appliedIntensity = 0;

  public constructor(
    private readonly context: AudioContext,
    private readonly output: AudioNode,
    options: MusicSequencerOptions = {},
  ) {
    this.timers = options.timers ?? browserTimers;
    this.lookAheadSeconds = Math.max(0.001, finiteOr(options.lookAheadSeconds, DEFAULT_LOOK_AHEAD_SECONDS));
    this.intervalMs = Math.max(8, finiteOr(options.intervalMs, DEFAULT_INTERVAL_MS));
    this.startDelaySeconds = Math.max(0, finiteOr(options.startDelaySeconds, DEFAULT_START_DELAY_SECONDS));
    this.maxActiveSources = Math.max(4, Math.floor(finiteOr(options.maxActiveSources, DEFAULT_MAX_ACTIVE_SOURCES)));
  }

  public start(reset = false): void {
    if (this.destroyed || this.running) return;
    if (reset) this.resetTransport();
    this.activate(true);
  }

  public pause(): void {
    if (this.destroyed || !this.running) return;
    this.running = false;
    this.clearTimer();
  }

  public resume(): void {
    if (this.destroyed || this.running) return;
    this.activate(this.nextStepTime <= 0);
  }

  public stop(reset = true): void {
    if (this.destroyed) return;
    this.running = false;
    this.clearTimer();
    this.stopActiveVoices();
    if (reset) this.resetTransport();
  }

  public setIntensity(intensity: number): void {
    this.targetIntensity = Number.isFinite(intensity)
      ? Math.max(0, Math.min(1, intensity))
      : 0;
  }

  public destroy(): void {
    if (this.destroyed) return;
    this.stop(true);
    this.destroyed = true;
    this.noiseBuffer = null;
  }

  public snapshot(): Readonly<MusicSequencerSnapshot> {
    return Object.freeze({
      running: this.running,
      destroyed: this.destroyed,
      patternStep: this.nextStep,
      completedLoops: this.completedLoops,
      bpm: this.bpm,
      targetIntensity: this.targetIntensity,
      appliedIntensity: this.appliedIntensity,
      activeSources: this.activeVoices.size,
      timerActive: this.timerId !== null,
    });
  }

  private readonly scheduleWindow = (): void => {
    try {
      this.scheduleSteps();
    } catch {
      // A later browser-node failure silences music without breaking gameplay.
      this.failTransport();
    }
  };

  private scheduleSteps(): void {
    if (!this.running || this.destroyed) return;
    const now = this.context.currentTime;
    const horizon = now + this.lookAheadSeconds;
    let guard = LOOP_STEPS * 2;

    this.skipLateSteps(now - MAX_SCHEDULE_LATENESS_SECONDS);
    while (this.nextStepTime <= horizon && guard > 0) {
      this.scheduleStep(this.nextStep, this.nextStepTime);
      this.advanceStep();
      guard -= 1;
    }
  }

  private activate(reanchorClock: boolean): void {
    this.running = true;
    if (reanchorClock) this.nextStepTime = this.context.currentTime + this.startDelaySeconds;
    try {
      this.scheduleSteps();
      if (!this.running || this.destroyed) return;
      this.timerId = this.timers.setInterval(this.scheduleWindow, this.intervalMs);
    } catch (error) {
      this.failTransport();
      throw error;
    }
  }

  private failTransport(): void {
    this.running = false;
    this.clearTimer();
    this.stopActiveVoices();
  }

  private skipLateSteps(cutoff: number): void {
    let remaining = MAX_SKIPPED_STEPS_PER_TICK;
    while (this.nextStepTime < cutoff && remaining > 0) {
      if (this.nextStep % STEPS_PER_BAR === 0) this.applyPendingIntensity();
      this.advanceStep();
      remaining -= 1;
    }
    if (this.nextStepTime < cutoff) this.nextStepTime = cutoff;
  }

  private scheduleStep(step: number, time: number): void {
    if (step % STEPS_PER_BAR === 0) this.applyPendingIntensity();
    const secondsPerBeat = 60 / this.bpm;

    for (const event of LEAD_BY_STEP.get(step) ?? []) {
      this.scheduleNote(event, time, secondsPerBeat, 'square', 0.18, 0.012);
    }
    for (const event of BASS_BY_STEP.get(step) ?? []) {
      this.scheduleNote(event, time, secondsPerBeat, 'triangle', 0.2, 0.018);
    }

    const fullArpeggio = this.appliedIntensity >= 0.34;
    if (fullArpeggio || step % 2 === 0) {
      for (const event of ARPEGGIO_BY_STEP.get(step) ?? []) {
        this.scheduleNote(event, time, secondsPerBeat, 'square', fullArpeggio ? 0.074 : 0.052, 0.006);
      }
    }

    for (const event of DRUMS_BY_STEP.get(step) ?? []) {
      if ((event.kind === 'openHat' && this.appliedIntensity < 0.25)
        || (event.kind === 'hat' && this.appliedIntensity < 0.62 && step % 4 !== 0)) continue;
      this.scheduleDrum(event, time);
    }
  }

  private scheduleNote(
    event: NoteEvent,
    time: number,
    secondsPerBeat: number,
    type: OscillatorType,
    gainScale: number,
    attack: number,
  ): void {
    if (!this.hasVoiceCapacity()) return;
    const duration = Math.max(0.025, event.duration * secondsPerBeat);
    const end = time + duration;
    const oscillator = this.context.createOscillator();
    const envelope = this.context.createGain();

    oscillator.type = type;
    oscillator.frequency.setValueAtTime(midiToFrequency(event.midi), time);
    envelope.gain.setValueAtTime(SILENCE, time);
    envelope.gain.exponentialRampToValueAtTime(Math.max(SILENCE, event.velocity * gainScale), time + Math.min(attack, duration * 0.28));
    envelope.gain.exponentialRampToValueAtTime(SILENCE, end);
    oscillator.connect(envelope);
    envelope.connect(this.output);
    this.registerVoice(oscillator, [oscillator, envelope]);
    oscillator.start(time);
    oscillator.stop(end + 0.012);
  }

  private scheduleDrum(event: DrumEvent, time: number): void {
    if (!this.hasVoiceCapacity()) return;
    if (event.kind === 'kick') {
      this.scheduleKick(time, event.velocity);
      return;
    }
    this.scheduleNoiseDrum(time, event.kind, event.velocity);
  }

  private scheduleKick(time: number, velocity: number): void {
    const duration = 0.13;
    const oscillator = this.context.createOscillator();
    const envelope = this.context.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(118, time);
    oscillator.frequency.exponentialRampToValueAtTime(44, time + duration);
    envelope.gain.setValueAtTime(Math.max(SILENCE, velocity * 0.24), time);
    envelope.gain.exponentialRampToValueAtTime(SILENCE, time + duration);
    oscillator.connect(envelope);
    envelope.connect(this.output);
    this.registerVoice(oscillator, [oscillator, envelope]);
    oscillator.start(time);
    oscillator.stop(time + duration + 0.01);
  }

  private scheduleNoiseDrum(time: number, kind: Exclude<DrumEvent['kind'], 'kick'>, velocity: number): void {
    const duration = kind === 'snare' ? 0.105 : kind === 'openHat' ? 0.14 : 0.035;
    const source = this.context.createBufferSource();
    const filter = this.context.createBiquadFilter();
    const envelope = this.context.createGain();
    source.buffer = this.getNoiseBuffer();
    filter.type = kind === 'snare' ? 'bandpass' : 'highpass';
    filter.frequency.setValueAtTime(kind === 'snare' ? 1_850 : 5_400, time);
    filter.Q.setValueAtTime(kind === 'snare' ? 0.72 : 0.38, time);
    const scale = kind === 'snare' ? 0.12 : kind === 'openHat' ? 0.055 : 0.038;
    envelope.gain.setValueAtTime(Math.max(SILENCE, velocity * scale), time);
    envelope.gain.exponentialRampToValueAtTime(SILENCE, time + duration);
    source.connect(filter);
    filter.connect(envelope);
    envelope.connect(this.output);
    this.registerVoice(source, [source, filter, envelope]);
    source.start(time);
    source.stop(time + duration + 0.008);
  }

  private getNoiseBuffer(): AudioBuffer {
    if (this.noiseBuffer !== null) return this.noiseBuffer;
    const length = Math.max(1, Math.floor(this.context.sampleRate * 0.22));
    const buffer = this.context.createBuffer(1, length, this.context.sampleRate);
    const samples = buffer.getChannelData(0);
    let state = 0x5a11c;
    for (let index = 0; index < samples.length; index += 1) {
      state = (state * 1_664_525 + 1_013_904_223) >>> 0;
      samples[index] = state / 0x7fffffff - 1;
    }
    this.noiseBuffer = buffer;
    return buffer;
  }

  private registerVoice(source: AudioScheduledSourceNode, nodes: readonly AudioNode[]): void {
    const voice: ActiveVoice = Object.freeze({ source, nodes: Object.freeze([...nodes]) });
    this.activeVoices.set(source, voice);
    source.addEventListener('ended', () => this.releaseVoice(source), { once: true });
  }

  private releaseVoice(source: AudioScheduledSourceNode): void {
    const voice = this.activeVoices.get(source);
    if (voice === undefined) return;
    this.activeVoices.delete(source);
    for (const node of voice.nodes) this.disconnect(node);
  }

  private stopActiveVoices(): void {
    for (const voice of [...this.activeVoices.values()]) {
      try { voice.source.stop(); } catch { /* Already stopped or not fully started. */ }
      this.activeVoices.delete(voice.source);
      for (const node of voice.nodes) this.disconnect(node);
    }
  }

  private hasVoiceCapacity(): boolean {
    return this.activeVoices.size < this.maxActiveSources;
  }

  private advanceStep(): void {
    this.nextStep += 1;
    if (this.nextStep >= LOOP_STEPS) {
      this.nextStep = 0;
      this.completedLoops += 1;
    }
    this.nextStepTime += 60 / this.bpm / STEPS_PER_BEAT;
  }

  private applyPendingIntensity(): void {
    this.appliedIntensity = this.targetIntensity;
    this.bpm = BASE_BPM + (MAX_BPM - BASE_BPM) * this.appliedIntensity;
  }

  private resetTransport(): void {
    this.nextStep = 0;
    this.completedLoops = 0;
    this.nextStepTime = 0;
    this.appliedIntensity = 0;
    this.targetIntensity = 0;
    this.bpm = BASE_BPM;
  }

  private clearTimer(): void {
    if (this.timerId === null) return;
    this.timers.clearInterval(this.timerId);
    this.timerId = null;
  }

  private disconnect(node: AudioNode): void {
    try { node.disconnect(); } catch { /* Continue releasing the remaining graph. */ }
  }
}
