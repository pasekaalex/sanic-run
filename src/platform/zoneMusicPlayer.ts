import { ZONES, zoneAtDistance, type ZoneId } from '../game/zones';

export type ZoneMusicId = ZoneId;

export interface ZoneMusicTrack {
  readonly id: ZoneMusicId;
  readonly bpm: 148 | 164 | 178;
  readonly startDistance: number;
  readonly url: string;
}

export const ZONE_MUSIC_CROSSFADE_SECONDS = 1.2;

const ZONE_MUSIC_METADATA = Object.freeze({
  'ringwood-rush': Object.freeze({
    bpm: 148,
    url: '/music/ringwood-rush.mp3',
  }),
  'liquidity-loop': Object.freeze({
    bpm: 164,
    url: '/music/liquidity-loop.mp3',
  }),
  'ansem-after-dark': Object.freeze({
    bpm: 178,
    url: '/music/ansem-after-dark.mp3',
  }),
} as const satisfies Readonly<Record<
  ZoneId,
  Readonly<Pick<ZoneMusicTrack, 'bpm' | 'url'>>
>>);

export const ZONE_MUSIC_TRACKS: readonly ZoneMusicTrack[] = Object.freeze(
  ZONES.map(({ id, startDistance }) => Object.freeze({
    id,
    startDistance,
    ...ZONE_MUSIC_METADATA[id],
  })),
);

const TRACK_BY_ID = new Map(
  ZONE_MUSIC_TRACKS.map((track) => [track.id, track] as const),
);

const CROSSFADE_CURVE_SAMPLES = 65;
const FADE_IN_CURVE = Float32Array.from(
  { length: CROSSFADE_CURVE_SAMPLES },
  (_, index) => Math.sin((index / (CROSSFADE_CURVE_SAMPLES - 1)) * Math.PI * 0.5),
);
const FADE_OUT_CURVE = Float32Array.from(
  { length: CROSSFADE_CURVE_SAMPLES },
  (_, index) => Math.cos((index / (CROSSFADE_CURVE_SAMPLES - 1)) * Math.PI * 0.5),
);

interface ZoneMusicPlayerOptions {
  readonly fetcher?: typeof fetch;
}

interface PlaybackGraph {
  readonly gain: GainNode;
  released: boolean;
  readonly source: AudioBufferSourceNode;
}

interface LoadedSlot {
  readonly buffer: AudioBuffer;
  playback: PlaybackGraph | null;
  readonly track: ZoneMusicTrack;
}

export interface ZoneMusicPlayerSnapshot {
  readonly activeSources: number;
  readonly activeZone: ZoneMusicId | null;
  readonly destroyed: boolean;
  readonly nextZone: ZoneMusicId | null;
  readonly requestedZone: ZoneMusicId;
  readonly retainedBuffers: number;
  readonly retainedZones: readonly ZoneMusicId[];
  readonly running: boolean;
}

export const zoneMusicAtDistance = (distance: number): ZoneMusicTrack => {
  return TRACK_BY_ID.get(zoneAtDistance(distance).id) ?? ZONE_MUSIC_TRACKS[0]!;
};

export class ZoneMusicPlayer {
  private active: LoadedSlot | null = null;
  private destroyed = false;
  private desiredRunning = false;
  private failedZone: ZoneMusicId | null = null;
  private readonly fetcher: typeof fetch;
  private readonly loads = new Map<ZoneMusicId, Promise<LoadedSlot>>();
  private outgoing: LoadedSlot | null = null;
  private prefetched: LoadedSlot | null = null;
  private preloadInFlight: ZoneMusicId | null = null;
  private reconcileInFlight = false;
  private reconcilePending = false;
  private requestRevision = 0;
  private requestedTrack: ZoneMusicTrack = ZONE_MUSIC_TRACKS[0]!;

  public constructor(
    private readonly context: AudioContext,
    private readonly output: AudioNode,
    options: ZoneMusicPlayerOptions = {},
  ) {
    this.fetcher = options.fetcher ?? ((input, init) => globalThis.fetch(input, init));
  }

  public start(reset = false): void {
    if (this.destroyed) return;
    if (reset) this.stopPlayback();
    this.desiredRunning = true;
    this.failedZone = null;
    if (this.activateRetainedTrack()) return;
    this.requestReconcile();
  }

  public pause(): void {
    if (this.destroyed) return;
    this.desiredRunning = false;
  }

  public resume(): void {
    if (this.destroyed) return;
    this.desiredRunning = true;
    this.failedZone = null;
    if (this.activateRetainedTrack()) return;
    this.requestReconcile();
  }

  public stop(_reset = true): void {
    if (this.destroyed) return;
    this.desiredRunning = false;
    this.stopPlayback();
  }

  public setDistance(distance: number): void {
    this.setZone(zoneMusicAtDistance(distance).id);
  }

  public setZone(zone: ZoneMusicId): void {
    if (this.destroyed) return;
    const track = TRACK_BY_ID.get(zone);
    if (track === undefined) return;

    if (track.id === this.requestedTrack.id) {
      if (
        this.active === null
        && this.failedZone !== track.id
        && this.desiredRunning
        && !this.reconcileInFlight
      ) this.requestReconcile();
      return;
    }

    this.requestedTrack = track;
    this.failedZone = null;
    this.requestRevision += 1;
    this.releaseOutgoingImmediately();
    if (this.prefetched?.track.id !== track.id) this.prefetched = null;
    if (!this.desiredRunning) return;
    this.requestReconcile();
  }

  public destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.desiredRunning = false;
    this.requestRevision += 1;
    this.reconcilePending = false;
    this.stopSlot(this.outgoing);
    this.stopSlot(this.active);
    this.outgoing = null;
    this.active = null;
    this.prefetched = null;
    this.failedZone = null;
    this.loads.clear();
  }

  public snapshot(): Readonly<ZoneMusicPlayerSnapshot> {
    const retainedZones = this.outgoing !== null && this.active !== null
      ? [this.outgoing.track.id, this.active.track.id]
      : [
          ...(this.active === null ? [] : [this.active.track.id]),
          ...(this.prefetched === null ? [] : [this.prefetched.track.id]),
        ];
    const activeSources = Number(this.active?.playback !== null && this.active !== null)
      + Number(this.outgoing?.playback !== null && this.outgoing !== null);

    return Object.freeze({
      activeSources,
      activeZone: this.active?.track.id ?? null,
      destroyed: this.destroyed,
      nextZone: this.prefetched?.track.id ?? null,
      requestedZone: this.requestedTrack.id,
      retainedBuffers: retainedZones.length,
      retainedZones: Object.freeze(retainedZones),
      running: this.desiredRunning,
    });
  }

  private requestReconcile(): void {
    this.reconcilePending = true;
    if (this.reconcileInFlight) return;
    this.reconcileInFlight = true;
    void this.drainReconcile();
  }

  private activateRetainedTrack(): boolean {
    if (
      this.active === null
      || this.active.track.id !== this.requestedTrack.id
      || this.outgoing !== null
    ) return false;
    if (this.active.playback === null) {
      this.active.playback = this.startPlayback(this.active.buffer, 1);
    }
    if (this.active.playback === null) return false;
    this.preloadFollowing();
    return true;
  }

  private async drainReconcile(): Promise<void> {
    while (this.reconcilePending && !this.destroyed) {
      this.reconcilePending = false;
      try {
        await this.reconcileOnce();
      } catch {
        // Missing or undecodable music silences only the music layer.
      }
    }
    this.reconcileInFlight = false;
    if (this.reconcilePending && !this.destroyed) this.requestReconcile();
  }

  private async reconcileOnce(): Promise<void> {
    const revision = this.requestRevision;
    const requested = this.requestedTrack;

    if (this.active?.track.id === requested.id) {
      if (this.desiredRunning && this.active.playback === null) {
        this.active.playback = this.startPlayback(this.active.buffer, 1);
      }
      if (this.desiredRunning && this.active.playback !== null && this.outgoing === null) {
        this.preloadFollowing();
      }
      return;
    }

    let loaded: LoadedSlot;
    if (this.prefetched?.track.id === requested.id) {
      loaded = this.prefetched;
      this.prefetched = null;
    } else {
      this.prefetched = null;
      try {
        loaded = await this.loadTrack(requested);
      } catch (error) {
        if (
          !this.destroyed
          && revision === this.requestRevision
          && requested.id === this.requestedTrack.id
        ) {
          this.failedZone = requested.id;
          this.stopSlot(this.outgoing);
          this.stopSlot(this.active);
          this.outgoing = null;
          this.active = null;
          this.prefetched = null;
        }
        throw error;
      }
    }

    if (
      this.destroyed
      || revision !== this.requestRevision
      || requested.id !== this.requestedTrack.id
    ) return;

    this.failedZone = null;
    this.installRequested(loaded);
  }

  private installRequested(loaded: LoadedSlot): void {
    const current = this.active;
    if (current === null) {
      this.active = loaded;
      if (this.desiredRunning) {
        loaded.playback = this.startPlayback(loaded.buffer, 1);
        if (loaded.playback !== null) this.preloadFollowing();
      }
      return;
    }

    if (!this.desiredRunning || current.playback === null) {
      this.stopSlot(current);
      this.active = loaded;
      if (this.desiredRunning) {
        loaded.playback = this.startPlayback(loaded.buffer, 1);
        if (loaded.playback !== null) this.preloadFollowing();
      }
      return;
    }

    const incoming = this.createPlayback(loaded.buffer);
    if (incoming === null) {
      this.prefetched = loaded;
      return;
    }

    const now = this.context.currentTime;
    try {
      current.playback.gain.gain.cancelScheduledValues(now);
      current.playback.gain.gain.setValueAtTime(
        Math.max(0, Math.min(1, current.playback.gain.gain.value)),
        now,
      );
      current.playback.gain.gain.setValueCurveAtTime(
        FADE_OUT_CURVE,
        now,
        ZONE_MUSIC_CROSSFADE_SECONDS,
      );
      incoming.gain.gain.setValueAtTime(0, now);
      incoming.gain.gain.setValueCurveAtTime(
        FADE_IN_CURVE,
        now,
        ZONE_MUSIC_CROSSFADE_SECONDS,
      );
      incoming.source.start(now);
      current.playback.source.stop(now + ZONE_MUSIC_CROSSFADE_SECONDS);
    } catch {
      this.releasePlayback(incoming, true);
      this.prefetched = loaded;
      return;
    }

    loaded.playback = incoming;
    this.outgoing = current;
    this.active = loaded;
    this.prefetched = null;
  }

  private startPlayback(buffer: AudioBuffer, gainValue: number): PlaybackGraph | null {
    const playback = this.createPlayback(buffer);
    if (playback === null) return null;
    try {
      playback.gain.gain.setValueAtTime(gainValue, this.context.currentTime);
      playback.source.start(this.context.currentTime);
      return playback;
    } catch {
      this.releasePlayback(playback, true);
      return null;
    }
  }

  private createPlayback(buffer: AudioBuffer): PlaybackGraph | null {
    let source: AudioBufferSourceNode | null = null;
    let gain: GainNode | null = null;
    try {
      source = this.context.createBufferSource();
      gain = this.context.createGain();
      source.buffer = buffer;
      source.loop = true;
      source.connect(gain);
      gain.connect(this.output);
      const playback: PlaybackGraph = { source, gain, released: false };
      source.addEventListener('ended', () => this.handlePlaybackEnded(playback), { once: true });
      return playback;
    } catch {
      this.stopNode(source);
      this.disconnect(source);
      this.disconnect(gain);
      return null;
    }
  }

  private handlePlaybackEnded(playback: PlaybackGraph): void {
    this.releasePlayback(playback, false);
    if (this.outgoing?.playback === playback) {
      this.outgoing.playback = null;
      this.outgoing = null;
      if (this.desiredRunning) this.preloadFollowing();
      return;
    }
    if (this.active?.playback === playback) this.active.playback = null;
  }

  private stopPlayback(): void {
    this.stopSlot(this.outgoing);
    this.outgoing = null;
    if (this.active?.playback !== null && this.active !== null) {
      const playback = this.active.playback;
      this.active.playback = null;
      this.releasePlayback(playback, true);
    }
  }

  private stopSlot(slot: LoadedSlot | null): void {
    if (slot?.playback === null || slot === null) return;
    const playback = slot.playback;
    slot.playback = null;
    this.releasePlayback(playback, true);
  }

  private releaseOutgoingImmediately(): void {
    if (this.outgoing === null) return;
    this.stopSlot(this.outgoing);
    this.outgoing = null;
  }

  private releasePlayback(playback: PlaybackGraph, stop: boolean): void {
    if (playback.released) return;
    playback.released = true;
    if (stop) this.stopNode(playback.source);
    this.disconnect(playback.source);
    this.disconnect(playback.gain);
  }

  private preloadFollowing(): void {
    const active = this.active;
    if (
      this.destroyed
      || !this.desiredRunning
      || active === null
      || active.playback === null
      || this.outgoing !== null
      || this.requestedTrack.id !== active.track.id
    ) return;

    const activeIndex = ZONE_MUSIC_TRACKS.findIndex(({ id }) => id === active.track.id);
    const next = ZONE_MUSIC_TRACKS[activeIndex + 1];
    if (next === undefined) {
      this.prefetched = null;
      return;
    }
    if (this.prefetched?.track.id === next.id || this.preloadInFlight === next.id) return;

    const revision = this.requestRevision;
    this.preloadInFlight = next.id;
    void this.loadTrack(next).then((loaded) => {
      if (
        !this.destroyed
        && revision === this.requestRevision
        && this.active?.track.id === active.track.id
        && this.requestedTrack.id === active.track.id
        && this.outgoing === null
      ) this.prefetched = loaded;
    }).catch(() => {
      // A failed preload is retried only if the zone is later requested.
    }).finally(() => {
      if (this.preloadInFlight === next.id) this.preloadInFlight = null;
    });
  }

  private loadTrack(track: ZoneMusicTrack): Promise<LoadedSlot> {
    const inFlight = this.loads.get(track.id);
    if (inFlight !== undefined) return inFlight;

    const promise = this.fetcher(track.url).then(async (response) => {
      if (!response.ok) throw new Error(`Music request failed: ${response.status}`);
      const encoded = await response.arrayBuffer();
      const buffer = await this.context.decodeAudioData(encoded);
      return { buffer, playback: null, track };
    });
    this.loads.set(track.id, promise);
    void promise.finally(() => {
      if (this.loads.get(track.id) === promise) this.loads.delete(track.id);
    }).catch(() => {
      // The caller owns the operational failure; this contains finally's derived promise.
    });
    return promise;
  }

  private stopNode(source: AudioScheduledSourceNode | null): void {
    try {
      source?.stop(this.context.currentTime);
    } catch {
      // A source may not have started or may already be stopped.
    }
  }

  private disconnect(node: AudioNode | null): void {
    try {
      node?.disconnect();
    } catch {
      // Continue releasing the rest of the music graph.
    }
  }
}
