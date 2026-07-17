import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  createVersionedServiceWorker,
  type ServiceWorkerBuildFile,
} from '../../build/pwaServiceWorker';

const projectPath = (...parts: readonly string[]): string => (
  resolve(process.cwd(), ...parts)
);

const PUBLIC_FINGERPRINT_FILES = Object.freeze([
  'manifest.webmanifest',
  'favicon.png',
  'icons/sanic-192.png',
  'icons/sanic-512.png',
  'icons/sanic-maskable-512.png',
  'models/sanic-runner.glb',
  'models/sanic-spin-ball.glb',
  'models/sanic-ring.glb',
  'models/forest-kit.glb',
  'media/sanic-game-promo.png',
  'media/sanic-score-card-bg.png',
  'music/ringwood-rush.mp3',
  'music/liquidity-loop.mp3',
  'music/ansem-after-dark.mp3',
]);

const readApplicationJavaScript = (outDir: string): string => {
  const html = readFileSync(projectPath(outDir, 'index.html'), 'utf8');
  const source = html.match(/<script[^>]+src="([^"]+\.js)"/)?.[1];
  if (source === undefined) throw new Error(`Built ${outDir} has no application script`);
  return readFileSync(projectPath(outDir, source.replace(/^\/+/, '')), 'utf8');
};

const readPrecacheUrls = (serviceWorker: string): readonly string[] => {
  const match = serviceWorker.match(
    /const PRECACHE_URLS = Object\.freeze\((\[[\s\S]*?\])\);/,
  );
  if (match?.[1] === undefined) throw new Error('Generated service worker has no precache list');
  return JSON.parse(match[1]) as readonly string[];
};

const readWarmRuntimeUrls = (serviceWorker: string): readonly string[] => {
  const match = serviceWorker.match(
    /const WARM_RUNTIME_URLS = Object\.freeze\((\[[\s\S]*?\])\);/,
  );
  if (match?.[1] === undefined) throw new Error('Generated service worker has no warm list');
  return JSON.parse(match[1]) as readonly string[];
};

const buildFingerprintFiles = (outDir: string): readonly ServiceWorkerBuildFile[] => {
  const assetsPath = projectPath(outDir, 'assets');
  const bundleFiles: ServiceWorkerBuildFile[] = readdirSync(assetsPath).map((filename) => ({
    fileName: `assets/${filename}`,
    contents: readFileSync(resolve(assetsPath, filename)),
  }));
  for (const filename of ['index.html', ...PUBLIC_FINGERPRINT_FILES]) {
    bundleFiles.push({
      fileName: filename,
      contents: readFileSync(projectPath(outDir, filename)),
    });
  }
  return bundleFiles;
};

const readVersion = (serviceWorker: string): string => {
  const version = serviceWorker.match(/const CACHE_VERSION = "([a-f0-9]{16})";/)?.[1];
  if (version === undefined) throw new Error('Generated service worker has no cache version');
  return version;
};

describe.each(['dist', 'dist-adversarial'])(
  'production PWA artifact: %s',
  (outDir) => {
    it('ships canonical install metadata and exact icon files', () => {
      const manifest = JSON.parse(
        readFileSync(projectPath(outDir, 'manifest.webmanifest'), 'utf8'),
      ) as {
        readonly start_url: string;
        readonly scope: string;
        readonly icons: readonly { readonly src: string }[];
      };
      expect(manifest.start_url).toBe('https://www.sanic.fun/');
      expect(manifest.scope).toBe('https://www.sanic.fun/');
      expect(manifest.icons.map(({ src }) => src)).toEqual([
        '/icons/sanic-192.png',
        '/icons/sanic-512.png',
        '/icons/sanic-maskable-512.png',
      ]);
      for (const { src } of manifest.icons) {
        expect(existsSync(projectPath(outDir, src.slice(1)))).toBe(true);
      }

      const html = readFileSync(projectPath(outDir, 'index.html'), 'utf8');
      expect(html).toContain('rel="manifest" href="/manifest.webmanifest"');
      expect(html).toContain('rel="canonical" href="https://www.sanic.fun/"');
    });

    it('generates a bundle-derived versioned worker with runtime-only large media', () => {
      const path = projectPath(outDir, 'sw.js');
      expect(existsSync(path)).toBe(true);
      const serviceWorker = readFileSync(path, 'utf8');
      const precacheUrls = readPrecacheUrls(serviceWorker);
      const warmRuntimeUrls = readWarmRuntimeUrls(serviceWorker);
      const immutableAssets = readdirSync(projectPath(outDir, 'assets'))
        .map((filename) => `/assets/${filename}`)
        .sort();

      expect(precacheUrls).toEqual(expect.arrayContaining([
        '/index.html',
        '/manifest.webmanifest',
        ...immutableAssets,
      ]));
      expect(precacheUrls.some((url) => (
        url.startsWith('/models/')
        || url.startsWith('/media/')
        || url.startsWith('/music/')
        || url.startsWith('/icons/')
      ))).toBe(false);
      expect(warmRuntimeUrls).toEqual(expect.arrayContaining([
        '/models/sanic-runner.glb',
        '/models/sanic-spin-ball.glb',
        '/models/sanic-ring.glb',
        '/models/forest-kit.glb',
        '/media/sanic-game-promo.png',
        '/media/sanic-score-card-bg.png',
        '/music/ringwood-rush.mp3',
        '/music/liquidity-loop.mp3',
        '/music/ansem-after-dark.mp3',
      ]));
      expect(serviceWorker).toContain("name.startsWith(SANIC_CACHE_PREFIX)");
      const expected = createVersionedServiceWorker({
        buildFiles: buildFingerprintFiles(outDir),
        immutableAssets,
        runtimeWarmUrls: warmRuntimeUrls,
      });
      expect(readVersion(serviceWorker)).toBe(expected.version);
      expect(serviceWorker).toBe(expected.source);
    });

    it('retains the post-load registration code in normal production', () => {
      const javaScript = readApplicationJavaScript(outDir);
      expect(javaScript).toContain('/sw.js');
      expect(javaScript).toContain('updateViaCache');
      expect(javaScript).toContain('WARM_RUNTIME');
    });
  },
);

describe('explicit E2E artifact', () => {
  it('contains no generated worker or registration implementation', () => {
    expect(existsSync(projectPath('dist-e2e', 'sw.js'))).toBe(false);
    const javaScript = readApplicationJavaScript('dist-e2e');
    expect(javaScript).not.toContain('/sw.js');
    expect(javaScript).not.toContain('updateViaCache');
    expect(javaScript).not.toContain('WARM_RUNTIME');
  });
});

describe('normal and adversarial production parity', () => {
  it('emits the same worker when NODE_ENV changes but Vite mode remains production', () => {
    expect(readFileSync(projectPath('dist-adversarial', 'sw.js'))).toEqual(
      readFileSync(projectPath('dist', 'sw.js')),
    );
  });
});
