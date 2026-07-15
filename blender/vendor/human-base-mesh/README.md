# Blender Studio Human Base Mesh provenance

`body-male-realistic-cc0.blend` is a project-local isolation of one object from
the Blender Studio Human Base Meshes bundle. The full bundle is not copied into
this repository.

- Version: `1.4.1`
- License: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Official demo page: https://www.blender.org/download/demo-files/
- Direct archive: https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip
- Archive SHA-256: `811f43accbb31a88266d932f8f5563b2d13586fca0ba2693aad1f5fe582b3515`
- Selected source object: `GEO-body_male_realistic`
- Embedded collection author: `Dan Ulrich`
- Embedded collection description: `Realistic scan data model with multiresolution details`
- Prepared object: `SANIC_CC0_MaleBase`

The official demo page identifies Human Base Meshes v1.4.1 as CC0. Rebuild the
trimmed source with Blender 4.2 LTS or newer (the project currently uses Blender
5.1) after downloading and verifying the archive:

```bash
blender --background --python-exit-code 1 \
  --python blender/scripts/prepare_human_base.py -- \
  /tmp/sanic-human-base/v1.4.1/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend \
  blender/vendor/human-base-mesh/body-male-realistic-cc0.blend
```

The preparation script uses an exact normalized-name selector, discards the
asset-library layout offset and unrelated datablocks, retains the source mesh's
Multires data, and records the provenance properties used by the SANIC asset
validator.
