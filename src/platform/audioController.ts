import { MusicSequencer } from './musicSequencer';

const MASTER_GAIN = 0.16;
const EFFECTS_GAIN = 0.95;
const MUSIC_GAIN = 0.52;
const SILENCE = 0.0001;

interface ToneOptions {
  readonly startFrequency: number;
  readonly endFrequency: number;
  readonly duration: number;
  readonly volume: number;
  readonly type: OscillatorType;
  readonly delay?: number;
}

interface WindGraph {
  readonly source: AudioBufferSourceNode;
  readonly filter: BiquadFilterNode;
  readonly gain: GainNode;
}

export class AudioController {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  private effectsBus: GainNode | null = null;
  private musicBus: GainNode | null = null;
  private music: MusicSequencer | null = null;
  private wind: WindGraph | null = null;
  private muted: boolean;
  private desiredRunning = false;
  private stateSyncInFlight = false;
  private destroyed = false;
  private readonly handleContextStateChange = (): void => {
    this.requestStateSync();
  };

  public constructor(muted = false) {
    this.muted = muted;
  }

  public start(): void {
    if (this.destroyed) return;
    this.desiredRunning = true;

    if (this.context !== null) {
      this.requestStateSync();
      return;
    }

    if (typeof window.AudioContext !== 'function') return;

    let context: AudioContext | null = null;
    let master: GainNode | null = null;
    let effectsBus: GainNode | null = null;
    let musicBus: GainNode | null = null;
    let music: MusicSequencer | null = null;
    let wind: WindGraph | null = null;

    try {
      context = new window.AudioContext();
      master = context.createGain();
      effectsBus = context.createGain();
      musicBus = context.createGain();
      master.gain.setValueAtTime(this.muted ? 0 : MASTER_GAIN, context.currentTime);
      effectsBus.gain.setValueAtTime(EFFECTS_GAIN, context.currentTime);
      musicBus.gain.setValueAtTime(MUSIC_GAIN, context.currentTime);
      effectsBus.connect(master);
      musicBus.connect(master);
      master.connect(context.destination);

      wind = this.createWind(context, effectsBus);
      music = new MusicSequencer(context, musicBus);
      music.start();
      if (context.state !== 'running') music.pause();
      this.context = context;
      this.master = master;
      this.effectsBus = effectsBus;
      this.musicBus = musicBus;
      this.music = music;
      this.wind = wind;
      context.addEventListener('statechange', this.handleContextStateChange);
      this.requestStateSync();
    } catch {
      this.removeContextStateListener(context);
      music?.destroy();
      this.cleanupWind(wind);
      this.disconnect(musicBus);
      this.disconnect(effectsBus);
      this.disconnect(master);
      this.closeContext(context);
      if (this.context === context) {
        this.context = null;
        this.master = null;
        this.effectsBus = null;
        this.musicBus = null;
        this.music = null;
        this.wind = null;
      }
    }
  }

  public setMuted(muted: boolean): void {
    this.muted = muted;

    const context = this.context;
    const master = this.master;
    if (context === null || master === null) return;

    const now = context.currentTime;
    const currentGain = Math.max(0, Math.min(MASTER_GAIN, master.gain.value));
    master.gain.cancelScheduledValues(now);
    master.gain.setValueAtTime(currentGain, now);
    master.gain.linearRampToValueAtTime(muted ? 0 : MASTER_GAIN, now + 0.025);
  }

  public pickup(multiplier: number): void {
    const level = Number.isFinite(multiplier)
      ? Math.max(1, Math.min(5, Math.round(multiplier)))
      : 1;
    const baseFrequency = 620 + (level - 1) * 85;

    this.tone({
      startFrequency: baseFrequency,
      endFrequency: baseFrequency * 1.3,
      duration: 0.09,
      volume: 0.32,
      type: 'square',
    });
    this.tone({
      startFrequency: baseFrequency * 1.45,
      endFrequency: baseFrequency * 1.75,
      duration: 0.1,
      volume: 0.2,
      type: 'sine',
      delay: 0.045,
    });
  }

  public jump(): void {
    this.tone({
      startFrequency: 210,
      endFrequency: 570,
      duration: 0.18,
      volume: 0.28,
      type: 'triangle',
    });
  }

  public lane(): void {
    this.tone({
      startFrequency: 180,
      endFrequency: 125,
      duration: 0.075,
      volume: 0.16,
      type: 'sine',
    });
  }

  public impact(): void {
    this.tone({
      startFrequency: 130,
      endFrequency: 42,
      duration: 0.3,
      volume: 0.48,
      type: 'sawtooth',
    });
    this.noiseBurst(0.22, 0.42, 480);
  }

  public suspend(): void {
    if (this.destroyed) return;
    this.desiredRunning = false;
    this.music?.pause();
    this.requestStateSync();
  }

  public resume(): void {
    if (this.destroyed) return;
    this.desiredRunning = true;
    this.requestStateSync();
  }

  public setIntensity(intensity: number): void {
    if (this.destroyed) return;
    this.music?.setIntensity(intensity);
  }

  public gameOver(): void {
    if (this.destroyed) return;
    this.music?.stop(true);
  }

  public restart(): void {
    if (this.destroyed) return;
    this.desiredRunning = true;
    this.music?.stop(true);
    this.requestStateSync();
  }

  public destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;

    const context = this.context;
    this.removeContextStateListener(context);
    this.music?.destroy();
    this.cleanupWind(this.wind);
    this.disconnect(this.musicBus);
    this.disconnect(this.effectsBus);
    this.disconnect(this.master);

    this.music = null;
    this.wind = null;
    this.musicBus = null;
    this.effectsBus = null;
    this.master = null;
    this.context = null;

    this.closeContext(context);
  }

  private requestStateSync(): void {
    const context = this.context;
    if (this.destroyed || context === null || context.state === 'closed' || this.stateSyncInFlight) return;

    const requestedRunning = this.desiredRunning;
    this.syncMusicTransport(context);
    let transition: Promise<void>;
    try {
      if (requestedRunning && context.state !== 'running') {
        transition = context.resume();
      } else if (!requestedRunning && context.state === 'running') {
        transition = context.suspend();
      } else {
        return;
      }
    } catch {
      return;
    }

    this.stateSyncInFlight = true;
    void transition.catch(() => undefined).finally(() => {
      if (context !== this.context) return;
      this.stateSyncInFlight = false;
      if (this.desiredRunning !== requestedRunning) {
        this.requestStateSync();
        return;
      }
      this.syncMusicTransport(context);
    });
  }

  private syncMusicTransport(context: AudioContext): void {
    const music = this.music;
    if (music === null) return;
    if (!this.desiredRunning || context.state !== 'running') {
      music.pause();
      return;
    }
    try {
      music.resume();
    } catch {
      // Later synthesis failures silence music while effects and gameplay continue.
      music.stop(false);
    }
  }

  private createWind(context: AudioContext, master: AudioNode): WindGraph {
    const frameCount = Math.max(1, Math.floor(context.sampleRate * 2));
    const buffer = context.createBuffer(1, frameCount, context.sampleRate);
    const samples = buffer.getChannelData(0);
    for (let index = 0; index < samples.length; index += 1) {
      samples[index] = Math.random() * 2 - 1;
    }

    let source: AudioBufferSourceNode | null = null;
    let filter: BiquadFilterNode | null = null;
    let gain: GainNode | null = null;

    try {
      source = context.createBufferSource();
      filter = context.createBiquadFilter();
      gain = context.createGain();

      source.buffer = buffer;
      source.loop = true;
      filter.type = 'bandpass';
      filter.frequency.setValueAtTime(760, context.currentTime);
      filter.Q.setValueAtTime(0.45, context.currentTime);
      gain.gain.setValueAtTime(0.018, context.currentTime);

      source.connect(filter);
      filter.connect(gain);
      gain.connect(master);
      source.start();
      return { source, filter, gain };
    } catch (error) {
      this.stop(source);
      this.disconnect(source);
      this.disconnect(filter);
      this.disconnect(gain);
      throw error;
    }
  }

  private cleanupWind(wind: WindGraph | null): void {
    if (wind === null) return;

    this.stop(wind.source);
    this.disconnect(wind.source);
    this.disconnect(wind.filter);
    this.disconnect(wind.gain);
  }

  private stop(source: AudioScheduledSourceNode | null): void {
    try {
      source?.stop();
    } catch {
      // The source may have failed before starting or already be stopped.
    }
  }

  private disconnect(node: AudioNode | null): void {
    try {
      node?.disconnect();
    } catch {
      // Continue releasing the rest of the graph if one node is already gone.
    }
  }

  private closeContext(context: AudioContext | null): void {
    try {
      if (context !== null && context.state !== 'closed') {
        void context.close().catch(() => undefined);
      }
    } catch {
      // Context shutdown must not escape controller cleanup.
    }
  }

  private removeContextStateListener(context: AudioContext | null): void {
    try {
      context?.removeEventListener('statechange', this.handleContextStateChange);
    } catch {
      // Listener cleanup must not prevent the rest of the graph from releasing.
    }
  }

  private tone(options: ToneOptions): void {
    const context = this.context;
    const effectsBus = this.effectsBus;
    if (
      this.destroyed
      || this.muted
      || context === null
      || context.state !== 'running'
      || effectsBus === null
    ) return;

    let oscillator: OscillatorNode | null = null;
    let envelope: GainNode | null = null;

    try {
      const start = context.currentTime + (options.delay ?? 0);
      const attackEnd = start + Math.min(0.012, options.duration * 0.25);
      const end = start + options.duration;
      oscillator = context.createOscillator();
      envelope = context.createGain();

      oscillator.type = options.type;
      oscillator.frequency.setValueAtTime(options.startFrequency, start);
      oscillator.frequency.exponentialRampToValueAtTime(options.endFrequency, end);
      envelope.gain.setValueAtTime(SILENCE, start);
      envelope.gain.exponentialRampToValueAtTime(options.volume, attackEnd);
      envelope.gain.exponentialRampToValueAtTime(SILENCE, end);

      oscillator.connect(envelope);
      envelope.connect(effectsBus);
      const createdOscillator = oscillator;
      const createdEnvelope = envelope;
      oscillator.addEventListener('ended', () => {
        this.disconnect(createdOscillator);
        this.disconnect(createdEnvelope);
      }, { once: true });
      oscillator.start(start);
      oscillator.stop(end + 0.01);
    } catch {
      this.stop(oscillator);
      this.disconnect(oscillator);
      this.disconnect(envelope);
    }
  }

  private noiseBurst(duration: number, volume: number, frequency: number): void {
    const context = this.context;
    const effectsBus = this.effectsBus;
    if (
      this.destroyed
      || this.muted
      || context === null
      || context.state !== 'running'
      || effectsBus === null
    ) return;

    let source: AudioBufferSourceNode | null = null;
    let filter: BiquadFilterNode | null = null;
    let envelope: GainNode | null = null;

    try {
      const frameCount = Math.max(1, Math.floor(context.sampleRate * duration));
      const buffer = context.createBuffer(1, frameCount, context.sampleRate);
      const samples = buffer.getChannelData(0);
      for (let index = 0; index < samples.length; index += 1) {
        samples[index] = Math.random() * 2 - 1;
      }

      source = context.createBufferSource();
      filter = context.createBiquadFilter();
      envelope = context.createGain();
      const now = context.currentTime;

      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(frequency, now);
      envelope.gain.setValueAtTime(volume, now);
      envelope.gain.exponentialRampToValueAtTime(SILENCE, now + duration);

      source.buffer = buffer;
      source.connect(filter);
      filter.connect(envelope);
      envelope.connect(effectsBus);
      const createdSource = source;
      const createdFilter = filter;
      const createdEnvelope = envelope;
      source.addEventListener('ended', () => {
        this.disconnect(createdSource);
        this.disconnect(createdFilter);
        this.disconnect(createdEnvelope);
      }, { once: true });
      source.start(now);
      source.stop(now + duration);
    } catch {
      this.stop(source);
      this.disconnect(source);
      this.disconnect(filter);
      this.disconnect(envelope);
    }
  }
}
