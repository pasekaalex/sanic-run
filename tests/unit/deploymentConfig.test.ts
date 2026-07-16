import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

interface HeaderRule {
  readonly source: string;
  readonly headers: readonly {
    readonly key: string;
    readonly value: string;
  }[];
}

const configPath = resolve(process.cwd(), 'vercel.json');
const config = JSON.parse(readFileSync(configPath, 'utf8')) as {
  readonly headers: readonly HeaderRule[];
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
