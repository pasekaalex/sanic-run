import { BRAND } from '../config';
import type { SimulationSnapshot } from '../game/types';
import type { ScoreRank } from './scoreCard';
import { getScoreRank } from './scoreCard';

export type AppPhase = 'loading' | 'intro' | 'playing' | 'paused' | 'gameOver' | 'unsupported';

export interface UIActions {
  start(): void;
  pause(): void;
  resume(): void;
  restart(): void;
  mute(muted: boolean): void;
  copyContract(): Promise<void>;
  share(): Promise<void>;
  focusGame(): void;
}

interface GameOverDetails {
  readonly rank: ScoreRank;
  readonly shareReady: boolean;
}

const externalAttributes = 'target="_blank" rel="noopener noreferrer"';

const linkMarkup = (): string => `
  <a class="link-chip" href="${BRAND.pumpUrl}" ${externalAttributes} aria-label="View on Pump.fun">PUMP.FUN</a>
  <a class="link-chip" href="${BRAND.xUrl}" ${externalAttributes} aria-label="Follow $SANIC on X">X / @MEMESOFSANIC</a>
`;

const contractMarkup = (className: string): string => `
  <div class="contract ${className}">
    <span class="contract__label">CA</span>
    <code data-contract>${BRAND.contract}</code>
    <button class="icon-button" type="button" data-action="copy" aria-label="Copy contract">COPY</button>
  </div>
`;

const stageMarqueeMarkup = (): string => `
  <div class="stage-marquee" data-stage-marquee>
    <span class="stage-marquee__checker" aria-hidden="true"></span>
    <span class="stage-marquee__chrome" aria-hidden="true"></span>
    <span class="stage-marquee__ring" aria-hidden="true"></span>
    <span data-stage-label>STAGE 01</span>
    <strong data-zone-label>TRENCH ZONE</strong>
    <span data-act-label>ACT 1</span>
  </div>
`;

export class GameUI {
  private readonly loading: HTMLElement;
  private readonly loadingMeter: HTMLElement;
  private readonly loadingBar: HTMLElement;
  private readonly loadingValue: HTMLElement;
  private readonly intro: HTMLElement;
  private readonly hud: HTMLElement;
  private readonly unsupported: HTMLElement;
  private readonly pausedDialog: HTMLDialogElement;
  private readonly resultsDialog: HTMLDialogElement;
  private readonly status: HTMLElement;
  private readonly ringValue: HTMLElement;
  private readonly multiplierValue: HTMLElement;
  private readonly scoreValue: HTMLElement;
  private readonly distanceValue: HTMLElement;
  private readonly resultsScore: HTMLElement;
  private readonly resultsDistance: HTMLElement;
  private readonly resultsRings: HTMLElement;
  private readonly resultsBest: HTMLElement;
  private readonly resultsRank: HTMLElement;
  private readonly shareButton: HTMLButtonElement;
  private readonly saveCardLink: HTMLAnchorElement;
  private readonly unsupportedReason: HTMLElement;
  private readonly unsupportedPromo: HTMLImageElement;
  private readonly muteButtons: readonly HTMLButtonElement[];
  private readonly lifecycleButtons: readonly HTMLButtonElement[];
  private readonly contextBanners: readonly HTMLElement[];
  private phase: AppPhase = 'loading';
  private muted = false;
  private destroyed = false;
  private focusBeforeDialog: HTMLElement | null = null;

  public constructor(
    private readonly root: HTMLElement,
    private readonly actions: UIActions,
  ) {
    root.dataset.uiTheme = 'pixel-16';
    root.dataset.arcadeShell = 'trench-circuit-94';
    root.replaceChildren();
    root.innerHTML = `
      <header class="topbar" aria-label="$SANIC quick links">
        <span class="mini-wordmark">$SANIC</span>
        ${contractMarkup('contract--desktop')}
        <nav class="topbar__links" aria-label="Project links">${linkMarkup()}</nav>
      </header>

      <div class="attract-stage" data-attract-stage aria-hidden="true">
        <div class="arcade-bezel" data-arcade-bezel aria-hidden="true">
          <span class="arcade-bezel__top"></span>
          <span class="arcade-bezel__right"></span>
          <span class="arcade-bezel__bottom"></span>
          <span class="arcade-bezel__left"></span>
        </div>
        <div class="arcade-score-strip" data-arcade-score-strip aria-hidden="true">
          <span>1 PLAYER</span><span>HI 000000</span><span>1994 MODE</span>
        </div>
        <span class="attract-stage__raster" aria-hidden="true"></span>
        <span class="attract-stage__ridge attract-stage__ridge--far" aria-hidden="true"></span>
        <span class="attract-stage__ridge attract-stage__ridge--near" aria-hidden="true"></span>
        <span class="attract-stage__cloud attract-stage__cloud--one"></span>
        <span class="attract-stage__cloud attract-stage__cloud--two"></span>
        <div class="attract-stage__hills">
          <span class="pixel-hill pixel-hill--back"></span>
          <span class="pixel-hill pixel-hill--front"></span>
        </div>
        <div class="attract-stage__grid"></div>
        <span class="pixel-ring pixel-ring--one"></span>
        <span class="pixel-ring pixel-ring--two"></span>
        <span class="pixel-ring pixel-ring--three"></span>
        <span class="pixel-ring pixel-ring--four"></span>
        <div class="attract-stage__checker"></div>
      </div>

      <section class="loading-card" data-view="loading" aria-labelledby="loading-title">
        ${stageMarqueeMarkup()}
        <p class="kicker">RUNNING UP THE TRENCHES</p>
        <h1 id="loading-title">$SANIC</h1>
        <div class="loading-meter" role="progressbar" aria-label="Loading STAGE 01"
          aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"
          aria-valuetext="0% loaded"><span data-loading-bar></span></div>
        <p class="loading-percent"><span data-loading-value>0</span>% LOADED</p>
      </section>

      <section class="intro-panel" data-view="intro" aria-labelledby="intro-title" hidden>
        ${stageMarqueeMarkup()}
        <p class="kicker">${BRAND.tagline}</p>
        <div class="title-lockup" data-title-lockup>
          <h1 id="intro-title" aria-label="$SANIC">
            <span class="title-coin" aria-hidden="true">$</span>
            <span class="title-word" aria-hidden="true">SANIC</span>
          </h1>
          <p class="title-subtitle" aria-hidden="true">RING RUNNER</p>
        </div>
        <p class="context-banner" role="alert" data-context-banner hidden>SANIC HIT A DIMENSIONAL WALL</p>
        <div class="arcade-menu" data-arcade-menu>
          <span class="arcade-menu__cursor" aria-hidden="true">▶</span>
          <button class="primary-button" type="button" data-action="start">PRESS START</button>
          <small>GOTTA GO FAST</small>
        </div>
        <div class="meme-reel" role="group" data-meme-ticker aria-label="$SANIC meme reel">
          <span class="meme-reel__label" aria-hidden="true">LIVE FROM THE TRENCHES</span>
          <div class="meme-reel__window">
            <ul class="meme-reel__track">
              <li data-meme-line>ANSEM SAID ONE MORE RUN</li>
              <li data-meme-line>TRENCHES BUILT DIFFERENT</li>
              <li data-meme-line>I LOVE TO GO FAST</li>
              <li data-meme-line>SEND IT RESPONSIBLY</li>
              <li data-meme-line>0 RINGS IS A LIFESTYLE</li>
              <li data-meme-line>THE CHART NEEDS MORE BLUE</li>
            </ul>
          </div>
        </div>
        <p class="intro-panel__tagline">RUN THE TRENCHES. STACK RINGS.<br><strong>GO FAST.</strong></p>
        <div class="service-deck" data-service-deck>
          ${contractMarkup('contract--intro')}
          <nav class="intro-panel__links" aria-label="Launch links">${linkMarkup()}</nav>
          <div class="controls-copy" aria-label="Game controls">
            <span><b>A D / ← →</b> MOVE</span><span><b>W / ↑ / SPACE</b> JUMP</span><span><b>SWIPE</b> ON MOBILE</span>
          </div>
          <button class="text-button" type="button" data-action="mute" aria-label="Mute sound">SOUND: ON</button>
          <details class="disclosure"><summary>MEME COIN DISCLOSURE</summary><p>${BRAND.disclosure}</p></details>
        </div>
      </section>

      <section class="hud" data-view="hud" aria-label="Run statistics" hidden>
        <div class="hud__metric"><small>RINGS</small><strong data-rings>0</strong></div>
        <div class="hud__metric hud__metric--gold"><small>COMBO</small><strong data-multiplier>1×</strong></div>
        <div class="hud__metric"><small>SCORE</small><strong data-score>0</strong></div>
        <div class="hud__metric hud__metric--distance"><small>DISTANCE</small><strong data-distance>0m</strong></div>
        <div class="hud__actions">
          <button class="hud-button" type="button" data-action="mute" aria-label="Mute sound">SOUND ON</button>
          <button class="hud-button" type="button" data-action="pause" aria-label="Pause">PAUSE</button>
        </div>
        <p class="swipe-hint" aria-hidden="true">SWIPE ← ↑ →</p>
      </section>

      <dialog class="game-dialog pause-dialog" aria-labelledby="pause-title" data-dialog="pause">
        <div class="dialog-card">
          ${stageMarqueeMarkup()}
          <p class="kicker">SPEED TEMPORARILY REVOKED</p>
          <h2 id="pause-title">PAUSED</h2>
          <p class="context-banner" role="alert" data-context-banner hidden>SANIC HIT A DIMENSIONAL WALL</p>
          <div class="pause-stats"><span>SCORE <b data-pause-score>0</b></span><span>DISTANCE <b data-pause-distance>0m</b></span></div>
          <button class="primary-button" type="button" data-action="resume">RESUME</button>
          ${contractMarkup('contract--dialog')}
          <nav class="dialog-links" aria-label="Paused links">${linkMarkup()}</nav>
          <button class="text-button" type="button" data-action="mute" aria-label="Mute sound">SOUND: ON</button>
          <p class="dialog-disclosure">${BRAND.disclosure}</p>
        </div>
      </dialog>

      <dialog class="game-dialog results-dialog" aria-labelledby="results-title" data-dialog="results">
        <div class="dialog-card">
          ${stageMarqueeMarkup()}
          <p class="kicker">THE TIMELINE COULDN'T KEEP UP</p>
          <h2 id="results-title">GAME OVER</h2>
          <p class="context-banner" role="alert" data-context-banner hidden>SANIC HIT A DIMENSIONAL WALL</p>
          <p class="rank" data-results-rank>SIDELINED</p>
          <dl class="results-grid">
            <div><dt>SCORE</dt><dd data-results-score>0</dd></div>
            <div><dt>DISTANCE</dt><dd data-results-distance>0m</dd></div>
            <div><dt>RINGS</dt><dd data-results-rings>0</dd></div>
            <div><dt>BEST</dt><dd data-results-best>0</dd></div>
          </dl>
          <div class="results-actions">
            <button class="primary-button" type="button" data-action="restart">RUN IT BACK</button>
            <button class="secondary-button" type="button" data-action="share" disabled>SHARE SCORE</button>
            <a class="secondary-button save-card" data-save-card href="#" download hidden>SAVE SCORE CARD</a>
          </div>
          <p class="result-note">Bragging rights only. No tokens or financial value are awarded.</p>
        </div>
      </dialog>

      <section class="unsupported-panel" data-view="unsupported" hidden aria-labelledby="unsupported-title">
        <img src="/media/sanic-game-promo.png" alt="Buff blue Sanic charging through a forest of gold rings" data-unsupported-promo>
        <div class="unsupported-panel__scrim"></div>
        <div class="unsupported-panel__content">
          ${stageMarqueeMarkup()}
          <p class="kicker">STATIC SPEED MODE</p>
          <h1 id="unsupported-title">$SANIC</h1>
          <p class="unsupported-reason" data-unsupported-reason></p>
          ${contractMarkup('contract--fallback')}
          <nav class="dialog-links" aria-label="Fallback links">${linkMarkup()}</nav>
          <p class="dialog-disclosure">${BRAND.disclosure}</p>
        </div>
      </section>

      <p class="sr-status" role="status" aria-live="polite" aria-atomic="true" data-status></p>
    `;

    this.loading = this.required('[data-view="loading"]');
    this.loadingMeter = this.required('.loading-meter');
    this.loadingBar = this.required('[data-loading-bar]');
    this.loadingValue = this.required('[data-loading-value]');
    this.intro = this.required('[data-view="intro"]');
    this.hud = this.required('[data-view="hud"]');
    this.unsupported = this.required('[data-view="unsupported"]');
    this.pausedDialog = this.required<HTMLDialogElement>('[data-dialog="pause"]');
    this.resultsDialog = this.required<HTMLDialogElement>('[data-dialog="results"]');
    this.status = this.required('[data-status]');
    this.ringValue = this.required('[data-rings]');
    this.multiplierValue = this.required('[data-multiplier]');
    this.scoreValue = this.required('[data-score]');
    this.distanceValue = this.required('[data-distance]');
    this.resultsScore = this.required('[data-results-score]');
    this.resultsDistance = this.required('[data-results-distance]');
    this.resultsRings = this.required('[data-results-rings]');
    this.resultsBest = this.required('[data-results-best]');
    this.resultsRank = this.required('[data-results-rank]');
    this.shareButton = this.required<HTMLButtonElement>('[data-action="share"]');
    this.saveCardLink = this.required<HTMLAnchorElement>('[data-save-card]');
    this.unsupportedReason = this.required('[data-unsupported-reason]');
    this.unsupportedPromo = this.required<HTMLImageElement>('[data-unsupported-promo]');
    this.muteButtons = Object.freeze([...root.querySelectorAll<HTMLButtonElement>('[data-action="mute"]')]);
    this.lifecycleButtons = Object.freeze([...root.querySelectorAll<HTMLButtonElement>('[data-action="start"], [data-action="resume"], [data-action="restart"]')]);
    this.contextBanners = Object.freeze([...root.querySelectorAll<HTMLElement>('[data-context-banner]')]);
    root.addEventListener('click', this.handleClick);
    this.pausedDialog.addEventListener('cancel', this.handlePauseCancel);
    this.resultsDialog.addEventListener('cancel', this.handleResultsCancel);
    root.dataset.phase = 'loading';
    root.dataset.playerLane = '0';
  }

  public setLoading(progress: number): void {
    if (this.destroyed) return;
    const percent = Math.round(Math.max(0, Math.min(1, progress)) * 100);
    this.setPhase('loading');
    this.loadingBar.style.width = `${percent}%`;
    this.loadingValue.textContent = String(percent);
    this.loadingMeter.setAttribute('aria-valuenow', String(percent));
    this.loadingMeter.setAttribute('aria-valuetext', `${percent}% loaded`);
  }

  public showIntro(): void {
    if (this.destroyed) return;
    this.setPhase('intro');
    this.closeDialogs(true);
  }

  public showPlaying(snapshot: Readonly<SimulationSnapshot>, _bestScore: number): void {
    if (this.destroyed) return;
    this.setPhase('playing', snapshot);
    this.closeDialogs(true);
    this.projectMetrics(snapshot);
  }

  public showPaused(snapshot: Readonly<SimulationSnapshot>): void {
    if (this.destroyed) return;
    this.setPhase('paused', snapshot);
    this.required('[data-pause-score]').textContent = Math.floor(snapshot.score).toLocaleString('en-US');
    this.required('[data-pause-distance]').textContent = `${Math.round(snapshot.distance)}m`;
    this.openDialog(this.pausedDialog);
  }

  public showGameOver(
    snapshot: Readonly<SimulationSnapshot>,
    bestScore: number,
    details: GameOverDetails = { rank: getScoreRank(snapshot.score), shareReady: false },
  ): void {
    if (this.destroyed) return;
    this.setPhase('gameOver', snapshot);
    this.resultsScore.textContent = Math.floor(snapshot.score).toLocaleString('en-US');
    this.resultsDistance.textContent = `${Math.round(snapshot.distance).toLocaleString('en-US')}m`;
    this.resultsRings.textContent = Math.floor(snapshot.rings).toLocaleString('en-US');
    this.resultsBest.textContent = Math.floor(bestScore).toLocaleString('en-US');
    this.resultsRank.textContent = details.rank;
    this.shareButton.disabled = !details.shareReady;
    this.openDialog(this.resultsDialog);
  }

  public showUnsupported(reason: string): void {
    if (this.destroyed) return;
    this.setPhase('unsupported');
    this.closeDialogs(false);
    this.unsupportedReason.textContent = reason;
    this.unsupportedPromo.hidden = false;
  }

  public setMuted(muted: boolean): void {
    this.muted = muted;
    for (const button of this.muteButtons) {
      button.textContent = button.classList.contains('hud-button')
        ? `SOUND ${muted ? 'OFF' : 'ON'}`
        : `SOUND: ${muted ? 'OFF' : 'ON'}`;
      button.setAttribute('aria-label', muted ? 'Unmute sound' : 'Mute sound');
      button.setAttribute('aria-pressed', String(muted));
    }
  }

  public setShareReady(ready: boolean): void {
    this.shareButton.disabled = !ready;
  }

  public setContextAvailable(available: boolean): void {
    this.root.dataset.contextAvailable = String(available);
    for (const button of this.lifecycleButtons) button.disabled = !available;
    for (const banner of this.contextBanners) banner.hidden = available;
  }

  public setScoreCardDownload(url: string | null, filename = 'sanic-score.png'): void {
    if (url === null) {
      this.saveCardLink.hidden = true;
      this.saveCardLink.removeAttribute('href');
      return;
    }
    this.saveCardLink.href = url;
    this.saveCardLink.download = filename;
    this.saveCardLink.hidden = false;
  }

  public revealContractForManualCopy(): void {
    const phaseSelector: Partial<Record<AppPhase, string>> = {
      intro: '.contract--intro',
      playing: '.contract--desktop',
      paused: '.contract--dialog',
      gameOver: '.contract--desktop',
      unsupported: '.contract--fallback',
    };
    const container = phaseSelector[this.phase] === undefined
      ? null
      : this.root.querySelector<HTMLElement>(phaseSelector[this.phase]!);
    const contract = container?.querySelector<HTMLElement>('[data-contract]')
      ?? this.root.querySelector<HTMLElement>('[data-contract]');
    if (contract === null) return;
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(contract);
    selection?.removeAllRanges();
    selection?.addRange(range);
    contract.scrollIntoView({ block: 'nearest' });
  }

  public announce(message: string): void {
    if (this.destroyed) return;
    this.status.textContent = '';
    window.requestAnimationFrame(() => {
      if (!this.destroyed) this.status.textContent = message;
    });
  }

  public destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.root.removeEventListener('click', this.handleClick);
    this.pausedDialog.removeEventListener('cancel', this.handlePauseCancel);
    this.resultsDialog.removeEventListener('cancel', this.handleResultsCancel);
    this.closeDialogs(false);
    this.root.replaceChildren();
  }

  private readonly handleClick = (event: MouseEvent): void => {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLElement>('[data-action]')
      : null;
    const action = target?.dataset.action;
    if (action === undefined) return;

    switch (action) {
      case 'start': this.actions.start(); break;
      case 'pause': this.actions.pause(); break;
      case 'resume': this.actions.resume(); break;
      case 'restart': this.actions.restart(); break;
      case 'mute':
        this.actions.mute(!this.muted);
        if (this.phase === 'playing') this.actions.focusGame();
        break;
      case 'copy': void this.actions.copyContract(); break;
      case 'share': void this.actions.share(); break;
    }
  };

  private readonly handlePauseCancel = (event: Event): void => {
    event.preventDefault();
    if (this.phase === 'paused') this.actions.resume();
  };

  private readonly handleResultsCancel = (event: Event): void => {
    event.preventDefault();
  };

  private setPhase(phase: AppPhase, snapshot?: Readonly<SimulationSnapshot>): void {
    this.phase = phase;
    this.root.dataset.phase = phase;
    if (snapshot) this.root.dataset.playerLane = String(snapshot.lane);
    if (snapshot) this.root.dataset.playerAirborne = String(snapshot.playerY > 0.02);
    this.loading.hidden = phase !== 'loading';
    this.intro.hidden = phase !== 'intro';
    this.hud.hidden = phase !== 'playing';
    this.unsupported.hidden = phase !== 'unsupported';
    this.root.classList.toggle('is-playing', phase === 'playing');
  }

  private projectMetrics(snapshot: Readonly<SimulationSnapshot>): void {
    this.ringValue.textContent = Math.floor(snapshot.rings).toLocaleString('en-US');
    this.multiplierValue.textContent = `${Math.floor(snapshot.multiplier)}×`;
    this.scoreValue.textContent = Math.floor(snapshot.score).toLocaleString('en-US');
    this.distanceValue.textContent = `${Math.round(snapshot.distance).toLocaleString('en-US')}m`;
  }

  private openDialog(dialog: HTMLDialogElement): void {
    const other = dialog === this.pausedDialog ? this.resultsDialog : this.pausedDialog;
    if (other.open) other.close();
    if (dialog.open) return;
    this.focusBeforeDialog = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    try {
      dialog.showModal();
    } catch {
      dialog.setAttribute('open', '');
    }
    dialog.querySelector<HTMLElement>('button:not([disabled]), a[href]')?.focus();
  }

  private closeDialogs(restoreFocus: boolean): void {
    for (const dialog of [this.pausedDialog, this.resultsDialog]) {
      if (dialog.open) dialog.close();
    }
    if (restoreFocus && this.focusBeforeDialog?.isConnected) this.focusBeforeDialog.focus();
    this.focusBeforeDialog = null;
  }

  private required<ElementType extends HTMLElement = HTMLElement>(selector: string): ElementType {
    const element = this.root.querySelector<ElementType>(selector);
    if (element === null) throw new Error(`Missing UI element: ${selector}`);
    return element;
  }
}
