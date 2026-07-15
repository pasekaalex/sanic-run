import {
  AnimationClip,
  BoxGeometry,
  CapsuleGeometry,
  ConeGeometry,
  CylinderGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  SphereGeometry,
  TorusGeometry,
} from 'three';

export const FALLBACK_FOREST_PART_NAMES = [
  'KIT_Tree_A',
  'KIT_Tree_B',
  'KIT_Grass',
  'KIT_Fern',
  'KIT_Rock',
  'KIT_Mushroom',
  'KIT_Log',
  'KIT_Candle',
  'KIT_FUD',
  'KIT_Gap',
  'KIT_Sign_Stimmy',
  'KIT_Sign_Trenches',
  'KIT_Sign_Coping',
  'KIT_Sign_Memes',
] as const;

export type FallbackForestPartName = (typeof FALLBACK_FOREST_PART_NAMES)[number];

const cobalt = new MeshStandardMaterial({ color: 0x183bd1, roughness: 0.42, metalness: 0.08 });
const white = new MeshStandardMaterial({ color: 0xffffff, roughness: 0.32 });
const red = new MeshStandardMaterial({ color: 0xf5222d, roughness: 0.28 });
const cream = new MeshStandardMaterial({ color: 0xf5d6a4, roughness: 0.58 });
const black = new MeshStandardMaterial({ color: 0x080a16, roughness: 0.3 });
const gold = new MeshStandardMaterial({
  color: 0xffcf19,
  emissive: 0x5c2600,
  emissiveIntensity: 0.4,
  metalness: 0.88,
  roughness: 0.18,
});
const bark = new MeshStandardMaterial({ color: 0x6c3719, roughness: 0.9 });
const leaf = new MeshStandardMaterial({ color: 0x19a93e, roughness: 0.72 });
const grass = new MeshStandardMaterial({ color: 0x55db3d, roughness: 0.82 });
const stone = new MeshStandardMaterial({ color: 0x617475, roughness: 0.94 });
const soil = new MeshStandardMaterial({ color: 0x24120e, roughness: 1 });

const addMesh = (
  parent: Group,
  geometry: ConstructorParameters<typeof Mesh>[0],
  material: ConstructorParameters<typeof Mesh>[1],
  position: readonly [number, number, number],
  scale: readonly [number, number, number] = [1, 1, 1],
): Mesh => {
  const child = new Mesh(geometry, material);
  child.position.set(...position);
  child.scale.set(...scale);
  child.castShadow = true;
  child.receiveShadow = true;
  parent.add(child);
  return child;
};

export const createFallbackCharacter = (): {
  character: Group;
  animations: AnimationClip[];
} => {
  const character = new Group();
  character.name = 'SANIC_Fallback';

  addMesh(character, new CapsuleGeometry(0.8, 1.55, 8, 18), cobalt, [0, 2.65, 0], [1.18, 1, 0.82]);
  addMesh(character, new SphereGeometry(0.92, 24, 16), cobalt, [0, 4.38, 0.02], [1, 1.08, 0.9]);
  addMesh(character, new SphereGeometry(0.7, 20, 12), cream, [0, 4.15, -0.67], [1, 0.55, 0.42]);
  addMesh(character, new SphereGeometry(0.23, 16, 10), black, [0, 4.32, -1.02], [1.2, 0.72, 0.7]);

  for (const side of [-1, 1]) {
    addMesh(character, new CapsuleGeometry(0.28, 1.25, 6, 12), cobalt, [side * 1.05, 2.85, 0], [1.18, 1, 1]);
    addMesh(character, new SphereGeometry(0.44, 16, 12), white, [side * 1.08, 1.95, -0.1], [1.05, 1.2, 0.8]);
    addMesh(character, new CapsuleGeometry(0.29, 1.1, 6, 12), cobalt, [side * 0.45, 1.05, 0], [1, 1, 1]);
    addMesh(character, new BoxGeometry(0.88, 0.42, 1.45), red, [side * 0.48, 0.24, -0.35], [1, 1, 1]);
    addMesh(character, new BoxGeometry(0.95, 0.12, 1.55), white, [side * 0.48, 0.03, -0.35]);
  }

  for (let index = 0; index < 7; index += 1) {
    const angle = ((index - 3) / 6) * Math.PI * 0.8;
    const quill = addMesh(
      character,
      new ConeGeometry(0.4, 2.15, 10),
      cobalt,
      [Math.sin(angle) * 0.55, 4.5 + Math.cos(angle) * 0.38, 0.72],
      [1, 1, 0.9],
    );
    quill.rotation.x = Math.PI * 0.56;
    quill.rotation.z = -angle * 0.52;
  }

  const animations = ['Idle', 'Run', 'Jump', 'Crash'].map(
    (name) => new AnimationClip(name, name === 'Idle' ? 2 : 1, []),
  );
  return { character, animations };
};

export const createFallbackRing = (): Group => {
  const ring = new Group();
  ring.name = 'SANIC_Ring_Fallback';
  const torus = addMesh(ring, new TorusGeometry(0.62, 0.16, 16, 36), gold, [0, 0, 0]);
  torus.name = 'SANIC_Ring_Fallback_Mesh';
  return ring;
};

const createTree = (name: string, variant: number): Group => {
  const root = new Group();
  root.name = name;
  addMesh(root, new CylinderGeometry(0.32, 0.52, 4.1, 10), bark, [0, 2.05, 0]);
  addMesh(root, new ConeGeometry(1.45 + variant * 0.1, 3.1, 11), leaf, [0, 4.2, 0]);
  addMesh(root, new ConeGeometry(1.05, 2.5, 11), leaf, [0.3 * variant, 5.2, 0]);
  return root;
};

const createSign = (name: string): Group => {
  const root = new Group();
  root.name = name;
  addMesh(root, new CylinderGeometry(0.09, 0.12, 2.3, 8), bark, [0, 1.15, 0]);
  addMesh(root, new BoxGeometry(2.5, 0.8, 0.16), bark, [0, 2.1, 0]);
  addMesh(root, new BoxGeometry(2.08, 0.42, 0.05), gold, [0, 2.1, -0.1]);
  return root;
};

const createForestPart = (name: FallbackForestPartName): Group => {
  if (name === 'KIT_Tree_A') return createTree(name, -1);
  if (name === 'KIT_Tree_B') return createTree(name, 1);
  if (name.startsWith('KIT_Sign_')) return createSign(name);

  const root = new Group();
  root.name = name;
  if (name === 'KIT_Grass' || name === 'KIT_Fern') {
    for (let index = 0; index < 5; index += 1) {
      const blade = addMesh(root, new ConeGeometry(0.09, 0.7 + index * 0.07, 5), grass, [(index - 2) * 0.16, 0.35, 0]);
      blade.rotation.z = (index - 2) * 0.12;
    }
  } else if (name === 'KIT_Rock') {
    addMesh(root, new SphereGeometry(0.6, 9, 7), stone, [0, 0.42, 0], [1.2, 0.72, 0.9]);
  } else if (name === 'KIT_Mushroom') {
    addMesh(root, new CylinderGeometry(0.1, 0.14, 0.55, 8), cream, [0, 0.28, 0]);
    addMesh(root, new SphereGeometry(0.34, 12, 7, 0, Math.PI * 2, 0, Math.PI / 2), red, [0, 0.56, 0]);
  } else if (name === 'KIT_Log') {
    const log = addMesh(root, new CylinderGeometry(0.45, 0.5, 3.2, 12), bark, [0, 0.52, 0]);
    log.rotation.z = Math.PI / 2;
  } else if (name === 'KIT_Candle') {
    addMesh(root, new BoxGeometry(2.6, 1.2, 0.28), red, [0, 0.6, 0]);
    addMesh(root, new ConeGeometry(0.18, 0.5, 8), gold, [0, 1.42, 0]);
  } else if (name === 'KIT_FUD') {
    addMesh(root, new BoxGeometry(2.8, 1.35, 0.3), bark, [0, 0.72, 0]);
    addMesh(root, new BoxGeometry(2.2, 0.42, 0.12), red, [0, 0.82, -0.2]);
  } else {
    addMesh(root, new BoxGeometry(2.7, 0.12, 3.2), soil, [0, 0.02, 0]);
  }
  return root;
};

export const createFallbackForest = (): {
  forest: Group;
  parts: Map<FallbackForestPartName, Group>;
} => {
  const forest = new Group();
  forest.name = 'SANIC_Forest_Fallback';
  const parts = new Map<FallbackForestPartName, Group>();
  for (const name of FALLBACK_FOREST_PART_NAMES) {
    const part = createForestPart(name);
    forest.add(part);
    parts.set(name, part);
  }
  return { forest, parts };
};
