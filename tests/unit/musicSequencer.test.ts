import { describe, expect, it } from 'vitest';
import { LOOP_STEPS } from '../../src/platform/musicPattern';
import {
  MusicSequencer,
  type MusicSchedulerTimers,
} from '../../src/platform/musicSequencer';

class FakeAudioParam {
  public value = 0;
  public readonly values: number[] = [];

  public cancelScheduledValues(): void {}
  public exponentialRampToValueAtTime(value: number): void { this.value = value; this.values.push(value); }
  public linearRampToValueAtTime(value: number): void { this.value = value; this.values.push(value); }
  public setValueAtTime(value: number): void { this.value = value; this.values.push(value); }
}

class FakeAudioNode {
  public readonly connections: unknown[] = [];
  public disconnected = false;

  public connect(destination: unknown): unknown { this.connections.push(destination); return destination; }
  public disconnect(): void { this.disconnected = true; }
}

class FakeGainNode extends FakeAudioNode { public readonly gain = new FakeAudioParam(); }

class FakeFilterNode extends FakeAudioNode {
  public readonly frequency = new FakeAudioParam();
  public readonly Q = new FakeAudioParam();
  public type: BiquadFilterType = 'lowpass';
}

class FakeBuffer {
  private readonly data: Float32Array;
  public constructor(length: number) { this.data = new Float32Array(length); }
  public getChannelData(): Float32Array { return this.data; }
}

class FakeSourceNode extends FakeAudioNode {
  private readonly ended: Array<() => void> = [];
  public readonly starts: number[] = [];
  public readonly stops: number[] = [];

  public addEventListener(type: string, listener: () => void): void {
    if (type === 'ended') this.ended.push(listener);
  }

  public start(time = 0): void { this.starts.push(time); }
  public stop(time = 0): void { this.stops.push(time); }
  public finish(): void { for (const listener of this.ended.splice(0)) listener(); }
}

class FakeOscillatorNode extends FakeSourceNode {
  public readonly frequency = new FakeAudioParam();
  public type: OscillatorType = 'sine';
}

class FakeBufferSourceNode extends FakeSourceNode { public buffer: FakeBuffer | null = null; }

class FakeAudioContext {
  public currentTime = 4;
  public readonly sampleRate = 8_000;
  public readonly gains: FakeGainNode[] = [];
  public readonly filters: FakeFilterNode[] = [];
  public readonly oscillators: FakeOscillatorNode[] = [];
  public readonly sources: FakeBufferSourceNode[] = [];

  public createGain(): FakeGainNode {
    const node = new FakeGainNode();
    this.gains.push(node);
    return node;
  }

  public createBiquadFilter(): FakeFilterNode {
    const node = new FakeFilterNode();
    this.filters.push(node);
    return node;
  }

  public createBuffer(_channels: number, length: number): FakeBuffer { return new FakeBuffer(length); }

  public createBufferSource(): FakeBufferSourceNode {
    const node = new FakeBufferSourceNode();
    this.sources.push(node);
    return node;
  }

  public createOscillator(): FakeOscillatorNode {
    const node = new FakeOscillatorNode();
    this.oscillators.push(node);
    return node;
  }
}

class FakeTimers implements MusicSchedulerTimers {
  private readonly callbacks = new Map<number, () => void>();
  private nextId = 1;

  public setInterval(callback: () => void): number {
    const id = this.nextId;
    this.nextId += 1;
    this.callbacks.set(id, callback);
    return id;
  }

  public clearInterval(id: number): void { this.callbacks.delete(id); }
  public run(): void { for (const callback of [...this.callbacks.values()]) callback(); }
  public get activeCount(): number { return this.callbacks.size; }
}

const setup = (maxActiveSources = 24) => {
  const context = new FakeAudioContext();
  const output = new FakeAudioNode();
  const timers = new FakeTimers();
  const sequencer = new MusicSequencer(
    context as unknown as AudioContext,
    output as unknown as AudioNode,
    { timers, lookAheadSeconds: 0.02, startDelaySeconds: 0, maxActiveSources },
  );
  return { context, output, sequencer, timers };
};

describe('MusicSequencer', () => {
  it('allocates and schedules nothing before explicit start', () => {
    const { context, sequencer, timers } = setup();

    expect(timers.activeCount).toBe(0);
    expect(context.oscillators).toHaveLength(0);
    expect(context.sources).toHaveLength(0);
    expect(sequencer.snapshot()).toMatchObject({ running: false, patternStep: 0 });
  });

  it('starts idempotently with one transport and audible melodic voices', () => {
    const { context, sequencer, timers } = setup();

    sequencer.start();
    sequencer.start();

    expect(timers.activeCount).toBe(1);
    expect(context.oscillators.length).toBeGreaterThanOrEqual(4);
    expect(sequencer.snapshot()).toMatchObject({ running: true, patternStep: 1 });
  });

  it('wraps after exactly 256 sixteenth-note steps / 64 beats', () => {
    const { context, sequencer, timers } = setup(8);
    sequencer.start();

    context.currentTime += 32.01;
    timers.run();

    expect(LOOP_STEPS).toBe(256);
    expect(sequencer.snapshot()).toMatchObject({ completedLoops: 1, patternStep: 1 });
  });

  it('applies finite clamped intensity and tempo only at a bar boundary', () => {
    const { context, sequencer, timers } = setup(8);
    sequencer.start();
    sequencer.setIntensity(9);

    context.currentTime += 1.8;
    timers.run();
    expect(sequencer.snapshot()).toMatchObject({ appliedIntensity: 0, bpm: 120 });

    context.currentTime += 0.25;
    timers.run();
    expect(sequencer.snapshot()).toMatchObject({ appliedIntensity: 1, bpm: 132 });

    sequencer.setIntensity(Number.NaN);
    context.currentTime += 2;
    timers.run();
    expect(sequencer.snapshot().appliedIntensity).toBe(0);
  });

  it('pauses and resumes the cursor without duplicating or restarting transport', () => {
    const { context, sequencer, timers } = setup();
    sequencer.start();
    const beforePause = sequencer.snapshot().patternStep;
    const voicesBeforePause = sequencer.snapshot().activeSources;

    sequencer.pause();
    context.currentTime += 8;
    timers.run();
    expect(timers.activeCount).toBe(0);
    expect(sequencer.snapshot().patternStep).toBe(beforePause);
    expect(sequencer.snapshot().activeSources).toBe(voicesBeforePause);

    context.currentTime -= 8;
    sequencer.resume();
    sequencer.resume();
    expect(timers.activeCount).toBe(1);
    expect(sequencer.snapshot().patternStep).toBe(beforePause);
    expect(sequencer.snapshot().completedLoops).toBe(0);

    context.currentTime += 0.15;
    timers.run();
    expect(sequencer.snapshot().patternStep).toBeGreaterThan(beforePause);
  });

  it('clears prior-run intensity so a reset always restarts at 120 BPM', () => {
    const { context, sequencer, timers } = setup();
    sequencer.start();
    sequencer.setIntensity(1);
    context.currentTime += 2.1;
    timers.run();
    expect(sequencer.snapshot()).toMatchObject({ appliedIntensity: 1, bpm: 132 });

    sequencer.stop(true);
    sequencer.start();

    expect(sequencer.snapshot()).toMatchObject({
      targetIntensity: 0,
      appliedIntensity: 0,
      bpm: 120,
      patternStep: 1,
    });
  });

  it('skips overdue steps after a long stall instead of bursting them all at once', () => {
    const { context, sequencer, timers } = setup(32);
    sequencer.start();
    const voicesBeforeStall = context.oscillators.length + context.sources.length;

    context.currentTime += 12;
    timers.run();
    const voicesAfterStall = context.oscillators.length + context.sources.length;

    expect(voicesAfterStall - voicesBeforeStall).toBeLessThanOrEqual(8);
    expect(sequencer.snapshot().running).toBe(true);
  });

  it('bounds live sources and resets a stopped run to bar one', () => {
    const { context, sequencer, timers } = setup(6);
    sequencer.start();
    context.currentTime += 12;
    timers.run();

    expect(sequencer.snapshot().activeSources).toBeLessThanOrEqual(6);
    sequencer.stop(true);
    expect(timers.activeCount).toBe(0);
    expect(sequencer.snapshot()).toMatchObject({ running: false, patternStep: 0, completedLoops: 0 });
    expect([...context.oscillators, ...context.sources].some(({ stops }) => stops.length > 0)).toBe(true);

    sequencer.start();
    expect(sequencer.snapshot()).toMatchObject({ running: true, patternStep: 1, completedLoops: 0 });
  });

  it('destroys once, releases sources, and cannot be restarted', () => {
    const { sequencer, timers } = setup();
    sequencer.start();
    sequencer.destroy();
    sequencer.destroy();
    sequencer.start();

    expect(timers.activeCount).toBe(0);
    expect(sequencer.snapshot()).toMatchObject({ destroyed: true, running: false, activeSources: 0 });
  });
});
