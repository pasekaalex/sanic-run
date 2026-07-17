import {
  type AnimationAction,
  type Group,
  MathUtils,
  type Object3D,
  Vector3,
} from 'three';
import type { CharacterActionName } from './assetLoader';

export type CharacterPoseProbeUpdater = (
  actionName: CharacterActionName,
  action: AnimationAction | undefined,
) => void;

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

export const createCharacterPoseProbeUpdater = (
  canvas: HTMLCanvasElement,
  character: Group,
): CharacterPoseProbeUpdater => {
  const root = character.getObjectByName('root');
  const hips = character.getObjectByName('hips');
  const chest = character.getObjectByName('chest');
  const leftFoot = character.getObjectByName('footL');
  const rightFoot = character.getObjectByName('footR');
  if (!root || !hips || !chest || !leftFoot || !rightFoot) {
    return (): void => undefined;
  }
  const probe: CharacterPoseProbe = {
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

  return (actionName, action): void => {
    character.updateMatrixWorld(true);
    const rootPosition = character.worldToLocal(
      probe.root.getWorldPosition(probe.rootPosition),
    );
    const hipsPosition = character.worldToLocal(
      probe.hips.getWorldPosition(probe.hipsPosition),
    );
    const chestPosition = character.worldToLocal(
      probe.chest.getWorldPosition(probe.chestPosition),
    );
    const leftFootPosition = character.worldToLocal(
      probe.leftFoot.getWorldPosition(probe.leftFootPosition),
    );
    const rightFootPosition = character.worldToLocal(
      probe.rightFoot.getWorldPosition(probe.rightFootPosition),
    );
    const bodyLeanDegrees = MathUtils.radToDeg(
      Math.atan2(
        chestPosition.z - hipsPosition.z,
        chestPosition.y - hipsPosition.y,
      ),
    );
    canvas.dataset.poseProbe = [
      rootPosition.y,
      rootPosition.z,
      chestPosition.y,
      chestPosition.z,
      leftFootPosition.y,
      leftFootPosition.z,
      rightFootPosition.y,
      rightFootPosition.z,
      bodyLeanDegrees,
    ].map((value) => value.toFixed(5)).join(',');
    canvas.dataset.characterAction = actionName;
    canvas.dataset.characterActionTime = action?.time.toFixed(5) ?? 'missing';
    canvas.dataset.characterActionDuration = action?.getClip().duration.toFixed(5) ?? 'missing';
  };
};
