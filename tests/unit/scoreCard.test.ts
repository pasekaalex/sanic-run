import { describe, expect, it, vi } from 'vitest';
import type { SimulationSnapshot } from '../../src/game/types';
import {
  canonicalShareUrl,
  formatShareText,
  getScoreRank,
  renderScoreCard,
  type ScoreCardAdapter,
} from '../../src/ui/scoreCard';

const snapshot = (score: number): SimulationSnapshot => ({
  phase: 'gameOver',
  elapsed: 12,
  distance: 432.6,
  speed: 20,
  score,
  rings: 27,
  multiplier: 3,
  ringStreak: 7,
  lane: 0,
  playerX: 0,
  playerY: 0,
  jumpProgress: null,
  coins: [],
  obstacles: [],
  impactKind: 'log',
});

describe('score-card copy and ranks', () => {
  it.each([
    [1499, 'SIDELINED'],
    [1500, 'TRENCH TOURIST'],
    [4999, 'TRENCH TOURIST'],
    [5000, 'STIMMY SPRINTER'],
    [11999, 'STIMMY SPRINTER'],
    [12000, 'FULL PORT'],
    [24999, 'FULL PORT'],
    [25000, 'TOO FAST FOR THE TIMELINE'],
  ])('maps score %i to %s', (score, rank) => {
    expect(getScoreRank(score)).toBe(rank);
  });

  it('freezes the exact safe share sentence', () => {
    expect(formatShareText(4999.9)).toBe('I scored 4999 in $SANIC. I love to go fast.');
  });

  it('strips query and hash from the canonical share URL', () => {
    expect(canonicalShareUrl('https://sanic.test/play?seed=7#results'))
      .toBe('https://sanic.test/play');
  });
});

describe('renderScoreCard', () => {
  it('renders all exact runtime values into a nonempty PNG', async () => {
    const fillText = vi.fn();
    const drawImage = vi.fn();
    const fillRect = vi.fn();
    const context = { drawImage, fillRect, fillText } as unknown as CanvasRenderingContext2D;
    const png = new Blob(['png-bytes'], { type: 'image/png' });
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(context),
      toBlob: (callback: BlobCallback, type?: string) => callback(type === 'image/png' ? png : null),
    } as unknown as HTMLCanvasElement;
    const background = { width: 1200, height: 675 } as CanvasImageSource;
    const adapter: ScoreCardAdapter = {
      createCanvas: vi.fn().mockReturnValue(canvas),
      loadImage: vi.fn().mockResolvedValue(background),
    };

    const result = await renderScoreCard(
      snapshot(12_345),
      'FULL PORT',
      'https://sanic.test/',
      adapter,
    );

    expect(result.type).toBe('image/png');
    expect(result.size).toBeGreaterThan(0);
    expect(canvas.width).toBe(1200);
    expect(canvas.height).toBe(675);
    expect(drawImage).toHaveBeenCalledWith(background, 0, 0, 1200, 675);
    expect(fillRect).not.toHaveBeenCalled();
    const labels = fillText.mock.calls.map(([value]) => String(value));
    expect(labels).toEqual(expect.arrayContaining([
      '$SANIC', 'SCORE 12,345', 'RINGS 27', 'DISTANCE 433m', 'FULL PORT', 'sanic.test',
    ]));
  });

  it.each([
    ['error', new Error('background missing')],
    ['abort', new DOMException('background request aborted', 'AbortError')],
  ])('renders a procedural PNG when background loading ends in %s', async (_kind, failure) => {
    const addColorStop = vi.fn();
    const createLinearGradient = vi.fn().mockReturnValue({
      addColorStop,
    } as unknown as CanvasGradient);
    const fillRect = vi.fn();
    const fillText = vi.fn();
    const drawImage = vi.fn();
    const context = {
      createLinearGradient,
      drawImage,
      fillRect,
      fillText,
    } as unknown as CanvasRenderingContext2D;
    const png = new Blob(['procedural-png'], { type: 'image/png' });
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(context),
      toBlob: (callback: BlobCallback, type?: string) => callback(type === 'image/png' ? png : null),
    } as unknown as HTMLCanvasElement;
    const adapter: ScoreCardAdapter = {
      createCanvas: vi.fn().mockReturnValue(canvas),
      loadImage: vi.fn().mockRejectedValue(failure),
    };

    const result = await renderScoreCard(
      snapshot(12_345),
      'FULL PORT',
      'https://sanic.test/',
      adapter,
    );

    expect(result).toBe(png);
    expect(result.type).toBe('image/png');
    expect(result.size).toBeGreaterThan(0);
    expect(drawImage).not.toHaveBeenCalled();
    expect(createLinearGradient).toHaveBeenCalled();
    expect(addColorStop).toHaveBeenCalled();
    expect(fillRect).toHaveBeenCalledWith(0, 0, 1200, 675);
    const labels = fillText.mock.calls.map(([value]) => String(value));
    expect(labels).toEqual(expect.arrayContaining([
      '$SANIC', 'SCORE 12,345', 'RINGS 27', 'DISTANCE 433m', 'FULL PORT', 'sanic.test',
    ]));
  });

  it('rejects unavailable canvas output explicitly', async () => {
    const noContext = {
      width: 0,
      height: 0,
      getContext: () => null,
      toBlob: () => undefined,
    } as unknown as HTMLCanvasElement;
    const adapter: ScoreCardAdapter = {
      createCanvas: () => noContext,
      loadImage: vi.fn().mockResolvedValue({} as CanvasImageSource),
    };

    await expect(renderScoreCard(snapshot(1), 'SIDELINED', 'https://sanic.test', adapter))
      .rejects.toThrow('score card canvas');
  });

  it('rejects empty PNG encoder output explicitly', async () => {
    const context = {
      drawImage: vi.fn(),
      fillText: vi.fn(),
    } as unknown as CanvasRenderingContext2D;
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(context),
      toBlob: (callback: BlobCallback) => callback(null),
    } as unknown as HTMLCanvasElement;
    const adapter: ScoreCardAdapter = {
      createCanvas: () => canvas,
      loadImage: vi.fn().mockResolvedValue({} as CanvasImageSource),
    };

    await expect(renderScoreCard(snapshot(1), 'SIDELINED', 'https://sanic.test', adapter))
      .rejects.toThrow('score card PNG could not be created');
  });

  it('reports a thrown PNG encoder failure without swallowing it', async () => {
    const context = {
      drawImage: vi.fn(),
      fillText: vi.fn(),
    } as unknown as CanvasRenderingContext2D;
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(context),
      toBlob: () => {
        throw new Error('PNG encoder exploded');
      },
    } as unknown as HTMLCanvasElement;
    const adapter: ScoreCardAdapter = {
      createCanvas: () => canvas,
      loadImage: vi.fn().mockResolvedValue({} as CanvasImageSource),
    };

    await expect(renderScoreCard(snapshot(1), 'SIDELINED', 'https://sanic.test', adapter))
      .rejects.toThrow('PNG encoder exploded');
  });
});
