import {
  BoxGeometry,
  Group,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
} from 'three';
import { describe, expect, it, vi } from 'vitest';
import { InstancedTemplate } from '../../src/render/worldRenderer';

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
