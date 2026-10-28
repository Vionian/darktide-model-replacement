# Screenshot HUD portraits (2026-10-20)

Use when the user wants a source-game screenshot as the avatar rather than a
new Blender render. Source screenshot selection is an explicit art decision:
do not substitute another render, repaint facial details, or invent missing
horn/ear tips. Crop a slightly wider head silhouette, retain source RGB, and
create alpha only. Inspect ear interiors, thin horns, white clothing and hair
strands: segmentation often deletes these as background. Record source/crop
coordinates and retain transparent full-resolution cutouts for reproduction.

## Native HUD contract inspected

Readable source: Aussiemon/Darktide-Source-Code commit
`ba6c148f3c2768ca3ce20d846a12e56e2f433f3e` (public reference, not established as
byte-identical to the local retail build).

- `HudElementPlayerPanelBase._cb_set_player_icon(profile, grid_index, rows,
  columns, render_target)` sets `player_icon.style.texture.material_values`:
  `texture_icon`, `rows`, `columns`, zero-based `grid_index`, and
  `use_placeholder_texture`. It selects `_get_player_portrait_frame_material`
  separately. The personal and team HUD panels inherit this base.
- `UIPasses.apply_material_values` passes string-valued fields to
  `Material.set_texture`. A screenshot can therefore supply a compiled texture
  to the native frame's `texture_icon`, with rows/columns=1, grid_index=0 and
  placeholder=0. No replacement frame shader or whole-HUD redraw is needed.
- Keep frame textures, insignias, `desaturation`/`intensity` status shading,
  the atlas request ID, and its normal destroy callbacks. Save and restore only
  the fields being overridden plus the selected frame material. An asynchronous
  icon/frame callback, or a synchronous callback inside update, must not replace
  the stored native baseline with an already overridden screenshot state.
- Mod disable and unload must restore live widgets; destroy must forget them.
  Use weak panel keys. Do not store HUD instances as process-lifetime state.
  DMF accepts delayed class-name strings for hooks, useful before HUD class load.
- Route by actual profile archetype/breed and the active replacement registry
  winner; preserve Ogryn and characters without an assigned screenshot. Check
  custom-resource readiness before assigning a texture. Request one owned ticket
  per texture, not per frame, and release those tickets after restoring widgets.
- Cooked-folder discovery can expose the texture's name only as `#ID[hash]` in
  Custom Assets' generated manifest, even with readable names in build.json.
  Acquire the stable owning logical asset (`AnimeModelReplacement:<asset>`) in
  that case; plain-name `acquire_resource` cannot find a hash-only dictionary key.
  Verify registration against the primary wrapper's 64-bit name hash and the
  manifest resource's source path. Engine `Material.set_texture` still receives
  the authored full resource path, which hashes to that same resource identity.
- The local DMF `custom_textures.lua` functions are unimplemented stubs. A PNG
  copied into the mod folder does not become an engine texture.

For further screenshot identities and the distinction between visible RGB and
cleared zero-alpha pixels, see
[endfield-three-character-adaptation.md](endfield-three-character-adaptation.md).

## Resource and distribution evidence

The local `compile_screenshot_portraits.py` reuses the checked native v67 Oodle
writer with BC3 sRGB/alpha, complete mips and stream data. Both primary `.texture`
and `data/at/*.stream` are added to each existing body asset's `build.json`
artifacts/resources. Model unit bytes and skin binds are untouched. Source PNGs
are optional authoring/preview files; runtime needs the compiled resource pair.

Read back the native resource independently, decompress its top mip, compare the
encoded BC blocks, decode alpha, and inspect the result. Pillow versions without
DXGI BC3 support can decode a preview-only legacy DXT5 header around the same BC
blocks; do not alter the actual game texture's DXGI/sRGB metadata.

The production hook was exercised in LuaJIT with pending/loaded resources,
asynchronous and nested callbacks, 9 screenshot mappings x 6 human classes,
selection changes, disabled/unloaded states, native status shading, other
registry winners, and Ogryn exclusion. These tests establish Lua routing and
lifecycle, not retail shader orientation/color or actual game appearance.
Deploy/package verification and in-game acceptance remain separate evidence.

Reproducible project files under `tools/model-work/`:
`build_screenshot_portraits.py`, `compile_screenshot_portraits.py`,
`test_screenshot_portraits.py`; production hook:
`scripts/mods/AnimeModelReplacement/screenshot_portraits.lua`.
