# EFMI outfits: source geometry and optional Darktide costumes

Verified source: `Si Ink Mist base 3.2` by AzNxde. Converter:
`AnimeModelReplacement/tools/model-work/convert_si_ink_mist.py`.
These are findings from this package, not a universal 3Dmigoto layout.

## Recover draws before fitting skin

- An EFMI INI describes draw ranges, UV-mode overrides and mutually exclusive
  clothing options. Export only the selected default ranges; concatenating the
  entire index buffer can include overlapping variants and the source weapon.
  The reference-matched conversion restores 27 draws (25 outfit + 2 ink FX) and excludes the source-game
  static weapon/back object and optional recolored long-hair shell
  (20418 indices at 185049). The original Si hair is already retained; importing
  the extra shell produces overlapping hair/back surfaces. Darktide remains
  the equipment owner.
- Component3/5 VB0 has stride 16: float XYZ plus packed octahedral normal/tangent.
  Indices are uint32; other components can be uint16. VB1 starts with float2 UV,
  often stride 12. An alternate sleeves UV buffer only covers a prefix; its
  stride cannot be deduced from total component vertex count.
- VB2's usual stride is 16: four uint16 normalized weights and four uint16
  palette entries. These are merged draw-palette IDs, **not MMD bone IDs**.
  This package supplies no skeleton or original gesture animations. Nearest
  source-surface skin transfer must be labeled as an approximation, with
  distances and explicit remaps recorded separately from recovered geometry.
- The raw DDS UV convention and INI's per-mode scale/offset must both be
  reversed. Blender uses V=1-V; the native exporter reverses V once again.
  Compare an unlit source UV diagnostic with a compiled-resource preview to
  distinguish UV errors from skinning or PBR issues.

## Recover shader channels and cutouts from evidence

- In this package INI `ps-t17/18/19` means diffuse / metallic-smoothness /
  normal. This differs from the shaded CMB source graph's filename order.
  `hlsl/p1.hlsl` lines 498-528 explicitly derive roughness as `1-t18.A`
  and normal XY as `(t19.R*t19.A,t19.G)*2-1`. Read data maps as Non-Color,
  channel-packed; reverse normal green with the native V convention.
  Swapping the parameter and normal maps caused broken highlights and wet skin.
- The bare-body draw supplies diffuse16 + normal17, with no metallic map.
  Do not reuse a garment's smoothness/metallic map on skin. The native adaptation
  uses dielectric body ORM `(AO=1, roughness=.64, metallic=0)`; current native
  art adaptation separates black brocade (`.48` roughness floor, `.18` metal
  cap), silver satin (`.36/.42`) and metal accessories (`.29/.95`). Skin normal
  XY amplitude is reduced to `.25` of the decoded map.
  Those values are explicit art choices, not recovered original shader values.
- Nominally opaque garment modes `x245=100262/100264` still alpha-test
  diffuse at `.5` (`p1.hlsl` lines 189-249). Ignoring this left black atlas
  rectangles on collars, sleeve hems and the back. Keep their cutouts too.
  Source blended lace uses an explicitly adapted `.15` threshold here; this
  is not source alpha truth.
- The October 21 game test showed the entire outfit disappearing after all
  C3 garments were classified as Alpha. Resource registration, byte-for-byte
  deployment and Blender previews had passed, and the session logged no missing
  outfit resource. Do not treat packaging a copied hair Alpha provider as proof
  that it will render physical clothing. Preserve the proven `substance_basic`
  path for this outfit. `si_ink_mist_cutouts.py` now clips source UV masks into
  garment boundary geometry and interpolates source normals/skin weights.
  This approximates lace openings geometrically; it does not reproduce blended
  translucent fabric or prove the new build's in-game appearance.
- Boundary refinement has a finite native budget: this carrier has 31 chunks,
  uint16 geometry indices, and at most 21845 expanded single-sided triangles
  per chunk (10922 when the exporter doubles an Alpha card). Reserve minimum
  chunks from those bounds before distributing spare slots; proportional-only
  allocation can overflow a large garment group. Avoid refining an entire
  narrow UV triangle just because its rectangular bounds touch another island.
- Respect source `cull=none` with reverse faces and reversed normals where the
  native shader lacks two-sided rendering. Verify compiled textures/streams,
  rather than treating the restored Blender material alone as final output.

## Preserve head accessories and uncovered limbs

- Keeping only face/eye/hair material slots omitted Si's two horns and other
  head ornaments. Component0/6 vertices match the original shaded MMD exactly
  within 2e-6 source units. Retain matching original polygons with their source
  UVs/materials; do not fabricate horns or treat missing geometry as lighting.
  Both horns are visible in the corrected compiled front/back previews.
- Original Si has no complete arm skin under her old sleeves. The current
  reference shows bare hands and legs: exclude the optional white-stocking
  C3 draw (20472 indices at 312024), remove the original blue glove surface,
  and retain the continuous C5 forearm/hand. Fit the original source skeleton
  to that surface before MMR/native-contact adaptation. This replaces the
  earlier glove-plus-wrist-seam approach; inspect native posed closeups.
- Preserve C5's authored finger weights after verifying merged palette
  identities against the fitted original source skin field. Nearest-surface
  transfer alone can blend adjacent fingers across the web. This package's
  36 verified wrist/finger correspondences are in `si_ink_mist/conversion.json`.
  Do not generalize the raw palette IDs to another package. Recalculate hand
  normals after fitted-surface adaptation, rather than applying separate
  per-bone normal frames to an already fitted hand.
- New hanging cloth can inherit nearby source hand/finger weights during
  surface transfer. Reject such accidental influences when the original draw's
  arm palette shows no arm influence; inspect posed sleeves, not only rest mesh.
- Transfer new uncovered skin only from the original skin material's surface.
  Reject hair/ear/cloth donor weights on skin, and hair/ear weights on clothing.
  Global nearest-surface transfer contaminated 806 imported vertices with hair
  influences. Ear-side sway then pulled neck/skin and fitted bodice surfaces.
  Fit close chest skin and its bodice to the same chest anchor, feathering into
  waist/neck; retain actual hanging-cloth motion elsewhere. Check the final
  serialized palette weights too, after exporter remapping and quantization.
  Zero hair palette mass proves isolation from hair-only motion, not correctness
  under every full-body animation.
- Hidden Blender main objects can silently fail `object.join`. Unhide/select
  the intended active mesh and assert joined vertex count. Rebind missing image
  paths to verified embedded same-name images, not arbitrary available images.
- A template's geometry-slot budget is finite. Merge draws with identical
  diffuse/normal/packed/alpha material identities into slots; do not drop parts.

## Hair replacement and separate ink FX carriers

- `CommandList034` replaces hair diffuse with Resource373 / `Tex/59.dds`.
  On the retained MMD hair topology this atlas needs a vertical flip. Use the
  replacement texture without importing a duplicate long-hair shell. The
  exporter selects diffuse images by `_D.` / `_D_AOff.` names; a replacement
  named only `hair_reference.png` silently fell back to white. Assert the
  selected image identity, dimensions and nonconstant pixel variance, then
  inspect the compiled texture and render.
- The back ink shapes are separate Component9 / Component11 FX carriers,
  totalling 1868 source triangles. Unlike garment C3/C5, their indices are
  uint16, VB1 is stride20 (leading float2 UV), and VB2 stride8 stores four
  palette IDs without weights. The supplied package has no corresponding
  source skeleton or complete ink FX shader; do not parse this VB2 as weights.
- Current fallback anchors both carriers to the chest and exports both sides
  with a dark opaque material. Wide original FX panels become black spears
  without their fade shader; the fallback narrows cross-sections along each
  connected strip's source centerline (.12-.22 width factor). This is an
  explicit silhouette approximation, not recovered source transparency,
  original FX motion, or a general conversion rule. Preview confirms geometry
  presence only; native appearance remains subject to user game testing.

## Dense first-person skin: diagnose serialization before adding topology

- Ink Mist C5 has 12,332 source triangles per hand. Closeup roughness was not
  evidence of low source resolution. A neutral source / fitted-float32 /
  quantized-half comparison isolated export precision: at native world heights,
  HALF4 introduced up to .551 mm error and collapsed 1,498 fitted first-person
  hand triangles. FLOAT3 readback retained the float32 surface with zero such
  degenerate triangles. Body-hand counterpart was 1,201 -> 0. These figures
  describe this exact source/build, not other characters.
- The profile-scoped FLOAT3 channel uses enum 2, stride 12; the existing native
  parser supports it. The inspected Daniya/Qianxia/Aimisi arm references use
  HALF4, so they do not establish FLOAT3 game compatibility. Native rendering
  of this format is pending user testing; do not claim it from parser success.
- Readers must resolve POSITION through channel type and stream, never assume
  stream1 is half4. Update serializer validation, actual-unit previews and
  bounds/TBN audits together. Keep the byte-for-byte preview/unit guard.
- Source UV seams also duplicated 906 hand vertices. Local weld at 1e-7 and
  conservative hand-only smoothing retain UV loop data and skin weights; carry
  non-hand custom normals through BMesh in a temporary corner attribute. Blind
  subdivision exceeded the native geometry-slot budget and was rejected.
- Full precision does not repair fitting or motion by itself. Native contact
  world matrices remained identical (maximum difference 0); actual MMR32 and
  synthetic source-motion probes were retained. Use separate neutral and
  textured compiled renders to distinguish contour, weights and shading.
- A remaining nail-side crease survived disabling the normal texture. On the
  same fitted surface, adapting three-joint weight fields per corresponding
  digit from Daniya/Qianxia/Aimisi reduced it. Sample four nearby points in
  each reference, take the median field, retain the digit's total influence
  and other palm/wrist drivers, and reconcile duplicate surface positions.
  This is an Ink Mist adaptation after its source/MMR fitting, not a reason
  to replace every character's authored weights. Compare compiled rest and
  grip renders, check all digits, and verify serialized weights as well as
  source arrays. The 22 synthetic probes improved 99th-percentile edge stretch
  (grip 1.800 -> 1.548; charge 2.047 -> 1.685), but do not prove all in-game
  weapons, extreme poses or absence of every local crease.

## One provider, four complete outfits

Si uses `si_outfit = original / ink_mist / short_skirt / lolita`; keep original assets intact and use
separate body/arms resource names. Acquire all four pairs once, clear old physics
with the old configuration, then replace body/arms paths and their corresponding
proportion/jiggle configurations together. Check preview cleanup while switching
four slots repeatedly. The October 21 lifecycle mock passed 40 switches across
four preview slots with eight distinct body/arms packages and no orphan actors.
This is a Lua lifecycle test, not a live-game verdict.

## Si third-person source digit proportions (October 21)

- Names containing `hand` include fingers. Treating that entire namespace as
  native-position arm joints stretched Si's two-segment digit spans: thumb
  60.7 to 90.2 mm, index 53.2 to 70.0, middle 58.4 to 73.5, ring 55.5 to 61.8,
  pinky 41.8 to 51.1 in this source scale. Inspect serialized pivots, not only
  surface silhouettes or curl limits.
- The four Si profiles now keep native wrist, palm and finger-1 anchors;
  finger-2/3 offsets use their own source lengths in the native rest directions.
  Runtime FK supplies those offsets with unchanged native rotation deltas.
  MMR fits the source surface to those same destinations; reference skin fields
  are rebased to the shorter joints before sampling. Changing skeleton pivots
  without the surface fit, inverse binds and weight-field coordinates disagrees.
- Actual unit readback matched source segment lengths within 4.6e-8 m and
  hand skin identity within 2.4e-7. The 22 synthetic runtime cases retained wrist
  contacts and finger lengths. First-person engine-linked joints remain native.
  These offline results do not establish every weapon grip or in-game success.
- Real MMR constraints ran for both body and arms; original game animations were
  unavailable. Keep the synthetic-motion label and per-pass authoring evidence.

## Short Skirt / Lolita source and build details

- Preserve the two supplied source INIs; no outfit author was identified there.
  Do not infer an author from the importer, source model or native porter.
- Lolita Component1 explicitly binds the white-hair `ff3790c7` diffuse. Matching
  source vertices established identical numeric UVs on 10,670 original hair
  loops. Flip the DDS-derived PNG vertically for the retained MMD UVs; keep the
  original hair mesh and weights. Short Skirt has no equivalent hair replacement
  in its supplied INI, so retain original Si hair rather than inventing a tint.
- Garment double-sided export exceeded the template's 31 geometry slots. Only
  the dense Lolita garment was collapsed to .88 of its source triangle count;
  skin, original head and horns were excluded. UV/weights were interpolated and
  preserved corner normals carried through BMesh. This ratio is specific to
  this asset's slot counts, not a reusable quality default.
- Short Skirt's closed sleeves covered skin that poked through after retarget.
  A profile-specific build mask removed 2,138 hidden skin polygons inside the
  source arm tubes, retaining hands and an 18 mm cuff margin. Compiled back
  previews removed those spots. Do not apply this to exposed-arm outfits.
- Lolita C9/C11 contain 1,868 ink-effect triangles. Preserve them separately,
  with the documented narrowed opaque-strip approximation used for Ink Mist.
  RabbitFx fade/shader source is absent; neither opaque strips nor native PBR
  reproduce that source shader exactly.
- A Blender attribute proxy can become invalid after `BMesh.to_mesh`. Retain
  its string name before mutation, then retrieve the attribute again.
- Missing external diffuse images may have several embedded same-name copies.
  Compare dimensions and decoded pixel hashes before selecting a deterministic
  equivalent; fail on unequal candidates instead of silently choosing a texture.

Costume resources belong in future share-package dependency closure even though
the character/provider count stays 13. Endfield-only settings must now preserve
Si's outfit widget while excluding Daniya's form widget and shortcut. Widget
indices need remapping after filtering. The October 20 archives predate this
costume; changing the build script does not update existing ZIPs.

Preserve AzNxde's original notice and author URL. Native alpha clip/PBR is an
approximation of source translucent fabric; source UV recovery and successful
serialization do not prove the original game's complete shading or animation.
