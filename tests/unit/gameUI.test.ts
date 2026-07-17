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

describe('GameUI dialog compatibility', () => {
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
});
