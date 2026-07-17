import { AnimationClip, Group, type Object3D } from 'three';
import {
  DRACO_GLTF_CONFIG,
  DRACOLoader,
} from 'three/addons/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { ASSET_URLS } from '../config';
import {
  createFallbackCharacter,
  createFallbackForest,
  createFallbackRing,
  createFallbackSpinBall,
  FALLBACK_FOREST_PART_NAMES,
} from './fallbackAssets';

export const CHARACTER_ACTION_NAMES = ['Idle', 'Run', 'Jump', 'Crash'] as const;
export const FOREST_PART_NAMES = FALLBACK_FOREST_PART_NAMES;
export type CharacterActionName = (typeof CHARACTER_ACTION_NAMES)[number];
export type ForestPartName = (typeof FOREST_PART_NAMES)[number];

export interface GltfLike {
  readonly scene: Group;
  readonly animations: readonly AnimationClip[];
}

export interface LoaderLike {
  loadAsync(
    url: string,
    onProgress?: (event: ProgressEvent<EventTarget>) => void,
  ): Promise<GltfLike>;
}

export interface LoadedAssets {
  readonly character: Group;
  readonly animations: readonly AnimationClip[];
  readonly spinBall: Object3D;
  readonly ring: Object3D;
  readonly forest: Group;
  readonly forestParts: ReadonlyMap<ForestPartName, Object3D>;
  readonly usingFallback: boolean;
  readonly fallback: Readonly<{
    character: boolean;
    spinBall: boolean;
    ring: boolean;
    forest: boolean;
  }>;
}

type ProgressCallback = (progress: number) => void;
type Category = 'character' | 'spinBall' | 'ring' | 'forest';

/** A missing GLB must fail soft before the 20-second startup ceiling. */
const ASSET_CATEGORY_DEADLINE_MS = 20_000;

const hasRenderableDescendant = (root: Object3D): boolean => {
  let found = false;
  root.traverse((child) => {
    if ((child as Object3D & { isMesh?: boolean }).isMesh === true) found = true;
  });
  return found;
};

const makeReadonlyMap = <Key, Value>(source: ReadonlyMap<Key, Value>): ReadonlyMap<Key, Value> => Object.freeze({
  get size() { return source.size; },
  get: (key: Key) => source.get(key),
  has: (key: Key) => source.has(key),
  entries: () => source.entries(),
  keys: () => source.keys(),
  values: () => source.values(),
  forEach: (callback: (value: Value, key: Key, map: ReadonlyMap<Key, Value>) => void, thisArg?: unknown) => {
    source.forEach((value, key) => callback.call(thisArg, value, key, source));
  },
  [Symbol.iterator]: () => source[Symbol.iterator](),
});

const selectCharacter = (gltf: GltfLike | undefined): {
  character: Group;
  animations: AnimationClip[];
  fallback: boolean;
} => {
  if (gltf && hasRenderableDescendant(gltf.scene)) {
    const byName = new Map(gltf.animations.map((clip) => [clip.name, clip]));
    const animations = CHARACTER_ACTION_NAMES.map((name) => byName.get(name));
    if (animations.every((clip): clip is AnimationClip => clip !== undefined)) {
      return { character: gltf.scene, animations, fallback: false };
    }
  }
  const fallback = createFallbackCharacter();
  return { ...fallback, fallback: true };
};

const selectRing = (gltf: GltfLike | undefined): { ring: Object3D; fallback: boolean } => {
  const candidate = gltf?.scene.getObjectByName('SANIC_Ring');
  if (candidate && hasRenderableDescendant(candidate)) {
    return { ring: candidate, fallback: false };
  }
  return { ring: createFallbackRing(), fallback: true };
};

const selectSpinBall = (gltf: GltfLike | undefined): { spinBall: Object3D; fallback: boolean } => {
  const candidate = gltf?.scene.getObjectByName('SANIC_SpinBall');
  if (candidate && hasRenderableDescendant(candidate)) {
    return { spinBall: candidate, fallback: false };
  }
  return { spinBall: createFallbackSpinBall(), fallback: true };
};

const selectForest = (gltf: GltfLike | undefined): {
  forest: Group;
  parts: Map<ForestPartName, Object3D>;
  fallback: boolean;
} => {
  if (gltf) {
    const parts = new Map<ForestPartName, Object3D>();
    for (const name of FOREST_PART_NAMES) {
      const candidate = gltf.scene.getObjectByName(name);
      if (!candidate || !hasRenderableDescendant(candidate)) {
        parts.clear();
        break;
      }
      parts.set(name, candidate);
    }
    if (parts.size === FOREST_PART_NAMES.length) {
      return { forest: gltf.scene, parts, fallback: false };
    }
  }
  const fallback = createFallbackForest();
  return { ...fallback, fallback: true };
};

export class AssetLoader {
  private readonly loader: LoaderLike;
  private readonly dracoLoader: DRACOLoader | null;

  constructor(loader?: LoaderLike) {
    if (loader) {
      this.loader = loader;
      this.dracoLoader = null;
      return;
    }
    this.dracoLoader = new DRACOLoader()
      .setDecoderPath(DRACO_GLTF_CONFIG)
      .setWorkerLimit(2);
    this.loader = new GLTFLoader().setDRACOLoader(this.dracoLoader);
  }

  async load(onProgress: ProgressCallback = () => undefined): Promise<LoadedAssets> {
    const categories: readonly Category[] = ['character', 'spinBall', 'ring', 'forest'];
    const urls: Record<Category, string> = {
      character: ASSET_URLS.character,
      spinBall: ASSET_URLS.spinBall,
      ring: ASSET_URLS.ring,
      forest: ASSET_URLS.forest,
    };
    const categoryProgress: Record<Category, number> = {
      character: 0,
      spinBall: 0,
      ring: 0,
      forest: 0,
    };
    let reported = -1;
    const report = (): void => {
      const next = Math.max(0, Math.min(1, categories.reduce(
        (total, category) => total + categoryProgress[category],
        0,
      ) / categories.length));
      if (next <= reported) return;
      reported = next;
      onProgress(next);
    };
    report();

    const loadCategory = async (category: Category): Promise<GltfLike | undefined> => {
      let complete = false;
      let deadline: number | undefined;
      const request = Promise.resolve()
        .then(() => this.loader.loadAsync(urls[category], (event) => {
          if (complete) return;
          const fraction = event.total > 0
            ? event.loaded / event.total
            : event.loaded > 0
              ? Math.min(0.95, event.loaded / (event.loaded + 1_000_000))
              : 0;
          categoryProgress[category] = Math.max(categoryProgress[category], Math.min(0.99, fraction));
          report();
        }))
        .catch(() => undefined);
      const timeout = new Promise<undefined>((resolve) => {
        deadline = setTimeout(resolve, ASSET_CATEGORY_DEADLINE_MS);
      });
      try {
        return await Promise.race([request, timeout]);
      } finally {
        complete = true;
        if (deadline !== undefined) clearTimeout(deadline);
        categoryProgress[category] = 1;
        report();
      }
    };

    const [characterGltf, spinBallGltf, ringGltf, forestGltf] = await Promise.all(categories.map(loadCategory));
    this.dracoLoader?.dispose();
    const character = selectCharacter(characterGltf);
    const spinBall = selectSpinBall(spinBallGltf);
    const ring = selectRing(ringGltf);
    const forest = selectForest(forestGltf);
    const fallback = Object.freeze({
      character: character.fallback,
      spinBall: spinBall.fallback,
      ring: ring.fallback,
      forest: forest.fallback,
    });

    return Object.freeze({
      character: character.character,
      animations: Object.freeze([...character.animations]),
      spinBall: spinBall.spinBall,
      ring: ring.ring,
      forest: forest.forest,
      forestParts: makeReadonlyMap(forest.parts),
      usingFallback: fallback.character || fallback.spinBall || fallback.ring || fallback.forest,
      fallback,
    });
  }
}
