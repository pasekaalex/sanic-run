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
type FakeAudioContextState = AudioContextState | 'interrupted';

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
  public disconnectCount = 0;
  public disconnected = false;

  public connect(destination: unknown): unknown {
    this.connections.push(destination);
    return destination;
  }

  public disconnect(): void {
    this.disconnectCount += 1;
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

  public dispatchEnded(): void {
    for (const listener of this.endedListeners.splice(0)) listener();
  }

  public start(): void {
    this.started += 1;
    if (this.throwOnStart) throw new Error('source start failed');
    this.fail('start');
  }

  public stop(): void {
    this.stopped += 1;
    this.fail('stop');
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
  public state: FakeAudioContextState;
  private deferredResume = false;
  private failure: { point: FailurePoint; skippedMatches: number } | null = null;
  private readonly pendingResumeResolutions: Array<() => void> = [];
  private readonly pendingSuspendResolutions: Array<() => void> = [];
  private stateBeforeInterruption: 'running' | 'suspended' | null = null;
  private readonly stateChangeListeners = new Set<() => void>();

  public constructor(
    private readonly throwOnWindStart = false,
    private readonly deferSuspend = false,
    private readonly throwOnMusicStart = false,
    private readonly rejectResume = false,
    initialState: FakeAudioContextState = 'running',
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

  public decodeAudioData(_data: ArrayBuffer): Promise<FakeAudioBuffer> {
    return Promise.resolve(new FakeAudioBuffer(4));
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

  public interrupt(): void {
    if (this.state !== 'running') return;
    this.stateBeforeInterruption = 'running';
    this.setState('interrupted');
  }

  public pendingFailure(): FailurePoint | null {
    return this.failure?.point ?? null;
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
    const complete = (): void => {
      if (this.state === 'interrupted') this.stateBeforeInterruption = 'suspended';
      this.setState('suspended');
    };
    if (this.deferSuspend) {
      return new Promise((resolve) => {
        this.pendingSuspendResolutions.push(() => {
          complete();
          resolve();
        });
      });
    }
    complete();
    return Promise.resolve();
  }

  public resolvePendingSuspends(): void {
    for (const resolve of this.pendingSuspendResolutions.splice(0)) resolve();
  }

  public setState(state: FakeAudioContextState): void {
    if (this.state === state) return;
    this.state = state;
    this.dispatchStateChange();
  }

  public stateBeforeInterruptionValue(): 'running' | 'suspended' | null {
    return this.stateBeforeInterruption;
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
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const installMusicFetch = (): ReturnType<typeof vi.fn> => {
  const fetcher = vi.fn(async () => ({
    ok: true,
    arrayBuffer: async () => Uint8Array.of(1).buffer,
  } as Response));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
};

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

const nodeCountDelta = (
  context: FakeAudioContext,
  before: ReturnType<typeof captureNodeCounts>,
) => {
  const after = captureNodeCounts(context);
  return {
    bufferSources: after.bufferSources - before.bufferSources,
    filters: after.filters - before.filters,
    gains: after.gains - before.gains,
    oscillators: after.oscillators - before.oscillators,
  };
};

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

  it('starts decoded authored music once and reserves oscillators for synthesized effects', async () => {
    const context = new FakeAudioContext();
    const constructions = installAudioContext(context);
    installMusicFetch();
    const audio = new AudioController();

    audio.start();
    audio.start();
    await vi.waitFor(() => {
      expect(context.bufferSources.length).toBeGreaterThanOrEqual(2);
    });
    expect(context.oscillators).toHaveLength(0);

    audio.jump();

    expect(constructions()).toBe(1);
    expect(context.bufferSources.length).toBeGreaterThanOrEqual(2);
    expect(context.bufferSources[0]?.started).toBe(1);
    expect(context.bufferSources[1]?.loop).toBe(true);
    expect(context.oscillators).toHaveLength(1);
    expect(context.oscillators[0]?.type).toBe('triangle');
    audio.destroy();
  });

  it('uses the latest authoritative zone supplied before start for the first authored track', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const fetcher = installMusicFetch();
    const audio = new AudioController();

    expect(() => audio.setZone('liquidity-loop')).not.toThrow();
    audio.start();
    await vi.waitFor(() => {
      expect(fetcher).toHaveBeenCalled();
    });

    expect(fetcher.mock.calls[0]?.[0]).toBe('/music/liquidity-loop.mp3');
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

  it('serializes an app pause through native suspend while the context is interrupted', async () => {
    const context = new FakeAudioContext(false, true);
    installAudioContext(context);
    const audio = new AudioController();
    context.addEventListener('statechange', () => {
      if (context.state === 'interrupted') audio.suspend();
    });

    audio.start();
    context.interrupt();
    expect(context.state).toBe('interrupted');
    expect(context.stateBeforeInterruptionValue()).toBe('running');

    audio.suspend();
    context.dispatchStateChange();
    expect(context.suspendCount).toBe(1);
    expect(context.resumeCount).toBe(0);

    context.resolvePendingSuspends();
    await vi.waitFor(() => {
      expect(context.state).toBe('suspended');
      expect(context.stateBeforeInterruptionValue()).toBe('suspended');
      expect(context.suspendCount).toBe(1);
      expect(context.resumeCount).toBe(0);
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
    ['buffer-source', 0, { bufferSources: 0, filters: 0, gains: 1, oscillators: 1 }],
    ['filter', 0, { bufferSources: 1, filters: 0, gains: 1, oscillators: 1 }],
    ['gain', 1, { bufferSources: 1, filters: 1, gains: 1, oscillators: 1 }],
    ['start', 1, { bufferSources: 1, filters: 1, gains: 2, oscillators: 1 }],
    ['stop', 1, { bufferSources: 1, filters: 1, gains: 2, oscillators: 1 }],
  ] as const)(
    'impact contains a later noise %s failure and releases partial effect nodes',
    (failure, skippedMatches, expectedDelta) => {
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
      const delta = nodeCountDelta(context, before);
      const pendingFailure = context.pendingFailure();
      audio.destroy();

      expect(thrown).toBeUndefined();
      expect(pendingFailure).toBeNull();
      expect(delta).toEqual(expectedDelta);
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

  it('resets decoded music at game over and restarts it from the beginning for the next run', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    installMusicFetch();
    const audio = new AudioController();

    audio.start();
    await vi.waitFor(() => {
      expect(context.bufferSources.length).toBeGreaterThanOrEqual(2);
    });
    const firstMusicSource = context.bufferSources[1];
    audio.gameOver();
    audio.restart();

    expect(firstMusicSource?.stopped).toBeGreaterThan(0);
    expect(context.bufferSources).toHaveLength(3);
    expect(context.bufferSources[2]).toMatchObject({
      buffer: firstMusicSource?.buffer,
      loop: true,
      started: 1,
    });
    expect(context.oscillators).toHaveLength(0);
    audio.destroy();
  });

  it('keeps the effects context recoverable at game over without restarting music', async () => {
    vi.useFakeTimers();
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    audio.gameOver();
    const voicesAfterGameOver = context.oscillators.length;
    expect(vi.getTimerCount()).toBe(0);

    context.deferNextResume();
    context.setState('suspended');
    expect(context.resumeCount).toBe(1);
    context.resolvePendingResumes();
    await Promise.resolve();
    await Promise.resolve();

    expect(context.state).toBe('running');
    expect(context.oscillators).toHaveLength(voicesAfterGameOver);
    expect(vi.getTimerCount()).toBe(0);

    audio.impact();
    expect(context.oscillators).toHaveLength(voicesAfterGameOver + 1);
    audio.destroy();
  });

  it('releases transient effect graphs at destroy without double cleanup', () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    const audio = new AudioController();

    audio.start();
    const before = captureNodeCounts(context);
    audio.impact();
    const created = captureCreatedNodes(context, before);
    expect(created.bufferSources).toHaveLength(1);
    expect(created.filters).toHaveLength(1);
    expect(created.gains).toHaveLength(2);
    expect(created.oscillators).toHaveLength(1);
    for (const node of [
      ...created.bufferSources,
      ...created.filters,
      ...created.gains,
      ...created.oscillators,
    ]) {
      expect(node.disconnected).toBe(false);
    }

    audio.destroy();
    for (const source of [...created.bufferSources, ...created.oscillators]) {
      expect(source.stopped).toBe(2);
      expect(source.disconnectCount).toBe(1);
    }
    for (const node of [...created.filters, ...created.gains]) {
      expect(node.disconnectCount).toBe(1);
    }

    for (const source of [...created.bufferSources, ...created.oscillators]) {
      source.dispatchEnded();
    }
    for (const node of [
      ...created.bufferSources,
      ...created.filters,
      ...created.gains,
      ...created.oscillators,
    ]) {
      expect(node.disconnectCount).toBe(1);
    }
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

  it('keeps the effects graph alive when initial authored music fetch fails', async () => {
    const context = new FakeAudioContext();
    installAudioContext(context);
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new Error('music unavailable');
    }));
    const audio = new AudioController();

    expect(() => audio.start()).not.toThrow();
    await Promise.resolve();
    await Promise.resolve();
    expect(context.closeCount).toBe(0);
    audio.jump();
    expect(context.oscillators).toHaveLength(1);
    audio.destroy();
    expect(context.closeCount).toBe(1);
  });
});
