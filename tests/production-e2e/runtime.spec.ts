import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';

const productionOutDir = process.env.SANIC_PRODUCTION_OUT_DIR ?? 'dist';
const bundleMarkers = [
  'e2e-center',
  'e2e-obstacle-center',
  'sanic:e2e-crash',
  'forceFallback',
  'poseProbe',
  '.get(`seed`)',
  '.get("seed")',
  ".get('seed')",
] as const;

const readProductionJavaScript = (): string => {
  const assetsDirectory = resolve(productionOutDir, 'assets');
  return readdirSync(assetsDirectory)
    .filter((file) => file.endsWith('.js'))
    .map((file) => readFileSync(resolve(assetsDirectory, file), 'utf8'))
    .join('\n');
};

test('production bundle omits every e2e hook implementation', () => {
  const bundledJavaScript = readProductionJavaScript();
  for (const marker of bundleMarkers) expect(bundledJavaScript).not.toContain(marker);
});

test('production ignores every e2e query backdoor', async ({ page }) => {
  await page.route('**/*.glb', (route) => route.abort('aborted'));
  await page.goto('/?seed=7&e2e=1&forceFallback=1');
  const ui = page.locator('#app-ui');
  const canvas = page.locator('#game-canvas');

  await expect(ui).toHaveAttribute('data-phase', 'intro');
  await expect(canvas).toBeVisible();
  await expect(canvas).not.toHaveAttribute('data-pose-probe', /.+/);

  await page.getByRole('button', { name: 'PRESS START' }).click();
  await expect(ui).toHaveAttribute('data-phase', 'playing');
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await page.waitForTimeout(250);

  await expect(ui).toHaveAttribute('data-phase', 'playing');
  await expect(canvas).not.toHaveAttribute('data-pose-probe', /.+/);
});
