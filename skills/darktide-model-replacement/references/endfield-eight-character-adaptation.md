# Eight additional Endfield characters: verified conversion lessons

Workspace: `AnimeModelReplacement/tools/model-work/`.
Selectors and reference-image identities live in `endfield_wave2.py`: Chen Qianyu,
Gilberta, Liino, Mifu, Perlica, Tangtang, Yvonne and Zhuang Fangyi. Do not infer
character identity from the ordering of anonymous screenshot filenames.

## Concave eye whites and native backface culling

The Chen source's sclera custom normals average source Y=+0.336, while iris
normals average Y=-0.976. A globally correct winding convention does not make
every authored MMD surface visible: some eye-white interiors require their
reverse side. The native preview with backface culling showed large black gaps
around the irises. Lighting/exposure did not fix that geometry loss.

For this batch, `endfield_profiles.py` exports the `目白` triangles twice with
opposite winding and opposite corner normals, preserving UVs and skin drivers.
Backface culling selects one surface; the second side is not an additional
coplanar front-facing layer. The Chen slot contains 232 source triangles and
464 exported eye-white triangles; the compiled face render restores the white
regions. This is a scoped source-material adaptation, not a reason to reverse
the entire model or disable culling for every shader. Inspect original source
normals and winding before applying it to another character.

Source face normals now retain more of the original nose shape: these eight
profiles use 0.35 broad-normal blending rather than the shared Roshia default
of 0.75. The original four profiles retain their previous value. Do not treat
one blend amount as a universal lighting fix.

## Material presets and color fidelity

- The Chen `.blend` contains MMD materials but no shaded material proxies.
  Its separately provided CMB final preset stores `CMB_CARRIER_000..010`, not
  the original object names in `mapping.json` recipes. Append carriers, map
  the recipe index to the original material slot, and read their parameter
  columns. Fail if expected carriers are missing. No source blend is saved.
- Read the authored vector `_BaseColor` as well as normal/metallic switches.
  Multiply diffuse in linear space, then encode sRGB. Record authored values
  separately from screenshot-based art calibration.
- `_D_AOff.png` is a valid authored diffuse variant (Liino), not a missing
  `_D.png`. Preserve it rather than replacing it with an arbitrary image node.
- Inspect alpha in the UV regions actually used by a material. Whole-texture
  alpha minima do not classify individual slots. In this batch Liino slot 17,
  Perlica 13, Tangtang 14/15 and Yvonne 13 use opaque physical surfaces; other
  slots can be real alpha cards. Gilberta `尾巴` and Mifu `尾` use actual alpha
  hair cards and must not be forced to opaque rectangles.
- Measured screenshot colors are art direction, not recovered toon-shader
  parameters. `measure_endfield_wave2_colors.py` records exact source/preview
  ROIs and pixel counts; `wave2_color_calibration.json` stores the selected
  bounded face correction and hair correction. Inspect sampled regions for
  hair, makeup, background and highlight contamination before using gains.
  Keep an uncalibrated copy. Never claim this reproduces Endfield lighting in
  every Darktide environment.
- For color-only iterations, `refresh_endfield_wave2_colors.py` recompiles the
  same named diffuse textures and updates manifest byte sizes. It asserts
  unchanged body unit and **all compiled first-person resources**, retaining
  the tested joints/contact data. Native texture readback still runs.

## MMR and validation evidence

The eight models use their original MMD armatures as MMR owners: 2 wrists and
30 authored finger joints, no automatic 90-degree rounding. MMR evaluated
placement/rotation is consumed by offline surface fitting. Anatomy fitting and
ring-weight transfer are separate from MMR. Native first-person contacts keep
the proven human node names, parents and inverse binds; no runtime curl gains
or per-weapon offsets are introduced.

`mmr_hand_authoring.json` must contain all seven **source-owner** motion probes.
The initial build can have none because runtime pose fixtures do not exist
yet. Generate fixtures with the production Lua stress runner, then evaluate
the actual source-owner constraints again. A native-to-native audit alone is
not evidence that source hands were authored with MMR.

`asset_audit.json`, `contact_runtime_audit.json`, `source_hand_audit.json`,
`wave2_delivery_audit.json` and `wave2_integration_audit.json` distinguish native
resource, synthetic motion and routing checks from gameplay. Previews require
stream/index equality with the actual compiled unit and decode native texture
headers/high-mip streams. Changed geometry/normals invalidates old renders;
color changes require new material previews but do not justify redoing an
unchanged animation pipeline.

No original Endfield gesture/weapon animation library was supplied. Synthetic
staff/shield/dual-blade probes do not establish every live Darktide weapon's
grip, fast-camera behavior or lighting. Deployment and user screenshots remain
separate evidence.

## Face refinement: source shader outputs, UVs and contrast

`bake_endfield_face_albedo.py` transfers CMB's unlit `Z0_r_albedo` to the
current source mesh UVs. Disable proxy geometry-node outline modifiers during
the bake. Keep authored texture lookup UVs explicit and distinct from the bake
destination UV. Chen's supplied preset and current eye-white UVs differed by
about 0.04069; selecting only an active UV layer silently changed lookups.
Use the bake operator's `uv_layer` argument and explicit UVMap nodes for source
sampling. Apply the source linear BaseColor once, then encode sRGB for native
diffuse resources. A bake that already includes BaseColor must not receive it
again in the exporter. No source blend is saved.

Do not assume every exposed diagnostic shader output is usable. Liino's lash
and mouth `Z0_r_albedo` bakes were exactly black, while the supplied original
diffuse contained purple lash and mouth detail. Those two layers explicitly
retain the original diffuse; the audit records the selected source. Black
pixels alone are not a universal reason to discard an authored material.

Separate face, iris, sclera and lash corrections. Inspect each character's
reference and compiled preview: increasing eye contrast uniformly made Liino
and Gilberta's lashes excessively dark. Keep screenshot art gains separate
from recovered CMB values. Restoring authored eye-layer spacing, scoped reverse
sides for concave sclera/lashes, and reducing PBR glare preserve painted iris
highlights; they do not reproduce the complete Endfield toon renderer.

Two experiments were rejected: exporting the full CMB inverted hull caused
triangular cheek shadows and black nose artifacts under `substance_basic`;
baking final eye `ret_gBuffer0` embeds fixed lighting. Both remain opt-in
diagnostics and are excluded from production. Verify generated-resource
previews rather than presenting these experiments as successful fixes.

For a material-only follow-up, `integrate_endfield_wave2.py --assets-only` and
`deploy_endfield_wave2.ps1 -AssetsOnly` preserve provider/menu Lua and copy
manifest-listed resources. Regenerate the latter using
`prepare_endfield_wave2_deploy.py` after changing the base deployment script.
The face audit checks all 248 existing compiled first-person files against
the pre-change game baseline. Runtime SHA snapshots, deployment backup, native
resource readback and the patcher dry-run provide separate evidence; none
establishes live game lighting or weapon contact.
