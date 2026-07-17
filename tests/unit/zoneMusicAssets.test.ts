import { existsSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ZONE_MUSIC_TRACKS } from '../../src/platform/zoneMusicPlayer';

const projectRoot = resolve(import.meta.dirname, '../..');

describe('authored zone music assets', () => {
  it('ships every manifest track as an MP3 within the combined payload budget', () => {
    const paths = ZONE_MUSIC_TRACKS.map(({ url }) =>
      resolve(projectRoot, 'public', url.replace(/^\//, '')));

    expect(paths.every((path) => existsSync(path))).toBe(true);
    const payload = paths.reduce((total, path) => total + statSync(path).size, 0);
    expect(payload).toBeGreaterThan(100_000);
    expect(payload).toBeLessThanOrEqual(950_000);

    for (const path of paths) {
      const header = readFileSync(path).subarray(0, 3).toString('ascii');
      expect(header).toBe('ID3');
    }
  });

  it('includes the reproducible source renderer beside the application sources', () => {
    expect(existsSync(resolve(projectRoot, 'scripts/render-zone-music.mjs'))).toBe(true);
  });
});
