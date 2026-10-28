# Additional Endfield outfits: October 23 source set

Scope: the 12 supplied folders under `Skins`, converted
by `AnimeModelReplacement/tools/model-work/adapt_skins.py` and
`build_new_skin.py`. These findings concern those files, not arbitrary EFMI
or EFF versions. Keep original characters and previously accepted costume
resources distinct from new exports.

## Source selection and skin transfer

- Evaluate the supplied INI's selected draw ranges and material bindings. A
  single component can mix accessories, skin, hair and garments; classifying
  the entire component by its nearest original material can discard changed
  hairstyles. Cocoa Puff explicitly selects `back_hair` and `new_hair` using
  its own body atlas; preserve those selected draws and textures.
- Lolita Roshia's two binary source choices yield four combinations; Little
  Devil Endministrator's selected palette yields four. Treat an outfit and
  its combination number as separate settings. Do not describe every source
  toggle as a different complete costume or invent unsupported variants.
- Export source donor weights from actual armature-bone groups only. MMD
  auxiliary groups such as edge controls are not deform joints. Filter before
  selecting and normalizing the top four weights, and record the contract
  `bone-groups-only-top4-normalized-v2`. Rebuild dependent transfer data if that
  donor contract changes.
- Draw palette IDs require measured correspondence, not MMD index reuse.
  Preserve explicit source finger identities where present, with geometrical
  agreement checks. Restrict bare-skin transfer to the original skin field and
  reject accidental hair weights on skin/garments. Keep the source arm rest
  fitting maps with the conversion evidence.
- Make the original mesh datablock single-user before stripping polygons or
  garment-only decimation. The shaded source can share it with CMB carriers;
  editing shared data can silently destroy material-reference geometry.

## EFF left/right naming in Water Ink Si

This package's `Bip001_L_Hand` is on the original MMD model's right side and
`Bip001_R_Hand` is on its left. Explicit names alone crossed the hand palettes.
The converter now resolves each hand's side from the high-weight wrist surface
position and the fitted source wrist positions, then applies that side mapping
consistently to fingers, arms, clavicles and legs. It asserts both sides are
present and unambiguous. `conversion.json` records `{L: R, R: L}` for this
source only; never install that swap as a global EFF rule.

## Missing textures and prepared source donors

- Costume files can retain old source-relative image paths even when the
  shaded Blender source has usable packed images. Resolve paths before MMR
  saves a review blend in another directory.
- Chen Qianyu's original MMD blend lacks its external face/iris files. Its
  separately supplied CMB preset contains the authoritative material carriers
  and loads them inside `prepare_source`. Costume image recovery must run
  **after** that loader; a recovery loop before it cannot see the donors.
- Prefer exact image identities. If using a material's own CMB carrier, require
  an unambiguous original diffuse, excluding unrelated shared lookup images.
  Fail on unresolved required textures rather than baking white. A Blender
  'keeping packed image' warning alone does not establish a missing compiled
  texture: check decoded dimensions/pixels and the final native preview.
- Roshia's closed tail underlayer samples real original fur colors. Resolve
  source texture references before generating it; install preview placeholders
  only after source geometry preparation. Retain byte-for-byte comparisons
  between reconstructed preview geometry and the actual exported unit.

## UI and runtime integration

Use a per-provider costume catalog containing the original plus each distinct
outfit/variant. Each selection owns a body, first-person arms, proportion
configuration and jiggle configuration. Clear old actors/physics with the old
configuration before changing that selection. Keep unrelated class targeting,
weapon attachment, first-person camera synchronization and preview ownership
from the accepted runtime.

Nested DMF dropdown `show_widgets` indices belong to their own `sub_widgets`
array. Show the combination control only on outfits that have combinations.
Removing visible jiggle/shortcut widgets must also prevent saved old tuning
values from overriding the authored defaults. Removing UI controls need not
remove the outfit's authored secondary motion.

Check resource closure after staging all body/arms build manifests; lifecycle
mocks deliberately reject unstaged assets. Preserve original character assets,
back up the installed mod and resource registration, copy only the intended
files, run Custom Assets patcher, then verify its dry run and deployed hashes.

MMR records, native readback, compiled previews, synthetic pose/contact tests
and Lua lifecycle tests are separate evidence. Source game animations were not
supplied; these offline checks cannot certify every in-game weapon or exact
source-game transparency, lighting and physics. Keep current deployment and
remaining game checks in the task's durable status file.

## Final source-part and hand-field review

- An original head-weighted polygon is not automatically a retained accessory.
  Roshia's original red hood contains head-weighted Cloth panels; retaining
  those left a red shell under both new outfits. Exclude verified old clothing
  while retaining horns/ears. Lolita's selected hair-component draw replaces
  the headband, not the original hairstyle; its INI leaves original hair active.
  Inspect compiled back views as well as faces before promotion.
- Serialization and synthetic joint-matrix checks cannot detect a malformed
  rest hand. In this batch, wrist vertices carried sleeve/jacket palette mass,
  and nearest-surface transfer sometimes switched adjacent digits. Rest-hand
  source/export edge comparisons exposed spikes up to 32.8 times the source
  edge length on JK Perlica.
- A raw joint channel's average donor majority is insufficient around blended
  knuckles. `costume_hand_weights.py` compares complete spatial influence fields
  with canonical source hand channels, requiring correlation, separation from
  the runner-up, centroid agreement and uniqueness. Store this evidence apart
  from GPU IDs. Explicit EFF names and verified side mappings remain authoritative.
  Do not subsequently overwrite recovered authored hand weights with an
  unqualified nearest-point fallback.
- On majority-hand vertices, remove verified non-anatomical garment/helper
  influences and renormalize anatomical ratios together. Keep source positions,
  source joint identities and MMR fitting. The batch's thresholds and Japanese
  names are local implementation choices, not a rule to strip valid corrective
  bones from unrelated models.
- The JK Perlica pilot's 99th-percentile edge ratio decreased from 2.923 to
  2.236, with the maximum decreasing from 32.816 to 11.226. This establishes
  reduced discontinuities, not perfect thumb anatomy or live weapon contact.
  Inspect actual native hand images alongside these metrics.
- Compare the prepared mesh saved with MMR authoring evidence to actual exported
  positions. Roshia preparation appends its closed tail core; assuming raw
  costume and prepared mesh have identical vertex counts breaks the comparison.
  Topology, resource equality, matrix checks and game tests are distinct evidence.

## Local weight discontinuities after anatomical mapping

- Correct digit names do not guarantee continuous skinning. Water Ink Si had
  wrist/other residual mass on majority-digit distal surfaces; removing only
  those residuals on the measured source digit region improved the edge audit
  without changing positions. Keep proximal knuckle/palm blends outside that
  scoped operation.
- A remaining 0.356 mm source edge on one right ring-finger segment had sharply
  different adjacent-joint ratios. Reconcile only verified same-digit micro-edge
  components, preserving each vertex's total hand mass and the source positions.
  This final repair touched two vertices in this asset. It is not a general
  instruction to smooth all weights or shorten fingers.
- The refreshed actual-export audit measured p99 source/export edge ratio 2.017
  and maximum 11.750; the existing guards (p99 < 4, maximum < 12) were unchanged.
  Compiled body/left/right-hand previews, resource readback and synthetic contact
  checks also passed. These establish the scoped offline result, not all-weapon
  game validation or absence of every crease.

## UI catalogs and source placeholder images

- DMF localizes dropdown `option.text` in place. Never reuse one options table
  across class widgets: a shared table is localized repeatedly and can display
  nested angle/book marks such as `<<<<<祀>>>>>`. Generate a fresh option table
  for every dropdown, then parse the generated Lua and walk every nested option.
- Treat outfit variants as a catalog contract. When source files are visually
  identical, keep one outfit entry and remove obsolete `_v2`/`_v3`/`_v4`
  resources during deployment; stale native resources can otherwise survive in
  the game directory even after the UI no longer exposes them.
- MMD blends commonly contain an empty external diffuse node beside a packed
  duplicate named with `.001`. Before tail sampling or native export, resolve
  empty nodes by normalized image identity and choose the largest packed image.
  A successful Blender load alone does not prove that the exported texture is
  non-white; inspect dimensions and the final preview.

## Outfit-specific geometric stability

- For a close JK skirt/coat, a small lower-hem radial margin (about 4--5 mm,
  fading to zero at the waist) is safer than contracting the whole skirt. Keep
  UVs and the upper silhouette unchanged and record the policy in
  `conversion.json`.
- For a simplified skin draw that spans both thighs, nearest-surface transfer
  must constrain donors by leg side and a local height band. A single global
  nearest query can borrow the opposite leg or knee field and produce a long
  triangular stretch when the native animation runs.
- A closed tail core should preserve the source chain and attachment while
  using enough radial samples for a round root. Layered longitudinal bands and
  bounded strand contrast improve the native PBR read without copying another
  outfit's tail mesh or changing its dynamic pivots.
