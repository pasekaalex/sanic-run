export const BRAND = Object.freeze({
  name: '$SANIC',
  tagline: 'I LOVE TO GO FAST',
  contract: 'CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump',
  pumpUrl: 'https://pump.fun/coin/CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump',
  xUrl: 'https://x.com/memesofsanic',
  disclosure: '$SANIC is a memecoin made for entertainment. No utility, no promises, no financial advice. Verify the contract and only risk what you can afford to lose. Not affiliated with or endorsed by Ansem, SEGA, or Sonic the Hedgehog.',
});

export const GAME = Object.freeze({
  lanes: [-1, 0, 1] as const,
  laneWidth: 3.2,
  fixedStep: 1 / 60,
  startSpeed: 18,
  maxSpeed: 36,
  ringScore: 100,
  ringsPerMultiplier: 10,
  maxMultiplier: 5,
  spawnAhead: 190,
  zoneTransitionSeconds: 2.4,
});

export const ASSET_URLS = Object.freeze({
  character: '/models/sanic-runner.glb',
  spinBall: '/models/sanic-spin-ball.glb',
  ring: '/models/sanic-ring.glb',
  forest: '/models/forest-kit.glb',
  promo: '/media/sanic-game-promo.png',
  scoreCard: '/media/sanic-score-card-bg.png',
});
