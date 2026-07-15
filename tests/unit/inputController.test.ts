import { afterEach, describe, expect, it, vi } from 'vitest';
import { InputController } from '../../src/platform/inputController';

interface PointerCaptureTarget {
  readonly element: HTMLElement;
  readonly setPointerCapture: ReturnType<typeof vi.fn>;
  readonly releasePointerCapture: ReturnType<typeof vi.fn>;
}

const makeTarget = (): PointerCaptureTarget => {
  const element = document.createElement('div');
  const setPointerCapture = vi.fn();
  const releasePointerCapture = vi.fn();

  Object.defineProperties(element, {
    setPointerCapture: { configurable: true, value: setPointerCapture },
    hasPointerCapture: { configurable: true, value: vi.fn().mockReturnValue(true) },
    releasePointerCapture: { configurable: true, value: releasePointerCapture },
  });
  document.body.append(element);

  return { element, setPointerCapture, releasePointerCapture };
};

const pointer = (
  type: 'pointerdown' | 'pointerup' | 'pointercancel',
  pointerId: number,
  clientX: number,
  clientY: number,
): PointerEvent => new PointerEvent(type, { pointerId, clientX, clientY });

afterEach(() => {
  document.body.replaceChildren();
});

describe('InputController', () => {
  it('maps keyboard controls to semantic commands', () => {
    const onCommand = vi.fn();
    const { element } = makeTarget();
    const input = new InputController(element, onCommand);

    for (const key of ['ArrowLeft', 'a', 'ArrowRight', 'D', 'ArrowUp', 'w', ' ', 'p', 'Escape']) {
      window.dispatchEvent(new KeyboardEvent('keydown', { key }));
    }

    expect(onCommand.mock.calls.map(([command]) => command)).toEqual([
      'left', 'left', 'right', 'right', 'jump', 'jump', 'jump', 'pause', 'pause',
    ]);
    input.destroy();
  });

  it('ignores repeating and unrelated keyboard events', () => {
    const onCommand = vi.fn();
    const { element } = makeTarget();
    const input = new InputController(element, onCommand);

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', repeat: true }));
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

    expect(onCommand).not.toHaveBeenCalled();
    input.destroy();
  });

  it('ignores game keys from interactive and editable controls', () => {
    const onCommand = vi.fn();
    const { element } = makeTarget();
    const input = new InputController(element, onCommand);
    const button = document.createElement('button');
    const inputField = document.createElement('input');
    const editable = document.createElement('div');
    const summary = document.createElement('summary');
    editable.contentEditable = 'true';
    document.body.append(button, inputField, editable, summary);

    for (const target of [button, inputField, editable, summary]) {
      target.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
      target.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    }

    expect(onCommand).not.toHaveBeenCalled();
    input.destroy();
  });

  it('maps dominant horizontal and upward swipes at the threshold', () => {
    const onCommand = vi.fn();
    const { element, setPointerCapture, releasePointerCapture } = makeTarget();
    const input = new InputController(element, onCommand);

    element.dispatchEvent(pointer('pointerdown', 1, 100, 100));
    element.dispatchEvent(pointer('pointerup', 1, 142, 104));
    element.dispatchEvent(pointer('pointerdown', 2, 100, 100));
    element.dispatchEvent(pointer('pointerup', 2, 30, 104));
    element.dispatchEvent(pointer('pointerdown', 3, 100, 100));
    element.dispatchEvent(pointer('pointerup', 3, 104, 58));

    expect(onCommand.mock.calls.map(([command]) => command)).toEqual(['right', 'left', 'jump']);
    expect(setPointerCapture).toHaveBeenCalledTimes(3);
    expect(releasePointerCapture).toHaveBeenCalledTimes(3);
    input.destroy();
  });

  it('ignores short, downward, tied, and mismatched-pointer gestures', () => {
    const onCommand = vi.fn();
    const { element } = makeTarget();
    const input = new InputController(element, onCommand);

    element.dispatchEvent(pointer('pointerdown', 1, 100, 100));
    element.dispatchEvent(pointer('pointerup', 1, 141, 100));
    element.dispatchEvent(pointer('pointerdown', 2, 100, 100));
    element.dispatchEvent(pointer('pointerup', 2, 100, 150));
    element.dispatchEvent(pointer('pointerdown', 3, 100, 100));
    element.dispatchEvent(pointer('pointerup', 3, 150, 50));
    element.dispatchEvent(pointer('pointerdown', 4, 100, 100));
    element.dispatchEvent(pointer('pointerup', 5, 170, 100));

    expect(onCommand).not.toHaveBeenCalled();
    input.destroy();
  });

  it('clears a cancelled gesture', () => {
    const onCommand = vi.fn();
    const { element } = makeTarget();
    const input = new InputController(element, onCommand);

    element.dispatchEvent(pointer('pointerdown', 1, 100, 100));
    element.dispatchEvent(pointer('pointercancel', 1, 100, 100));
    element.dispatchEvent(pointer('pointerup', 1, 170, 100));

    expect(onCommand).not.toHaveBeenCalled();
    input.destroy();
  });

  it('removes every listener when destroyed', () => {
    const onCommand = vi.fn();
    const { element, setPointerCapture } = makeTarget();
    const input = new InputController(element, onCommand);

    input.destroy();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));
    element.dispatchEvent(pointer('pointerdown', 1, 100, 100));
    element.dispatchEvent(pointer('pointerup', 1, 170, 100));

    expect(onCommand).not.toHaveBeenCalled();
    expect(setPointerCapture).not.toHaveBeenCalled();
  });
});
