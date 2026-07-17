import { ASSET_URLS } from '../config';
import type { SimulationSnapshot } from '../game/types';

export type ScoreRank =
  | 'SIDELINED'
  | 'TRENCH TOURIST'
  | 'STIMMY SPRINTER'
  | 'FULL PORT'
  | 'TOO FAST FOR THE TIMELINE';

export interface ScoreCardAdapter {
  createCanvas(width: number, height: number): HTMLCanvasElement;
  loadImage(source: string): Promise<CanvasImageSource>;
}

const WIDTH = 1200;
const HEIGHT = 675;

const browserAdapter: ScoreCardAdapter = {
  createCanvas: (width, height) => {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    return canvas;
  },
  loadImage: (source) => new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.decoding = 'async';
    image.addEventListener('load', () => resolve(image), { once: true });
    image.addEventListener('error', () => reject(new Error('score card background failed to load')), { once: true });
    image.src = source;
  }),
};

export const getScoreRank = (score: number): ScoreRank => {
  const value = Number.isFinite(score) ? Math.max(0, Math.floor(score)) : 0;
  if (value < 1_500) return 'SIDELINED';
  if (value < 5_000) return 'TRENCH TOURIST';
  if (value < 12_000) return 'STIMMY SPRINTER';
  if (value < 25_000) return 'FULL PORT';
  return 'TOO FAST FOR THE TIMELINE';
};

export const formatShareText = (score: number): string => (
  `I scored ${Math.max(0, Math.floor(Number.isFinite(score) ? score : 0))} in $SANIC. I love to go fast.`
);

export const canonicalShareUrl = (source: string): string => {
  const url = new URL(source);
  url.search = '';
  url.hash = '';
  return url.toString();
};

const displaySite = (siteUrl: string): string => {
  const url = new URL(siteUrl);
  const path = url.pathname === '/' ? '' : url.pathname.replace(/\/$/, '');
  return `${url.host}${path}`;
};

const drawProceduralBackground = (context: CanvasRenderingContext2D): void => {
  const sky = context.createLinearGradient(0, 0, WIDTH, HEIGHT);
  sky.addColorStop(0, '#050729');
  sky.addColorStop(0.54, '#1237a6');
  sky.addColorStop(1, '#08bcd1');
  context.fillStyle = sky;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  // A pixel sun and speed trails keep the no-asset card in the 90s arcade world.
  context.fillStyle = '#ffe330';
  for (let row = 0; row < 7; row += 1) {
    const inset = Math.abs(3 - row) * 18;
    context.fillRect(884 + inset, 90 + row * 24, 244 - inset * 2, 18);
  }
  context.fillStyle = 'rgba(255, 255, 255, .72)';
  for (let streak = 0; streak < 6; streak += 1) {
    context.fillRect(724 + streak * 38, 286 + streak * 19, 312 - streak * 34, 8);
  }

  const tile = 52;
  for (let y = 0; y < 5; y += 1) {
    for (let x = 0; x < 12; x += 1) {
      context.fillStyle = (x + y) % 2 === 0 ? '#15226f' : '#ffe330';
      context.fillRect(576 + x * tile, 430 + y * tile, tile, tile);
    }
  }

  const copyPanel = context.createLinearGradient(0, 0, 760, 0);
  copyPanel.addColorStop(0, 'rgba(2, 4, 31, .98)');
  copyPanel.addColorStop(0.78, 'rgba(2, 4, 31, .88)');
  copyPanel.addColorStop(1, 'rgba(2, 4, 31, 0)');
  context.fillStyle = copyPanel;
  context.fillRect(0, 0, 820, HEIGHT);
};

const canvasToPng = (canvas: HTMLCanvasElement): Promise<Blob> => new Promise((resolve, reject) => {
  canvas.toBlob((blob) => {
    if (blob === null || blob.size === 0 || blob.type !== 'image/png') {
      reject(new Error('score card PNG could not be created'));
      return;
    }
    resolve(blob);
  }, 'image/png');
});

export const renderScoreCard = async (
  snapshot: Readonly<SimulationSnapshot>,
  rank: ScoreRank,
  siteUrl: string,
  adapter: ScoreCardAdapter = browserAdapter,
): Promise<Blob> => {
  const canvas = adapter.createCanvas(WIDTH, HEIGHT);
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const context = canvas.getContext('2d');
  if (context === null) throw new Error('score card canvas is unavailable');

  let background: CanvasImageSource | null = null;
  try {
    background = await adapter.loadImage(ASSET_URLS.scoreCard);
  } catch {
    // The raster is decorative: retain a complete, shareable card without it.
  }
  if (background === null) drawProceduralBackground(context);
  else context.drawImage(background, 0, 0, WIDTH, HEIGHT);
  context.textAlign = 'left';
  context.textBaseline = 'alphabetic';
  context.shadowColor = 'rgba(0, 0, 0, .55)';
  context.shadowBlur = 8;
  context.fillStyle = '#ffe330';
  context.font = '400 82px Bangers, Impact, sans-serif';
  context.fillText('$SANIC', 74, 104);

  context.shadowBlur = 4;
  context.fillStyle = '#ffffff';
  context.font = '700 38px "Space Mono", monospace';
  context.fillText(`SCORE ${Math.floor(snapshot.score).toLocaleString('en-US')}`, 76, 210);
  context.fillText(`RINGS ${Math.floor(snapshot.rings).toLocaleString('en-US')}`, 76, 276);
  context.fillText(`DISTANCE ${Math.round(snapshot.distance).toLocaleString('en-US')}m`, 76, 342);

  context.fillStyle = '#ffe330';
  context.font = rank.length > 18
    ? '400 48px Bangers, Impact, sans-serif'
    : '400 62px Bangers, Impact, sans-serif';
  context.fillText(rank, 76, 438);
  context.fillStyle = '#ffffff';
  context.font = '700 24px "Space Mono", monospace';
  context.fillText(displaySite(siteUrl), 76, 570);

  return canvasToPng(canvas);
};
