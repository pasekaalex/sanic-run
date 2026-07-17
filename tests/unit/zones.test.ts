import { describe, expect, it } from 'vitest';
import { ZONES, speedAtDistance, zoneAtDistance } from '../../src/game/zones';

describe('zone progression', () => {
  it('selects the three immutable zones at exact distance boundaries', () => {
    expect([
      zoneAtDistance(-1).id,
      zoneAtDistance(0).id,
      zoneAtDistance(839.999).id,
      zoneAtDistance(840).id,
      zoneAtDistance(1_959.999).id,
      zoneAtDistance(1_960).id,
      zoneAtDistance(20_000).id,
    ]).toEqual([
      'ringwood-rush',
      'ringwood-rush',
      'ringwood-rush',
      'liquidity-loop',
      'liquidity-loop',
      'ansem-after-dark',
      'ansem-after-dark',
    ]);

    expect(ZONES.map(({ stageLabel, zoneLabel, actLabel }) => ({
      stageLabel,
      zoneLabel,
      actLabel,
    }))).toEqual([
      { stageLabel: 'STAGE 01', zoneLabel: 'RINGWOOD RUSH', actLabel: 'ACT 1' },
      { stageLabel: 'STAGE 02', zoneLabel: 'LIQUIDITY LOOP', actLabel: 'ACT 1' },
      { stageLabel: 'STAGE 03', zoneLabel: 'ANSEM AFTER DARK', actLabel: 'ACT 1' },
    ]);
    expect(Object.isFrozen(ZONES)).toBe(true);
    expect(ZONES.every(Object.isFrozen)).toBe(true);
  });

  it('uses one continuous monotonic curve through all zone speed anchors', () => {
    expect([
      speedAtDistance(-100),
      speedAtDistance(0),
      speedAtDistance(840),
      speedAtDistance(1_960),
      speedAtDistance(2_520),
      speedAtDistance(20_000),
    ]).toEqual([18, 18, 24, 32, 36, 36]);

    const samples = Array.from({ length: 401 }, (_, index) => speedAtDistance(index * 10));
    expect(samples.every((speed, index) => (
      index === 0 || speed >= samples[index - 1]!
    ))).toBe(true);
  });
});
