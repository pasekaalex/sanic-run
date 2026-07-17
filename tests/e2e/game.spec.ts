import { expect, test, type Locator, type Page } from '@playwright/test';

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

const expectReachableInViewport = async (
  locator: Locator,
  viewport: Readonly<{ width: number; height: number }>,
): Promise<void> => {
  await locator.evaluate((element) => element.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
};

const expectInitiallyHorizontallyBounded = async (locator: Locator, viewportWidth: number): Promise<void> => {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewportWidth);
};

const expectPortraitIntroReachable = async (
  page: Page,
  viewport: Readonly<{ width: number; height: number }>,
): Promise<void> => {
  await page.setViewportSize(viewport);
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);

  const intro = page.locator('[data-view="intro"]');
  for (const locator of [
    intro.locator('[data-stage-marquee]'),
    intro.locator('[data-title-lockup]'),
    intro.locator('[data-meme-ticker]'),
    intro.getByRole('button', { name: 'PRESS START' }),
  ]) {
    await expectInitiallyHorizontallyBounded(locator, viewport.width);
  }

  for (const locator of [
    intro.locator('[data-service-deck] .contract code'),
    intro.getByRole('button', { name: 'Copy contract' }),
    intro.getByRole('link', { name: 'View on Pump.fun' }),
    intro.getByRole('link', { name: 'Follow $SANIC on X' }),
    intro.getByText('MEME COIN DISCLOSURE', { exact: true }),
  ]) {
    await expectReachableInViewport(locator, viewport);
  }

  for (const ornament of [
    page.locator('.arcade-score-strip'),
    page.locator('.attract-stage__ridge--far'),
    page.locator('.pixel-ring--three'),
    page.locator('.pixel-ring--four'),
  ]) {
    await expect(ornament).toBeHidden();
  }
};

const beginRun = async (page: Page): Promise<void> => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.getByRole('heading', { name: '$SANIC' })).toBeVisible();
  await expect(page.getByText('SWIPE', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'PRESS START' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
};

const withHeldModels = async (
  page: Page,
  assertion: () => Promise<void>,
): Promise<void> => {
  let release = (): void => undefined;
  let releasedModel = false;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/models/*.glb', async (route) => {
    if (!releasedModel) {
      releasedModel = true;
      await route.continue();
      return;
    }
    await gate;
    await route.continue();
  });
  await page.goto('/?seed=7&e2e=1');
  try {
    await assertion();
  } finally {
    release();
  }
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

test('boots as a stage-aware cartridge screen with accessible progress', async ({ page }) => {
  await withHeldModels(page, async () => {
    const ui = page.locator('#app-ui');
    await expect(ui).toHaveAttribute('data-ui-theme', 'pixel-16');
    await expect(ui).toHaveAttribute('data-arcade-shell', 'trench-circuit-94');
    await expect(ui).toHaveAttribute('data-phase', 'loading');
    await expect(page.locator('[data-view="loading"] [data-stage-label]')).toHaveText('STAGE 01');
    const progress = page.getByRole('progressbar', { name: 'Loading STAGE 01' });
    await expect(progress).toHaveAttribute('aria-valuemin', '0');
    await expect(progress).toHaveAttribute('aria-valuemax', '100');
    await expect(page.locator('[data-loading-value]')).toHaveText('25');
    await expect(progress).toHaveAttribute('aria-valuenow', '25');
    await expect(progress).toHaveAttribute('aria-valuetext', '25% loaded');
  });
});

test('presents one selected PRESS START action and complete stage identity', async ({ page }) => {
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('[data-view="intro"] [data-stage-label]')).toHaveText('STAGE 01');
  await expect(page.locator('[data-view="intro"] [data-zone-label]')).toHaveText('TRENCH ZONE');
  await expect(page.locator('[data-view="intro"] [data-act-label]')).toHaveText('ACT 1');
  const start = page.getByRole('button', { name: 'PRESS START' });
  await expect(start).toBeVisible();
  await expect(start).toHaveAttribute('data-action', 'start');
  await expect(page.getByText('GOTTA GO FAST', { exact: true })).toBeVisible();

  await page.keyboard.press('Tab');
  await expect(start).toBeFocused();
  const focus = await start.evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, outline: style.outlineColor };
  });
  expect(contrastRatio(focus.outline, focus.background)).toBeGreaterThanOrEqual(3);
});

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
  await page.getByRole('button', { name: 'PRESS START' }).click();
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
  await expect(page.getByRole('button', { name: 'PRESS START' })).toBeVisible();

  const shell = await page.evaluate(() => {
    const style = (selector: string, pseudo?: string): CSSStyleDeclaration =>
      getComputedStyle(document.querySelector<HTMLElement>(selector)!, pseudo);
    return {
      rootRaster: style('#app-ui', '::before').backgroundImage,
      bezelChecker: style('.arcade-bezel__bottom').backgroundImage,
      bezelPointerEvents: style('[data-arcade-bezel]').pointerEvents,
      chrome: style('.stage-marquee__chrome').backgroundImage,
      checker: style('.stage-marquee__checker').backgroundImage,
      ringRadius: style('.stage-marquee__ring').borderRadius,
      titleFill: style('.title-word').backgroundImage,
      cursorAnimation: style('.arcade-menu__cursor').animationName,
      titleAnimation: style('.title-lockup').animationName,
    };
  });
  expect(shell.rootRaster).toContain('repeating-linear-gradient');
  expect(shell.bezelChecker).toContain('repeating-conic-gradient');
  expect(shell.bezelPointerEvents).toBe('none');
  expect(shell.chrome).toContain('linear-gradient');
  expect(shell.checker).toContain('repeating-conic-gradient');
  expect(shell.ringRadius).toBe('50%');
  expect(shell.titleFill).toContain('linear-gradient');
  expect(shell.cursorAnimation).not.toBe('none');
  expect(shell.titleAnimation).not.toBe('none');

  const motion = await page.evaluate(() => {
    const style = (selector: string): CSSStyleDeclaration =>
      getComputedStyle(document.querySelector<HTMLElement>(selector)!);
    return {
      stageOpacity: style('[data-attract-stage]').opacity,
      gridAnimation: style('.attract-stage__grid').animationName,
      checkerAnimation: style('.attract-stage__checker').animationName,
      ringAnimation: style('.pixel-ring').animationName,
      titleAnimation: style('.title-lockup').animationName,
      promptAnimation: style('.arcade-menu__cursor').animationName,
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
    return [1_800, 5_400, 9_000, 12_600, 16_200, 19_800].map((time) => {
      animation.currentTime = time;
      return Math.round(new DOMMatrixReadOnly(getComputedStyle(track).transform).m42 * 100) / 100;
    });
  });
  expect(reelOffsets).toEqual([0, -28, -56, -84, -112, -140]);

  await page.getByRole('button', { name: 'PRESS START' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
  await expect(attractStage).toHaveCSS('opacity', '0');
  const playingStage = await page.evaluate(() => {
    const style = (selector: string): CSSStyleDeclaration =>
      getComputedStyle(document.querySelector<HTMLElement>(selector)!);
    return {
      opacity: Number(style('[data-attract-stage]').opacity),
      visibility: style('[data-attract-stage]').visibility,
      bezelOpacity: Number(style('[data-arcade-bezel]').opacity),
      bezelVisibility: style('[data-arcade-bezel]').visibility,
      gridPlayState: style('.attract-stage__grid').animationPlayState,
      checkerPlayState: style('.attract-stage__checker').animationPlayState,
      ringPlayState: style('.pixel-ring').animationPlayState,
      titlePlayState: style('.title-lockup').animationPlayState,
      cursorPlayState: style('.arcade-menu__cursor').animationPlayState,
      marqueeCheckerPlayState: style('[data-view="intro"] .stage-marquee__checker').animationPlayState,
    };
  });
  expect(playingStage).toEqual({
    opacity: 0,
    visibility: 'hidden',
    bezelOpacity: 0,
    bezelVisibility: 'hidden',
    gridPlayState: 'paused',
    checkerPlayState: 'paused',
    ringPlayState: 'paused',
    titlePlayState: 'paused',
    cursorPlayState: 'paused',
    marqueeCheckerPlayState: 'paused',
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

test('prunes arcade ornament at 600px for the 320x568 mobile layout', async ({ page }) => {
  await page.setViewportSize({ width: 600, height: 800 });
  await page.goto('/?seed=7&e2e=1');
  for (const ornament of [
    page.locator('.arcade-score-strip'),
    page.locator('.attract-stage__ridge--far'),
    page.locator('.pixel-ring--three'),
    page.locator('.pixel-ring--four'),
  ]) {
    await expect(ornament).toBeHidden();
  }
});

test('keeps 390x844 title actions reachable in the 320x568 regression group', async ({ page }) => {
  await expectPortraitIntroReachable(page, { width: 390, height: 844 });
});

test('keeps cartridge title actions reachable at 320x568', async ({ page }) => {
  await expectPortraitIntroReachable(page, { width: 320, height: 568 });

  const compactTheme = await page.evaluate(() => ({
    titleShadow: getComputedStyle(document.querySelector('.title-word')!).textShadow,
    stageDisplay: getComputedStyle(document.querySelector('.hud__stage')!).display,
    distanceDisplay: getComputedStyle(document.querySelector('.hud__metric--distance')!).display,
    serviceWidths: [...document.querySelectorAll<HTMLElement>('[data-service-deck] > *')].map(
      (element) => ({
        child: element.getBoundingClientRect().width,
        parentContent: element.parentElement!.clientWidth -
          Number.parseFloat(getComputedStyle(element.parentElement!).paddingLeft) -
          Number.parseFloat(getComputedStyle(element.parentElement!).paddingRight),
      }),
    ),
    launchWidths: [...document.querySelectorAll<HTMLElement>('[data-service-deck] .intro-panel__links > *')].map(
      (element) => ({
        child: element.getBoundingClientRect().width,
        parent: element.parentElement!.getBoundingClientRect().width,
      }),
    ),
  }));
  expect(compactTheme.titleShadow).not.toContain('6px 6px');
  expect(compactTheme.stageDisplay).toBe('none');
  expect(compactTheme.distanceDisplay).toBe('none');
  for (const widths of compactTheme.serviceWidths) {
    expect(widths.child).toBeGreaterThanOrEqual(widths.parentContent - 1);
  }
  for (const widths of compactTheme.launchWidths) {
    expect(widths.child).toBeGreaterThanOrEqual(widths.parent - 1);
  }
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
    const title = getComputedStyle(document.querySelector('.title-lockup')!);
    const prompt = getComputedStyle(document.querySelector('.arcade-menu__cursor')!);
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
  expect(await page.locator('#app-ui').evaluate((ui) =>
    ui.getAnimations({ subtree: true }).filter((animation) => animation.playState === 'running').length
  )).toBe(0);
  await expect(page.locator('.arcade-menu__cursor')).toBeVisible();
  await expect(page.getByRole('button', { name: 'PRESS START' })).toBeVisible();
});

test('renders a cartridge HUD as one opaque stage strip', async ({ page }) => {
  await beginRun(page);

  const stage = page.locator('.hud > [data-hud-stage]:first-child');
  await expect(stage).toHaveText(/P1\s+TRENCH ZONE\s+ACT 1/);
  await expect(stage).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('.hud__metric')).toHaveCount(4);
  await expect(page.locator('.hud__actions .hud-button')).toHaveCount(2);

  const strip = await page.locator('.hud').evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      backgroundImage: style.backgroundImage,
      borderColor: style.borderTopColor,
      boxShadow: style.boxShadow,
    };
  });
  expect(strip.backgroundImage).toContain('linear-gradient');
  expect(strip.borderColor).toBe('rgb(255, 244, 208)');
  expect(strip.boxShadow).not.toBe('none');
});

test('keeps 700px cartridge HUD actions inside the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 700 });
  await beginRun(page);

  const actionBoxes = await page.locator('.hud__actions .hud-button').evaluateAll((buttons) =>
    buttons.map((button) => {
      const { left, right, width, height } = button.getBoundingClientRect();
      return { left, right, width, height };
    }),
  );
  for (const box of actionBoxes) {
    expect(box.left).toBeGreaterThanOrEqual(0);
    expect(box.right).toBeLessThanOrEqual(700);
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
  await expect(page.locator('[data-hud-stage]')).toBeHidden();
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
  await expect(page.getByRole('dialog', { name: 'PAUSED' })).toBeVisible();
  await expect(page.locator('.pause-dialog [data-stage-label]')).toHaveText('STAGE 01');
  const resume = page.getByRole('button', { name: /^resume$/i });
  await expect(resume).toBeFocused();
  await expect(page.locator('#game-canvas')).toHaveAttribute('data-presentation', 'character');
  await expect(page.locator('#game-canvas')).toHaveAttribute('data-game-phase', 'paused');
  const pausedTheme = await page.evaluate(() => {
    const animationSelectors = [
      '.attract-stage__grid',
      '.attract-stage__checker',
      '.pixel-ring',
      '.title-lockup',
      '.arcade-menu__cursor',
      '.meme-reel__track',
      '[data-view="intro"] .stage-marquee__checker',
      '[data-view="intro"] .stage-marquee__ring',
    ];
    return {
      headingColor: getComputedStyle(document.querySelector('.pause-dialog h2')!).color,
      selectionColor: getComputedStyle(document.querySelector('[data-action="resume"]')!).backgroundColor,
      attractPlayStates: animationSelectors.map((selector) =>
        getComputedStyle(document.querySelector(selector)!).animationPlayState),
    };
  });
  await resume.click();
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-player-lane', '-1');
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await expect(page.getByRole('dialog', { name: 'GAME OVER' })).toBeVisible();
  await expect(page.locator('.results-dialog [data-stage-label]')).toHaveText('STAGE 01');
  const restart = page.getByRole('button', { name: /^run it back$/i });
  await expect(restart).toBeFocused();

  const resultsTheme = await page.evaluate(() => {
    const grid = document.querySelector<HTMLElement>('.results-grid')!;
    const rows = [...grid.querySelectorAll<HTMLElement>(':scope > div')];
    const animationSelectors = [
      '.attract-stage__grid',
      '.attract-stage__checker',
      '.pixel-ring',
      '.title-lockup',
      '.arcade-menu__cursor',
      '.meme-reel__track',
      '[data-view="intro"] .stage-marquee__checker',
      '[data-view="intro"] .stage-marquee__ring',
    ];
    return {
      headingColor: getComputedStyle(document.querySelector('.results-dialog h2')!).color,
      selectionColor: getComputedStyle(document.querySelector('[data-action="restart"]')!).backgroundColor,
      gridBackground: getComputedStyle(grid).backgroundColor,
      nonFirstBorderLeftWidths: rows.slice(1).map((row) => getComputedStyle(row).borderLeftWidth),
      rowShadows: rows.map((row) => getComputedStyle(row).boxShadow),
      attractPlayStates: animationSelectors.map((selector) =>
        getComputedStyle(document.querySelector(selector)!).animationPlayState),
    };
  });

  expect(resultsTheme.gridBackground).toBe('rgb(7, 9, 43)');
  expect(resultsTheme.nonFirstBorderLeftWidths).toEqual(['0px', '0px', '0px']);
  expect(resultsTheme.rowShadows).toEqual(['none', 'none', 'none', 'none']);
  expect(pausedTheme.headingColor).toBe('rgb(98, 234, 219)');
  expect(resultsTheme.headingColor).toBe('rgb(237, 75, 79)');
  expect(pausedTheme.selectionColor).toBe('rgb(255, 212, 59)');
  expect(resultsTheme.selectionColor).toBe('rgb(255, 212, 59)');
  expect(pausedTheme.attractPlayStates).toEqual(Array(8).fill('paused'));
  expect(resultsTheme.attractPlayStates).toEqual(Array(8).fill('paused'));

  await restart.click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
});

test('keeps the coral GAME OVER heading large enough on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await beginRun(page);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  await expect(page.getByRole('dialog', { name: 'GAME OVER' })).toBeVisible();

  const heading = await page.locator('.results-dialog h2').evaluate((element) => {
    const style = getComputedStyle(element);
    const panel = getComputedStyle(element.closest('.dialog-card')!);
    return {
      color: style.color,
      background: panel.backgroundColor,
      fontSize: Number.parseFloat(style.fontSize),
    };
  });
  expect(heading.color).toBe('rgb(237, 75, 79)');
  expect(heading.fontSize).toBeGreaterThanOrEqual(24);
  expect(contrastRatio(heading.color, heading.background)).toBeGreaterThanOrEqual(3);
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
  const dialog = page.getByRole('dialog', { name: 'PAUSED' });
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  expect(box!.y + box!.height).toBeLessThanOrEqual(844);
});

test('short landscape keeps launch and legal controls scrollable', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'mobile landscape regression');
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/?seed=7&e2e=1');
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'intro');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(844);

  for (const ornament of [
    page.locator('.title-subtitle'),
    page.locator('.arcade-score-strip'),
    page.locator('.attract-stage__ridge--far'),
    page.locator('.pixel-ring--two'),
    page.locator('.pixel-ring--three'),
    page.locator('.pixel-ring--four'),
  ]) {
    await expect(ornament).toBeHidden();
  }

  const intro = page.locator('[data-view="intro"]');
  const introDisclosure = intro.getByText('MEME COIN DISCLOSURE', { exact: true });
  for (const control of [
    intro.locator('[data-stage-marquee]'),
    intro.getByRole('button', { name: 'PRESS START' }),
    intro.locator('[data-service-deck] .contract code'),
    intro.getByRole('button', { name: 'Copy contract' }),
    intro.getByRole('link', { name: 'View on Pump.fun' }),
    intro.getByRole('link', { name: 'Follow $SANIC on X' }),
    introDisclosure,
  ]) {
    await expectReachableInViewport(control, { width: 844, height: 390 });
  }

  await introDisclosure.click();
  const introLegal = intro.getByText(/No utility, no promises, no financial advice/);
  await expectReachableInViewport(introLegal, { width: 844, height: 390 });
});

test('short landscape keeps play and pause controls scrollable', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'mobile landscape regression');
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/?seed=7&e2e=1');
  await page.getByRole('button', { name: 'PRESS START' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');

  for (const control of [
    page.getByRole('button', { name: 'Mute sound' }),
    page.getByRole('button', { name: 'Pause' }),
  ]) {
    await expect(control).toBeVisible();
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(844);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height).toBeLessThanOrEqual(390);
  }

  await page.getByRole('button', { name: 'Pause' }).click();
  const dialog = page.getByRole('dialog', { name: 'PAUSED' });
  for (const control of [
    dialog.getByRole('button', { name: /^resume$/i }),
    dialog.locator('.contract code'),
    dialog.getByRole('button', { name: 'Copy contract' }),
    dialog.getByRole('link', { name: 'View on Pump.fun' }),
    dialog.getByRole('link', { name: 'Follow $SANIC on X' }),
    dialog.getByText(/No utility, no promises, no financial advice/),
  ]) {
    await expectReachableInViewport(control, { width: 844, height: 390 });
  }
});

test('short landscape keeps restart and share controls scrollable', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'mobile landscape regression');
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/?seed=7&e2e=1');
  await page.getByRole('button', { name: 'PRESS START' }).click();
  await expect(page.locator('#app-ui')).toHaveAttribute('data-phase', 'playing');
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('sanic:e2e-crash')));
  const results = page.getByRole('dialog', { name: 'GAME OVER' });
  for (const control of [
    results.locator('[data-action="restart"]'),
    results.locator('[data-action="share"]'),
  ]) {
    await expectReachableInViewport(control, { width: 844, height: 390 });
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(844);
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
