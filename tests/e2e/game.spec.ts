import { expect, test, type Page } from '@playwright/test';

const CONTRACT = 'CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump';
const PUMP_URL = `https://pump.fun/coin/${CONTRACT}`;

const parseCssColor = (color: string): readonly [number, number, number] => {
  const value = color.trim();
  if (/^#[0-9a-f]{6}$/i.test(value)) {
    return [1, 3, 5].map((index) => Number.parseInt(value.slice(index, index + 2), 16)) as [number, number, number];
  }
  const channels = value.match(/[\d.]+/g)?.slice(0, 3).map(Number);
  if (!channels || channels.length !== 3) throw new Error(`Unsupported CSS color: ${color}`);
  return channels as [number, number, number];
};

const contrastRatio = (foreground: string, background: string): number => {
  const luminance = (color: string): number => {
    const normalize = (channel: number): number => {
      const value = channel / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    };
    const [red, green, blue] = parseCssColor(color);
    return 0.2126 * normalize(red) + 0.7152 * normalize(green) + 0.0722 * normalize(blue);
  };
  const foregroundLuminance = luminance(foreground);
  const backgroundLuminance = luminance(background);
  return (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
};

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

test('creates a melodic browser audio graph only after the Start gesture', async ({ page }) => {
  await page.addInitScript(() => {
    const probe = {
      contexts: 0,
      oscillators: [] as OscillatorNode[],
      bufferSources: [] as AudioBufferSourceNode[],
    };
    const NativeAudioContext = window.AudioContext;
    const originalCreateOscillator = NativeAudioContext.prototype.createOscillator;
    const originalCreateBufferSource = NativeAudioContext.prototype.createBufferSource;

    NativeAudioContext.prototype.createOscillator = function createOscillator(): OscillatorNode {
      const oscillator = originalCreateOscillator.call(this);
      probe.oscillators.push(oscillator);
      return oscillator;
    };
    NativeAudioContext.prototype.createBufferSource = function createBufferSource(): AudioBufferSourceNode {
      const source = originalCreateBufferSource.call(this);
      probe.bufferSources.push(source);
      return source;
    };

    const InstrumentedAudioContext = class extends NativeAudioContext {
      public constructor(options?: AudioContextOptions) {
        super(options);
        probe.contexts += 1;
      }
    };
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: InstrumentedAudioContext });
    Object.defineProperty(window, '__sanicAudioProbe', { configurable: true, value: probe });
  });

  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');
  const readProbe = () => page.evaluate(() => {
    const probe = (window as typeof window & {
      __sanicAudioProbe: {
        contexts: number;
        oscillators: OscillatorNode[];
        bufferSources: AudioBufferSourceNode[];
      };
    }).__sanicAudioProbe;
    return {
      contexts: probe.contexts,
      oscillatorTypes: probe.oscillators.map(({ type }) => type),
      bufferSources: probe.bufferSources.length,
    };
  });

  expect(await readProbe()).toEqual({ contexts: 0, oscillatorTypes: [], bufferSources: 0 });
  await page.getByRole('button', { name: 'GOTTA GO FAST' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');

  await expect.poll(readProbe).toMatchObject({ contexts: 1 });
  const probe = await readProbe();
  expect(probe.bufferSources).toBeGreaterThanOrEqual(2);
  expect(probe.oscillatorTypes.length).toBeGreaterThanOrEqual(4);
  expect(probe.oscillatorTypes).toContain('square');
  expect(probe.oscillatorTypes).toContain('triangle');
  expect(probe.oscillatorTypes).toContain('sine');
});

test('uses a pixel UI shell without pixelating the WebGL game', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  const ui = page.locator('#app-ui');
  const canvas = page.locator('#game-canvas');
  await expect(ui).toHaveAttribute('data-ui-theme', 'pixel-16');
  await expect(ui).toHaveAttribute('data-phase', 'intro');
  await expect(canvas).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  const styles = await page.evaluate(() => {
    const canvasElement = document.querySelector<HTMLCanvasElement>('#game-canvas')!;
    const canvas = getComputedStyle(canvasElement);
    const canvasRect = canvasElement.getBoundingClientRect();
    const panelStyles = [...document.querySelectorAll<HTMLElement>(
      '.loading-card, .intro-panel, .dialog-card, .unsupported-panel__content',
    )].map((panel) => {
      const style = getComputedStyle(panel);
      return { backdrop: style.backdropFilter, radius: style.borderRadius };
    });
    const buttonFonts = [...document.querySelectorAll<HTMLElement>('.primary-button, .secondary-button')].map(
      (button) => getComputedStyle(button).fontFamily,
    );
    const pixelFontLoaded = Array.from(document.fonts).some(
      (face) => face.family.replace(/^['"]|['"]$/g, '') === 'Press Start 2P' && face.status === 'loaded',
    );
    return {
      canvasImageRendering: canvas.imageRendering,
      canvasFilter: canvas.filter,
      canvasTransform: canvas.transform,
      canvasHidden: canvasElement.hidden,
      canvasRect: {
        left: canvasRect.left,
        top: canvasRect.top,
        width: canvasRect.width,
        height: canvasRect.height,
      },
      canvasBackingWidth: canvasElement.width,
      canvasBackingHeight: canvasElement.height,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      panelStyles,
      buttonFonts,
      pixelFontLoaded,
    };
  });

  expect(styles.canvasImageRendering).toBe('auto');
  expect(styles.canvasFilter).toBe('none');
  expect(styles.canvasTransform).toBe('none');
  expect(styles.canvasHidden).toBe(false);
  expect(styles.canvasRect.left).toBe(0);
  expect(styles.canvasRect.top).toBe(0);
  expect(styles.canvasRect.width).toBe(styles.viewportWidth);
  expect(styles.canvasRect.height).toBe(styles.viewportHeight);
  expect(styles.canvasBackingWidth).toBe(styles.viewportWidth);
  expect(styles.canvasBackingHeight).toBe(styles.viewportHeight);
  for (const panel of styles.panelStyles) {
    expect(panel.radius).toBe('0px');
    expect(panel.backdrop).toBe('none');
  }
  for (const font of styles.buttonFonts) expect(font).toContain('Press Start 2P');
  expect(styles.pixelFontLoaded).toBe(true);
});

test('loads every production GLB category without a silent fallback', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  const canvas = page.locator('#game-canvas');
  for (const category of ['character', 'spin-ball', 'ring', 'forest']) {
    await expect(canvas).toHaveAttribute(`data-${category}-asset`, 'glb');
  }
});

test('runs an original animated 16-bit attract mode with a meme reel', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');

  const attractStage = page.locator('[data-attract-stage]');
  await expect(attractStage).toBeVisible();
  await expect(attractStage).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('[data-meme-ticker]')).toHaveAttribute('aria-label', '$SANIC meme reel');

  const memes = [
    'ANSEM SAID ONE MORE RUN',
    'TRENCHES BUILT DIFFERENT',
    'I LOVE TO GO FAST',
    'SEND IT RESPONSIBLY',
    '0 RINGS IS A LIFESTYLE',
    'THE CHART NEEDS MORE BLUE',
  ];
  await expect(page.locator('[data-meme-line]')).toHaveText(memes);
  await expect(page.getByText('PRESS START', { exact: true })).toBeVisible();

  const motion = await page.evaluate(() => {
    const style = (selector: string): CSSStyleDeclaration =>
      getComputedStyle(document.querySelector<HTMLElement>(selector)!);
    return {
      stageOpacity: style('[data-attract-stage]').opacity,
      gridAnimation: style('.attract-stage__grid').animationName,
      checkerAnimation: style('.attract-stage__checker').animationName,
      ringAnimation: style('.pixel-ring').animationName,
      titleAnimation: style('.intro-panel h1').animationName,
      promptAnimation: style('.start-callout').animationName,
      tickerAnimation: style('.meme-reel__track').animationName,
    };
  });

  expect(Number(motion.stageOpacity)).toBeGreaterThan(0.5);
  expect(motion.gridAnimation).not.toBe('none');
  expect(motion.checkerAnimation).not.toBe('none');
  expect(motion.ringAnimation).not.toBe('none');
  expect(motion.titleAnimation).not.toBe('none');
  expect(motion.promptAnimation).not.toBe('none');
  expect(motion.tickerAnimation).not.toBe('none');

  const reelOffsets = await page.locator('.meme-reel__track').evaluate((track) => {
    const animation = track.getAnimations()[0];
    if (animation === undefined) throw new Error('Missing meme reel animation');
    animation.pause();
    return [1_200, 3_600, 6_000, 8_400, 10_800, 13_200].map((time) => {
      animation.currentTime = time;
      return Math.round(new DOMMatrixReadOnly(getComputedStyle(track).transform).m42 * 100) / 100;
    });
  });
  expect(reelOffsets).toEqual([0, -28, -56, -84, -112, -140]);

  await page.getByRole('button', { name: 'GOTTA GO FAST' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
  const playingStage = await attractStage.evaluate((element) => ({
    opacity: Number(getComputedStyle(element).opacity),
    visibility: getComputedStyle(element).visibility,
    gridPlayState: getComputedStyle(element.querySelector('.attract-stage__grid')!).animationPlayState,
    checkerPlayState: getComputedStyle(element.querySelector('.attract-stage__checker')!).animationPlayState,
    ringPlayState: getComputedStyle(element.querySelector('.pixel-ring')!).animationPlayState,
  }));
  expect(playingStage).toEqual({
    opacity: 0,
    visibility: 'hidden',
    gridPlayState: 'paused',
    checkerPlayState: 'paused',
    ringPlayState: 'paused',
  });
});

test('renders hard-edged pixel panels, counters, and controls', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');

  const styles = await page.evaluate(() => {
    const root = document.querySelector<HTMLElement>('#app-ui')!;
    const rootStyle = getComputedStyle(root);
    const panelElement = document.querySelector('[data-view="intro"]')!;
    const panel = getComputedStyle(panelElement);
    const panelDecoration = getComputedStyle(panelElement, '::before');
    const dialog = getComputedStyle(document.querySelector('.dialog-card')!);
    const contract = getComputedStyle(document.querySelector('.contract--intro')!);
    const counter = getComputedStyle(document.querySelector('.hud__metric')!);
    const button = getComputedStyle(document.querySelector('[data-action="start"]')!);
    const secondaryButton = getComputedStyle(document.querySelector('.secondary-button')!);
    const contextBanner = getComputedStyle(document.querySelector('.context-banner')!);
    const dialogHeading = getComputedStyle(document.querySelector('.dialog-card h2')!);
    const hudLabel = getComputedStyle(document.querySelector('.hud__metric small')!);
    const meterSegments = getComputedStyle(document.querySelector('.loading-meter')!, '::after');
    const speedStripes = getComputedStyle(root, '::after');
    return {
      panelShadow: panel.boxShadow,
      panelDecoration: panelDecoration.backgroundImage,
      contractRadius: contract.borderRadius,
      contractBackdrop: contract.backdropFilter,
      counterRadius: counter.borderRadius,
      counterBackdrop: counter.backdropFilter,
      buttonRadius: button.borderRadius,
      buttonBorder: button.borderTopWidth,
      buttonTiming: button.transitionTimingFunction,
      secondaryColor: secondaryButton.color,
      secondaryBrightBlue: rootStyle.getPropertyValue('--pixel-blue-hi').trim(),
      contextColor: contextBanner.color,
      contextRed: rootStyle.getPropertyValue('--pixel-red').trim(),
      dialogHeadingFont: dialogHeading.fontFamily,
      hudLabelFont: hudLabel.fontFamily,
      meterSegments: meterSegments.backgroundImage,
      speedStripes: speedStripes.backgroundImage,
      speedStripeSize: speedStripes.backgroundSize,
      speedStripeRepeat: speedStripes.backgroundRepeat,
      dialogOverflow: dialog.overflowY,
    };
  });

  const panelOffset = (page.viewportSize()?.width ?? 1440) <= 600 ? '4px 4px 0px' : '8px 8px 0px';
  expect(styles.panelShadow).toContain(panelOffset);
  expect(styles.panelDecoration).toContain('repeating-conic-gradient');
  expect(styles.contractRadius).toBe('0px');
  expect(styles.contractBackdrop).toBe('none');
  expect(styles.counterRadius).toBe('0px');
  expect(styles.counterBackdrop).toBe('none');
  expect(styles.buttonRadius).toBe('0px');
  expect(styles.buttonBorder).toBe('3px');
  expect(styles.buttonTiming).toContain('steps');
  expect(styles.dialogHeadingFont).toContain('Press Start 2P');
  expect(styles.hudLabelFont).toContain('Press Start 2P');
  expect(contrastRatio(styles.secondaryColor, styles.secondaryBrightBlue)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(styles.contextColor, styles.contextRed)).toBeGreaterThanOrEqual(4.5);
  expect(styles.meterSegments).toContain('8px');
  expect(styles.speedStripes).toContain('repeating-linear-gradient');
  expect(styles.speedStripes).toContain('0deg');
  expect(styles.speedStripeSize).toContain('48px 100%');
  expect(styles.speedStripeRepeat).toContain('no-repeat');
  expect(styles.dialogOverflow).toBe('auto');
});

test('keeps mobile pixel labels readable before reducing ornament', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?seed=7&e2e=1');
  await expect(page.getByRole('heading', { name: '$SANIC' })).toBeVisible();

  const labelSizes = await page.evaluate(() => {
    const selectors = [
      '.link-chip',
      '.contract code',
      '.hud__metric small',
      '.controls-copy',
      '.contract__label',
      '.icon-button',
      '.disclosure summary',
      '.swipe-hint',
      '.results-grid dt',
    ];
    return selectors.map((selector) => Number.parseFloat(getComputedStyle(document.querySelector(selector)!).fontSize));
  });

  for (const size of labelSizes) expect(size).toBeGreaterThanOrEqual(8.32);
});

test('disables themed transitions when reduced motion is requested', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');

  const motion = await page.evaluate(() => {
    const button = getComputedStyle(document.querySelector('[data-action="start"]')!);
    const stripes = getComputedStyle(document.querySelector('#app-ui')!, '::after');
    const grid = getComputedStyle(document.querySelector('.attract-stage__grid')!);
    const checker = getComputedStyle(document.querySelector('.attract-stage__checker')!);
    const ring = getComputedStyle(document.querySelector('.pixel-ring')!);
    const title = getComputedStyle(document.querySelector('.intro-panel h1')!);
    const prompt = getComputedStyle(document.querySelector('.start-callout')!);
    const ticker = getComputedStyle(document.querySelector('.meme-reel__track')!);
    return {
      buttonAnimation: button.animationName,
      buttonTransition: button.transitionDuration,
      stripeAnimation: stripes.animationName,
      stripeTransition: stripes.transitionDuration,
      gridAnimation: grid.animationName,
      checkerAnimation: checker.animationName,
      ringAnimation: ring.animationName,
      titleAnimation: title.animationName,
      promptAnimation: prompt.animationName,
      tickerAnimation: ticker.animationName,
    };
  });

  expect(motion).toEqual({
    buttonAnimation: 'none',
    buttonTransition: '0s',
    stripeAnimation: 'none',
    stripeTransition: '0s',
    gridAnimation: 'none',
    checkerAnimation: 'none',
    ringAnimation: 'none',
    titleAnimation: 'none',
    promptAnimation: 'none',
    tickerAnimation: 'none',
  });
});

test('keeps 390px HUD controls clear of every metric tile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await beginRun(page);

  const metrics = await page.locator('.hud__metric').evaluateAll((elements) =>
    elements.map((element) => {
      const { left, right, top, bottom } = element.getBoundingClientRect();
      return { left, right, top, bottom };
    }),
  );
  const actions = await page.locator('.hud__actions').evaluate((element) => {
    const { left, right, top, bottom } = element.getBoundingClientRect();
    return { left, right, top, bottom };
  });
  const soundControl = await page.getByRole('button', { name: 'Mute sound' }).evaluate((element) => ({
    color: getComputedStyle(element).color,
    fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
    generatedContent: getComputedStyle(element, '::after').content,
    text: element.textContent,
    width: element.getBoundingClientRect().width,
  }));

  for (const metric of metrics) {
    const overlaps =
      metric.left < actions.right && metric.right > actions.left && metric.top < actions.bottom && metric.bottom > actions.top;
    expect(overlaps).toBe(false);
  }
  expect(soundControl.text).toContain('SOUND ON');
  expect(soundControl.color).not.toBe('rgba(0, 0, 0, 0)');
  expect(soundControl.fontSize).toBeGreaterThanOrEqual(8.32);
  expect(soundControl.generatedContent).toBe('none');
  expect(soundControl.width).toBeGreaterThanOrEqual(86);
});

test('starts, responds to controls, pauses, crashes, and restarts', async ({ page }) => {
  await beginRun(page);
  await page.getByRole('button', { name: 'Mute sound' }).click();
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe('game-canvas');
  await page.evaluate(() => new Promise<void>((resolve, reject) => {
    const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas');
    const pause = document.querySelector<HTMLButtonElement>('[data-action="pause"]');
    if (canvas === null || pause === null) {
      reject(new Error('Missing game canvas or pause control'));
      return;
    }
    const timeout = window.setTimeout(() => {
      observer.disconnect();
      reject(new Error('Jump presentation never reached spin'));
    }, 5_000);
    const pauseOnSpin = (): void => {
      if (canvas.dataset.presentation !== 'spin') return;
      window.clearTimeout(timeout);
      observer.disconnect();
      pause.click();
      resolve();
    };
    const observer = new MutationObserver(pauseOnSpin);
    observer.observe(canvas, { attributes: true, attributeFilter: ['data-presentation'] });
    window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space' }));
    pauseOnSpin();
  }));
  await expect(page.getByRole('dialog', { name: 'Paused' })).toBeVisible();
  await expect(page.locator('#game-canvas')).toHaveAttribute('data-presentation', 'character');
  await expect(page.locator('#game-canvas')).toHaveAttribute('data-game-phase', 'paused');
  await page.getByRole('button', { name: 'Resume' }).click();
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-player-lane', '-1');
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
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'https://www.sanic.fun/');
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', 'https://www.sanic.fun/');
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', 'https://www.sanic.fun/media/sanic-og.jpg');
  await expect(page.locator('meta[property="og:image:width"]')).toHaveAttribute('content', '1200');
  await expect(page.locator('meta[property="og:image:height"]')).toHaveAttribute('content', '630');
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute('content', 'summary_large_image');
  await expect(page.locator('meta[name="twitter:site"]')).toHaveAttribute('content', '@memesofsanic');
  await expect(page.locator('meta[name="twitter:image"]')).toHaveAttribute('content', 'https://www.sanic.fun/media/sanic-og.jpg');
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
