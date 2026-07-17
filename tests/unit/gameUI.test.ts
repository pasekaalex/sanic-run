import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SimulationSnapshot } from '../../src/game/types';
import { GameUI, type UIActions } from '../../src/ui/gameUI';

const snapshot: SimulationSnapshot = {
  phase: 'paused',
  elapsed: 0,
  distance: 12,
  speed: 18,
  score: 120,
  rings: 2,
  multiplier: 1,
  ringStreak: 2,
  lane: 0,
  playerX: 0,
  playerY: 0,
  jumpProgress: null,
  coins: [],
  obstacles: [],
  impactKind: null,
};

const snapshotAt = (
  distance: number,
  phase: SimulationSnapshot['phase'] = 'playing',
): SimulationSnapshot => ({
  ...snapshot,
  phase,
  elapsed: distance / 20,
  distance,
  speed: distance >= 1_960 ? 32 : distance >= 840 ? 24 : 18,
  score: Math.floor(distance),
});

const inertDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'inert');
const showModalDescriptor = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const closeDescriptor = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');

const restoreDescriptor = (
  target: object,
  name: string,
  descriptor: PropertyDescriptor | undefined,
): void => {
  if (descriptor === undefined) Reflect.deleteProperty(target, name);
  else Object.defineProperty(target, name, descriptor);
};

describe('GameUI', () => {
  beforeEach(() => {
    document.body.innerHTML = '<canvas id="game-canvas" tabindex="-1"></canvas><main id="app-ui"></main>';
    Object.defineProperty(HTMLElement.prototype, 'inert', {
      configurable: true,
      get(this: HTMLElement): boolean {
        return this.hasAttribute('inert');
      },
      set(this: HTMLElement, value: boolean) {
        this.toggleAttribute('inert', value);
      },
    });
    Object.defineProperties(HTMLDialogElement.prototype, {
      showModal: {
        configurable: true,
        value: (): never => {
          throw new DOMException('Modal dialogs unavailable', 'NotSupportedError');
        },
      },
      close: {
        configurable: true,
        value: (): never => {
          throw new DOMException('Dialog close unavailable', 'NotSupportedError');
        },
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    restoreDescriptor(HTMLElement.prototype, 'inert', inertDescriptor);
    restoreDescriptor(HTMLDialogElement.prototype, 'showModal', showModalDescriptor);
    restoreDescriptor(HTMLDialogElement.prototype, 'close', closeDescriptor);
    document.body.replaceChildren();
  });

  it('restores the focus target from before a fallback dialog handoff', () => {
    const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas')!;
    const root = document.querySelector<HTMLElement>('#app-ui')!;
    const actions: UIActions = {
      start: () => undefined,
      pause: () => undefined,
      resume: () => undefined,
      restart: () => undefined,
      mute: () => undefined,
      copyContract: async () => undefined,
      share: async () => undefined,
      focusGame: () => canvas.focus(),
    };
    const addListenerSpy = vi.spyOn(HTMLDialogElement.prototype, 'addEventListener');
    const removeListenerSpy = vi.spyOn(HTMLDialogElement.prototype, 'removeEventListener');
    const ui = new GameUI(root, actions);

    canvas.focus();
    expect(document.activeElement).toBe(canvas);

    ui.showPaused(snapshot);
    expect(root.querySelector<HTMLDialogElement>('[data-dialog="pause"]')!.open).toBe(true);
    ui.showGameOver({ ...snapshot, phase: 'gameOver' }, 120);
    expect(root.querySelector<HTMLDialogElement>('[data-dialog="pause"]')!.open).toBe(false);
    expect(root.querySelector<HTMLDialogElement>('[data-dialog="results"]')!.open).toBe(true);
    expect(canvas.inert).toBe(true);

    ui.showPlaying({ ...snapshot, phase: 'playing' }, 120);
    expect(root.querySelector<HTMLDialogElement>('[data-dialog="results"]')!.open).toBe(false);
    expect(document.activeElement).toBe(canvas);
    expect(canvas.inert).toBe(false);
    expect([...root.children].every((element) => !(element instanceof HTMLElement) || !element.inert)).toBe(true);
    for (const dialog of root.querySelectorAll<HTMLDialogElement>('[data-dialog]')) {
      expect(dialog.hasAttribute('role')).toBe(false);
      expect(dialog.hasAttribute('aria-modal')).toBe(false);
    }
    const addedKeydownListeners = addListenerSpy.mock.calls
      .filter(([type]) => type === 'keydown')
      .map(([, listener]) => listener);
    const removedKeydownListeners = removeListenerSpy.mock.calls
      .filter(([type]) => type === 'keydown')
      .map(([, listener]) => listener);
    expect(addedKeydownListeners).toHaveLength(2);
    expect(removedKeydownListeners).toEqual(addedKeydownListeners);

    ui.destroy();
  });

  it('projects the distance-derived stage and zone through every run view', () => {
    const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas')!;
    const root = document.querySelector<HTMLElement>('#app-ui')!;
    const actions: UIActions = {
      start: () => undefined,
      pause: () => undefined,
      resume: () => undefined,
      restart: () => undefined,
      mute: () => undefined,
      copyContract: async () => undefined,
      share: async () => undefined,
      focusGame: () => canvas.focus(),
    };
    const ui = new GameUI(root, actions);

    ui.setLoading(0.5);
    expect(root.dataset.zone).toBe('ringwood-rush');
    expect(root.querySelector('[data-view="loading"] [data-zone-label]')?.textContent)
      .toBe('RINGWOOD RUSH');
    ui.showIntro();
    expect(root.querySelector('[data-view="intro"] [data-stage-label]')?.textContent)
      .toBe('STAGE 01');

    ui.showPlaying(snapshotAt(840), 0);
    expect(root.dataset).toMatchObject({ zone: 'liquidity-loop', stage: '02', act: '1' });
    expect(root.querySelector('[data-hud-zone-label]')?.textContent).toBe('LIQUIDITY LOOP');
    expect(root.querySelector('[data-hud-stage]')?.getAttribute('aria-hidden')).toBe('true');
    expect(root.querySelector('[data-view="hud"]')?.getAttribute('aria-label'))
      .toContain('STAGE 02, LIQUIDITY LOOP, ACT 1');

    ui.showPaused(snapshotAt(1_200, 'paused'));
    expect(root.querySelector('.pause-dialog [data-zone-label]')?.textContent)
      .toBe('LIQUIDITY LOOP');

    ui.showGameOver(snapshotAt(1_960, 'gameOver'), 1_960);
    expect(root.dataset.zone).toBe('ansem-after-dark');
    expect(root.querySelector('.results-dialog [data-stage-label]')?.textContent)
      .toBe('STAGE 03');
    expect(root.querySelector('.results-dialog [data-zone-label]')?.textContent)
      .toBe('ANSEM AFTER DARK');

    ui.destroy();
  });

  it('shows and announces each forward zone transition only once', () => {
    const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas')!;
    const root = document.querySelector<HTMLElement>('#app-ui')!;
    const actions: UIActions = {
      start: () => undefined,
      pause: () => undefined,
      resume: () => undefined,
      restart: () => undefined,
      mute: () => undefined,
      copyContract: async () => undefined,
      share: async () => undefined,
      focusGame: () => canvas.focus(),
    };
    const ui = new GameUI(root, actions);
    const announce = vi.spyOn(ui, 'announce');

    ui.showPlaying(snapshotAt(0), 0);
    ui.showPlaying(snapshotAt(839.99), 0);
    expect(announce).not.toHaveBeenCalled();

    ui.showPlaying(snapshotAt(840), 0);
    const transition = root.querySelector<HTMLElement>('[data-zone-transition]');
    expect(transition?.hidden).toBe(false);
    expect(transition?.getAttribute('aria-hidden')).toBe('true');
    expect(transition?.textContent).toMatch(/STAGE 02\s+LIQUIDITY LOOP\s+ACT 1/);
    expect(announce).toHaveBeenCalledTimes(1);
    expect(announce).toHaveBeenLastCalledWith('STAGE 02 — LIQUIDITY LOOP — ACT 1');

    ui.showPlaying(snapshotAt(900), 0);
    ui.showPaused(snapshotAt(900, 'paused'));
    ui.showPlaying(snapshotAt(900), 0);
    expect(announce).toHaveBeenCalledTimes(1);

    ui.showPlaying(snapshotAt(1_960), 0);
    expect(announce).toHaveBeenCalledTimes(2);
    expect(announce).toHaveBeenLastCalledWith('STAGE 03 — ANSEM AFTER DARK — ACT 1');

    ui.showPlaying(snapshotAt(0), 0);
    expect(root.dataset.zone).toBe('ringwood-rush');
    expect(transition?.hidden).toBe(true);
    expect(announce).toHaveBeenCalledTimes(2);

    ui.destroy();
  });

  it('rewrites zone labels only when the projected zone changes', () => {
    const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas')!;
    const root = document.querySelector<HTMLElement>('#app-ui')!;
    const actions: UIActions = {
      start: () => undefined,
      pause: () => undefined,
      resume: () => undefined,
      restart: () => undefined,
      mute: () => undefined,
      copyContract: async () => undefined,
      share: async () => undefined,
      focusGame: () => canvas.focus(),
    };
    const ui = new GameUI(root, actions);
    const projectZone = vi.spyOn(
      ui as unknown as { projectZone(zone: unknown): void },
      'projectZone',
    );

    ui.setLoading(0.25);
    ui.setLoading(0.5);
    ui.showIntro();
    ui.showIntro();
    ui.showPlaying(snapshotAt(1), 0);
    ui.showPlaying(snapshotAt(800), 0);
    expect(projectZone).not.toHaveBeenCalled();

    ui.showPlaying(snapshotAt(840), 0);
    ui.showPlaying(snapshotAt(900), 0);
    ui.showPaused(snapshotAt(900, 'paused'));
    expect(projectZone).toHaveBeenCalledTimes(1);

    ui.showIntro();
    ui.showIntro();
    expect(projectZone).toHaveBeenCalledTimes(2);

    ui.destroy();
  });
});
