export interface CameraFraming {
  readonly fov: number;
  readonly lateralOffset: number;
  readonly cameraZ: number;
  readonly lookTargetZ: number;
}

const PORTRAIT_MOBILE: Readonly<CameraFraming> = Object.freeze({
  fov: 66,
  lateralOffset: 2.25,
  cameraZ: 11.4,
  lookTargetZ: -8.5,
});

const NARROW_LANDSCAPE: Readonly<CameraFraming> = Object.freeze({
  fov: 61,
  lateralOffset: 2.25,
  cameraZ: 9.9,
  lookTargetZ: -8.5,
});

const DESKTOP: Readonly<CameraFraming> = Object.freeze({
  fov: 53,
  lateralOffset: 3.45,
  cameraZ: 9.1,
  lookTargetZ: -10.5,
});

const safeDimension = (value: number): number =>
  Number.isFinite(value) && value > 0 ? value : 1;

export const cameraFramingForViewport = (
  width: number,
  height: number,
): Readonly<CameraFraming> => {
  const safeWidth = safeDimension(width);
  const safeHeight = safeDimension(height);

  if (safeWidth >= 700) return DESKTOP;
  if (safeHeight >= safeWidth) return PORTRAIT_MOBILE;
  return NARROW_LANDSCAPE;
};
