import { BRAND, GAME } from '../config';
import { GameSimulation } from '../game/simulation';
import type { GameCommand, SimulationSnapshot } from '../game/types';
import { jumpStarted } from '../render/animationTiming';
import { AudioController } from '../platform/audioController';
import { InputController } from '../platform/inputController';
import { loadPreferences, savePreferences, type Preferences } from '../platform/storage';
import { AssetLoader } from '../render/assetLoader';
import { WorldRenderer } from '../render/worldRenderer';
import { GameUI, type AppPhase, type UIActions } from '../ui/gameUI';
import {
  canonicalShareUrl,
  formatShareText,
  getScoreRank,
  renderScoreCard,
} from '../ui/scoreCard';
import { createE2EHarness, type E2EHarness } from './e2eHarness';

const MAX_FRAME_SECONDS = 0.25;
const UI_INTERVAL_MS = 50;
const DEFAULT_SEED = 0x5a11c;
const DEFAULT_CRASH_DURATION_SECONDS = 1;
const CRASH_SETTLE_FRAME_MS = 50;
const IMPACT_SUSPEND_MS = 360;

const supportsWebGL2 = (): boolean => {
  try {
    const probe = document.createElement('canvas');
    const context = probe.getContext('webgl2', {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
    });
    context?.getExtension('WEBGL_lose_context')?.loseContext();
    return context !== null;
  } catch {
    return false;
  }
};

export class GameApp {
  private readonly e2eHarness: E2EHarness | null = import.meta.env.MODE === 'e2e'
    ? createE2EHarness(new URLSearchParams(window.location.search))
    : null;
  private readonly simulation: GameSimulation;
  private readonly audio: AudioController;
  private readonly input: InputController;
  private readonly ui: GameUI;
  private preferences: Preferences;
  private renderer: WorldRenderer | null = null;
  private phase: AppPhase = 'loading';
  private previousSnapshot: Readonly<SimulationSnapshot>;
  private currentSnapshot: Readonly<SimulationSnapshot>;
  private accumulator = 0;
  private lastFrameTime: number | null = null;
  private lastUiTime = 0;
  private rafId: number | null = null;
  private destroyed = false;
  private initializationId = 0;
  private runId = 0;
  private scoreCardBlob: Blob | null = null;
  private scoreCardFile: File | null = null;
  private scoreCardObjectUrl: string | null = null;
  private contextAvailable = true;
  private impactSuspendTimer: number | null = null;
  private crashTransitionTimer: number | null = null;
  private crashTransitionMs = (DEFAULT_CRASH_DURATION_SECONDS * 1_000)
    + CRASH_SETTLE_FRAME_MS;

  public constructor(
    private readonly canvas: HTMLCanvasElement,
    root: HTMLElement,
  ) {
    this.preferences = loadPreferences();
    this.simulation = new GameSimulation(
      this.e2eHarness?.seed ?? DEFAULT_SEED,
      this.e2eHarness?.source,
    );
    this.previousSnapshot = this.simulation.snapshot();
    this.currentSnapshot = this.previousSnapshot;
    this.audio = new AudioController(this.preferences.muted);

    const actions: UIActions = {
      start: () => this.start(),
      pause: () => this.pause(),
      resume: () => this.resume(),
      restart: () => this.restart(),
      mute: (muted) => this.setMuted(muted),
      copyContract: () => this.copyContract(),
      share: () => this.share(),
      focusGame: () => this.focusGame(),
    };
    this.ui = new GameUI(root, actions);
    this.ui.setMuted(this.preferences.muted);
    this.input = new InputController(canvas, (command) => this.handleCommand(command));

    document.addEventListener('visibilitychange', this.handleVisibilityChange);
    window.addEventListener('blur', this.handleWindowBlur);
    this.e2eHarness?.attachCrashHandler(this.simulation, (previous, current) => {
      this.previousSnapshot = previous;
      this.currentSnapshot = current;
      this.afterStep(previous, current);
    });
  }

  public async initialize(): Promise<void> {
    const initializationId = ++this.initializationId;
    this.phase = 'loading';
    this.ui.setLoading(0);

    if (
      this.e2eHarness?.simulateUnsupported === true
      || !supportsWebGL2()
    ) {
      if (!this.destroyed && initializationId === this.initializationId) {
        this.phase = 'unsupported';
        this.canvas.hidden = true;
        this.ui.showUnsupported('YOUR BROWSER IS TOO SLOW FOR SANIC');
      }
      return;
    }

    try {
      const assets = await new AssetLoader().load((progress) => {
        if (!this.destroyed && initializationId === this.initializationId) {
          this.ui.setLoading(progress);
        }
      });
      if (this.destroyed || initializationId !== this.initializationId) return;

      const crashDuration = assets.animations.find(({ name }) => name === 'Crash')?.duration;
      if (crashDuration !== undefined && Number.isFinite(crashDuration) && crashDuration > 0) {
        this.crashTransitionMs = (crashDuration * 1_000) + CRASH_SETTLE_FRAME_MS;
      }
      this.canvas.dataset.characterAsset = assets.fallback.character ? 'fallback' : 'glb';
      this.canvas.dataset.spinBallAsset = assets.fallback.spinBall ? 'fallback' : 'glb';
      this.canvas.dataset.ringAsset = assets.fallback.ring ? 'fallback' : 'glb';
      this.canvas.dataset.forestAsset = assets.fallback.forest ? 'fallback' : 'glb';

      this.renderer = new WorldRenderer(this.canvas, assets, {
        onContextLost: this.handleContextLost,
        onContextRestored: this.handleContextRestored,
        enableTestProbes: this.e2eHarness?.testProbes === true,
      });
      this.renderer.setLowEffects(this.preferences.lowEffects || this.e2eHarness?.lowEffects === true);
      this.phase = 'intro';
      this.ui.showIntro();
      this.startLoop();
    } catch {
      if (this.destroyed || initializationId !== this.initializationId) return;
      this.phase = 'unsupported';
      this.canvas.hidden = true;
      this.ui.showUnsupported('SANIC HIT A DIMENSIONAL WALL');
    }
  }

  public destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.initializationId += 1;
    this.stopLoop();
    this.clearCrashSequence();
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    window.removeEventListener('blur', this.handleWindowBlur);
    this.e2eHarness?.destroy();
    this.input.destroy();
    this.audio.destroy();
    this.renderer?.destroy();
    this.renderer = null;
    this.revokeScoreCardUrl();
    this.scoreCardBlob = null;
    this.scoreCardFile = null;
    this.ui.destroy();
  }

  private start(): void {
    if (this.destroyed || !this.contextAvailable || this.phase !== 'intro' || this.renderer === null) return;
    this.audio.start();
    this.simulation.start();
    this.phase = 'playing';
    this.resetClocks();
    this.syncSnapshots();
    this.syncAudioIntensity(this.currentSnapshot);
    this.ui.showPlaying(this.currentSnapshot, this.preferences.bestScore);
    this.focusGame();
    this.ui.announce('RUN STARTED');
    this.startLoop();
  }

  private pause(): void {
    if (this.destroyed || this.phase !== 'playing') return;
    this.simulation.pause();
    this.phase = 'paused';
    this.stopLoop();
    this.syncSnapshots();
    this.renderer?.render(this.previousSnapshot, this.currentSnapshot, 1);
    this.audio.suspend();
    this.ui.showPaused(this.currentSnapshot);
  }

  private resume(): void {
    if (this.destroyed || !this.contextAvailable || this.phase !== 'paused') return;
    this.simulation.resume();
    this.phase = 'playing';
    this.audio.resume();
    this.resetClocks();
    this.syncSnapshots();
    this.ui.showPlaying(this.currentSnapshot, this.preferences.bestScore);
    this.focusGame();
    this.ui.announce('RUN RESUMED');
    this.startLoop();
  }

  private restart(): void {
    if (this.destroyed || !this.contextAvailable || this.phase !== 'gameOver') return;
    this.clearCrashSequence();
    this.clearScoreCard();
    this.runId += 1;
    this.simulation.restart(this.e2eHarness?.seed ?? DEFAULT_SEED);
    this.phase = 'playing';
    this.audio.restart();
    this.resetClocks();
    this.syncSnapshots();
    this.syncAudioIntensity(this.currentSnapshot);
    this.ui.showPlaying(this.currentSnapshot, this.preferences.bestScore);
    this.focusGame();
    this.ui.announce('RUN RESTARTED');
    this.startLoop();
  }

  private setMuted(muted: boolean): void {
    if (this.destroyed) return;
    this.preferences = Object.freeze({ ...this.preferences, muted });
    savePreferences(this.preferences);
    this.audio.setMuted(muted);
    this.ui.setMuted(muted);
    this.ui.announce(muted ? 'SOUND OFF' : 'SOUND ON');
  }

  private async copyContract(): Promise<void> {
    if (this.destroyed) return;
    try {
      await navigator.clipboard.writeText(BRAND.contract);
      if (!this.destroyed) {
        this.ui.announce('CONTRACT COPIED');
        if (this.phase === 'playing') this.focusGame();
      }
    } catch {
      if (this.destroyed) return;
      this.ui.revealContractForManualCopy();
      this.ui.announce('COPY MANUALLY');
    }
  }

  private async share(): Promise<void> {
    if (this.destroyed || this.phase !== 'gameOver') return;
    const file = this.scoreCardFile;
    const blob = this.scoreCardBlob;
    if (file === null || blob === null) {
      this.ui.announce('SCORE CARD IS STILL RENDERING');
      return;
    }

    const text = formatShareText(this.currentSnapshot.score);
    const url = canonicalShareUrl(window.location.href);
    let nativeSupported = false;
    try {
      nativeSupported = typeof navigator.share === 'function'
        && typeof navigator.canShare === 'function'
        && navigator.canShare({ files: [file] });
    } catch {
      nativeSupported = false;
    }

    if (!nativeSupported) {
      this.openShareIntent(text, url);
      this.exposeScoreCardDownload(blob);
      return;
    }

    try {
      await navigator.share({ files: [file], text, url, title: '$SANIC SCORE' });
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      if (!this.destroyed) this.ui.announce('SHARE FAILED — SAVE THE CARD INSTEAD');
      this.exposeScoreCardDownload(blob);
    }
  }

  private openShareIntent(text: string, url: string): void {
    const intent = new URL('https://twitter.com/intent/tweet');
    intent.searchParams.set('text', text);
    intent.searchParams.set('url', url);
    const popup = window.open(intent.toString(), '_blank', 'noopener,noreferrer');
    if (popup !== null) popup.opener = null;
  }

  private exposeScoreCardDownload(blob: Blob): void {
    if (this.scoreCardObjectUrl === null) this.scoreCardObjectUrl = URL.createObjectURL(blob);
    this.ui.setScoreCardDownload(
      this.scoreCardObjectUrl,
      `sanic-score-${Math.floor(this.currentSnapshot.score)}.png`,
    );
  }

  private handleCommand(command: GameCommand): void {
    if (this.destroyed) return;
    if (command === 'pause') {
      if (this.phase === 'playing') this.pause();
      else if (this.phase === 'paused') this.resume();
      return;
    }
    if (this.phase !== 'playing') return;

    const before = this.simulation.snapshot();
    this.simulation.command(command);
    this.currentSnapshot = this.simulation.snapshot();
    if (command === 'jump' && jumpStarted(before.jumpProgress, this.currentSnapshot.jumpProgress)) {
      this.audio.jump();
    }
    if ((command === 'left' || command === 'right') && this.currentSnapshot.lane !== before.lane) {
      this.audio.lane();
    }
    this.ui.showPlaying(this.currentSnapshot, this.preferences.bestScore);
  }

  private startLoop(): void {
    if (this.rafId !== null || this.destroyed) return;
    this.rafId = requestAnimationFrame(this.tick);
  }

  private stopLoop(): void {
    if (this.rafId === null) return;
    cancelAnimationFrame(this.rafId);
    this.rafId = null;
  }

  private shouldAnimate(): boolean {
    return this.phase === 'intro'
      || this.phase === 'playing'
      || (this.phase === 'gameOver' && this.crashTransitionTimer !== null);
  }

  private readonly tick = (timestamp: number): void => {
    this.rafId = null;
    if (this.destroyed) return;
    const renderer = this.renderer;
    if (renderer === null) return;

    if (this.lastFrameTime === null) this.lastFrameTime = timestamp;
    const elapsed = Math.min(MAX_FRAME_SECONDS, Math.max(0, (timestamp - this.lastFrameTime) / 1_000));
    this.lastFrameTime = timestamp;

    if (this.phase === 'playing') {
      this.accumulator = Math.min(MAX_FRAME_SECONDS, this.accumulator + elapsed);
      while (this.accumulator >= GAME.fixedStep && this.phase === 'playing') {
        this.previousSnapshot = this.currentSnapshot;
        this.simulation.step(GAME.fixedStep);
        this.currentSnapshot = this.simulation.snapshot();
        this.afterStep(this.previousSnapshot, this.currentSnapshot);
        this.accumulator -= GAME.fixedStep;
      }
      if (this.phase === 'playing' && timestamp - this.lastUiTime >= UI_INTERVAL_MS) {
        this.ui.showPlaying(this.currentSnapshot, this.preferences.bestScore);
        this.lastUiTime = timestamp;
      }
    }

    if (this.shouldAnimate()) {
      renderer.render(
        this.previousSnapshot,
        this.currentSnapshot,
        this.phase === 'playing' ? this.accumulator / GAME.fixedStep : 1,
      );
    }
    if (this.shouldAnimate()) this.startLoop();
  };

  private afterStep(
    previous: Readonly<SimulationSnapshot>,
    current: Readonly<SimulationSnapshot>,
  ): void {
    this.syncAudioIntensity(current);
    if (jumpStarted(previous.jumpProgress, current.jumpProgress)) this.audio.jump();
    if (current.rings > previous.rings) this.audio.pickup(current.multiplier);
    if (previous.phase !== 'gameOver' && current.phase === 'gameOver') this.finishRun(current);
  }

  private finishRun(snapshot: Readonly<SimulationSnapshot>): void {
    this.phase = 'gameOver';
    this.accumulator = 0;
    this.audio.gameOver();
    this.audio.impact();
    this.renderer?.render(this.previousSnapshot, snapshot, 1);
    this.clearCrashSequence();
    this.preferences = Object.freeze({
      ...this.preferences,
      bestScore: Math.max(this.preferences.bestScore, Math.floor(snapshot.score)),
    });
    savePreferences(this.preferences);
    const rank = getScoreRank(snapshot.score);
    const scoreCardRun = ++this.runId;
    this.impactSuspendTimer = window.setTimeout(() => {
      this.impactSuspendTimer = null;
      if (
        !this.destroyed
        && this.phase === 'gameOver'
        && scoreCardRun === this.runId
      ) this.audio.suspend();
    }, IMPACT_SUSPEND_MS);
    this.crashTransitionTimer = window.setTimeout(() => {
      this.crashTransitionTimer = null;
      if (
        this.destroyed
        || this.phase !== 'gameOver'
        || scoreCardRun !== this.runId
      ) return;
      this.stopLoop();
      this.renderer?.completeCrashAnimation();
      this.renderer?.render(this.previousSnapshot, snapshot, 1);
      this.ui.showGameOver(snapshot, this.preferences.bestScore, {
        rank,
        shareReady: false,
      });
      void this.prepareScoreCard(snapshot, rank, scoreCardRun);
    }, this.crashTransitionMs);
    this.startLoop();
  }

  private async prepareScoreCard(
    snapshot: Readonly<SimulationSnapshot>,
    rank: ReturnType<typeof getScoreRank>,
    scoreCardRun: number,
  ): Promise<void> {
    try {
      const blob = await renderScoreCard(snapshot, rank, canonicalShareUrl(window.location.href));
      if (this.destroyed || this.phase !== 'gameOver' || scoreCardRun !== this.runId) return;
      this.scoreCardBlob = blob;
      this.scoreCardFile = new File(
        [blob],
        `sanic-score-${Math.floor(snapshot.score)}.png`,
        { type: 'image/png' },
      );
      this.ui.setShareReady(true);
    } catch {
      if (!this.destroyed && scoreCardRun === this.runId) {
        this.ui.announce('SCORE CARD COULD NOT BE RENDERED');
      }
    }
  }

  private readonly handleVisibilityChange = (): void => {
    if (document.hidden && this.phase === 'playing') this.pause();
  };

  private readonly handleWindowBlur = (): void => {
    if (this.phase === 'playing') this.pause();
  };

  private readonly handleContextLost = (): void => {
    this.contextAvailable = false;
    this.ui.setContextAvailable(false);
    if (this.phase === 'playing') this.pause();
    this.ui.announce('SANIC HIT A DIMENSIONAL WALL');
  };

  private readonly handleContextRestored = (): void => {
    this.contextAvailable = true;
    this.ui.setContextAvailable(true);
    this.ui.announce('DIMENSION RESTORED — PRESS RESUME');
  };

  private syncSnapshots(): void {
    this.currentSnapshot = this.simulation.snapshot();
    this.previousSnapshot = this.currentSnapshot;
  }

  private syncAudioIntensity(snapshot: Readonly<SimulationSnapshot>): void {
    const speedRange = GAME.maxSpeed - GAME.startSpeed;
    const intensity = speedRange > 0 ? (snapshot.speed - GAME.startSpeed) / speedRange : 0;
    this.audio.setIntensity(intensity);
  }

  private resetClocks(): void {
    this.accumulator = 0;
    this.lastFrameTime = null;
    this.lastUiTime = 0;
  }

  private focusGame(): void {
    try {
      this.canvas.focus({ preventScroll: true });
    } catch {
      this.canvas.focus();
    }
  }

  private clearScoreCard(): void {
    this.revokeScoreCardUrl();
    this.scoreCardBlob = null;
    this.scoreCardFile = null;
    this.ui.setScoreCardDownload(null);
    this.ui.setShareReady(false);
  }

  private clearCrashSequence(): void {
    if (this.impactSuspendTimer !== null) {
      window.clearTimeout(this.impactSuspendTimer);
      this.impactSuspendTimer = null;
    }
    if (this.crashTransitionTimer !== null) {
      window.clearTimeout(this.crashTransitionTimer);
      this.crashTransitionTimer = null;
    }
  }

  private revokeScoreCardUrl(): void {
    if (this.scoreCardObjectUrl === null) return;
    URL.revokeObjectURL(this.scoreCardObjectUrl);
    this.scoreCardObjectUrl = null;
  }
}
