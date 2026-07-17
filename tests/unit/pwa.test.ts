import { afterEach, describe, expect, it, vi } from 'vitest';

const loadPwaModule = async () => import('../../src/platform/pwa');

const installServiceWorkerRegistrar = (
  register: ReturnType<typeof vi.fn>,
  overrides: Readonly<Record<string, unknown>> = {},
): void => {
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { register, ...overrides },
  });
};

afterEach(() => {
  Reflect.deleteProperty(navigator, 'serviceWorker');
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.resetModules();
});

describe('PWA registration gate', () => {
  it.each(['development', 'e2e', 'test'])(
    'never schedules registration in %s mode',
    async (mode) => {
      const register = vi.fn();
      installServiceWorkerRegistrar(register);
      const { registerPwaAfterLoad } = await loadPwaModule();

      registerPwaAfterLoad(mode, Promise.resolve(true));
      await Promise.resolve();
      window.dispatchEvent(new Event('load'));
      await Promise.resolve();

      expect(register).not.toHaveBeenCalled();
    },
  );

  it('waits until window load without blocking registration on game initialization', async () => {
    const registration = {} as ServiceWorkerRegistration;
    const register = vi.fn().mockResolvedValue(registration);
    installServiceWorkerRegistrar(register);
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const { registerPwaAfterLoad } = await loadPwaModule();
    let markInitialized: ((success: boolean) => void) | undefined;
    const initialization = new Promise<boolean>((resolve) => {
      markInitialized = resolve;
    });

    registerPwaAfterLoad('production', initialization);
    expect(register).not.toHaveBeenCalled();

    window.dispatchEvent(new Event('load'));
    await vi.waitFor(() => expect(register).toHaveBeenCalledOnce());
    expect(register).toHaveBeenCalledWith('/sw.js', {
      scope: '/',
      updateViaCache: 'none',
    });

    markInitialized!(true);
    await Promise.resolve();
  });

  it('defers registration to a task when the load event already fired', async () => {
    vi.useFakeTimers();
    const register = vi.fn().mockResolvedValue({} as ServiceWorkerRegistration);
    installServiceWorkerRegistrar(register);
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    const { registerPwaAfterLoad } = await loadPwaModule();

    registerPwaAfterLoad('production', Promise.resolve(true));
    await Promise.resolve();
    expect(register).not.toHaveBeenCalled();

    await vi.runAllTimersAsync();
    expect(register).toHaveBeenCalledOnce();
  });

  it('registers the app shell but does not warm runtime assets when intro is unavailable', async () => {
    vi.useFakeTimers();
    const postMessage = vi.fn();
    const registration = {
      active: { postMessage },
    } as unknown as ServiceWorkerRegistration;
    const register = vi.fn().mockResolvedValue(registration);
    installServiceWorkerRegistrar(register, {
      ready: Promise.resolve(registration),
    });
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    const { registerPwaAfterLoad } = await loadPwaModule();

    registerPwaAfterLoad('production', Promise.resolve(false));
    await Promise.resolve();
    await vi.runAllTimersAsync();

    expect(register).toHaveBeenCalledOnce();
    expect(postMessage).not.toHaveBeenCalled();
  });

  it('warms core runtime assets through the active worker after readiness', async () => {
    const postMessage = vi.fn();
    const active = { postMessage };
    const registration = { active } as unknown as ServiceWorkerRegistration;
    const register = vi.fn().mockResolvedValue(registration);
    installServiceWorkerRegistrar(register, {
      controller: null,
      ready: Promise.resolve(registration),
    });
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const { registerPwaAfterLoad } = await loadPwaModule();

    registerPwaAfterLoad('production', Promise.resolve(true));
    await Promise.resolve();
    window.dispatchEvent(new Event('load'));
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    await vi.waitFor(() => expect(postMessage).toHaveBeenCalledOnce());
    expect(postMessage).toHaveBeenCalledWith({ type: 'WARM_RUNTIME' });
  });
});

describe('fail-soft idempotent registration', () => {
  it('returns null when service workers are unavailable', async () => {
    const { registerPwa } = await loadPwaModule();

    await expect(registerPwa('production')).resolves.toBeNull();
  });

  it('shares one registration attempt across repeated calls', async () => {
    const registration = {} as ServiceWorkerRegistration;
    const register = vi.fn().mockResolvedValue(registration);
    installServiceWorkerRegistrar(register);
    const { registerPwa } = await loadPwaModule();

    const first = registerPwa('production');
    const second = registerPwa('production');

    expect(first).toBe(second);
    await expect(first).resolves.toBe(registration);
    expect(register).toHaveBeenCalledOnce();
  });

  it('absorbs registration rejection without an unhandled app failure', async () => {
    const register = vi.fn().mockRejectedValue(new Error('registration denied'));
    installServiceWorkerRegistrar(register);
    const { registerPwa } = await loadPwaModule();

    await expect(registerPwa('production')).resolves.toBeNull();
  });
});
