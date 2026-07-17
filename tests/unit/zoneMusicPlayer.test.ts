import { describe, expect, it, vi } from 'vitest';
import { ZONES } from '../../src/game/zones';
import {
  ZONE_MUSIC_CROSSFADE_SECONDS,
  ZONE_MUSIC_TRACKS,
  ZoneMusicPlayer,
  zoneMusicAtDistance,
} from '../../src/platform/zoneMusicPlayer';

interface ParamEvent {
  readonly kind: 'cancel' | 'curve' | 'set';
  readonly value?: number;
  readonly values?: readonly number[];
  readonly startTime: number;
  readonly duration?: number;
}

class FakeAudioParam {
  public readonly events: ParamEvent[] = [];
  public value = 1;

  public cancelScheduledValues(startTime: number): void {
    this.events.push({ kind: 'cancel', startTime });
  }

  public setValueAtTime(value: number, startTime: number): void {
    this.value = value;
    this.events.push({ kind: 'set', value, startTime });
  }

  public setValueCurveAtTime(
    values: Float32Array,
    startTime: number,
    duration: number,
  ): void {
    this.value = values.at(-1) ?? this.value;
    this.events.push({
      kind: 'curve',
      values: [...values],
      startTime,
      duration,
    });
  }
}

class FakeAudioNode {
  public readonly connections: unknown[] = [];
  public disconnectCount = 0;

  public connect(destination: unknown): unknown {
    this.connections.push(destination);
    return destination;
  }

  public disconnect(): void {
    this.disconnectCount += 1;
  }
}

class FakeGainNode extends FakeAudioNode {
  public readonly gain = new FakeAudioParam();
}

class FakeAudioBuffer {
  public constructor(public readonly marker: number) {}
}

class FakeBufferSourceNode extends FakeAudioNode {
  private readonly endedListeners: Array<() => void> = [];
  public buffer: FakeAudioBuffer | null = null;
  public loop = false;
  public readonly starts: number[] = [];
  public readonly stops: number[] = [];

  public addEventListener(type: string, listener: () => void): void {
    if (type === 'ended') this.endedListeners.push(listener);
  }

  public dispatchEnded(): void {
    for (const listener of this.endedListeners.splice(0)) listener();
  }

  public start(when = 0): void {
    this.starts.push(when);
  }

  public stop(when = 0): void {
    this.stops.push(when);
  }
}

class FakeAudioContext {
  public readonly bufferSources: FakeBufferSourceNode[] = [];
  public readonly decodedMarkers: number[] = [];
  public readonly gains: FakeGainNode[] = [];
  public currentTime = 10;

  public createBufferSource(): FakeBufferSourceNode {
    const source = new FakeBufferSourceNode();
    this.bufferSources.push(source);
    return source;
  }

  public createGain(): FakeGainNode {
    const gain = new FakeGainNode();
    this.gains.push(gain);
    return gain;
  }

  public decodeAudioData(data: ArrayBuffer): Promise<FakeAudioBuffer> {
    const marker = new Uint8Array(data)[0] ?? 0;
    this.decodedMarkers.push(marker);
    return Promise.resolve(new FakeAudioBuffer(marker));
  }
}

interface FetchHarness {
  readonly calls: string[];
  readonly fetcher: typeof fetch;
}

interface Deferred<Value> {
  readonly promise: Promise<Value>;
  readonly resolve: (value: Value) => void;
}

const deferred = <Value>(): Deferred<Value> => {
  let resolve!: (value: Value) => void;
  const promise = new Promise<Value>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
};

const encodedResponse = (marker: number, ok = true): Response => ({
  ok,
  status: ok ? 200 : 503,
  arrayBuffer: async () => Uint8Array.of(marker).buffer,
}) as Response;

const successfulFetch = (): FetchHarness => {
  const calls: string[] = [];
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);
    const marker = ZONE_MUSIC_TRACKS.findIndex(({ url: candidate }) => candidate === url) + 1;
    return {
      ok: true,
      arrayBuffer: async () => Uint8Array.of(marker).buffer,
    } as Response;
  }) as unknown as typeof fetch;
  return { calls, fetcher };
};

const waitForSnapshot = async (
  player: ZoneMusicPlayer,
  predicate: (snapshot: ReturnType<ZoneMusicPlayer['snapshot']>) => boolean,
): Promise<ReturnType<ZoneMusicPlayer['snapshot']>> => {
  await vi.waitFor(() => {
    expect(predicate(player.snapshot())).toBe(true);
  });
  return player.snapshot();
};

describe('zone music manifest', () => {
  it('maps exact stage boundaries to the three authored tracks', () => {
    expect(ZONE_MUSIC_TRACKS.map(({ id, bpm, url }) => ({ id, bpm, url }))).toEqual([
      { id: 'ringwood-rush', bpm: 148, url: '/music/ringwood-rush.mp3' },
      { id: 'liquidity-loop', bpm: 164, url: '/music/liquidity-loop.mp3' },
      { id: 'ansem-after-dark', bpm: 178, url: '/music/ansem-after-dark.mp3' },
    ]);

    expect(zoneMusicAtDistance(-1).id).toBe('ringwood-rush');
    expect(zoneMusicAtDistance(839.999).id).toBe('ringwood-rush');
    expect(zoneMusicAtDistance(840).id).toBe('liquidity-loop');
    expect(zoneMusicAtDistance(1_959.999).id).toBe('liquidity-loop');
    expect(zoneMusicAtDistance(1_960).id).toBe('ansem-after-dark');
    expect(zoneMusicAtDistance(Number.POSITIVE_INFINITY).id).toBe('ansem-after-dark');
    expect(zoneMusicAtDistance(Number.NaN).id).toBe('ringwood-rush');
    expect(ZONE_MUSIC_TRACKS.map(({ id, startDistance }) => ({
      id,
      startDistance,
    }))).toEqual(ZONES.map(({ id, startDistance }) => ({
      id,
      startDistance,
    })));
  });
});

describe('ZoneMusicPlayer', () => {
  it('waits for start before fetching, then retains only the active and next decoded tracks', async () => {
    const context = new FakeAudioContext();
    const output = new FakeAudioNode();
    const { calls, fetcher } = successfulFetch();
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      output as unknown as AudioNode,
      { fetcher },
    );

    expect(calls).toEqual([]);
    expect(player.snapshot()).toMatchObject({
      activeSources: 0,
      retainedBuffers: 0,
      running: false,
    });

    player.start();
    const snapshot = await waitForSnapshot(
      player,
      ({ activeZone, nextZone }) =>
        activeZone === 'ringwood-rush' && nextZone === 'liquidity-loop',
    );

    expect(calls).toEqual([
      '/music/ringwood-rush.mp3',
      '/music/liquidity-loop.mp3',
    ]);
    expect(snapshot).toMatchObject({
      activeSources: 1,
      activeZone: 'ringwood-rush',
      destroyed: false,
      nextZone: 'liquidity-loop',
      requestedZone: 'ringwood-rush',
      retainedBuffers: 2,
      running: true,
    });
    expect(context.bufferSources[0]).toMatchObject({
      buffer: { marker: 1 },
      loop: true,
      starts: [10],
    });
  });

  it('crossfades a prefetched zone with complementary equal-power curves over 1.2 seconds', async () => {
    const context = new FakeAudioContext();
    const { fetcher } = successfulFetch();
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );
    player.start();
    await waitForSnapshot(player, ({ nextZone }) => nextZone === 'liquidity-loop');

    player.setDistance(840);

    expect(player.snapshot()).toMatchObject({
      activeSources: 2,
      activeZone: 'liquidity-loop',
      nextZone: null,
      requestedZone: 'liquidity-loop',
      retainedBuffers: 2,
    });
    expect(context.bufferSources).toHaveLength(2);
    expect(context.bufferSources[0]?.stops).toEqual([
      context.currentTime + ZONE_MUSIC_CROSSFADE_SECONDS,
    ]);
    expect(context.bufferSources[1]).toMatchObject({
      buffer: { marker: 2 },
      loop: true,
      starts: [context.currentTime],
    });

    const outgoingCurve = context.gains[0]?.gain.events.find(({ kind }) => kind === 'curve');
    const incomingCurve = context.gains[1]?.gain.events.find(({ kind }) => kind === 'curve');
    expect(outgoingCurve?.duration).toBe(1.2);
    expect(incomingCurve?.duration).toBe(1.2);
    expect(outgoingCurve?.values?.[0]).toBeCloseTo(1, 6);
    expect(outgoingCurve?.values?.at(-1)).toBeCloseTo(0, 6);
    expect(incomingCurve?.values?.[0]).toBeCloseTo(0, 6);
    expect(incomingCurve?.values?.at(-1)).toBeCloseTo(1, 6);

    const middle = Math.floor((outgoingCurve?.values?.length ?? 1) / 2);
    const outgoingMiddle = outgoingCurve?.values?.[middle] ?? 0;
    const incomingMiddle = incomingCurve?.values?.[middle] ?? 0;
    expect(outgoingMiddle ** 2 + incomingMiddle ** 2).toBeCloseTo(1, 4);
  });

  it('releases the outgoing buffer before preloading the following zone', async () => {
    const context = new FakeAudioContext();
    const { calls, fetcher } = successfulFetch();
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );
    player.start();
    await waitForSnapshot(player, ({ nextZone }) => nextZone === 'liquidity-loop');
    player.setDistance(840);

    expect(player.snapshot().retainedZones).toEqual([
      'ringwood-rush',
      'liquidity-loop',
    ]);
    expect(calls).not.toContain('/music/ansem-after-dark.mp3');

    context.bufferSources[0]?.dispatchEnded();
    const snapshot = await waitForSnapshot(
      player,
      ({ nextZone }) => nextZone === 'ansem-after-dark',
    );

    expect(snapshot.retainedZones).toEqual([
      'liquidity-loop',
      'ansem-after-dark',
    ]);
    expect(snapshot).toMatchObject({
      activeSources: 1,
      retainedBuffers: 2,
    });
    expect(context.bufferSources[0]?.disconnectCount).toBe(1);
    expect(context.gains[0]?.disconnectCount).toBe(1);
  });

  it('does no reconciliation, fetch, or source work for repeated updates inside the active zone', async () => {
    const context = new FakeAudioContext();
    const { calls, fetcher } = successfulFetch();
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );
    player.start();
    await waitForSnapshot(player, ({ nextZone }) => nextZone === 'liquidity-loop');
    const requestReconcile = vi.spyOn(
      player as unknown as { requestReconcile(): void },
      'requestReconcile',
    );
    const initialCalls = [...calls];
    const initialSources = context.bufferSources.length;

    for (let index = 0; index < 1_000; index += 1) {
      player.setDistance(index % 840);
    }
    await Promise.resolve();

    expect(requestReconcile).not.toHaveBeenCalled();
    expect(calls).toEqual(initialCalls);
    expect(context.bufferSources).toHaveLength(initialSources);
  });

  it('contains fetch and decode failures and can recover on a later zone request', async () => {
    const context = new FakeAudioContext();
    let shouldFail = true;
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      if (shouldFail) throw new Error('offline');
      const marker = String(input).includes('liquidity') ? 2 : 3;
      return {
        ok: true,
        arrayBuffer: async () => Uint8Array.of(marker).buffer,
      } as Response;
    }) as unknown as typeof fetch;
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );

    expect(() => player.start()).not.toThrow();
    await vi.waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(1);
    });
    expect(player.snapshot()).toMatchObject({
      activeSources: 0,
      activeZone: null,
      retainedBuffers: 0,
      running: true,
    });

    shouldFail = false;
    expect(() => player.setDistance(840)).not.toThrow();
    await waitForSnapshot(player, ({ activeZone }) => activeZone === 'liquidity-loop');
    expect(context.bufferSources).toHaveLength(1);
  });

  it('discards zone one when its fetch resolves after zone two is requested', async () => {
    const context = new FakeAudioContext();
    const ringwood = deferred<Response>();
    const liquidity = deferred<Response>();
    const calls: string[] = [];
    const fetcher = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      return url.includes('ringwood') ? ringwood.promise : liquidity.promise;
    }) as unknown as typeof fetch;
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );

    player.start();
    player.setDistance(840);
    ringwood.resolve(encodedResponse(1));
    await vi.waitFor(() => {
      expect(calls).toContain('/music/liquidity-loop.mp3');
    });
    liquidity.resolve(encodedResponse(2));
    await waitForSnapshot(player, ({ activeZone }) => activeZone === 'liquidity-loop');

    expect(player.snapshot()).toMatchObject({
      activeZone: 'liquidity-loop',
      requestedZone: 'liquidity-loop',
    });
    expect(context.bufferSources.map(({ buffer }) => buffer?.marker)).toEqual([2]);
  });

  it('does not retain or play a fetch that resolves after destroy', async () => {
    const context = new FakeAudioContext();
    const response = deferred<Response>();
    const fetcher = vi.fn(() => response.promise) as unknown as typeof fetch;
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );

    player.start();
    player.destroy();
    response.resolve(encodedResponse(1));
    await vi.waitFor(() => {
      expect(context.decodedMarkers).toEqual([1]);
    });

    expect(context.bufferSources).toEqual([]);
    expect(player.snapshot()).toMatchObject({
      activeSources: 0,
      activeZone: null,
      destroyed: true,
      retainedBuffers: 0,
    });
  });

  it('treats a non-OK music response as silence without rejecting publicly', async () => {
    const context = new FakeAudioContext();
    const fetcher = vi.fn(async () => encodedResponse(0, false)) as unknown as typeof fetch;
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );

    expect(() => player.start()).not.toThrow();
    await vi.waitFor(() => {
      expect(fetcher).toHaveBeenCalledOnce();
    });
    await Promise.resolve();

    expect(context.decodedMarkers).toEqual([]);
    expect(context.bufferSources).toEqual([]);
    expect(player.snapshot()).toMatchObject({
      activeSources: 0,
      activeZone: null,
      retainedBuffers: 0,
      running: true,
    });
  });

  it('preserves a suspended source, resets on stop/restart, and releases all nodes on destroy', async () => {
    const context = new FakeAudioContext();
    const { fetcher } = successfulFetch();
    const player = new ZoneMusicPlayer(
      context as unknown as AudioContext,
      new FakeAudioNode() as unknown as AudioNode,
      { fetcher },
    );
    player.start();
    await waitForSnapshot(player, ({ nextZone }) => nextZone === 'liquidity-loop');
    const firstSource = context.bufferSources[0];

    player.pause();
    player.resume();
    expect(context.bufferSources).toHaveLength(1);
    expect(firstSource?.stops).toEqual([]);

    player.stop(true);
    expect(firstSource?.stops).toEqual([context.currentTime]);
    expect(player.snapshot()).toMatchObject({
      activeSources: 0,
      activeZone: 'ringwood-rush',
      retainedBuffers: 2,
      running: false,
    });

    player.start(true);
    expect(context.bufferSources).toHaveLength(2);
    expect(context.bufferSources[1]).toMatchObject({
      buffer: { marker: 1 },
      starts: [context.currentTime],
    });

    player.destroy();
    player.destroy();
    expect(context.bufferSources[1]?.stops).toEqual([context.currentTime]);
    expect(context.bufferSources[1]?.disconnectCount).toBe(1);
    expect(context.gains[1]?.disconnectCount).toBe(1);
    expect(player.snapshot()).toMatchObject({
      activeSources: 0,
      activeZone: null,
      destroyed: true,
      retainedBuffers: 0,
      running: false,
    });
  });
});
