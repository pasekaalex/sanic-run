import type { GamePhase } from '../game/types';
import type { CharacterActionName } from './assetLoader';

export type JumpPresentation = 'character' | 'spin';

export const characterActionFor = (
  phase: GamePhase,
  jumpProgress: number | null,
): CharacterActionName => {
  if (phase === 'gameOver') return 'Crash';
  if (phase !== 'playing') return 'Idle';
  return jumpProgress === null ? 'Run' : 'Jump';
};

export const jumpClipTime = (duration: number, progress: number): number => {
  const safeDuration = Number.isFinite(duration) ? Math.max(0, duration) : 0;
  const safeProgress = Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : 0;
  return safeDuration * safeProgress;
};

export const jumpStarted = (
  previousProgress: number | null,
  currentProgress: number | null,
): boolean => previousProgress === null && currentProgress !== null;

export const jumpPresentation = (progress: number | null): JumpPresentation => {
  if (progress === null || !Number.isFinite(progress)) return 'character';
  return progress >= 0.16 && progress <= 0.82 ? 'spin' : 'character';
};

export const animationCrossfadeSeconds = (action: CharacterActionName): number => {
  if (action === 'Crash') return 0.08;
  if (action === 'Jump') return 0.035;
  return 0.14;
};

export const interpolateJumpProgress = (
  previousProgress: number | null,
  currentProgress: number | null,
  alpha: number,
): number | null => {
  if (currentProgress === null) return previousProgress === null ? null : 1;
  if (previousProgress === null) return currentProgress;
  const blend = Number.isFinite(alpha) ? Math.max(0, Math.min(1, alpha)) : 0;
  return previousProgress + (currentProgress - previousProgress) * blend;
};
