import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

interface HeaderRule {
  readonly source: string;
  readonly headers: readonly {
    readonly key: string;
    readonly value: string;
  }[];
}

interface RewriteRule {
  readonly source: string;
  readonly destination: string;
}

const configPath = resolve(process.cwd(), 'vercel.json');
const config = JSON.parse(readFileSync(configPath, 'utf8')) as {
  readonly headers: readonly HeaderRule[];
  readonly rewrites?: readonly RewriteRule[];
};

const readPublicFile = (filename: string): string => {
  const path = resolve(process.cwd(), 'public', filename);
  return existsSync(path) ? readFileSync(path, 'utf8') : '';
};

const headerValueFor = (source: string, key: string): string | undefined => (
  config.headers
    .find((rule) => rule.source === source)
    ?.headers.find((header) => header.key.toLowerCase() === key.toLowerCase())
    ?.value
);

const cacheControlFor = (source: string): string | undefined => (
  headerValueFor(source, 'cache-control')
);

describe('Vercel cache policy', () => {
  it.each(['/models/(.*)', '/media/(.*)'])(
    'revalidates stable asset URLs so model and promo replacements reach returning players: %s',
    (source) => {
      expect(cacheControlFor(source)).toBe('public, max-age=0, must-revalidate');
    },
  );

  it('keeps content-hashed build assets immutable', () => {
    expect(cacheControlFor('/assets/(.*)')).toBe('public, max-age=31536000, immutable');
  });
});

describe('Vercel content security policy', () => {
  it('permits bundled Draco WASM and blob workers without broad unsafe eval', () => {
    const policy = headerValueFor('/(.*)', 'content-security-policy');
    expect(policy).toBeDefined();
    const directives = new Map(policy!.split(';').map((directive) => {
      const [name, ...values] = directive.trim().split(/\s+/);
      return [name, values] as const;
    }));

    expect(directives.get('script-src')).toContain("'wasm-unsafe-eval'");
    expect(directives.get('script-src')).not.toContain("'unsafe-eval'");
    expect(directives.get('worker-src')).toEqual(["'self'", 'blob:']);
    expect(directives.get('connect-src')).toEqual(["'self'", 'blob:']);
  });
});

describe('Crawler routes', () => {
  it('publishes plain-text robots directives with the canonical sitemap URL', () => {
    const robots = readPublicFile('robots.txt');
    expect(robots).not.toMatch(/[<>]/);
    expect(robots.split(/\r?\n/).filter(Boolean)).toEqual([
      'User-agent: *',
      'Allow: /',
      'Sitemap: https://sanic.fun/sitemap.xml',
    ]);
  });

  it('publishes a parseable sitemap containing only the canonical site URL', () => {
    const sitemap = new DOMParser().parseFromString(readPublicFile('sitemap.xml'), 'application/xml');
    expect(sitemap.querySelector('parsererror')).toBeNull();
    expect([...sitemap.getElementsByTagName('loc')].map((node) => node.textContent)).toEqual([
      'https://sanic.fun/',
    ]);
  });

  it('does not mask unknown static paths with an unconditional SPA rewrite', () => {
    expect(config.rewrites?.some(({ source, destination }) => (
      source === '/(.*)' && destination === '/index.html'
    )) ?? false).toBe(false);
  });
});
