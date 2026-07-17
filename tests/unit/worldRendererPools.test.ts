import {
  BoxGeometry,
  Group,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
} from 'three';
import { describe, expect, it, vi } from 'vitest';
import type { SimulationSnapshot } from '../../src/game/types';
import { InstancedTemplate, WorldRenderer } from '../../src/render/worldRenderer';

const snapshot = (
  distance: number,
  rings: number,
  coins: SimulationSnapshot['coins'],
): Readonly<SimulationSnapshot> => Object.freeze({
  phase: 'playing',
  elapsed: distance,
  distance,
  speed: 36,
  score: rings * 100,
  rings,
  multiplier: 1,
  ringStreak: rings,
  lane: 0,
  playerX: 0,
  playerY: 0,
  jumpProgress: null,
  coins,
  obstacles: Object.freeze([]),
  impactKind: null,
});

describe('InstancedTemplate', () => {
  it('uploads changed instance matrices without recomputing unused culling bounds', () => {
    const geometry = new BoxGeometry(1, 1, 1);
    const material = new MeshBasicMaterial();
    const source = new Group();
    source.name = 'Source';
    source.add(new Mesh(geometry, material));
    const destination = new Group();
    const template = new InstancedTemplate(source, 4, destination, false);
    const instance = template.components[0]!.mesh;
    const computeBounds = vi.spyOn(instance, 'computeBoundingSphere');
    const versionBefore = instance.instanceMatrix.version;

    template.begin();
    template.add(new Matrix4().makeTranslation(1, 2, 3));
    template.commit();

    expect(instance.frustumCulled).toBe(false);
    expect(instance.count).toBe(1);
    expect(instance.instanceMatrix.version).toBeGreaterThan(versionBefore);
    expect(computeBounds).not.toHaveBeenCalled();

    geometry.dispose();
    material.dispose();
  });
});

describe('WorldRenderer pickup bookkeeping', () => {
  it('keeps only emitted coin identifiers inside the twelve-metre ring render window', () => {
    const renderer = Object.create(WorldRenderer.prototype) as WorldRenderer;
    const emittedCoins = new Map<string, number>();
    Object.defineProperties(renderer, {
      emittedCoins: { configurable: true, value: emittedCoins, writable: true },
      lowEffects: { configurable: true, value: false, writable: true },
      sparkles: {
        configurable: true,
        value: { emit: vi.fn() },
        writable: true,
      },
    });
    const updatePickupEffects = (
      renderer as unknown as {
        updatePickupEffects(
          previous: Readonly<SimulationSnapshot>,
          current: Readonly<SimulationSnapshot>,
        ): void;
      }
    ).updatePickupEffects.bind(renderer);

    for (let distance = 0; distance < 3_600; distance += 1) {
      const coin = Object.freeze({
        id: `coin-${distance}`,
        lane: 0,
        height: 0.9,
        offset: 0,
        at: distance,
      } as const);
      updatePickupEffects(
        snapshot(distance, distance, Object.freeze([coin])),
        snapshot(distance, distance + 1, Object.freeze([])),
      );
    }

    const retained = (
      renderer as unknown as { emittedCoins: ReadonlyMap<string, number> | ReadonlySet<string> }
    ).emittedCoins;
    expect(retained.size).toBe(13);
    expect(retained.has('coin-3586')).toBe(false);
    expect(retained.has('coin-3587')).toBe(true);
    expect(retained.has('coin-3599')).toBe(true);

    updatePickupEffects(
      snapshot(3_599, 3_600, Object.freeze([])),
      snapshot(3_612, 3_600, Object.freeze([])),
    );
    expect(retained.size).toBe(0);
  });
});
