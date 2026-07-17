import { createHash } from 'node:crypto';

export interface ServiceWorkerBuildFile {
  readonly fileName: string;
  readonly contents: string | Uint8Array;
}

export interface ServiceWorkerSourceOptions {
  readonly immutableAssets: readonly string[];
  readonly runtimeWarmUrls: readonly string[];
  readonly version: string;
}

export interface VersionedServiceWorkerOptions {
  readonly buildFiles: readonly ServiceWorkerBuildFile[];
  readonly immutableAssets: readonly string[];
  readonly runtimeWarmUrls: readonly string[];
}

export interface VersionedServiceWorker {
  readonly source: string;
  readonly version: string;
}

const APP_SHELL_URL = '/index.html';
const POLICY_VERSION_PLACEHOLDER = 'sanic-policy-template';
const RUNTIME_PREFIXES = Object.freeze(['/models/', '/media/', '/music/']);
const STATIC_SHELL_URLS = Object.freeze([
  APP_SHELL_URL,
  '/manifest.webmanifest',
  '/favicon.png',
]);

export const createCacheVersion = (
  files: readonly ServiceWorkerBuildFile[],
): string => {
  const hash = createHash('sha256');
  for (const file of [...files].sort((left, right) => (
    left.fileName.localeCompare(right.fileName)
  ))) {
    hash.update(file.fileName);
    hash.update('\0');
    hash.update(file.contents);
    hash.update('\0');
  }
  return hash.digest('hex').slice(0, 16);
};

export const immutableAssetUrls = (
  fileNames: readonly string[],
): readonly string[] => (
  [...new Set(fileNames
    .map((fileName) => fileName.replace(/^\/+/, ''))
    .filter((fileName) => fileName.startsWith('assets/'))
    .map((fileName) => `/${fileName}`))]
    .sort()
);

export const createServiceWorkerSource = ({
  immutableAssets,
  runtimeWarmUrls,
  version,
}: ServiceWorkerSourceOptions): string => {
  if (!/^[a-z0-9_-]+$/i.test(version)) {
    throw new Error('Service-worker cache version must be URL-safe');
  }
  const precacheUrls = [...new Set([
    ...STATIC_SHELL_URLS,
    ...immutableAssets,
  ])].sort();
  const warmUrls = [...new Set(runtimeWarmUrls)].sort();
  if (warmUrls.some((url) => (
    !url.startsWith('/')
    || url.startsWith('//')
    || !RUNTIME_PREFIXES.some((prefix) => url.startsWith(prefix))
  ))) {
    throw new Error('Runtime warm URLs must be same-origin model, media, or music paths');
  }

  return `/* Generated from the production Vite bundle. Do not edit. */
const CACHE_VERSION = ${JSON.stringify(version)};
const SANIC_CACHE_PREFIX = 'sanic-';
const SHELL_CACHE = \`\${SANIC_CACHE_PREFIX}shell-\${CACHE_VERSION}\`;
const ASSET_CACHE = \`\${SANIC_CACHE_PREFIX}assets-\${CACHE_VERSION}\`;
const RUNTIME_CACHE = \`\${SANIC_CACHE_PREFIX}runtime-\${CACHE_VERSION}\`;
const CURRENT_CACHES = Object.freeze([SHELL_CACHE, ASSET_CACHE, RUNTIME_CACHE]);
const APP_SHELL_URL = ${JSON.stringify(APP_SHELL_URL)};
const PRECACHE_URLS = Object.freeze(${JSON.stringify(precacheUrls, null, 2)});
const RUNTIME_PREFIXES = Object.freeze(${JSON.stringify(RUNTIME_PREFIXES)});
const WARM_RUNTIME_URLS = Object.freeze(${JSON.stringify(warmUrls, null, 2)});

const isSuccessfulSameOriginResponse = (response) => (
  response.ok && (response.type === 'basic' || response.type === 'default')
);

const cacheFirstImmutable = async (request) => {
  const cached = await caches.match(request);
  if (cached !== undefined) return cached;

  const response = await fetch(request);
  if (isSuccessfulSameOriginResponse(response)) {
    const cache = await caches.open(ASSET_CACHE);
    await cache.put(request, response.clone());
  }
  return response;
};

const networkFirstNavigation = async (request) => {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const response = await fetch(request);
    const pathname = new URL(request.url).pathname;
    if (
      isSuccessfulSameOriginResponse(response)
      && (pathname === '/' || pathname === APP_SHELL_URL)
    ) {
      await cache.put(APP_SHELL_URL, response.clone());
    }
    return response;
  }
  catch {
    return (await cache.match(APP_SHELL_URL)) ?? Response.error();
  }
};

const networkFirstRuntime = async (request) => {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request);
    if (isSuccessfulSameOriginResponse(response)) {
      await cache.put(request, response.clone());
    }
    return response;
  }
  catch {
    return (await cache.match(request)) ?? Response.error();
  }
};

const warmRuntimeCache = async () => {
  const cache = await caches.open(RUNTIME_CACHE);
  await Promise.allSettled(WARM_RUNTIME_URLS.map(async (url) => {
    const request = new Request(
      new URL(url, self.location.origin).toString(),
      { cache: 'no-cache' },
    );
    if (await cache.match(request) !== undefined) return;
    const response = await fetch(request);
    if (isSuccessfulSameOriginResponse(response)) {
      await cache.put(request, response);
    }
  }));
};

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    await cache.add(new Request(APP_SHELL_URL, { cache: 'reload' }));
    await Promise.allSettled(
      PRECACHE_URLS
        .filter((url) => url !== APP_SHELL_URL)
        .map((url) => cache.add(new Request(url, { cache: 'reload' }))),
    );
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter((name) => (
        name.startsWith(SANIC_CACHE_PREFIX) && !CURRENT_CACHES.includes(name)
      ))
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data?.type !== 'WARM_RUNTIME') return;
  event.waitUntil(warmRuntimeCache());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirstNavigation(request));
    return;
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirstImmutable(request));
    return;
  }
  if (
    request.destination === 'font'
    || RUNTIME_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))
  ) {
    event.respondWith(networkFirstRuntime(request));
  }
});
`;
};

export const createVersionedServiceWorker = ({
  buildFiles,
  immutableAssets,
  runtimeWarmUrls,
}: VersionedServiceWorkerOptions): VersionedServiceWorker => {
  const policyTemplate = createServiceWorkerSource({
    immutableAssets,
    runtimeWarmUrls,
    version: POLICY_VERSION_PLACEHOLDER,
  });
  const version = createCacheVersion([
    ...buildFiles,
    {
      fileName: '__generated__/sw-policy-template.js',
      contents: policyTemplate,
    },
  ]);

  return Object.freeze({
    source: createServiceWorkerSource({
      immutableAssets,
      runtimeWarmUrls,
      version,
    }),
    version,
  });
};
