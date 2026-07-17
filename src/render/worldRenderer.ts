import {
  ACESFilmicToneMapping,
  AnimationAction,
  AnimationMixer,
  Box3,
  BoxGeometry,
  BufferGeometry,
  Color,
  DirectionalLight,
  DynamicDrawUsage,
  Euler,
  Fog,
  Group,
  HemisphereLight,
  InstancedMesh,
  LoopOnce,
  LoopRepeat,
  Material,
  MathUtils,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  Quaternion,
  Scene,
  SphereGeometry,
  SRGBColorSpace,
  Texture,
  Vector3,
  WebGLRenderer,
} from 'three';
import { GAME } from '../config';
import type { ObstacleKind, SimulationSnapshot } from '../game/types';
import {
  CHARACTER_ACTION_NAMES,
  FOREST_PART_NAMES,
  type CharacterActionName,
  type ForestPartName,
  type LoadedAssets,
} from './assetLoader';
import {
  animationCrossfadeSeconds,
  characterActionFor,
  interpolateJumpProgress,
  jumpClipTime,
  jumpPresentation,
  runTimeScale,
} from './animationTiming';
import { uniformScaleForHeight } from './modelScale';
import { nextSpinRotation } from './spinPresentation';

export interface WorldRendererOptions {
  readonly onContextLost?: () => void;
  readonly onContextRestored?: () => void;
  readonly enableTestProbes?: boolean;
}

interface InstancedComponent {
  readonly mesh: InstancedMesh;
  readonly localMatrix: Matrix4;
  readonly scratchMatrix: Matrix4;
}

interface ObstaclePool {
  readonly roots: Object3D[];
  used: number;
}

interface Particle {
  readonly position: Vector3;
  readonly velocity: Vector3;
  life: number;
  readonly totalLife: number;
  readonly size: number;
}

interface CharacterPoseProbe {
  readonly root: Object3D;
  readonly hips: Object3D;
  readonly chest: Object3D;
  readonly leftFoot: Object3D;
  readonly rightFoot: Object3D;
  readonly rootPosition: Vector3;
  readonly hipsPosition: Vector3;
  readonly chestPosition: Vector3;
  readonly leftFootPosition: Vector3;
  readonly rightFootPosition: Vector3;
}

const ZERO = new Vector3();
const IDENTITY_QUATERNION = new Quaternion();
const UNIT_SCALE = new Vector3(1, 1, 1);
const CHARACTER_WORLD_HEIGHT = 4.12;
const SPIN_BALL_WORLD_DIAMETER = 1.815;
const RING_RENDER_BEHIND_DISTANCE = 12;
const REQUIRED_POOL_CAPACITIES = Object.freeze({
  rings: 180,
  trees: 120,
  grassAndFern: 360,
  rocksAndMushrooms: 80,
});

const hash01 = (value: number): number => {
  const mixed = Math.sin(value * 12.9898 + 78.233) * 43_758.5453;
  return mixed - Math.floor(mixed);
};

const materialAt = (material: Material | Material[], index: number): Material => (
  Array.isArray(material) ? material[index] ?? material[0]! : material
);

const createCharacterPoseProbe = (
  character: Group,
  enabled: boolean,
): CharacterPoseProbe | null => {
  if (!enabled) return null;
  const root = character.getObjectByName('root');
  const hips = character.getObjectByName('hips');
  const chest = character.getObjectByName('chest');
  const leftFoot = character.getObjectByName('footL');
  const rightFoot = character.getObjectByName('footR');
  if (!root || !hips || !chest || !leftFoot || !rightFoot) return null;
  return {
    root,
    hips,
    chest,
    leftFoot,
    rightFoot,
    rootPosition: new Vector3(),
    hipsPosition: new Vector3(),
    chestPosition: new Vector3(),
    leftFootPosition: new Vector3(),
    rightFootPosition: new Vector3(),
  };
};

const geometryComponent = (
  source: BufferGeometry,
  start: number,
  count: number,
): BufferGeometry => {
  const component = source.clone();
  component.clearGroups();
  component.addGroup(start, count, 0);
  return component;
};

export class InstancedTemplate {
  readonly capacity: number;
  readonly components: readonly InstancedComponent[];
  private cursor = 0;

  constructor(root: Object3D, capacity: number, destination: Group, shadows: boolean) {
    this.capacity = capacity;
    const components: InstancedComponent[] = [];
    root.updateWorldMatrix(true, true);
    const inverseRoot = root.matrixWorld.clone().invert();

    root.traverse((child) => {
      const source = child as Mesh;
      if (!source.isMesh || !source.geometry || !source.material) return;
      source.updateWorldMatrix(true, false);
      const localMatrix = inverseRoot.clone().multiply(source.matrixWorld);
      const positionCount = source.geometry.getAttribute('position')?.count ?? 0;
      const drawCount = source.geometry.index?.count ?? positionCount;
      const groups = Array.isArray(source.material) && source.geometry.groups.length > 0
        ? source.geometry.groups
        : [{ start: 0, count: drawCount, materialIndex: 0 }];

      for (const group of groups) {
        if (group.count <= 0) continue;
        const geometry = groups.length > 1
          ? geometryComponent(source.geometry, group.start, group.count)
          : source.geometry;
        const material = materialAt(source.material, group.materialIndex ?? 0);
        const mesh = new InstancedMesh(geometry, material, capacity);
        mesh.name = `${root.name}_${source.name || 'Mesh'}_Instances`;
        mesh.instanceMatrix.setUsage(DynamicDrawUsage);
        mesh.count = 0;
        mesh.castShadow = shadows;
        mesh.receiveShadow = true;
        mesh.frustumCulled = false;
        destination.add(mesh);
        components.push({ mesh, localMatrix, scratchMatrix: new Matrix4() });
      }
    });
    this.components = components;
  }

  begin(): void {
    this.cursor = 0;
  }

  add(placement: Matrix4): void {
    if (this.cursor >= this.capacity) return;
    for (const component of this.components) {
      component.scratchMatrix.multiplyMatrices(placement, component.localMatrix);
      component.mesh.setMatrixAt(this.cursor, component.scratchMatrix);
    }
    this.cursor += 1;
  }

  commit(): void {
    for (const component of this.components) {
      component.mesh.count = this.cursor;
      component.mesh.instanceMatrix.needsUpdate = true;
    }
  }

  markDirty(): void {
    for (const component of this.components) component.mesh.instanceMatrix.needsUpdate = true;
  }
}

class ParticlePool {
  readonly mesh: InstancedMesh;
  private readonly particles: Particle[] = [];
  private readonly dummy = new Object3D();

  constructor(
    capacity: number,
    geometry: BufferGeometry,
    material: Material,
    destination: Group,
    name: string,
  ) {
    this.mesh = new InstancedMesh(geometry, material, capacity);
    this.mesh.name = name;
    this.mesh.instanceMatrix.setUsage(DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.castShadow = false;
    this.mesh.count = 0;
    destination.add(this.mesh);
  }

  emit(origin: Vector3, count: number, seed: number, dust = false): void {
    const available = this.mesh.instanceMatrix.count - this.particles.length;
    for (let index = 0; index < Math.min(count, available); index += 1) {
      const angle = hash01(seed + index * 7.17) * Math.PI * 2;
      const speed = dust ? 0.7 + hash01(seed + index * 2.1) : 2.1 + hash01(seed + index * 3.8) * 2;
      this.particles.push({
        position: origin.clone(),
        velocity: new Vector3(
          Math.cos(angle) * speed,
          dust ? 0.45 + hash01(seed + index) : 1.8 + hash01(seed + index) * 2.4,
          Math.sin(angle) * speed * (dust ? 0.45 : 1),
        ),
        life: dust ? 0.55 : 0.78,
        totalLife: dust ? 0.55 : 0.78,
        size: dust ? 0.08 + hash01(seed + index * 9) * 0.12 : 0.08 + hash01(seed + index * 9) * 0.1,
      });
    }
  }

  update(dt: number): void {
    let visible = 0;
    for (let index = this.particles.length - 1; index >= 0; index -= 1) {
      const particle = this.particles[index]!;
      particle.life -= dt;
      if (particle.life <= 0) {
        this.particles.splice(index, 1);
        continue;
      }
      particle.velocity.y -= 4.2 * dt;
      particle.position.addScaledVector(particle.velocity, dt);
    }
    for (const particle of this.particles) {
      const scale = particle.size * Math.max(0.15, particle.life / particle.totalLife);
      this.dummy.position.copy(particle.position);
      this.dummy.scale.setScalar(scale);
      this.dummy.updateMatrix();
      this.mesh.setMatrixAt(visible, this.dummy.matrix);
      visible += 1;
    }
    this.mesh.count = visible;
    this.mesh.instanceMatrix.needsUpdate = true;
  }

  clear(): void {
    this.particles.length = 0;
    this.mesh.count = 0;
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}

export class WorldRenderer {
  private readonly canvas: HTMLCanvasElement;
  private readonly assets: LoadedAssets;
  private readonly options: WorldRendererOptions;
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(53, 1, 0.1, 320);
  private readonly world = new Group();
  private readonly instances = new Group();
  private readonly particles = new Group();
  private readonly character: Group;
  private readonly poseProbe: CharacterPoseProbe | null;
  private readonly spinBall: Object3D;
  private readonly mixer: AnimationMixer;
  private readonly actions = new Map<CharacterActionName, AnimationAction>();
  private readonly ringTemplate: InstancedTemplate;
  private readonly sceneryTemplates = new Map<ForestPartName, InstancedTemplate>();
  private readonly obstaclePools: Record<ObstacleKind, ObstaclePool>;
  private readonly laneMarkers: InstancedMesh;
  private readonly directionalLight: DirectionalLight;
  private readonly sparkles: ParticlePool;
  private readonly dust: ParticlePool;
  private readonly placementDummy = new Object3D();
  private readonly lookTarget = new Vector3();
  private readonly emittedCoins = new Map<string, number>();
  private currentActionName: CharacterActionName | null = null;
  private lowEffects = false;
  private contextLost = false;
  private destroyed = false;
  private lastDistance = 0;
  private lastPlayerX = 0;
  private cameraBank = 0;
  private lastFrameTime = performance.now();
  private lastDustAt = 0;
  private spinRotation = 0;

  private readonly handleResize = (): void => this.resize();
  private readonly handleContextLost = (event: Event): void => {
    event.preventDefault();
    this.contextLost = true;
    this.options.onContextLost?.();
  };
  private readonly handleContextRestored = (): void => {
    if (this.destroyed) return;
    this.contextLost = false;
    this.renderer.resetState();
    this.ringTemplate.markDirty();
    this.sceneryTemplates.forEach((template) => template.markDirty());
    this.laneMarkers.instanceMatrix.needsUpdate = true;
    this.sparkles.mesh.instanceMatrix.needsUpdate = true;
    this.dust.mesh.instanceMatrix.needsUpdate = true;
    this.markTexturesDirty();
    this.resize();
    this.options.onContextRestored?.();
  };

  constructor(canvas: HTMLCanvasElement, assets: LoadedAssets, options: WorldRendererOptions = {}) {
    this.canvas = canvas;
    this.assets = assets;
    this.options = options;
    this.renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.16;
    this.renderer.setClearColor(0x64ded5, 0);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFShadowMap;

    this.scene.fog = new Fog(new Color(0x66d9cf), 42, 225);
    this.scene.add(this.world);
    this.world.add(this.instances, this.particles);

    this.directionalLight = this.createLighting();
    this.createGround();
    this.laneMarkers = this.createLaneMarkers();

    this.character = assets.character;
    this.character.name ||= 'SANIC_Character';
    const characterBounds = new Box3().setFromObject(this.character);
    const characterHeight = characterBounds.max.y - characterBounds.min.y;
    this.character.scale.multiplyScalar(
      uniformScaleForHeight(characterHeight, CHARACTER_WORLD_HEIGHT),
    );
    this.character.rotation.y = Math.PI;
    this.character.traverse((object) => {
      const mesh = object as Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    });
    this.poseProbe = createCharacterPoseProbe(
      this.character,
      this.options.enableTestProbes === true,
    );
    this.spinBall = assets.spinBall;
    this.spinBall.name ||= 'SANIC_SpinBall';
    const spinBounds = new Box3().setFromObject(this.spinBall);
    const spinSize = spinBounds.getSize(new Vector3());
    const spinMaximumDimension = Math.max(spinSize.x, spinSize.y, spinSize.z);
    this.spinBall.scale.multiplyScalar(
      uniformScaleForHeight(spinMaximumDimension, SPIN_BALL_WORLD_DIAMETER),
    );
    this.spinBall.rotation.y = Math.PI;
    this.spinBall.visible = false;
    this.spinBall.traverse((object) => {
      const mesh = object as Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    });
    this.world.add(this.character, this.spinBall);
    this.mixer = new AnimationMixer(this.character);
    for (const name of CHARACTER_ACTION_NAMES) {
      const clip = assets.animations.find((candidate) => candidate.name === name);
      if (!clip) continue;
      const action = this.mixer.clipAction(clip);
      action.enabled = true;
      action.clampWhenFinished = name === 'Crash' || name === 'Jump';
      action.setLoop(name === 'Crash' || name === 'Jump' ? LoopOnce : LoopRepeat, name === 'Crash' || name === 'Jump' ? 1 : Infinity);
      this.actions.set(name, action);
    }
    this.switchAnimation('Idle');

    this.ringTemplate = new InstancedTemplate(
      assets.ring,
      REQUIRED_POOL_CAPACITIES.rings,
      this.instances,
      false,
    );
    this.createSceneryTemplates();
    this.obstaclePools = {
      log: this.createObstaclePool('KIT_Log', 18),
      candle: this.createObstaclePool('KIT_Candle', 18),
      fud: this.createObstaclePool('KIT_FUD', 18),
      gap: this.createObstaclePool('KIT_Gap', 18),
    };

    const sparkleMaterial = new MeshStandardMaterial({
      color: 0xffdb24,
      emissive: 0xff8a00,
      emissiveIntensity: 2,
      metalness: 0.7,
      roughness: 0.2,
    });
    const dustMaterial = new MeshStandardMaterial({
      color: 0xd19a62,
      transparent: true,
      opacity: 0.62,
      roughness: 1,
      depthWrite: false,
    });
    this.sparkles = new ParticlePool(64, new SphereGeometry(1, 6, 5), sparkleMaterial, this.particles, 'SANIC_PickupSparkles');
    this.dust = new ParticlePool(48, new SphereGeometry(1, 6, 5), dustMaterial, this.particles, 'SANIC_RunDust');

    canvas.addEventListener('webglcontextlost', this.handleContextLost);
    canvas.addEventListener('webglcontextrestored', this.handleContextRestored);
    window.addEventListener('resize', this.handleResize, { passive: true });
    this.resize();
  }

  render(
    previous: Readonly<SimulationSnapshot>,
    current: Readonly<SimulationSnapshot>,
    alpha: number,
  ): void {
    if (this.destroyed) return;
    const now = performance.now();
    const dt = MathUtils.clamp((now - this.lastFrameTime) / 1_000, 0, 0.05);
    this.lastFrameTime = now;
    if (this.contextLost) return;

    const restarted = current.distance + 0.25 < this.lastDistance;
    if (restarted) this.snapForRestart(current);
    const from = restarted ? current : previous;
    const blend = MathUtils.clamp(alpha, 0, 1);
    const distance = MathUtils.lerp(from.distance, current.distance, blend);
    const playerX = MathUtils.lerp(from.playerX, current.playerX, blend);
    const playerY = MathUtils.lerp(from.playerY, current.playerY, blend);
    const jumpProgress = interpolateJumpProgress(
      from.jumpProgress,
      current.jumpProgress,
      blend,
    );

    this.character.position.set(playerX, playerY, 0);
    this.spinBall.position.set(playerX, playerY + 1.45, 0);
    this.updateAnimation(current, jumpProgress, dt);
    const showSpin = current.phase === 'playing'
      && jumpPresentation(jumpProgress) === 'spin';
    this.canvas.dataset.presentation = showSpin ? 'spin' : 'character';
    this.canvas.dataset.jumpProgress = jumpProgress === null
      ? 'none'
      : jumpProgress.toFixed(3);
    this.canvas.dataset.gamePhase = current.phase;
    this.spinRotation = nextSpinRotation(
      this.spinRotation,
      showSpin,
      current.speed,
      dt,
    );
    if (showSpin) {
      this.character.visible = false;
      this.spinBall.visible = true;
      this.spinBall.rotation.x = this.spinRotation;
    } else {
      this.resetSpinPresentation();
    }
    this.updateRings(current, distance);
    this.updateObstacles(current, distance);
    this.updateScenery(distance);
    this.updateLaneMarkers(distance);
    this.updatePickupEffects(from, current);
    this.updateDust(current, playerX, playerY);
    this.sparkles.update(dt);
    this.dust.update(dt);
    this.updateCamera(playerX, playerY, dt);

    this.renderer.render(this.scene, this.camera);
    this.lastDistance = current.distance;
    this.lastPlayerX = playerX;
  }

  resize(): void {
    if (this.destroyed) return;
    const width = Math.max(1, this.canvas.clientWidth || window.innerWidth || 1);
    const height = Math.max(1, this.canvas.clientHeight || window.innerHeight || 1);
    const mobile = width < 700;
    const dprCap = this.lowEffects ? 1 : mobile ? 1.5 : 1.75;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprCap));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.fov = mobile ? 61 : 53;
    this.camera.updateProjectionMatrix();
  }

  setLowEffects(enabled: boolean): void {
    if (this.destroyed || this.lowEffects === enabled) return;
    this.lowEffects = enabled;
    this.renderer.shadowMap.enabled = !enabled;
    this.directionalLight.castShadow = !enabled;
    if (enabled) this.dust.clear();
    this.resize();
  }

  completeCrashAnimation(): void {
    if (this.destroyed) return;
    const crash = this.actions.get('Crash');
    if (!crash) return;
    this.mixer.stopAllAction();
    crash.reset().setEffectiveWeight(1).play();
    crash.time = crash.getClip().duration;
    this.mixer.update(0);
    this.currentActionName = 'Crash';
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.canvas.removeEventListener('webglcontextlost', this.handleContextLost);
    this.canvas.removeEventListener('webglcontextrestored', this.handleContextRestored);
    window.removeEventListener('resize', this.handleResize);

    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.character);
    this.sparkles.clear();
    this.dust.clear();

    const geometries = new Set<BufferGeometry>();
    const materials = new Set<Material>();
    const textures = new Set<Texture>();
    const collect = (root: Object3D): void => {
      root.traverse((object) => {
        const mesh = object as Mesh;
        if (!mesh.isMesh) return;
        if (mesh.geometry) geometries.add(mesh.geometry);
        const meshMaterials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of meshMaterials) {
          if (!material) continue;
          materials.add(material);
          for (const value of Object.values(material as unknown as Record<string, unknown>)) {
            if (value && typeof value === 'object' && (value as Texture).isTexture) textures.add(value as Texture);
          }
        }
      });
    };
    collect(this.scene);
    collect(this.assets.ring);
    collect(this.assets.forest);
    textures.forEach((texture) => texture.dispose());
    materials.forEach((material) => material.dispose());
    geometries.forEach((geometry) => geometry.dispose());
    this.scene.clear();
    this.renderer.renderLists.dispose();
    this.renderer.dispose();
  }

  private createLighting(): DirectionalLight {
    const hemisphere = new HemisphereLight(0xbefcff, 0x27551f, 2.45);
    this.scene.add(hemisphere);

    const sun = new DirectionalLight(0xffd48a, 4.25);
    sun.position.set(-14, 24, 12);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1_024, 1_024);
    sun.shadow.camera.left = -13;
    sun.shadow.camera.right = 13;
    sun.shadow.camera.top = 16;
    sun.shadow.camera.bottom = -5;
    sun.shadow.camera.near = 2;
    sun.shadow.camera.far = 55;
    sun.shadow.bias = -0.00025;
    sun.target.position.set(0, 0, -16);
    this.scene.add(sun, sun.target);
    return sun;
  }

  private createGround(): void {
    const grassMaterial = new MeshStandardMaterial({ color: 0x159c42, roughness: 0.94 });
    const dirtMaterial = new MeshStandardMaterial({ color: 0xa76735, roughness: 0.98 });
    const verge = new Mesh(new PlaneGeometry(72, 420), grassMaterial);
    verge.name = 'SANIC_ForestFloor';
    verge.rotation.x = -Math.PI / 2;
    verge.position.set(0, -0.1, -155);
    verge.receiveShadow = true;
    this.world.add(verge);

    const road = new Mesh(new PlaneGeometry(15.4, 420), dirtMaterial);
    road.name = 'SANIC_GroundRibbon';
    road.rotation.x = -Math.PI / 2;
    road.position.set(0, -0.075, -155);
    road.receiveShadow = true;
    this.world.add(road);
  }

  private createLaneMarkers(): InstancedMesh {
    const geometry = new BoxGeometry(0.075, 0.025, 2.6);
    const material = new MeshStandardMaterial({
      color: 0xffe6a6,
      emissive: 0x4b2800,
      emissiveIntensity: 0.16,
      roughness: 0.72,
    });
    const markers = new InstancedMesh(geometry, material, 96);
    markers.name = 'SANIC_LaneMarkers';
    markers.instanceMatrix.setUsage(DynamicDrawUsage);
    markers.frustumCulled = false;
    markers.receiveShadow = true;
    this.instances.add(markers);
    return markers;
  }

  private createSceneryTemplates(): void {
    const capacities: Partial<Record<ForestPartName, number>> = {
      KIT_Tree_A: REQUIRED_POOL_CAPACITIES.trees / 2,
      KIT_Tree_B: REQUIRED_POOL_CAPACITIES.trees / 2,
      KIT_Grass: REQUIRED_POOL_CAPACITIES.grassAndFern / 2,
      KIT_Fern: REQUIRED_POOL_CAPACITIES.grassAndFern / 2,
      KIT_Rock: REQUIRED_POOL_CAPACITIES.rocksAndMushrooms / 2,
      KIT_Mushroom: REQUIRED_POOL_CAPACITIES.rocksAndMushrooms / 2,
      KIT_Sign_Stimmy: 4,
      KIT_Sign_Trenches: 4,
      KIT_Sign_Coping: 4,
      KIT_Sign_Memes: 4,
    };
    for (const name of FOREST_PART_NAMES) {
      const capacity = capacities[name];
      const root = this.assets.forestParts.get(name);
      if (!capacity || !root) continue;
      this.sceneryTemplates.set(name, new InstancedTemplate(root, capacity, this.instances, true));
    }
  }

  private createObstaclePool(name: ForestPartName, capacity: number): ObstaclePool {
    const source = this.assets.forestParts.get(name);
    if (!source) return { roots: [], used: 0 };
    source.traverse((object) => {
      const mesh = object as Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    });
    const roots = Array.from({ length: capacity }, (_, index) => {
      const clone = source.clone(true);
      clone.name = `${name}_Pool_${index}`;
      clone.visible = false;
      this.world.add(clone);
      return clone;
    });
    return { roots, used: 0 };
  }

  private switchAnimation(name: CharacterActionName): void {
    if (this.currentActionName === name) return;
    const next = this.actions.get(name);
    if (!next) return;
    const current = this.currentActionName ? this.actions.get(this.currentActionName) : undefined;
    next.reset().setEffectiveWeight(1).play();
    if (current) {
      current.paused = false;
      current.crossFadeTo(next, animationCrossfadeSeconds(name), false);
    }
    else next.fadeIn(0.1);
    this.currentActionName = name;
  }

  private updateAnimation(
    snapshot: Readonly<SimulationSnapshot>,
    jumpProgress: number | null,
    dt: number,
  ): void {
    const desired = characterActionFor(snapshot.phase, jumpProgress);
    this.canvas.dataset.characterAction = desired;
    this.switchAnimation(desired);
    this.actions.get('Run')?.setEffectiveTimeScale(runTimeScale(snapshot.speed, GAME.startSpeed));

    const jump = this.actions.get('Jump');
    if (jump) jump.paused = desired === 'Jump';
    this.mixer.update(Math.min(dt, 0.05));
    if (desired === 'Jump' && jumpProgress !== null && jump) {
      jump.time = jumpClipTime(jump.getClip().duration, jumpProgress);
      this.mixer.update(0);
    }
    this.updatePoseProbe();
  }

  private updatePoseProbe(): void {
    const probe = this.poseProbe;
    if (probe === null) return;
    this.character.updateMatrixWorld(true);
    const root = this.character.worldToLocal(
      probe.root.getWorldPosition(probe.rootPosition),
    );
    const hips = this.character.worldToLocal(
      probe.hips.getWorldPosition(probe.hipsPosition),
    );
    const chest = this.character.worldToLocal(
      probe.chest.getWorldPosition(probe.chestPosition),
    );
    const leftFoot = this.character.worldToLocal(
      probe.leftFoot.getWorldPosition(probe.leftFootPosition),
    );
    const rightFoot = this.character.worldToLocal(
      probe.rightFoot.getWorldPosition(probe.rightFootPosition),
    );
    const bodyLeanDegrees = MathUtils.radToDeg(
      Math.atan2(chest.z - hips.z, chest.y - hips.y),
    );
    this.canvas.dataset.poseProbe = [
      root.y,
      root.z,
      chest.y,
      chest.z,
      leftFoot.y,
      leftFoot.z,
      rightFoot.y,
      rightFoot.z,
      bodyLeanDegrees,
    ].map((value) => value.toFixed(5)).join(',');
  }

  private updateRings(snapshot: Readonly<SimulationSnapshot>, distance: number): void {
    this.ringTemplate.begin();
    for (let index = 0; index < snapshot.coins.length; index += 1) {
      const coin = snapshot.coins[index]!;
      const forward = coin.at - distance;
      if (forward < -12 || forward > 225) continue;
      const pulse = 0.84 + Math.sin(snapshot.elapsed * 7 + index * 0.7) * 0.055;
      this.placementDummy.position.set(coin.lane * GAME.laneWidth, coin.height, -forward);
      this.placementDummy.rotation.set(0, snapshot.elapsed * 4.8 + index * 0.21, 0);
      this.placementDummy.scale.setScalar(pulse);
      this.placementDummy.updateMatrix();
      this.ringTemplate.add(this.placementDummy.matrix);
    }
    this.ringTemplate.commit();
  }

  private updateObstacles(snapshot: Readonly<SimulationSnapshot>, distance: number): void {
    for (const pool of Object.values(this.obstaclePools)) {
      pool.used = 0;
      for (const root of pool.roots) root.visible = false;
    }
    for (const obstacle of snapshot.obstacles) {
      const forward = obstacle.at - distance;
      if (forward < -9 || forward > 210) continue;
      const pool = this.obstaclePools[obstacle.kind];
      const root = pool.roots[pool.used];
      if (!root) continue;
      pool.used += 1;
      root.visible = true;
      root.position.set(obstacle.lane * GAME.laneWidth, obstacle.kind === 'gap' ? 0.01 : 0, -forward);
      root.rotation.set(0, 0, 0);
      root.scale.setScalar(obstacle.kind === 'gap' ? 1.08 : 1);
      root.updateMatrix();
    }
  }

  private updateScenery(distance: number): void {
    this.sceneryTemplates.forEach((template) => template.begin());

    const treeCount = this.lowEffects ? 60 : REQUIRED_POOL_CAPACITIES.trees;
    const treeStart = Math.floor(distance / 5) - 6;
    for (let slot = 0; slot < treeCount; slot += 1) {
      const longitudinal = Math.floor(slot / 2);
      const segment = treeStart + longitudinal;
      const side = slot % 2 === 0 ? -1 : 1;
      const name: ForestPartName = segment % 2 === 0 ? 'KIT_Tree_A' : 'KIT_Tree_B';
      const x = side * (8.1 + hash01(segment * 11 + side) * 6.2);
      this.placeScenery(name, x, segment * 5 - distance, hash01(segment * 17 + side), 0.82, 1.38);
    }

    const foliageCount = this.lowEffects ? 150 : REQUIRED_POOL_CAPACITIES.grassAndFern;
    const foliageStart = Math.floor(distance / 1.7) - 10;
    for (let slot = 0; slot < foliageCount; slot += 1) {
      const longitudinal = Math.floor(slot / 2);
      const segment = foliageStart + longitudinal;
      const side = slot % 2 === 0 ? -1 : 1;
      const name: ForestPartName = segment % 2 === 0 ? 'KIT_Grass' : 'KIT_Fern';
      const x = side * (6.7 + hash01(segment * 23 + side) * 8.7);
      this.placeScenery(name, x, segment * 1.7 - distance, hash01(segment * 29 + side), 0.7, 1.22);
    }

    const detailCount = this.lowEffects ? 36 : REQUIRED_POOL_CAPACITIES.rocksAndMushrooms;
    const detailStart = Math.floor(distance / 7.5) - 4;
    for (let slot = 0; slot < detailCount; slot += 1) {
      const longitudinal = Math.floor(slot / 2);
      const segment = detailStart + longitudinal;
      const side = slot % 2 === 0 ? -1 : 1;
      const name: ForestPartName = segment % 2 === 0 ? 'KIT_Rock' : 'KIT_Mushroom';
      const x = side * (7.1 + hash01(segment * 31 + side) * 7.8);
      this.placeScenery(name, x, segment * 7.5 - distance, hash01(segment * 37 + side), 0.72, 1.25);
    }

    const signs: readonly ForestPartName[] = [
      'KIT_Sign_Stimmy',
      'KIT_Sign_Trenches',
      'KIT_Sign_Coping',
      'KIT_Sign_Memes',
    ];
    const signCycle = Math.floor(distance / 220) * 220;
    signs.forEach((name, index) => {
      for (let cycle = 0; cycle < 2; cycle += 1) {
        const at = signCycle + cycle * 220 + 34 + index * 43;
        const side = index % 2 === 0 ? -1 : 1;
        this.placeScenery(name, side * 8.3, at - distance, side < 0 ? 0.42 : 0.58, 0.92, 1.04);
      }
    });

    this.sceneryTemplates.forEach((template) => template.commit());
  }

  private placeScenery(
    name: ForestPartName,
    x: number,
    forward: number,
    rotationSeed: number,
    minScale: number,
    maxScale: number,
  ): void {
    const template = this.sceneryTemplates.get(name);
    if (!template || forward < -38 || forward > 275) return;
    const isSign = name.startsWith('KIT_Sign_');
    const scale = isSign ? minScale : MathUtils.lerp(minScale, maxScale, hash01(rotationSeed * 41));
    this.placementDummy.position.set(x, 0, -forward);
    this.placementDummy.rotation.set(0, isSign ? (x < 0 ? -0.24 : 0.24) : rotationSeed * Math.PI * 2, 0);
    this.placementDummy.scale.setScalar(scale);
    this.placementDummy.updateMatrix();
    template.add(this.placementDummy.matrix);
  }

  private updateLaneMarkers(distance: number): void {
    const first = Math.floor(distance / 6) * 6 - 18;
    let cursor = 0;
    for (let row = 0; row < 48; row += 1) {
      const at = first + row * 6;
      for (const x of [-GAME.laneWidth / 2, GAME.laneWidth / 2]) {
        this.placementDummy.position.set(x, -0.045, -(at - distance));
        this.placementDummy.rotation.set(0, 0, 0);
        this.placementDummy.scale.copy(UNIT_SCALE);
        this.placementDummy.updateMatrix();
        this.laneMarkers.setMatrixAt(cursor, this.placementDummy.matrix);
        cursor += 1;
      }
    }
    this.laneMarkers.count = cursor;
    this.laneMarkers.instanceMatrix.needsUpdate = true;
  }

  private updatePickupEffects(
    previous: Readonly<SimulationSnapshot>,
    current: Readonly<SimulationSnapshot>,
  ): void {
    const minimumRenderedDistance = current.distance - RING_RENDER_BEHIND_DISTANCE;
    for (const [id, distance] of this.emittedCoins) {
      if (distance < minimumRenderedDistance) this.emittedCoins.delete(id);
    }

    let pickups = Math.max(0, current.rings - previous.rings);
    if (pickups === 0) return;
    const currentIds = new Set(current.coins.map((coin) => coin.id));
    const removed = previous.coins
      .filter((coin) => !currentIds.has(coin.id) && !this.emittedCoins.has(coin.id))
      .sort((left, right) => Math.abs(left.at - current.distance) - Math.abs(right.at - current.distance));
    for (const coin of removed) {
      if (pickups <= 0) break;
      this.emittedCoins.set(coin.id, coin.at);
      const origin = new Vector3(
        coin.lane * GAME.laneWidth,
        coin.height,
        -(coin.at - current.distance),
      );
      this.sparkles.emit(origin, this.lowEffects ? 4 : 10, current.rings * 13.7 + coin.at);
      pickups -= 1;
    }
  }

  private updateDust(snapshot: Readonly<SimulationSnapshot>, playerX: number, playerY: number): void {
    if (this.lowEffects || snapshot.phase !== 'playing' || playerY > 0.12) return;
    if (snapshot.elapsed - this.lastDustAt < 0.075) return;
    this.lastDustAt = snapshot.elapsed;
    this.dust.emit(new Vector3(playerX, 0.08, 0.5), 2, snapshot.elapsed * 100, true);
  }

  private updateCamera(playerX: number, playerY: number, dt: number): void {
    const mobile = (this.canvas.clientWidth || window.innerWidth) < 700;
    const laneVelocity = dt > 0 ? (playerX - this.lastPlayerX) / dt : 0;
    const targetBank = this.lowEffects ? 0 : MathUtils.clamp(-laneVelocity * 0.007, -0.055, 0.055);
    this.cameraBank = MathUtils.lerp(this.cameraBank, targetBank, 1 - Math.exp(-dt * 10));
    const quarterX = mobile ? 2.25 : 3.45;
    this.camera.position.set(quarterX + playerX * 0.13, 4.25 + playerY * 0.1, mobile ? 9.9 : 9.1);
    this.lookTarget.set(playerX * 0.2, 1.65 + playerY * 0.18, mobile ? -8.5 : -10.5);
    this.camera.lookAt(this.lookTarget);
    this.camera.rotation.z += this.cameraBank;
  }

  private snapForRestart(snapshot: Readonly<SimulationSnapshot>): void {
    this.emittedCoins.clear();
    this.sparkles.clear();
    this.dust.clear();
    this.lastDustAt = snapshot.elapsed;
    this.lastPlayerX = snapshot.playerX;
    this.cameraBank = 0;
    for (const pool of Object.values(this.obstaclePools)) {
      pool.used = 0;
      for (const root of pool.roots) root.visible = false;
    }
    this.currentActionName = null;
    this.actions.forEach((action) => action.stop());
    this.resetSpinPresentation();
  }

  private resetSpinPresentation(): void {
    this.spinRotation = 0;
    this.spinBall.rotation.x = 0;
    this.spinBall.visible = false;
    this.character.visible = true;
  }

  private markTexturesDirty(): void {
    const visited = new Set<Texture>();
    const scan = (root: Object3D): void => {
      root.traverse((object) => {
        const mesh = object as Mesh;
        if (!mesh.isMesh) return;
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of materials) {
          if (!material) continue;
          for (const value of Object.values(material as unknown as Record<string, unknown>)) {
            if (!value || typeof value !== 'object' || !(value as Texture).isTexture) continue;
            const texture = value as Texture;
            if (visited.has(texture)) continue;
            visited.add(texture);
            texture.needsUpdate = true;
          }
        }
      });
    };
    scan(this.scene);
    scan(this.assets.ring);
    scan(this.assets.forest);
  }
}
