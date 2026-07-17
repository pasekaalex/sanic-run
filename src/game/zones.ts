import { GAME } from '../config';

export type ZoneId = 'ringwood-rush' | 'liquidity-loop' | 'ansem-after-dark';

export interface ZoneDefinition {
  readonly id: ZoneId;
  readonly stage: 1 | 2 | 3;
  readonly stageLabel: string;
  readonly zoneLabel: string;
  readonly actLabel: 'ACT 1';
  readonly startDistance: number;
  readonly endDistance: number;
  readonly startSpeed: number;
  readonly endSpeed: number;
  readonly speedEndDistance: number;
}

const freezeZone = (zone: ZoneDefinition): Readonly<ZoneDefinition> => Object.freeze(zone);

export const ZONES = Object.freeze([
  freezeZone({
    id: 'ringwood-rush',
    stage: 1,
    stageLabel: 'STAGE 01',
    zoneLabel: 'RINGWOOD RUSH',
    actLabel: 'ACT 1',
    startDistance: 0,
    endDistance: 840,
    startSpeed: GAME.startSpeed,
    endSpeed: 24,
    speedEndDistance: 840,
  }),
  freezeZone({
    id: 'liquidity-loop',
    stage: 2,
    stageLabel: 'STAGE 02',
    zoneLabel: 'LIQUIDITY LOOP',
    actLabel: 'ACT 1',
    startDistance: 840,
    endDistance: 1_960,
    startSpeed: 24,
    endSpeed: 32,
    speedEndDistance: 1_960,
  }),
  freezeZone({
    id: 'ansem-after-dark',
    stage: 3,
    stageLabel: 'STAGE 03',
    zoneLabel: 'ANSEM AFTER DARK',
    actLabel: 'ACT 1',
    startDistance: 1_960,
    endDistance: Number.POSITIVE_INFINITY,
    startSpeed: 32,
    endSpeed: GAME.maxSpeed,
    speedEndDistance: 2_520,
  }),
] as const satisfies readonly Readonly<ZoneDefinition>[]);

const normalizedDistance = (distance: number): number => {
  if (Number.isNaN(distance) || distance <= 0) return 0;
  return distance;
};

export const zoneAtDistance = (distance: number): Readonly<ZoneDefinition> => {
  const normalized = normalizedDistance(distance);
  return ZONES.find((zone) => normalized < zone.endDistance) ?? ZONES.at(-1)!;
};

export const speedAtDistance = (distance: number): number => {
  const normalized = normalizedDistance(distance);
  const zone = zoneAtDistance(normalized);
  const rampLength = zone.speedEndDistance - zone.startDistance;
  const progress = rampLength <= 0
    ? 1
    : Math.max(0, Math.min(1, (normalized - zone.startDistance) / rampLength));
  return zone.startSpeed + (zone.endSpeed - zone.startSpeed) * progress;
};
