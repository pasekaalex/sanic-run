# $SANIC Runner

Playable Three.js coin runner for `$SANIC`.

- Live: https://sanic-run.vercel.app
- Source: https://github.com/pasekaalex/sanic-run
- X: https://x.com/memesofsanic
- Pump.fun: https://pump.fun/coin/CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump
- Contract: `CMNDT7PK5gHY8ZknhzEC2Q7UMDs2b7LT6c1eX7Kepump`

## Local development

```bash
npm ci
npm run dev
npm test
npm run build
npx playwright test
```

Run the production build locally with `npm run preview`. Deploy the linked project directly with:

```bash
vercel --prod --yes
```

## Original 3D assets

The reproducible Blender sources are `blender/sanic-source.blend` and `blender/world-source.blend`. Rebuild and validate them with Blender 5.1+:

```bash
blender --background --python blender/scripts/build_sanic.py
blender --background --python blender/scripts/build_world.py
blender --background blender/sanic-source.blend --python blender/scripts/validate_assets.py -- character
blender --background blender/world-source.blend --python blender/scripts/validate_assets.py -- world
```

Web exports live in `public/models/`. Launch art is `public/media/sanic-game-promo.png`; the generated social card is `public/media/sanic-og.jpg`; the runtime score-card background is `public/media/sanic-score-card-bg.png`.

## Deployment

The canonical repository is https://github.com/pasekaalex/sanic-run. Production is hosted by Vercel at https://www.sanic.fun.
