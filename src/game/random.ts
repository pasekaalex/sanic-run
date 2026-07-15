const UINT32_RANGE = 0x1_0000_0000;
const NONZERO_FALLBACK_SEED = 0x9e37_79b9;

export class XorShift32 {
  private state: number;

  constructor(seed: number) {
    const normalizedSeed = seed >>> 0;
    this.state = normalizedSeed === 0 ? NONZERO_FALLBACK_SEED : normalizedSeed;
  }

  next(): number {
    let value = this.state;
    value ^= value << 13;
    value ^= value >>> 17;
    value ^= value << 5;
    this.state = value >>> 0;
    return this.state / UINT32_RANGE;
  }

  pick<T>(items: readonly T[]): T {
    if (items.length === 0) throw new RangeError('Cannot pick from an empty collection');
    return items[Math.floor(this.next() * items.length)]!;
  }
}
