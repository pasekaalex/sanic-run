import {
  AnimationClip,
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
} from 'three';
import { describe, expect, it, vi } from 'vitest';
import { ASSET_URLS } from '../../src/config';
import {
  AssetLoader,
  FOREST_PART_NAMES,
  type GltfLike,
  type LoaderLike,
} from '../../src/render/assetLoader';

const mesh = (name: string): Mesh => {
  const value = new Mesh(new BoxGeometry(1, 1, 1), new MeshBasicMaterial());
  value.name = name;
  return value;
};

const renderableGroup = (name: string): Group => {
  const group = new Group();
  group.name = name;
  group.add(mesh(`${name}_Mesh`));
  return group;
};

const characterGltf = (actions = ['Idle', 'Run', 'Jump', 'Crash']): GltfLike => {
  const scene = renderableGroup('SANIC_Armature');
  return { scene, animations: actions.map((name) => new AnimationClip(name, 1)) };
};

const ringGltf = (): GltfLike => {
  const scene = new Group();
  scene.add(renderableGroup('SANIC_Ring'));
  return { scene, animations: [] };
};

const spinBallGltf = (): GltfLike => {
  const scene = new Group();
  scene.add(mesh('SANIC_SpinBall'));
  return { scene, animations: [] };
};

const forestGltf = (names: readonly string[] = FOREST_PART_NAMES): GltfLike => {
  const scene = new Group();
  names.forEach((name) => scene.add(renderableGroup(name)));
  return { scene, animations: [] };
};

const loaderFor = (assets: Record<string, GltfLike | Error>): LoaderLike => ({
  loadAsync: vi.fn(async (url: string, onProgress?: (event: ProgressEvent) => void) => {
    onProgress?.({ loaded: 25, total: 0 } as ProgressEvent);
    onProgress?.({ loaded: 100, total: 100 } as ProgressEvent);
    const result = assets[url];
    if (result instanceof Error) throw result;
    if (!result) throw new Error(`Missing fixture for ${url}`);
    return result;
  }),
});

describe('AssetLoader', () => {
  it('returns branded fallback assets when all GLBs reject', async () => {
    const loader = new AssetLoader({
      loadAsync: vi.fn().mockRejectedValue(new Error('offline')),
    });

    const assets = await loader.load(() => undefined);

    expect(assets.usingFallback).toBe(true);
    expect(assets.character.name).toBe('SANIC_Fallback');
    expect(assets.spinBall.name).toBe('SANIC_SpinBall_Fallback');
    expect(assets.ring.name).toBe('SANIC_Ring_Fallback');
    expect([...assets.forestParts.keys()]).toEqual(FOREST_PART_NAMES);
  });

  it('keeps a valid semantic spin-ball root when every other category fails', async () => {
    const spinBall = spinBallGltf();
    const loader = new AssetLoader(loaderFor({
      [ASSET_URLS.character]: new Error('character unavailable'),
      [ASSET_URLS.spinBall]: spinBall,
      [ASSET_URLS.ring]: new Error('ring unavailable'),
      [ASSET_URLS.forest]: new Error('forest unavailable'),
    }));

    const assets = await loader.load();

    expect(assets.spinBall.name).toBe('SANIC_SpinBall');
    expect(assets.fallback).toEqual({
      character: true,
      spinBall: false,
      ring: true,
      forest: true,
    });
  });

  it('keeps valid categories when just one category is malformed', async () => {
    const validCharacter = characterGltf();
    const validForest = forestGltf();
    const loader = new AssetLoader(loaderFor({
      [ASSET_URLS.character]: validCharacter,
      [ASSET_URLS.spinBall]: spinBallGltf(),
      [ASSET_URLS.ring]: { scene: renderableGroup('Wrong_Ring'), animations: [] },
      [ASSET_URLS.forest]: validForest,
    }));

    const assets = await loader.load();

    expect(assets.character).toBe(validCharacter.scene);
    expect(assets.ring.name).toBe('SANIC_Ring_Fallback');
    expect(assets.forest).toBe(validForest.scene);
    expect(assets.fallback).toEqual({ character: false, spinBall: false, ring: true, forest: false });
  });

  it('requires all four actions and every renderable forest root', async () => {
    const missingAction = characterGltf(['Idle', 'Run', 'Jump']);
    const missingPart = forestGltf(FOREST_PART_NAMES.slice(0, -1));
    const loader = new AssetLoader(loaderFor({
      [ASSET_URLS.character]: missingAction,
      [ASSET_URLS.spinBall]: spinBallGltf(),
      [ASSET_URLS.ring]: ringGltf(),
      [ASSET_URLS.forest]: missingPart,
    }));

    const assets = await loader.load();

    expect(assets.fallback).toEqual({ character: true, spinBall: false, ring: false, forest: true });
    expect(assets.ring.name).toBe('SANIC_Ring');
    expect(assets.animations.map((clip) => clip.name)).toEqual(['Idle', 'Run', 'Jump', 'Crash']);
  });

  it('accepts direct named Mesh roots produced for single-material glTF parts', async () => {
    const directRing = new Group();
    directRing.add(mesh('SANIC_Ring'));
    const directForest = forestGltf();
    const grassRoot = directForest.scene.getObjectByName('KIT_Grass')!;
    directForest.scene.remove(grassRoot);
    directForest.scene.add(mesh('KIT_Grass'));
    const loader = new AssetLoader(loaderFor({
      [ASSET_URLS.character]: characterGltf(),
      [ASSET_URLS.spinBall]: spinBallGltf(),
      [ASSET_URLS.ring]: { scene: directRing, animations: [] },
      [ASSET_URLS.forest]: directForest,
    }));

    const assets = await loader.load();

    expect(assets.fallback.ring).toBe(false);
    expect(assets.fallback.forest).toBe(false);
    expect(assets.ring.name).toBe('SANIC_Ring');
    expect(assets.forestParts.get('KIT_Grass')?.name).toBe('KIT_Grass');
  });

  it('reports monotonic normalized progress even when totals are unknown', async () => {
    const progress: number[] = [];
    const loader = new AssetLoader(loaderFor({
      [ASSET_URLS.character]: characterGltf(),
      [ASSET_URLS.spinBall]: spinBallGltf(),
      [ASSET_URLS.ring]: ringGltf(),
      [ASSET_URLS.forest]: forestGltf(),
    }));

    await loader.load((value) => progress.push(value));

    expect(progress[0]).toBe(0);
    expect(progress.at(-1)).toBe(1);
    expect(progress.every((value) => value >= 0 && value <= 1)).toBe(true);
    expect(progress.every((value, index) => index === 0 || value >= progress[index - 1]!)).toBe(true);
  });

  it('settles every category within the documented 20-second ceiling when one request hangs', async () => {
    vi.useFakeTimers();
    try {
      const fixtures: Record<string, GltfLike> = {
        [ASSET_URLS.spinBall]: spinBallGltf(),
        [ASSET_URLS.ring]: ringGltf(),
        [ASSET_URLS.forest]: forestGltf(),
      };
      const progress: number[] = [];
      const loader = new AssetLoader({
        loadAsync: vi.fn((url: string) => {
          if (url === ASSET_URLS.character) {
            return new Promise<GltfLike>(() => undefined);
          }
          return Promise.resolve(fixtures[url]!);
        }),
      });
      let result: Awaited<ReturnType<AssetLoader['load']>> | undefined;
      void loader.load((value) => progress.push(value)).then((assets) => {
        result = assets;
      });

      await vi.advanceTimersByTimeAsync(19_999);
      expect(result).toBeUndefined();

      await vi.advanceTimersByTimeAsync(1);
      expect(result?.fallback).toEqual({
        character: true,
        spinBall: false,
        ring: false,
        forest: false,
      });
      expect(result?.character.name).toBe('SANIC_Fallback');
      expect(progress.at(-1)).toBe(1);
      expect(progress.filter((value) => value === 1)).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('ignores progress and settlement from category requests that finish after the deadline', async () => {
    vi.useFakeTimers();
    try {
      let reportLateCharacter = (_event: ProgressEvent): void => undefined;
      let reportLateForest = (_event: ProgressEvent): void => undefined;
      let resolveLateCharacter = (_value: GltfLike): void => undefined;
      let rejectLateForest = (_error: Error): void => undefined;
      const loader = new AssetLoader({
        loadAsync: vi.fn((
          url: string,
          onProgress?: (event: ProgressEvent) => void,
        ) => {
          if (url === ASSET_URLS.character) {
            reportLateCharacter = onProgress ?? reportLateCharacter;
            return new Promise<GltfLike>((resolve) => {
              resolveLateCharacter = resolve;
            });
          }
          if (url === ASSET_URLS.forest) {
            reportLateForest = onProgress ?? reportLateForest;
            return new Promise<GltfLike>((_resolve, reject) => {
              rejectLateForest = reject;
            });
          }
          return Promise.resolve(url === ASSET_URLS.spinBall ? spinBallGltf() : ringGltf());
        }),
      });
      const progress: number[] = [];
      let result: Awaited<ReturnType<AssetLoader['load']>> | undefined;
      void loader.load((value) => progress.push(value)).then((assets) => {
        result = assets;
      });

      await vi.advanceTimersByTimeAsync(20_000);
      expect(result?.fallback).toEqual({
        character: true,
        spinBall: false,
        ring: false,
        forest: true,
      });
      const progressAtDeadline = [...progress];

      reportLateCharacter({ loaded: 100, total: 100 } as ProgressEvent);
      reportLateForest({ loaded: 100, total: 100 } as ProgressEvent);
      resolveLateCharacter(characterGltf());
      rejectLateForest(new Error('late forest failure'));
      await Promise.resolve();
      await Promise.resolve();

      expect(result?.fallback.character).toBe(true);
      expect(result?.fallback.forest).toBe(true);
      expect(progress).toEqual(progressAtDeadline);
      expect(progress.filter((value) => value === 1)).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('returns immutable metadata wrappers without freezing Three objects', async () => {
    const loader = new AssetLoader(loaderFor({
      [ASSET_URLS.character]: characterGltf(),
      [ASSET_URLS.spinBall]: spinBallGltf(),
      [ASSET_URLS.ring]: ringGltf(),
      [ASSET_URLS.forest]: forestGltf(),
    }));

    const assets = await loader.load();

    expect(Object.isFrozen(assets)).toBe(true);
    expect(Object.isFrozen(assets.fallback)).toBe(true);
    expect(Object.isFrozen(assets.character)).toBe(false);
    expect(Object.isFrozen(assets.spinBall)).toBe(false);
    expect(Object.isFrozen(assets.ring)).toBe(false);
    expect(Object.isFrozen(assets.forestParts)).toBe(true);
  });
});
