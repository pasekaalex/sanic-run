import { afterEach, describe, expect, it, vi } from 'vitest';
import { AudioController } from '../../src/platform/audioController';

interface ScheduledValue {
  readonly kind: 'set' | 'exponential' | 'linear';
  readonly value: number;
}

type FailurePoint =
  | 'oscillator'
  | 'gain'
  | 'filter'
  | 'buffer-source'
  | 'start'
  | 'stop';

type EffectName = 'pickup' | 'jump' | 'lane' | 'impact';

class FakeAudioParam {
  public readonly scheduled: ScheduledValue[] = [];
  public value: number;

  public constructor(value: number) {
    this.value = value;
  }

  public cancelScheduledValues(): void {
    // Cancellation is observable through the next scheduled value.
  }

  public exponentialRampToValueAtTime(value: number): void {
    this.value = value;
    this.scheduled.push({ kind: 'exponential', value });
  }

  public linearRampToValueAtTime(value: number): void {
    this.value = value;
    this.scheduled.push({ kind: 'linear', value });
  }

  public setValueAtTime(value: number): void {
    this.value = value;
    this.scheduled.push({ kind: 'set', value });
  }
}

class FakeAudioNode {
  public readonly connections: unknown[] = [];
  public disconnected = false;

  public connect(destination: unknown): unknown {
    this.connections.push(destination);
    return destination;
  }

  public disconnect(): void {
    this.disconnected = true;
  }
}

class FakeGainNode extends FakeAudioNode {
  public readonly gain = new FakeAudioParam(1);
}

class FakeBiquadFilterNode extends FakeAudioNode {
  public readonly frequency = new FakeAudioParam(350);
  public readonly Q = new FakeAudioParam(1);
  public type: BiquadFilterType = 'lowpass';
}

class FakeAudioBuffer {
  private readonly samples: Float32Array;

  public constructor(length: number) {
    this.samples = new Float32Array(length);
  }

  public getChannelData(): Float32Array {
    return this.samples;
  }
}

class FakeScheduledSourceNode extends FakeAudioNode {
  private readonly endedListeners: Array<() => void> = [];
  public started = 0;
  public stopped = 0;

  public constructor(
    private readonly fail: (point: FailurePoint) => void,
    private readonly throwOnStart = false,
  ) {
    super();
  }

  public addEventListener(type: string, listener: () => void): void {
    if (type === 'ended') this.endedListeners.push(listener);
  }

  public start(): void {
    this.started += 1;
    if (this.throwOnStart) throw new Error('source start failed');
    this.fail('start');
  }

  public stop(): void {
    this.stopped += 1;
    this.fail('stop');
    for (const listener of this.endedListeners) listener();
  }
}

class FakeBufferSourceNode extends FakeScheduledSourceNode {
  public buffer: FakeAudioBuffer | null = null;
  public loop = false;
}

class FakeOscillatorNode extends FakeScheduledSourceNode {
  public readonly frequency = new FakeAudioParam(440);
  public type: OscillatorType = 'sine';
}

class FakeAudioContext {
  public readonly bufferSources: FakeBufferSourceNode[] = [];
  public readonly destination = new FakeAudioNode();
  public readonly filters: FakeBiquadFilterNode[] = [];
  public readonly gains: FakeGainNode[] = [];
  public readonly oscillators: FakeOscillatorNode[] = [];
  public readonly currentTime = 4;
  public readonly sampleRate = 20;
  public closeCount = 0;
  public resumeCount = 0;
  public suspendCount = 0;
  public state: AudioContextState;
  private deferredResume = false;
  private failure: { point: FailurePoint; skippedMatches: number } | null = null;
  private readonly pendingResumeResolutions: Array<() => void> = [];
  private readonly pendingSuspendResolutions: Array<() => void> = [];
  private readonly stateChangeListeners = new Set<() => void>();

  public constructor(
    private readonly throwOnWindStart = false,
    private readonly deferSuspend = false,
    private readonly throwOnMusicStart = false,
    private readonly rejectResume = false,
    initialState: AudioContextState = 'running',
  ) {
    this.state = initialState;
  }

  public addEventListener(type: string, listener: () => void): void {
    if (type === 'statechange') this.stateChangeListeners.add(listener);
  }

  public close(): Promise<void> {
    this.closeCount += 1;
    this.setState('closed');
    return Promise.resolve();
  }

  public createBiquadFilter(): FakeBiquadFilterNode {
    this.failIfConfigured('filter');
    const filter = new FakeBiquadFilterNode();
    this.filters.push(filter);
    return filter;
  }

  public createBuffer(_channels: number, length: number): FakeAudioBuffer {
    return new FakeAudioBuffer(length);
  }

  public createBufferSource(): FakeBufferSourceNode {
    this.failIfConfigured('buffer-source');
    const source = new FakeBufferSourceNode(
      (point) => this.failIfConfigured(point),
      this.throwOnWindStart && this.bufferSources.length === 0,
    );
    this.bufferSources.push(source);
    return source;
  }

  public createGain(): FakeGainNode {
    this.failIfConfigured('gain');
    const gain = new FakeGainNode();
    this.gains.push(gain);
    return gain;
  }

  public createOscillator(): FakeOscillatorNode {
    this.failIfConfigured('oscillator');
    if (this.throwOnMusicStart && this.oscillators.length === 0) {
      throw new Error('music oscillator creation failed');
    }
    const oscillator = new FakeOscillatorNode((point) => this.failIfConfigured(point));
    this.oscillators.push(oscillator);
    return oscillator;
  }

  public deferNextResume(): void {
    this.deferredResume = true;
  }

  public dispatchStateChange(): void {
    for (const listener of [...this.stateChangeListeners]) listener();
  }

  public failNext(point: FailurePoint, skippedMatches = 0): void {
    this.failure = { point, skippedMatches };
  }

  public removeEventListener(type: string, listener: () => void): void {
    if (type === 'statechange') this.stateChangeListeners.delete(listener);
  }

  public resume(): Promise<void> {
    this.resumeCount += 1;
    if (this.rejectResume) return Promise.reject(new Error('resume rejected'));
    if (this.deferredResume) {
      this.deferredResume = false;
      return new Promise((resolve) => {
        this.pendingResumeResolutions.push(() => {
          this.setState('running');
          resolve();
        });
      });
    }
    this.setState('running');
    return Promise.resolve();
  }

  public resolvePendingResumes(): void {
    for (const resolve of this.pendingResumeResolutions.splice(0)) resolve();
  }

  public suspend(): Promise<void> {
    this.suspendCount += 1;
    if (this.deferSuspend) {
      return new Promise((resolve) => {
        this.pendingSuspendResolutions.push(() => {
          this.setState('suspended');
          resolve();
        });
      });
    }
    this.setState('suspended');
    return Promise.resolve();
  }

  public resolvePendingSuspends(): void {
    for (const resolve of this.pendingSuspendResolutions.splice(0)) resolve();
  }

  public setState(state: AudioContextState): void {
    if (this.state === state) return;
    this.state = state;
    this.dispatchStateChange();
  }

  public stateListenerCount(): number {
    return this.stateChangeListeners.size;
  }

  private failIfConfigured(point: FailurePoint): void {
    if (this.failure?.point !== point) return;
    if (this.failure.skippedMatches > 0) {
      this.failure.skippedMatches -= 1;
      return;
    }
    this.failure = null;
    throw new Error(`${point} failed`);
  }
}

let restoreAudioContext: (() => void) | null = null;

const installAudioContext = (context: FakeAudioContext): (() => number) => {
  const original = Object.getOwnPropertyDescriptor(window, 'AudioContext');
  let constructions = 0;
  const AudioContextStub = function (): FakeAudioContext {
    constructions += 1;
    return context;
  };

  Object.defineProperty(window, 'AudioContext', {
    configurable: true,
    value: AudioContextStub,
  });
  restoreAudioContext = () => {
    if (original === undefined) {
      Reflect.deleteProperty(window, 'AudioContext');
    } else {
      Object.defineProperty(window, 'AudioContext', original);
    }
  };

  return () => constructions;
};

afterEach(() => {
  restoreAudioContext?.();
  restoreAudioContext = null;
  vi.useRealTimers();
});

const invokeEffect = (audio: AudioController, effect: EffectName): void => {
  if (effect === 'pickup') {
    audio.pickup(3);
    return;
  }
  audio[effect]();
};

const captureNodeCounts = (context: FakeAudioContext) => ({
  bufferSources: context.bufferSources.length,
  filters: context.filters.length,
  gains: context.gains.length,
  oscillators: context.oscillators.length,
});

const captureCreatedNodes = (
  context: FakeAudioContext,
  before: ReturnType<typeof captureNodeCounts>,
) => ({
  bufferSources: context.bufferSources.slice(before.bufferSources),
  filters: context.filters.slice(before.filters),
  gains: context.gains.slice(before.gains),
  oscillators: context.oscillators.slice(before.oscillators),
});

const expectCreatedNodesReleased = (
  created: ReturnType<typeof captureCreatedNodes>,
): void => {
  for (const source of [...created.bufferSources, ...created.oscillators]) {
    expect(source.stopped).toBeGreaterThan(0);
    expect(source.disconnected).toBe(true);
  }
  for (const node of [...created.filters, ...created.gains]) {
    expect(node.disconnected).toBe(true);
  }
};

describe('AudioController', () => {
  it('does not allocate a context or emit effects before explicit start', () => {
    const context = new FakeAudioContext();
    const constructions = installAudioContext(context);
    const audio = new AudioController();

    for (let attempt = 0; attempt < 2; attempt += 1) {
      audio.pickup(3);
      audio.jump();
      audio.lane();
      audio.impact();
    }

    expect(constructions()).toBe(0);
    expect(context.bufferSources).toHaveLength(0);
    expect(context.oscillators).toHaveLength(0);
  });

  it('starts once and enables melodic music plus synthesized effects', () => {
    const context = new FakeAudioContext();
    const constructions = installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    audio.start();
    audio.jump();

    expect(constructions()).toBe(1);
    expect(context.bufferSources.length).toBeGreaterThanOrEqual(2);
    expect(context.bufferSources[0]?.started).toBe(1);
    expect(context.oscillators.length).toBeGreaterThanOrEqual(5);
    expect(context.oscillators.every(({ started }) => started === 1)).toBe(true);
    audio.destroy();
  });

  it('routes conservative music and effects buses beneath the capped master', () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    const [master, effects, music] = context.gains;

    expect(master?.connections).toContain(context.destination);
    expect(effects?.connections).toContain(master);
    expect(music?.connections).toContain(master);
    expect(effects?.gain.scheduled.at(-1)?.value).toBeLessThanOrEqual(1);
    expect(music?.gain.scheduled.at(-1)?.value).toBeLessThan(0.6);
    audio.destroy();
  });

  it('publicly suspends and resumes the shared audio context', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    audio.suspend();
    expect(context.suspendCount).toBe(1);
    expect(context.state).toBe('suspended');

    audio.resume();
    await vi.waitFor(() => {
      expect(context.resumeCount).toBe(1);
      expect(context.state).toBe('running');
    });
    audio.destroy();
  });

  it('serializes a quick resume behind an in-flight suspend', async () => {
    const context = new FakeAudioContext(false, true);
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    audio.suspend();
    expect(context.suspendCount).toBe(1);

    audio.resume();
    context.resolvePendingSuspends();

    await vi.waitFor(() => {
      expect(context.resumeCount).toBe(1);
      expect(context.state).toBe('running');
    });
    audio.destroy();
  });

  it('keeps music scheduling quiescent when a suspended context rejects resume', async () => {
    vi.useFakeTimers();
    const context = new FakeAudioContext(false, false, false, true, 'suspended');
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    await Promise.resolve();
    await Promise.resolve();

    expect(context.resumeCount).toBe(1);
    expect(context.state).toBe('suspended');
    expect(vi.getTimerCount()).toBe(0);
    const frozenCounts = {
      oscillators: context.oscillators.length,
      bufferSources: context.bufferSources.length,
    };
    for (let attempt = 0; attempt < 4; attempt += 1) {
      audio.pickup(3);
      audio.jump();
      audio.lane();
      audio.impact();
    }
    expect({
      oscillators: context.oscillators.length,
      bufferSources: context.bufferSources.length,
    }).toEqual(frozenCounts);
    audio.destroy();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('serializes one recovery attempt after the context is externally suspended', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    audio.start();
    expect(context.stateListenerCount()).toBe(1);
    context.deferNextResume();
    context.setState('suspended');
    context.dispatchStateChange();

    expect(context.resumeCount).toBe(1);
    context.resolvePendingResumes();
    await vi.waitFor(() => {
      expect(context.state).toBe('running');
      expect(context.resumeCount).toBe(1);
    });
    audio.destroy();
  });

  it('does not auto-resume after an app-requested pause', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    expect(context.stateListenerCount()).toBe(1);
    audio.suspend();
    context.dispatchStateChange();
    await Promise.resolve();
    await Promise.resolve();

    expect(context.state).toBe('suspended');
    expect(context.suspendCount).toBe(1);
    expect(context.resumeCount).toBe(0);
    audio.destroy();
  });

  it('removes context-state recovery when destroyed', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    expect(context.stateListenerCount()).toBe(1);
    audio.destroy();
    expect(context.stateListenerCount()).toBe(0);
    context.setState('suspended');
    context.dispatchStateChange();
    await Promise.resolve();

    expect(context.resumeCount).toBe(0);
  });

  it.each(
    (['pickup', 'jump', 'lane', 'impact'] as const).flatMap((effect) => (
      (['oscillator', 'gain', 'start', 'stop'] as const).map((failure) => [effect, failure] as const)
    )),
  )('%s contains a later %s failure and releases partial effect nodes', (effect, failure) => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();
    audio.start();
    const before = captureNodeCounts(context);
    context.failNext(failure);

    let thrown: unknown;
    try {
      invokeEffect(audio, effect);
    } catch (error) {
      thrown = error;
    }
    const created = captureCreatedNodes(context, before);
    audio.destroy();

    expect(thrown).toBeUndefined();
    expectCreatedNodesReleased(created);
  });

  it.each([
    ['buffer-source', 0],
    ['filter', 0],
    ['gain', 1],
    ['start', 1],
    ['stop', 1],
  ] as const)(
    'impact contains a later noise %s failure and releases partial effect nodes',
    (failure, skippedMatches) => {
      const context = new FakeAudioContext();
      installAudioContext(context);
      const audio = new AudioController();
      audio.start();
      const before = captureNodeCounts(context);
      context.failNext(failure, skippedMatches);

      let thrown: unknown;
      try {
        audio.impact();
      } catch (error) {
        thrown = error;
      }
      const created = captureCreatedNodes(context, before);
      audio.destroy();

      expect(thrown).toBeUndefined();
      expectCreatedNodesReleased(created);
    },
  );

  it('caps the master gain and ramps mute state only between zero and the cap', () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    const master = context.gains[0];
    expect(master).toBeDefined();

    audio.setMuted(true);
    audio.setMuted(false);

    expect(master?.gain.scheduled.filter(({ kind }) => kind === 'linear').map(({ value }) => value))
      .toEqual([0, 0.16]);
    expect(Math.max(...(master?.gain.scheduled.map(({ value }) => value) ?? [])))
      .toBeLessThanOrEqual(0.16);
    audio.destroy();
  });

  it('resets music at game over and restarts it from bar one for the next run', () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    const firstPhraseVoices = context.oscillators.length;
    audio.setIntensity(1);
    audio.gameOver();
    audio.restart();

    expect(firstPhraseVoices).toBeGreaterThanOrEqual(4);
    expect(context.oscillators.length).toBeGreaterThan(firstPhraseVoices);
    audio.destroy();
  });

  it('stops and disconnects the complete audio graph before closing once', () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    audio.destroy();
    audio.destroy();

    expect(context.bufferSources[0]?.stopped).toBe(1);
    expect([
      context.bufferSources[0]?.disconnected,
      context.filters[0]?.disconnected,
      context.gains[0]?.disconnected,
      context.gains[1]?.disconnected,
      context.gains[2]?.disconnected,
      context.gains[3]?.disconnected,
    ]).toEqual([true, true, true, true, true, true]);
    expect(context.closeCount).toBe(1);
  });

  it('cleans every locally created resource when wind startup throws', () => {
    const context = new FakeAudioContext(true);
    installAudioContext(context);
    const audio = new AudioController();

    expect(() => audio.start()).not.toThrow();
    expect(context.closeCount).toBe(1);
    audio.destroy();

    expect(context.bufferSources[0]?.stopped).toBe(1);
    expect([
      context.bufferSources[0]?.disconnected,
      context.filters[0]?.disconnected,
      context.gains[0]?.disconnected,
      context.gains[1]?.disconnected,
      context.gains[2]?.disconnected,
      context.gains[3]?.disconnected,
    ]).toEqual([true, true, true, true, true, true]);
    expect(context.closeCount).toBe(1);
  });

  it('cleans wind and every bus when initial music graph creation fails', () => {
    const context = new FakeAudioContext(false, false, true);
    installAudioContext(context);
    const audio = new AudioController();

    expect(() => audio.start()).not.toThrow();
    expect(context.closeCount).toBe(1);
    audio.destroy();

    expect(context.bufferSources[0]?.stopped).toBe(1);
    expect([
      context.bufferSources[0]?.disconnected,
      context.filters[0]?.disconnected,
      context.gains[0]?.disconnected,
      context.gains[1]?.disconnected,
      context.gains[2]?.disconnected,
      context.gains[3]?.disconnected,
    ]).toEqual([true, true, true, true, true, true]);
    expect(context.closeCount).toBe(1);
  });
});
