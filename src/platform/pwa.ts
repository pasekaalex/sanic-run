const PRODUCTION_MODE = 'production';
const SERVICE_WORKER_URL = '/sw.js';

let registrationAttempt: Promise<ServiceWorkerRegistration | null> | null = null;
let registrationScheduled = false;

export const registerPwa = (
  mode: string,
): Promise<ServiceWorkerRegistration | null> => {
  if (
    mode !== PRODUCTION_MODE
    || typeof navigator === 'undefined'
    || !('serviceWorker' in navigator)
  ) {
    return Promise.resolve(null);
  }
  if (registrationAttempt !== null) return registrationAttempt;

  const serviceWorker = navigator.serviceWorker;
  registrationAttempt = Promise.resolve()
    .then(() => serviceWorker.register(SERVICE_WORKER_URL, {
      scope: '/',
      updateViaCache: 'none',
    }))
    .catch(() => null);
  return registrationAttempt;
};

const warmRuntimeCache = async (
  registration: ServiceWorkerRegistration,
): Promise<void> => {
  try {
    const incoming = registration.installing ?? registration.waiting ?? null;
    const worker = incoming === null
      ? registration.active ?? navigator.serviceWorker.controller
      : await new Promise<ServiceWorker | null>((resolve) => {
          const settle = (value: ServiceWorker | null): void => {
            incoming.removeEventListener('statechange', handleStateChange);
            resolve(value);
          };
          const handleStateChange = (): void => {
            if (incoming.state === 'activated') settle(incoming);
            else if (incoming.state === 'redundant') settle(null);
          };

          incoming.addEventListener('statechange', handleStateChange);
          handleStateChange();
        });
    worker?.postMessage({ type: 'WARM_RUNTIME' });
  } catch {
    // Offline support is optional and must never interrupt the game.
  }
};

export const registerPwaAfterLoad = (
  mode: string,
  initialization: Promise<boolean>,
): void => {
  if (
    mode !== PRODUCTION_MODE
    || registrationScheduled
    || typeof window === 'undefined'
    || typeof document === 'undefined'
  ) {
    return;
  }
  registrationScheduled = true;
  const initializationSucceeded = initialization.catch(() => false);

  const registerAndMaybeWarm = (): void => {
    void Promise.all([
      registerPwa(mode),
      initializationSucceeded,
    ]).then(([registration, succeeded]) => {
      if (registration === null || !succeeded) return;
      return warmRuntimeCache(registration);
    }).catch(() => undefined);
  };
  if (document.readyState === 'complete') {
    window.setTimeout(registerAndMaybeWarm, 0);
    return;
  }
  window.addEventListener('load', registerAndMaybeWarm, { once: true });
};
