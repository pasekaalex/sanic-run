import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

interface ManifestIcon {
  readonly src: string;
  readonly sizes: string;
  readonly type: string;
  readonly purpose?: string;
}

interface WebAppManifest {
  readonly id: string;
  readonly name: string;
  readonly short_name: string;
  readonly description: string;
  readonly start_url: string;
  readonly scope: string;
  readonly display: string;
  readonly background_color: string;
  readonly theme_color: string;
  readonly icons: readonly ManifestIcon[];
}

const publicPath = (...parts: readonly string[]): string => (
  resolve(process.cwd(), 'public', ...parts)
);

const readManifest = (): WebAppManifest => (
  JSON.parse(readFileSync(publicPath('manifest.webmanifest'), 'utf8')) as WebAppManifest
);

const readPngDimensions = (path: string): Readonly<{ width: number; height: number }> => {
  const png = readFileSync(path);
  expect(png.subarray(0, 8)).toEqual(Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  ]));
  return {
    width: png.readUInt32BE(16),
    height: png.readUInt32BE(20),
  };
};

describe('web app manifest', () => {
  it('publishes canonical standalone SANIC metadata', () => {
    const manifest = readManifest();

    expect(manifest).toMatchObject({
      id: 'https://www.sanic.fun/',
      name: '$SANIC — I Love To Go Fast',
      short_name: '$SANIC',
      start_url: 'https://www.sanic.fun/',
      scope: 'https://www.sanic.fun/',
      display: 'standalone',
      background_color: '#03194f',
      theme_color: '#0047ab',
    });
    expect(manifest.description.length).toBeGreaterThan(40);
  });

  it('declares exact 192, 512, and dedicated maskable original-art icons', () => {
    const manifest = readManifest();
    expect(manifest.icons).toEqual([
      {
        src: '/icons/sanic-192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/sanic-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/sanic-maskable-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'maskable',
      },
    ]);

    const expectedDimensions = new Map([
      ['sanic-192.png', 192],
      ['sanic-512.png', 512],
      ['sanic-maskable-512.png', 512],
    ]);
    for (const [filename, size] of expectedDimensions) {
      const path = publicPath('icons', filename);
      expect(readPngDimensions(path)).toEqual({ width: size, height: size });
      expect(statSync(path).size).toBeGreaterThan(10_000);
    }

    const regular = readFileSync(publicPath('icons', 'sanic-512.png'));
    const maskable = readFileSync(publicPath('icons', 'sanic-maskable-512.png'));
    expect(createHash('sha256').update(maskable).digest('hex')).not.toBe(
      createHash('sha256').update(regular).digest('hex'),
    );
  });

  it('keeps install icon payload below 500 KB', () => {
    const combinedBytes = [
      'sanic-192.png',
      'sanic-512.png',
      'sanic-maskable-512.png',
    ].reduce((total, filename) => (
      total + statSync(publicPath('icons', filename)).size
    ), 0);

    expect(combinedBytes).toBeLessThanOrEqual(500_000);
  });
});

describe('install and canonical document metadata', () => {
  it('links the manifest and icons while keeping every public URL on www.sanic.fun', () => {
    const manifest = readManifest();
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    const document = new DOMParser().parseFromString(html, 'text/html');

    expect(document.querySelector('link[rel="manifest"]')?.getAttribute('href'))
      .toBe('/manifest.webmanifest');
    expect(document.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href'))
      .toBe('/icons/sanic-192.png');
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href'))
      .toBe('https://www.sanic.fun/');
    expect(document.querySelector('meta[property="og:url"]')?.getAttribute('content'))
      .toBe('https://www.sanic.fun/');
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content'))
      .toBe('https://www.sanic.fun/media/sanic-og.jpg');
    expect(document.querySelector('meta[name="twitter:image"]')?.getAttribute('content'))
      .toBe('https://www.sanic.fun/media/sanic-og.jpg');
    expect(document.querySelector('meta[name="application-name"]')?.getAttribute('content'))
      .toBe('$SANIC');
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute('content'))
      .toBe(manifest.theme_color);
  });
});
