# Aitela, Laiwanting and Saixi: verified offline findings

Project: AnimeModelReplacement, 2026-10-22.
Evidence lives under tools/model-work/endfield_batch/wave3_delivery_audit.json
and the per-character audit reports. This work was integrated into the workspace,
not deployed or tested in the retail game. Original blend and PMX SHA256s were
checked unchanged. The findings below are source-specific, not universal presets.

## Source materials and native normal frames

- Aitela's Fur slot is actual head material; retain it with a separate surface
  response. Laiwanting slot14 Cloth1Alpha is physically opaque in the inspected
  source UV/alpha field; an Alpha name alone must not force card rendering.
- Saixi's stocking Cloth1 graph selects Z1_r_albedo; choosing only Z0_r_albedo
  misses the source output. Inspect the connected source graph, not just texture
  filename suffixes. The converter now accepts this explicitly selected output.
- Saixi emitted three zero-length corner normals in material11 in both body
  and arms. The exact upstream cause was not established. Native half-float
  octahedral bitangents became NaN, despite an apparently plausible static mesh.
  Float64 tangent projection alone did not fix the invalid input normal.
- Stabilize only invalid/nonfinite corner normals using valid same-triangle
  normals, then the geometric face direction. Reject completely degenerate
  triangles. Keep valid authored normals unchanged. Guard normal, tangent and
  cross-product lengths before octahedral encoding; reject nonfinite packed
  directions. Inspect the serialized float16 fields and decoded TBN dot errors.
  The checked models stay below .015 for normal/tangent and normal/bitangent
  dot errors and retain positive bounding sphere margins.

## Original hands, MMR and engine contacts

- Each source has 32 original wrist/digit correspondences. Preserve their
  skinning and use source-owner MMR evaluation before native surface fitting;
  compare the matching surface path in Daniya, Qianxia and Aimisi.
- A very short independent MMR calibration edit bone, located far from the
  origin, lost roll precision when Blender reconstructed its matrix. For this
  batch, set its display length to .15 before assigning the calibrated matrix.
  This is an offline helper length; never extend source joints or exported
  phalanges to solve that numerical problem. Check the evaluated matrices.
- 1P retains all40 native hand/metacarpal drivers and engine links. Selected
  source-length 3P profiles retain native wrist/palm/digit-root contacts while
  the20 middle/distal phalanges use rest-aware local FK at source lengths.
  Do not change these valid profiles just to satisfy an old audit demanding
  all40 3P joints use native positions. Instead verify the exceptions are only
  actual distal joints, with unit motion gain, and test their rotation/length
  transfer in production Lua. Equipment remains owned by the engine.
- Source actions did not provide usable original hand-animation clips.
  Seven MMR probes and22 synthetic pose cases/440 frames are offline evidence,
  not a guarantee of every live weapon grip or source-game animation fidelity.

## Controller, portraits and test integration

- Add a provider to descriptor registration, model definitions and localization
  together. Human and cryptic breed support must agree in both controller and
  provider; a working provider alone cannot bypass controller exclusion.
- The three screenshot identities were explicitly selected by the user. Keep
  hats, horns and ears; inset segmentation foreground seeds to avoid dragging
  gray background stripes into thin silhouette gaps. Retain source/crop hashes.
  Compare RGB only where alpha is nonzero: this project's matte writer clears
  RGB at fully transparent pixels. Resizing and BC3 compression are separate
  processing stages, not face repainting.
- Compile512x512 BC3 sRGB portraits into both primary texture and data stream,
  register both artifacts, and mirror them into the matching candidate manifests.
  Unit SHA256 must remain unchanged. Inspect independent native top-mip readback
  and decoded alpha, rather than displaying only the source PNG.
- Portrait resources have suffix portrait and the same0x6bd03744 footer profile
  as bca. Extend a closed texture-audit suffix map explicitly; do not skip new
  textures when the old audit raises KeyError. Supply CLASS and hook stubs when
  an integration harness loads the real controller; preserve production code.
- HUD routing was exercised for12 screenshot providers x6 classes with async
  callbacks, native status/frame preservation and restore on disable/unload.
  The combined scene lifecycle test covered19 providers; equipment ownership
  tests covered the16 providers that actually contain weapon_links.lua.
  These mocks do not establish actual game render or animation appearance.
