import { Matrix4, Object3D } from 'three';
import { describe, expect, it } from 'vitest';
import type { ForestPartName } from '../../src/render/assetLoader';
import { WorldRenderer } from '../../src/render/worldRenderer';

interface RecordedTemplate {
  readonly placements: Matrix4[];
  begin(): void;
  add(placement: Matrix4): void;
  commit(): void;
}

const makeTemplate = (): RecordedTemplate => ({
  placements: [],
  begin() {
    this.placements.length = 0;
  },
  add(placement) {
    this.placements.push(placement.clone());
  },
  commit() {
    // Placements are already captured for inspection.
  },
});

const sceneryAt = (distance: number): ReadonlyMap<ForestPartName, readonly Matrix4[]> => {
  const names: readonly ForestPartName[] = [
    'KIT_Tree_A',
    'KIT_Tree_B',
    'KIT_Grass',
    'KIT_Fern',
    'KIT_Rock',
    'KIT_Mushroom',
    'KIT_Sign_Stimmy',
    'KIT_Sign_Trenches',
    'KIT_Sign_Coping',
    'KIT_Sign_Memes',
  ];
  const templates = new Map(names.map((name) => [name, makeTemplate()]));
  const renderer = Object.create(WorldRenderer.prototype) as WorldRenderer;
  Object.defineProperties(renderer, {
    lowEffects: { configurable: true, value: false, writable: true },
    placementDummy: { configurable: true, value: new Object3D(), writable: true },
    sceneryTemplates: { configurable: true, value: templates, writable: true },
  });

  (renderer as unknown as { updateScenery(value: number): void }).updateScenery(distance);
  return new Map([...templates].map(([name, template]) => [name, template.placements]));
};

const modelAtSegment = (
  scenery: ReadonlyMap<ForestPartName, readonly Matrix4[]>,
  distance: number,
  spacing: number,
  segment: number,
  names: readonly ForestPartName[],
): ForestPartName | undefined => names.find((name) => scenery.get(name)?.some((matrix) => {
  const renderedZ = matrix.elements[14] ?? Number.NaN;
  const renderedSegment = Math.round((distance - renderedZ) / spacing);
  return renderedSegment === segment;
}));

describe('WorldRenderer scenery identity', () => {
  it('keeps foliage and detail models stable when their pool windows recycle', () => {
    const beforeFoliageRecycle = sceneryAt(1.699);
    const afterFoliageRecycle = sceneryAt(1.701);
    const beforeDetailRecycle = sceneryAt(7.499);
    const afterDetailRecycle = sceneryAt(7.501);

    expect(modelAtSegment(
      beforeFoliageRecycle,
      1.699,
      1.7,
      0,
      ['KIT_Grass', 'KIT_Fern'],
    )).toBe(modelAtSegment(
      afterFoliageRecycle,
      1.701,
      1.7,
      0,
      ['KIT_Grass', 'KIT_Fern'],
    ));
    expect(modelAtSegment(
      beforeDetailRecycle,
      7.499,
      7.5,
      0,
      ['KIT_Rock', 'KIT_Mushroom'],
    )).toBe(modelAtSegment(
      afterDetailRecycle,
      7.501,
      7.5,
      0,
      ['KIT_Rock', 'KIT_Mushroom'],
    ));
  });
});
