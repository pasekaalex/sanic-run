import { runInNewContext } from 'node:vm';
import { describe, expect, it, vi } from 'vitest';
import {
  createCacheVersion,
  createServiceWorkerSource,
  createVersionedServiceWorker,
  immutableAssetUrls,
  type ServiceWorkerBuildFile,
} from '../../build/pwaServiceWorker';

type WorkerEventHandler = (event: Record<string, unknown>) => void;

interface CacheDouble {
  readonly add: ReturnType<typeof vi.fn>;
  readonly addAll: ReturnType<typeof vi.fn>;
  readonly match: ReturnType<typeof vi.fn>;
  readonly put: ReturnType<typeof vi.fn>;
}

interface WorkerHarness {
  readonly assetCache: CacheDouble;
  readonly cacheStorage: {
    readonly delete: ReturnType<typeof vi.fn>;
    readonly keys: ReturnType<typeof vi.fn>;
    readonly match: ReturnType<typeof vi.fn>;
    readonly open: ReturnType<typeof vi.fn>;
  };
  readonly fetch: ReturnType<typeof vi.fn>;
  readonly handlers: ReadonlyMap<string, WorkerEventHandler>;
  readonly runtimeCache: CacheDouble;
  readonly shellCache: CacheDouble;
  readonly claim: ReturnType<typeof vi.fn>;
  readonly skipWaiting: ReturnType<typeof vi.fn>;
}

const createCacheDouble = (): CacheDouble => ({
  add: vi.fn().mockResolvedValue(undefined),
  addAll: vi.fn().mockResolvedValue(undefined),
  match: vi.fn().mockResolvedValue(undefined),
  put: vi.fn().mockResolvedValue(undefined),
});

const compileWorker = (
  source: string,
  cacheKeys: readonly string[] = [],
): WorkerHarness => {
  const handlers = new Map<string, WorkerEventHandler>();
  const shellCache = createCacheDouble();
  const assetCache = createCacheDouble();
  const runtimeCache = createCacheDouble();
  const claim = vi.fn().mockResolvedValue(undefined);
  const skipWaiting = vi.fn().mockResolvedValue(undefined);
  const cacheStorage = {
    delete: vi.fn().mockResolvedValue(true),
    keys: vi.fn().mockResolvedValue([...cacheKeys]),
    match: vi.fn().mockResolvedValue(undefined),
    open: vi.fn(async (name: string) => {
      if (name.startsWith('sanic-shell-')) return shellCache;
      if (name.startsWith('sanic-assets-')) return assetCache;
      return runtimeCache;
    }),
  };
  const fetch = vi.fn();

  class RequestDouble {
    public readonly url: string;
    public readonly cache?: string;

    public constructor(url: string, init?: { readonly cache?: string }) {
      this.url = url;
      this.cache = init?.cache;
    }
  }

  runInNewContext(source, {
    Promise,
    Request: RequestDouble,
    Response: { error: () => ({ type: 'error' }) },
    URL,
    caches: cacheStorage,
    fetch,
    self: {
      addEventListener: (type: string, handler: WorkerEventHandler) => {
        handlers.set(type, handler);
      },
      clients: { claim },
      location: { origin: 'https://www.sanic.fun' },
      skipWaiting,
    },
  });

  return {
    assetCache,
    cacheStorage,
    claim,
    fetch,
    handlers,
    runtimeCache,
    shellCache,
    skipWaiting,
  };
};

const triggerWaitUntil = async (
  handler: WorkerEventHandler | undefined,
): Promise<void> => {
  expect(handler).toBeDefined();
  let work: Promise<unknown> | undefined;
  handler!({
    waitUntil: (promise: Promise<unknown>) => {
      work = promise;
    },
  });
  expect(work).toBeDefined();
  await work;
};

const triggerFetch = async (
  handler: WorkerEventHandler | undefined,
  request: Readonly<{
    destination?: string;
    method: string;
    mode?: string;
    url: string;
  }>,
): Promise<unknown> => {
  expect(handler).toBeDefined();
  let response: Promise<unknown> | undefined;
  handler!({
    request,
    respondWith: (promise: Promise<unknown>) => {
      response = promise;
    },
  });
  expect(response).toBeDefined();
  return response;
};

describe('service-worker bundle fingerprint', () => {
  const files: readonly ServiceWorkerBuildFile[] = [
    { fileName: 'assets/index-a1b2c3d4.js', contents: 'console.log("a")' },
    { fileName: 'index.html', contents: '<main>SANIC</main>' },
  ];

  it('is deterministic across bundle enumeration order', () => {
    expect(createCacheVersion(files)).toBe(createCacheVersion([...files].reverse()));
    expect(createCacheVersion(files)).toMatch(/^[a-f0-9]{16}$/);
  });

  it('changes whenever emitted app-shell bytes change', () => {
    const changed = [
      files[0]!,
      { fileName: 'index.html', contents: '<main>SANIC V2</main>' },
    ];
    expect(createCacheVersion(changed)).not.toBe(createCacheVersion(files));
  });

  it('changes whenever a stable-path runtime asset changes', () => {
    const first = createVersionedServiceWorker({
      buildFiles: [
        ...files,
        { fileName: 'models/sanic-runner.glb', contents: 'runner-v3' },
      ],
      immutableAssets: ['/assets/index-a1b2c3d4.js'],
      runtimeWarmUrls: ['/models/sanic-runner.glb'],
    });
    const changed = createVersionedServiceWorker({
      buildFiles: [
        ...files,
        { fileName: 'models/sanic-runner.glb', contents: 'runner-v4' },
      ],
      immutableAssets: ['/assets/index-a1b2c3d4.js'],
      runtimeWarmUrls: ['/models/sanic-runner.glb'],
    });

    expect(changed.version).not.toBe(first.version);
    expect(changed.source).not.toBe(first.source);
  });

  it('selects only immutable Vite assets for precaching', () => {
    expect(immutableAssetUrls([
      'models/sanic-runner.glb',
      'assets/index-a1b2c3d4.js',
      'media/sanic-og.jpg',
      'assets/index-e5f6g7h8.css',
      'music/ringwood-rush.mp3',
      'assets/index-a1b2c3d4.js',
      'index.html',
    ])).toEqual([
      '/assets/index-a1b2c3d4.js',
      '/assets/index-e5f6g7h8.css',
    ]);
  });

  it('includes service-worker policy and warm-list changes in the cache version', () => {
    const first = createVersionedServiceWorker({
      buildFiles: files,
      immutableAssets: ['/assets/index-a1b2c3d4.js'],
      runtimeWarmUrls: ['/models/sanic-runner.glb'],
    });
    const changed = createVersionedServiceWorker({
      buildFiles: files,
      immutableAssets: ['/assets/index-a1b2c3d4.js'],
      runtimeWarmUrls: [
        '/models/sanic-runner.glb',
        '/music/ringwood-rush.mp3',
      ],
    });

    expect(first.version).not.toBe(changed.version);
    expect(first.source).toContain(`const CACHE_VERSION = "${first.version}";`);
  });
});

describe('generated service-worker lifecycle', () => {
  const source = createServiceWorkerSource({
    immutableAssets: [
      '/assets/index-a1b2c3d4.js',
      '/assets/index-e5f6g7h8.css',
    ],
    runtimeWarmUrls: [
      '/models/sanic-runner.glb',
      '/media/sanic-score-card-bg.png',
      '/music/ringwood-rush.mp3',
    ],
    version: '1234abcd5678ef90',
  });

  it('precaches the app shell without putting large runtime media in install', async () => {
    const worker = compileWorker(source);

    await triggerWaitUntil(worker.handlers.get('install'));

    expect(worker.shellCache.addAll).toHaveBeenCalledOnce();
    const addedUrls = (
      worker.shellCache.addAll.mock.calls[0]?.[0] as readonly {
        readonly url: string;
      }[]
    ).map(({ url }) => url);
    expect(addedUrls).toContain('/index.html');
    expect(addedUrls).toContain('/manifest.webmanifest');
    expect(addedUrls).toContain('/assets/index-a1b2c3d4.js');
    expect(addedUrls).not.toContain('/models/sanic-runner.glb');
    expect(addedUrls.some((url) => (
      url.startsWith('/models/')
      || url.startsWith('/media/')
      || url.startsWith('/music/')
    ))).toBe(false);
    expect(worker.skipWaiting).toHaveBeenCalledOnce();
  });

  it('rejects installation atomically and keeps the incumbent worker when any shell asset fails', async () => {
    const worker = compileWorker(source);
    worker.shellCache.addAll.mockRejectedValue(new TypeError('asset unavailable'));

    await expect(
      triggerWaitUntil(worker.handlers.get('install')),
    ).rejects.toThrow('asset unavailable');

    expect(worker.skipWaiting).not.toHaveBeenCalled();
  });

  it('deletes only superseded SANIC caches and claims clients', async () => {
    const worker = compileWorker(source, [
      'sanic-shell-old',
      'sanic-runtime-old',
      'sanic-shell-1234abcd5678ef90',
      'sanic-assets-1234abcd5678ef90',
      'sanic-runtime-1234abcd5678ef90',
      'another-app-cache',
    ]);

    await triggerWaitUntil(worker.handlers.get('activate'));

    expect(worker.cacheStorage.delete.mock.calls.map(([name]) => name)).toEqual([
      'sanic-shell-old',
      'sanic-runtime-old',
    ]);
    expect(worker.claim).toHaveBeenCalledOnce();
  });
});

describe('generated service-worker fetch policies', () => {
  const source = createServiceWorkerSource({
    immutableAssets: ['/assets/index-a1b2c3d4.js'],
    runtimeWarmUrls: [
      '/models/sanic-runner.glb',
      '/media/sanic-score-card-bg.png',
      '/music/ringwood-rush.mp3',
    ],
    version: '1234abcd5678ef90',
  });

  it('serves immutable hashed assets cache-first', async () => {
    const worker = compileWorker(source);
    const cached = { body: 'cached' };
    worker.cacheStorage.match.mockResolvedValue(cached);

    await expect(triggerFetch(worker.handlers.get('fetch'), {
      destination: 'script',
      method: 'GET',
      mode: 'cors',
      url: 'https://www.sanic.fun/assets/index-a1b2c3d4.js',
    })).resolves.toBe(cached);

    expect(worker.fetch).not.toHaveBeenCalled();
  });

  it('uses network-first navigation with the cached app shell as fallback', async () => {
    const worker = compileWorker(source);
    const shell = { body: 'offline shell' };
    worker.fetch.mockRejectedValue(new TypeError('offline'));
    worker.shellCache.match.mockResolvedValue(shell);

    await expect(triggerFetch(worker.handlers.get('fetch'), {
      method: 'GET',
      mode: 'navigate',
      url: 'https://www.sanic.fun/',
    })).resolves.toBe(shell);

    expect(worker.fetch).toHaveBeenCalledOnce();
    expect(worker.shellCache.match).toHaveBeenCalledWith('/index.html');
  });

  it.each([
    '/models/sanic-runner.glb',
    '/media/sanic-og.jpg',
    '/music/ringwood-rush.mp3',
  ])('runtime-caches successful same-origin stable media: %s', async (pathname) => {
    const worker = compileWorker(source);
    const response = {
      clone: vi.fn().mockReturnValue({ cloned: pathname }),
      ok: true,
      type: 'basic',
    };
    worker.fetch.mockResolvedValue(response);
    const request = {
      destination: '',
      method: 'GET',
      mode: 'cors',
      url: `https://www.sanic.fun${pathname}`,
    };

    await expect(triggerFetch(worker.handlers.get('fetch'), request)).resolves.toBe(response);

    expect(worker.runtimeCache.put).toHaveBeenCalledOnce();
    expect(worker.runtimeCache.put).toHaveBeenCalledWith(request, { cloned: pathname });
  });

  it('does not intercept cross-origin, non-GET, or unrelated requests', () => {
    const worker = compileWorker(source);
    const handler = worker.handlers.get('fetch');
    expect(handler).toBeDefined();
    const respondWith = vi.fn();

    for (const request of [
      {
        method: 'GET',
        mode: 'cors',
        url: 'https://cdn.example.com/media/sanic-og.jpg',
      },
      {
        method: 'POST',
        mode: 'cors',
        url: 'https://www.sanic.fun/media/sanic-og.jpg',
      },
      {
        method: 'GET',
        mode: 'cors',
        url: 'https://www.sanic.fun/api/score',
      },
    ]) {
      handler!({ request, respondWith });
    }

    expect(respondWith).not.toHaveBeenCalled();
  });
});

describe('generated first-install runtime warming', () => {
  const source = createServiceWorkerSource({
    immutableAssets: ['/assets/index-a1b2c3d4.js'],
    runtimeWarmUrls: [
      '/models/sanic-runner.glb',
      '/media/sanic-score-card-bg.png',
      '/music/ringwood-rush.mp3',
    ],
    version: '1234abcd5678ef90',
  });

  it('ignores every message except the exact warm command', () => {
    const worker = compileWorker(source);
    const handler = worker.handlers.get('message');
    expect(handler).toBeDefined();
    const waitUntil = vi.fn();

    for (const data of [
      undefined,
      null,
      {},
      { type: 'WARM_RUNTIME_ASSETS' },
      { type: 'WARM_RUNTIME', urls: ['https://evil.example/payload'] },
    ]) {
      handler!({ data, waitUntil });
    }

    expect(waitUntil).toHaveBeenCalledOnce();
  });

  it('keeps warming after one fetch fails and caches every successful response', async () => {
    const worker = compileWorker(source);
    const success = {
      ok: true,
      type: 'basic',
    };
    worker.fetch.mockImplementation(async (request: { readonly url: string }) => {
      if (request.url === 'https://www.sanic.fun/models/sanic-runner.glb') {
        throw new TypeError('model temporarily unavailable');
      }
      return success;
    });
    const handler = worker.handlers.get('message');
    expect(handler).toBeDefined();
    let work: Promise<unknown> | undefined;

    handler!({
      data: { type: 'WARM_RUNTIME' },
      waitUntil: (promise: Promise<unknown>) => {
        work = promise;
      },
    });
    expect(work).toBeDefined();
    await expect(work).resolves.toBeUndefined();

    expect(worker.fetch).toHaveBeenCalledTimes(3);
    expect(worker.runtimeCache.put).toHaveBeenCalledTimes(2);
    expect(worker.runtimeCache.put.mock.calls.map(
      ([request]) => (request as { readonly url: string }).url,
    )).toEqual([
      'https://www.sanic.fun/media/sanic-score-card-bg.png',
      'https://www.sanic.fun/music/ringwood-rush.mp3',
    ]);
  });

  it('skips network warming for assets already present in this release cache', async () => {
    const worker = compileWorker(source);
    worker.runtimeCache.match.mockImplementation(
      async (request: { readonly url: string }) => (
        request.url.endsWith('/models/sanic-runner.glb')
          ? { body: 'already warm' }
          : undefined
      ),
    );
    worker.fetch.mockResolvedValue({ ok: true, type: 'basic' });
    const handler = worker.handlers.get('message');
    let work: Promise<unknown> | undefined;

    handler!({
      data: { type: 'WARM_RUNTIME' },
      waitUntil: (promise: Promise<unknown>) => {
        work = promise;
      },
    });
    await work;

    expect(worker.runtimeCache.match).toHaveBeenCalledTimes(3);
    expect(worker.fetch).toHaveBeenCalledTimes(2);
    expect(worker.runtimeCache.put).toHaveBeenCalledTimes(2);
  });
});
