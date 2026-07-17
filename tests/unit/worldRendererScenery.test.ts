import {
  DirectionalLight,
  Fog,
  HemisphereLight,
  Matrix4,
  MeshStandardMaterial,
  Object3D,
  Scene,
} from 'three';
import { describe, expect, it, vi } from 'vitest';
import { ZONES, type ZoneId } from '../../src/game/zones';
import type { ForestPartName } from '../../src/render/assetLoader';
import {
  sceneryPoolCapacityForPart,
  sceneryPartForSegment,
  signPartForSlot,
  WorldRenderer,
} from '../../src/render/worldRenderer';

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
  it('uses deterministic, distinct per-zone scenery and sign selections', () => {
    const zoneIds = ZONES.map((zone) => zone.id);
    const signature = (zone: ZoneId, layer: 'tree' | 'foliage' | 'detail'): string => (
      Array.from(
        { length: 32 },
        (_, segment) => sceneryPartForSegment(layer, segment, zone),
      ).join('|')
    );

    for (const layer of ['tree', 'foliage', 'detail'] as const) {
      const signatures = zoneIds.map((zone) => signature(zone, layer));
      expect(new Set(signatures).size).toBe(zoneIds.length);
      expect(signature(zoneIds[0]!, layer)).toBe(signature(zoneIds[0]!, layer));
    }

    const signOrders = zoneIds.map((zone) => (
      Array.from({ length: 4 }, (_, slot) => signPartForSlot(slot, zone)).join('|')
    ));
    expect(new Set(signOrders).size).toBe(zoneIds.length);
  });

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

  it('allocates every deterministic scenery variant for the most skewed render window', () => {
    const layers = [
      {
        layer: 'tree',
        parts: ['KIT_Tree_A', 'KIT_Tree_B'],
        slots: 120,
      },
      {
        layer: 'foliage',
        parts: ['KIT_Grass', 'KIT_Fern'],
        slots: 360,
      },
      {
        layer: 'detail',
        parts: ['KIT_Rock', 'KIT_Mushroom'],
        slots: 80,
      },
    ] as const;

    for (const { layer, parts, slots } of layers) {
      const maximums = new Map<ForestPartName, number>(
        parts.map((part) => [part, 0]),
      );
      for (const zone of ZONES) {
        for (let windowStart = -64; windowStart <= 512; windowStart += 1) {
          const counts = new Map<ForestPartName, number>(
            parts.map((part) => [part, 0]),
          );
          for (let slot = 0; slot < slots; slot += 1) {
            const segment = windowStart + Math.floor(slot / 2);
            const part = sceneryPartForSegment(layer, segment, zone.id);
            counts.set(part, (counts.get(part) ?? 0) + 1);
          }
          for (const part of parts) {
            maximums.set(part, Math.max(
              maximums.get(part) ?? 0,
              counts.get(part) ?? 0,
            ));
          }
        }
      }

      expect(Math.max(...maximums.values())).toBeGreaterThan(slots / 2);
      for (const part of parts) {
        expect(sceneryPoolCapacityForPart(part)).toBeGreaterThanOrEqual(
          maximums.get(part) ?? Number.POSITIVE_INFINITY,
        );
      }
    }
  });

  it('mutates stable palette references only when the distance-derived zone changes', () => {
    const renderer = Object.create(WorldRenderer.prototype) as WorldRenderer;
    const zoneWrites: string[] = [];
    const dataset = new Proxy<Record<string, string>>({}, {
      set(target, property, value: string) {
        target[String(property)] = value;
        zoneWrites.push(value);
        return true;
      },
    });
    const canvas = { dataset } as unknown as HTMLCanvasElement;
    const scene = new Scene();
    scene.fog = new Fog(0xffffff, 42, 225);
    const hemisphereLight = new HemisphereLight();
    const directionalLight = new DirectionalLight();
    const groundMaterials = {
      verge: new MeshStandardMaterial(),
      road: new MeshStandardMaterial(),
    };
    const laneMarkerMaterial = new MeshStandardMaterial();
    const webglRenderer = {
      setClearColor: vi.fn(),
      toneMappingExposure: 0,
    };
    Object.defineProperties(renderer, {
      canvas: { configurable: true, value: canvas, writable: true },
      renderer: { configurable: true, value: webglRenderer, writable: true },
      scene: { configurable: true, value: scene, writable: true },
      hemisphereLight: { configurable: true, value: hemisphereLight, writable: true },
      directionalLight: { configurable: true, value: directionalLight, writable: true },
      groundMaterials: { configurable: true, value: groundMaterials, writable: true },
      laneMarkerMaterial: { configurable: true, value: laneMarkerMaterial, writable: true },
      currentZoneId: { configurable: true, value: null, writable: true },
    });
    const updateZonePresentation = (
      renderer as unknown as { updateZonePresentation(distance: number): void }
    ).updateZonePresentation.bind(renderer);
    const stableReferences = {
      fog: scene.fog,
      hemisphereLight,
      directionalLight,
      verge: groundMaterials.verge,
      road: groundMaterials.road,
      laneMarkerMaterial,
    };

    updateZonePresentation(0);
    const ringwoodFog = scene.fog.color.getHex();
    updateZonePresentation(500);
    updateZonePresentation(840);
    const liquidityFog = scene.fog.color.getHex();
    updateZonePresentation(1_000);
    updateZonePresentation(1_960);
    const afterDarkFog = scene.fog.color.getHex();

    expect(webglRenderer.setClearColor).toHaveBeenCalledTimes(3);
    expect(zoneWrites).toEqual([
      'ringwood-rush',
      'liquidity-loop',
      'ansem-after-dark',
    ]);
    expect(new Set([ringwoodFog, liquidityFog, afterDarkFog]).size).toBe(3);
    expect(canvas.dataset.zone).toBe('ansem-after-dark');
    expect({
      fog: scene.fog,
      hemisphereLight,
      directionalLight,
      verge: groundMaterials.verge,
      road: groundMaterials.road,
      laneMarkerMaterial,
    }).toEqual(stableReferences);

    groundMaterials.verge.dispose();
    groundMaterials.road.dispose();
    laneMarkerMaterial.dispose();
  });
});
