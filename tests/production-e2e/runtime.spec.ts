import { expect, test } from '@playwright/test';

test('production ignores every e2e query backdoor', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1&forceFallback=1');
  const ui = page.locator('#app-ui');
  const canvas = page.locator('#game-canvas');

  await expect(ui).toHaveAttribute('data-phase', 'intro');
  await expect(canvas).not.toHaveAttribute('data-pose-probe', /.+/);

  await page.getByRole('button', { name: 'PRESS START' }).click();
  await expect(ui).toHaveAttribute('data-phase', 'playing');
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await page.waitForTimeout(250);

  await expect(ui).toHaveAttribute('data-phase', 'playing');
  await expect(canvas).not.toHaveAttribute('data-pose-probe', /.+/);
});
