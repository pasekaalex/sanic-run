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

  const background = await adapter.loadImage(ASSET_URLS.scoreCard);
  context.drawImage(background, 0, 0, WIDTH, HEIGHT);
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
