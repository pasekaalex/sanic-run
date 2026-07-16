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

const cacheControlFor = (source: string): string | undefined => (
  config.headers
    .find((rule) => rule.source === source)
    ?.headers.find((header) => header.key.toLowerCase() === 'cache-control')
    ?.value
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
