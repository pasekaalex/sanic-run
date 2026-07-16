const SPIN_SPEED_FACTOR = 0.42;

export const nextSpinRotation = (
  currentRotation: number,
  showSpin: boolean,
  speed: number,
  deltaSeconds: number,
): number => showSpin
  ? currentRotation - speed * deltaSeconds * SPIN_SPEED_FACTOR
  : 0;
