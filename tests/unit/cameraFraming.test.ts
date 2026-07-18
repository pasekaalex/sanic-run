import { describe, expect, it } from 'vitest';
import { cameraFramingForViewport } from '../../src/render/cameraFraming';

describe('cameraFramingForViewport', () => {
  it('zooms out portrait mobile viewports', () => {
    expect(cameraFramingForViewport(390, 844)).toEqual({
      fov: 66,
      lateralOffset: 2.25,
      cameraZ: 11.4,
      lookTargetZ: -8.5,
    });
    expect(cameraFramingForViewport(699, 900)).toEqual({
      fov: 66,
      lateralOffset: 2.25,
      cameraZ: 11.4,
      lookTargetZ: -8.5,
    });
  });

  it('preserves narrow-landscape framing', () => {
    expect(cameraFramingForViewport(667, 375)).toEqual({
      fov: 61,
      lateralOffset: 2.25,
      cameraZ: 9.9,
      lookTargetZ: -8.5,
    });
  });

  it('preserves framing at and above the desktop breakpoint', () => {
    const desktop = {
      fov: 53,
      lateralOffset: 3.45,
      cameraZ: 9.1,
      lookTargetZ: -10.5,
    };

    expect(cameraFramingForViewport(700, 900)).toEqual(desktop);
    expect(cameraFramingForViewport(844, 390)).toEqual(desktop);
    expect(cameraFramingForViewport(1440, 900)).toEqual(desktop);
  });

  it('normalizes invalid dimensions to a safe portrait viewport', () => {
    const portraitMobile = {
      fov: 66,
      lateralOffset: 2.25,
      cameraZ: 11.4,
      lookTargetZ: -8.5,
    };

    expect(cameraFramingForViewport(0, 0)).toEqual(portraitMobile);
    expect(cameraFramingForViewport(Number.NaN, Number.NEGATIVE_INFINITY)).toEqual(
      portraitMobile,
    );
  });
});
