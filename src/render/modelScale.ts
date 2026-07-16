export const uniformScaleForHeight = (height: number, targetHeight: number): number => {
  if (!Number.isFinite(height) || height <= 0) return 1;
  if (!Number.isFinite(targetHeight) || targetHeight <= 0) return 1;
  return targetHeight / height;
};
