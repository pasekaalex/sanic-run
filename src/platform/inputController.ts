import type { GameCommand } from '../game/types';

const SWIPE_THRESHOLD = 42;

const KEY_COMMANDS: Readonly<Record<string, GameCommand>> = Object.freeze({
  arrowleft: 'left',
  a: 'left',
  arrowright: 'right',
  d: 'right',
  arrowup: 'jump',
  w: 'jump',
  ' ': 'jump',
  p: 'pause',
  escape: 'pause',
});

const isInteractiveKeyTarget = (target: EventTarget | null): boolean => (
  target instanceof Element
  && (
    target.closest('button, a, input, textarea, select, summary, [contenteditable]:not([contenteditable="false"])') !== null
    || (target instanceof HTMLElement && (target.isContentEditable || target.contentEditable === 'true'))
  )
);

interface PointerStart {
  readonly id: number;
  readonly x: number;
  readonly y: number;
}

export class InputController {
  private pointerStart: PointerStart | null = null;
  private destroyed = false;

  public constructor(
    private readonly target: HTMLElement,
    private readonly onCommand: (command: GameCommand) => void,
  ) {
    window.addEventListener('keydown', this.handleKeyDown);
    target.addEventListener('pointerdown', this.handlePointerDown);
    target.addEventListener('pointerup', this.handlePointerUp);
    target.addEventListener('pointercancel', this.handlePointerCancel);
  }

  public destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;

    window.removeEventListener('keydown', this.handleKeyDown);
    this.target.removeEventListener('pointerdown', this.handlePointerDown);
    this.target.removeEventListener('pointerup', this.handlePointerUp);
    this.target.removeEventListener('pointercancel', this.handlePointerCancel);

    if (this.pointerStart !== null) this.releasePointer(this.pointerStart.id);
    this.pointerStart = null;
  }

  private readonly handleKeyDown = (event: KeyboardEvent): void => {
    if (isInteractiveKeyTarget(event.target)) return;
    const command = KEY_COMMANDS[event.key.toLowerCase()];
    if (command === undefined) return;

    event.preventDefault();
    if (!event.repeat) this.onCommand(command);
  };

  private readonly handlePointerDown = (event: PointerEvent): void => {
    if (this.pointerStart !== null) return;

    this.pointerStart = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };

    try {
      this.target.setPointerCapture?.(event.pointerId);
    } catch {
      // A synthetic or interrupted pointer can disappear before capture.
    }
  };

  private readonly handlePointerUp = (event: PointerEvent): void => {
    const start = this.pointerStart;
    if (start === null || start.id !== event.pointerId) return;

    this.pointerStart = null;
    this.releasePointer(event.pointerId);

    const deltaX = event.clientX - start.x;
    const deltaY = event.clientY - start.y;
    const horizontalDistance = Math.abs(deltaX);
    const verticalDistance = Math.abs(deltaY);

    if (horizontalDistance >= SWIPE_THRESHOLD && horizontalDistance > verticalDistance) {
      event.preventDefault();
      this.onCommand(deltaX < 0 ? 'left' : 'right');
      return;
    }

    if (verticalDistance >= SWIPE_THRESHOLD && verticalDistance > horizontalDistance && deltaY < 0) {
      event.preventDefault();
      this.onCommand('jump');
    }
  };

  private readonly handlePointerCancel = (event: PointerEvent): void => {
    if (this.pointerStart?.id !== event.pointerId) return;

    this.pointerStart = null;
    this.releasePointer(event.pointerId);
  };

  private releasePointer(pointerId: number): void {
    try {
      if (this.target.hasPointerCapture?.(pointerId)) {
        this.target.releasePointerCapture?.(pointerId);
      }
    } catch {
      // Capture may already have been released by the browser.
    }
  }
}
