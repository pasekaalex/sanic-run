import { expect, test, type Page } from '@playwright/test';

const CONTRACT = 'CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump';
const PUMP_URL = `https://pump.fun/coin/${CONTRACT}`;

const beginRun = async (page: Page): Promise<void> => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.getByRole('heading', { name: '$SANIC' })).toBeVisible();
  await expect(page.getByText('SWIPE', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'GOTTA GO FAST' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
};

const touchSwipe = async (
  page: Page,
  from: Readonly<{ x: number; y: number }>,
  to: Readonly<{ x: number; y: number }>,
): Promise<void> => {
  const session = await page.context().newCDPSession(page);
  await session.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x: from.x, y: from.y }],
  });
  await session.send('Input.dispatchTouchEvent', {
    type: 'touchMove',
    touchPoints: [{ x: to.x, y: to.y }],
  });
  await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await session.detach();
};

test('starts, responds to controls, pauses, crashes, and restarts', async ({ page }) => {
  await beginRun(page);
  await page.getByRole('button', { name: 'Mute sound' }).click();
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe('game-canvas');
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-player-lane', '-1');
  await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Pause' }).click();
  await expect(page.getByRole('dialog', { name: 'Paused' })).toBeVisible();
  await page.getByRole('button', { name: 'Resume' }).click();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await expect(page.getByRole('dialog', { name: 'Run complete' })).toBeVisible();
  await page.getByRole('button', { name: 'RUN IT BACK' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
});

test('a persisted pagehide keeps the active game alive for BFCache restore', async ({ page, isMobile }) => {
  test.skip(isMobile, 'BFCache lifecycle is viewport-independent');
  await beginRun(page);
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
  });
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-player-lane', '-1');
  await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
});

test('copies the exact contract and exposes only exact launch links', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/');
  await page.getByRole('button', { name: 'Copy contract' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(CONTRACT);
  await expect(page.getByRole('link', { name: 'View on Pump.fun' })).toHaveAttribute('href', PUMP_URL);
  await expect(page.getByRole('link', { name: 'Follow $SANIC on X' })).toHaveAttribute('href', 'https://x.com/memesofsanic');
});

test('clipboard rejection selects the visible phase contract for manual copy', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: async () => Promise.reject(new DOMException('blocked', 'NotAllowedError')) },
    });
  });
  await page.goto('/');
  const copy = page.getByRole('button', { name: 'Copy contract' });
  const summary = page.getByText('MEME COIN DISCLOSURE', { exact: true });
  await expect(copy).toBeVisible();
  await expect(summary).toBeVisible();
  expect((await copy.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
  expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(43.5);
  await copy.click();
  await expect(page.getByRole('status')).toHaveText('COPY MANUALLY');
  const selected = await page.evaluate(() => {
    const selection = window.getSelection();
    const anchor = selection?.anchorNode;
    const element = anchor instanceof Element ? anchor : anchor?.parentElement;
    return {
      text: selection?.toString(),
      contractClass: element?.closest('.contract')?.className,
    };
  });
  expect(selected.text).toBe(CONTRACT);
  expect(selected.contractClass).toContain('contract--intro');
});

test('forced WebGL fallback keeps the launch controls and disclosure usable', async ({ page, context, isMobile }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/?forceFallback=1');

  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'unsupported');
  const fallback = page.locator('[data-view="unsupported"]');
  await expect(page.getByRole('img', { name: 'Buff blue Sanic charging through a forest of gold rings' })).toBeVisible();
  await expect(page.getByText('YOUR BROWSER IS TOO SLOW FOR SANIC')).toBeVisible();
  await expect(fallback.getByText(/No utility, no promises, no financial advice/)).toBeVisible();

  await page.getByRole('button', { name: 'Copy contract' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(CONTRACT);
  await expect(page.getByRole('link', { name: 'View on Pump.fun' })).toHaveAttribute('href', PUMP_URL);
  await expect(page.getByRole('link', { name: 'Follow $SANIC on X' })).toHaveAttribute('href', 'https://x.com/memesofsanic');
  await page.screenshot({
    path: isMobile ? 'test-results/sanic-fallback-mobile.png' : 'test-results/sanic-fallback.png',
    fullPage: true,
  });
});

test('publishes crawler-safe launch metadata', async ({ page, isMobile }) => {
  test.skip(isMobile, 'static metadata is viewport-independent');
  await page.goto('/?forceFallback=1');
  await expect(page).toHaveTitle('$SANIC — I Love To Go Fast');
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'https://sanic-run.vercel.app/');
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', 'https://sanic-run.vercel.app/');
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', 'https://sanic-run.vercel.app/media/sanic-og.jpg');
  await expect(page.locator('meta[property="og:image:width"]')).toHaveAttribute('content', '1200');
  await expect(page.locator('meta[property="og:image:height"]')).toHaveAttribute('content', '630');
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute('content', 'summary_large_image');
  await expect(page.locator('meta[name="twitter:site"]')).toHaveAttribute('content', '@memesofsanic');
});

test('fallback score sharing opens an encoded X intent and saves a PNG card', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'share', { configurable: true, value: undefined });
    Object.defineProperty(navigator, 'canShare', { configurable: true, value: undefined });
    const originalOpen = window.open;
    Object.defineProperty(window, '__sanicOpenedUrl', { configurable: true, writable: true, value: '' });
    window.open = ((url?: string | URL) => {
      (window as typeof window & { __sanicOpenedUrl: string }).__sanicOpenedUrl = String(url ?? '');
      return originalOpen.call(window, '', '_blank');
    }) as typeof window.open;
  });
  await beginRun(page);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await expect(page.getByRole('button', { name: 'SHARE SCORE' })).toBeEnabled();
  await page.getByRole('button', { name: 'SHARE SCORE' }).click();
  const opened = await page.evaluate(() => (window as typeof window & { __sanicOpenedUrl: string }).__sanicOpenedUrl);
  const url = new URL(opened);
  expect(`${url.origin}${url.pathname}`).toBe('https://twitter.com/intent/tweet');
  expect(url.searchParams.get('text')).toMatch(/^I scored \d+ in \$SANIC\. I love to go fast\.$/);
  expect(url.searchParams.get('url')).toBe(`${new URL(page.url()).origin}/`);
  const save = page.getByRole('link', { name: 'SAVE SCORE CARD' });
  await expect(save).toBeVisible();
  await expect(save).toHaveAttribute('download', /sanic-score-\d+\.png/);
  expect((await save.getAttribute('href'))?.startsWith('blob:')).toBe(true);
});

test('native score sharing attaches a nonempty PNG with exact safe copy', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, '__sanicSharePayload', {
      configurable: true,
      writable: true,
      value: null,
    });
    Object.defineProperty(navigator, 'canShare', {
      configurable: true,
      value: (data: ShareData) => Boolean(data.files?.[0]?.type === 'image/png'),
    });
    Object.defineProperty(navigator, 'share', {
      configurable: true,
      value: async (data: ShareData) => {
        const file = data.files?.[0];
        (window as typeof window & { __sanicSharePayload: unknown }).__sanicSharePayload = {
          name: file?.name,
          size: file?.size,
          type: file?.type,
          text: data.text,
          url: data.url,
        };
      },
    });
  });
  await beginRun(page);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await page.getByRole('button', { name: 'SHARE SCORE' }).click();
  await expect.poll(async () => page.evaluate(() => (
    window as typeof window & { __sanicSharePayload: {
      readonly name?: string;
      readonly size?: number;
      readonly type?: string;
      readonly text?: string;
      readonly url?: string;
    } | null }
  ).__sanicSharePayload)).not.toBeNull();
  const payload = await page.evaluate(() => (
    window as typeof window & { __sanicSharePayload: {
      readonly name?: string;
      readonly size?: number;
      readonly type?: string;
      readonly text?: string;
      readonly url?: string;
    } }
  ).__sanicSharePayload);
  expect(payload.type).toBe('image/png');
  expect(payload.size).toBeGreaterThan(0);
  expect(payload.name).toMatch(/^sanic-score-\d+\.png$/);
  expect(payload.text).toMatch(/^I scored \d+ in \$SANIC\. I love to go fast\.$/);
  expect(payload.url).toBe(`${new URL(page.url()).origin}/`);
});

test('touch swipe changes lane and the pause dialog stays inside the viewport', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'mobile project only');
  await beginRun(page);
  await touchSwipe(page, { x: 260, y: 500 }, { x: 150, y: 500 });
  await expect(page.locator('#app-ui')).toHaveAttribute('data-player-lane', '-1');
  await touchSwipe(page, { x: 195, y: 680 }, { x: 195, y: 520 });
  await expect(page.locator('#app-ui')).toHaveAttribute('data-player-airborne', 'true');
  await page.getByRole('button', { name: 'Pause' }).click();
  const dialog = page.getByRole('dialog', { name: 'Paused' });
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  expect(box!.y + box!.height).toBeLessThanOrEqual(844);
});

test('short landscape keeps launch and pause legal controls scrollable', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'mobile landscape regression');
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/?seed=7&e2e=1');
  const intro = page.locator('[data-view="intro"]');
  await expect(intro.getByRole('button', { name: 'Copy contract' })).toBeVisible();
  await expect(intro.getByRole('link', { name: 'View on Pump.fun' })).toBeVisible();
  await expect(intro.getByRole('link', { name: 'Follow $SANIC on X' })).toBeVisible();
  const introDisclosure = intro.getByText('MEME COIN DISCLOSURE', { exact: true });
  await introDisclosure.scrollIntoViewIfNeeded();
  await introDisclosure.click();
  const introLegal = intro.getByText(/No utility, no promises, no financial advice/);
  await introLegal.scrollIntoViewIfNeeded();
  await expect(introLegal).toBeVisible();
  await intro.getByRole('button', { name: 'GOTTA GO FAST' }).click();
  await page.getByRole('button', { name: 'Pause' }).click();
  const dialog = page.getByRole('dialog', { name: 'Paused' });
  for (const control of [
    dialog.getByRole('button', { name: 'Copy contract' }),
    dialog.getByRole('link', { name: 'View on Pump.fun' }),
    dialog.getByRole('link', { name: 'Follow $SANIC on X' }),
    dialog.getByText(/No utility, no promises, no financial advice/),
  ]) {
    await control.scrollIntoViewIfNeeded();
    await expect(control).toBeVisible();
  }
});

test('WebGL context loss gates resume until the context is restored', async ({ page, isMobile }) => {
  test.skip(isMobile, 'context lifecycle is viewport-independent');
  await beginRun(page);
  await page.locator('#game-canvas').dispatchEvent('webglcontextlost');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'paused');
  const contextMessage = page.getByRole('alert');
  await expect(contextMessage).toBeVisible();
  await expect(contextMessage).toHaveText('SANIC HIT A DIMENSIONAL WALL');
  const contextBox = await contextMessage.boundingBox();
  expect(contextBox?.width).toBeGreaterThanOrEqual(240);
  expect(contextBox?.height).toBeGreaterThanOrEqual(44);
  await expect(page.getByRole('button', { name: 'Resume' })).toBeDisabled();
  await page.keyboard.press('Escape');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'paused');
  await page.locator('#game-canvas').dispatchEvent('webglcontextrestored');
  await expect(page.getByRole('button', { name: 'Resume' })).toBeEnabled();
  await page.getByRole('button', { name: 'Resume' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
});
