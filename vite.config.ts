import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Plugin, ResolvedConfig } from 'vite';
import { defineConfig } from 'vitest/config';
import {
  createVersionedServiceWorker,
  immutableAssetUrls,
  type ServiceWorkerBuildFile,
} from './build/pwaServiceWorker';

const STATIC_FINGERPRINT_FILES = Object.freeze([
  'manifest.webmanifest',
  'favicon.png',
]);

const RUNTIME_WARM_URLS = Object.freeze([
  '/models/sanic-runner.glb',
  '/models/sanic-spin-ball.glb',
  '/models/sanic-ring.glb',
  '/models/forest-kit.glb',
  '/media/sanic-game-promo.png',
  '/media/sanic-score-card-bg.png',
  '/music/ringwood-rush.mp3',
  '/music/liquidity-loop.mp3',
  '/music/ansem-after-dark.mp3',
]);

const pwaServiceWorkerPlugin = (): Plugin => {
  let root = process.cwd();

  return {
    name: 'sanic-pwa-service-worker',
    apply: 'build',
    enforce: 'post',
    configResolved(config: ResolvedConfig): void {
      root = config.root;
    },
    generateBundle(_options, bundle): void {
      const buildFiles: ServiceWorkerBuildFile[] = Object.values(bundle).map((output) => ({
        fileName: output.fileName,
        contents: output.type === 'chunk' ? output.code : output.source,
      }));
      for (const filename of STATIC_FINGERPRINT_FILES) {
        buildFiles.push({
          fileName: filename,
          contents: readFileSync(resolve(root, 'public', filename)),
        });
      }

      const immutableAssets = immutableAssetUrls(
        Object.values(bundle).map(({ fileName }) => fileName),
      );
      const serviceWorker = createVersionedServiceWorker({
        buildFiles,
        immutableAssets,
        runtimeWarmUrls: RUNTIME_WARM_URLS,
      });
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: serviceWorker.source,
      });
    },
  };
};

export default defineConfig(({ mode }) => {
  const productionPlugins = mode === 'production'
    ? [pwaServiceWorkerPlugin()]
    : [];

  return {
    plugins: productionPlugins,
    test: {
      environment: 'jsdom',
      include: ['tests/unit/**/*.test.ts'],
    },
  };
});
