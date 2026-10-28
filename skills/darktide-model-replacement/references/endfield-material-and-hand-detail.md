# Endfield material and hand-surface findings (2026-10-19)

Use for the four Endfield source profiles in `AnimeModelReplacement/tools/model-work/`. These findings describe inspected source files and serialized candidates; runtime appearance still requires game screenshots.

## Opaque geometry with Alpha slot names

Typhoea `Cloth1Alpha1` (slot 13) contains the physical tail; `Cloth1Alpha2` (14) contains two physical horns. Their diffuse alpha is fully opaque. Endministrator `Cloth1Alpha` (15) is also physical opaque clothing. The triangles existed in the previous exports: absence in game is not sufficient evidence of missing geometry. Inspect source components, exported triangles and the actual material provider before changing bones or fabricating replacement parts. Candidate material streams now bind these slots to `substance_basic`; renders show the complete horns and tail. Keep real alpha cards separate.

## Source PBR channels and switches

- The shaded split objects, named `<main mesh>__<source material>`, retain Character Material Bridge graphs. Read their image socket links and parameter column; raw MMD material slot names alone do not identify texture meaning.
- In these files `_N` connects to `F1_BumpMap` and stores tangent normal X/Y in R/G with B=0. Decode XY, apply the authored `_UseBumpMap` and `_BumpScale`, constrain XY magnitude and reconstruct positive Z. Native BC5 stores only XY. A Blender preview also needs reconstructed Z, encoded back to [0,1]; setting B=1 unconditionally changes the normal.
- The exported UV flips V. Generated tangent-space bitangent consequently changes: convert normal green consistently with the exported tangent frame; undo that conversion once in Blender. Verify on the actual serializer rather than treating green inversion as universal for every pipeline.
- `_P` is connected to `F3_MetallicGlossMap`, not a conventional ORM map. The current conversion uses R as metallic and 1-alpha as roughness, with the authored intensity parameters. Its green channel is not reliable AO (Si's can be nearly zero): do not copy it to AO. Use neutral AO absent a verified AO source.
- Respect `_UseMetallicGlossMap`; when disabled, use authored `_Metallic` and `1-_Smoothness`, not a found but disabled image. Endministrator skin has `_BumpScale` about 0.6 and the metallic/gloss map disabled. These are source-specific values.
- Face and eye shading remains on the proven native material path with neutral normals. Do not reintroduce the earlier custom face emissive provider merely to improve a preview: its game fallback previously produced white faces.
- `inspect_endfield_color_path.py` round-trips a 0.5 byte PNG through Blender 5.2.2: both sRGB and Non-Color `image.pixels` returned ~0.502 for that file. Do not assume every Blender image buffer is linear or perform another gamma conversion without a measured probe; float/generated images can differ.

Native output uses own BC/BC5/ORM streams; no borrowed Qianxia seam normals. Hair remains nonmetallic with neutral normals: a trial applying the cloth metallic interpretation to Typhoea's hair produced black/chrome-looking sections in the side render and was rejected. A similarly named map/socket does not establish identical semantics across different part shaders.

This is a PBR approximation of the authored shader, not a port of Endfield's toon lighting, anisotropy or screen-space effects. Preview exposure and lamp changes do not modify Darktide lighting. Endministrator hair/mask additionally use explicitly labeled linear-albedo art calibration against supplied screenshots; those gains are visual tuning for that model, not recovered source shader parameters and must not be generalized to other characters.

## Rounded hands and animated weight transitions

- Original-hand MMR rest placement does not relocate skin-weight transition zones. Keep native wrist/finger bind matrices unchanged while investigating the mesh's deformation field separately. Do not compensate by rotating runtime fingers or changing weapon contacts.
- `endfield_skin_weights.py` samples ring-joint weights from the fitted native-space surfaces of Roshia, Daniya, Qianxia and Aimisi, preserving total ring influence and other influences before pruning/normalization. It is a candidate adaptation, not proof of every weapon/action. Report deformation measurements, including regressions or unchanged cases.
- `endfield_hand_detail.py` operates only on Endministrator hand skin. Exclude wrist/garment boundaries, interpolate loop UVs and deform weights during subdivision, smooth conservatively, then recompute hand normals on the **final fitted surface**. Merely transporting original normals through independently blended fitting matrices can retain visible shading seams.
- Triangulated hand/nail geometry can spike with spherical edge subdivision (`smooth` on `subdivide_edges`). Use linear subdivision plus controlled local smoothing and inspect fingertips, webs and garment boundaries. More vertices alone do not guarantee a rounder surface.
- Bulk-read corner/vertex normals with `foreach_get`; repeated RNA corner-normal access while modifying smoothing can make a local operation extremely slow. Ignore invalid BMesh handles returned after topology edits before traversing links.

## Evidence and delivery

`endfield_batch/defect_fixes_audit.json` compares native binds/inverse binds with the pre-fix units, checks real opaque material providers, normalized skin weights and synthetic posed ring-edge stretch. Original source MMR authoring uses 32 joints and seven synthetic motion cases per model. These checks do not prove in-game grip/camera behavior. Compare final preview geometry streams to compiled units, preserve deployment backups, hash copied artifacts and run the resource patcher's final dry-run before claiming deployment complete.

## Five-character standalone distribution

`package_endfield_five.py` allowlists five providers and ten body/arms folders, copying only manifest-listed compiled artifacts and comparing them to the current game installation. Keep current runtime modules, not the stale Lua from an earlier release. The packaged Roshia provider removes its obsolete `AnimeModelReplacement:qianxia` pre-acquire: self-contained texture/material streams do not make a lingering Lua acquisition of an absent character safe. Internal `qianxia_*` skeleton/helper names are independent of this package dependency and must not be blindly renamed or excluded.

`validate_endfield_five_package.py` checked the resulting 816 ZIP entries / 660 compiled artifacts / 120 Lua sources. In an isolated game fixture without frameworks, installation registered exactly ten assets; repeated installation preserved an existing loader sentinel and load-order entry, and final dry-run required zero resource changes. The real game database hash stayed unchanged. Existing plugin users can drop the folder and add one load-order entry; first-time users still need INSTALL.cmd once to bootstrap missing prerequisites. Never ship the fixture database, game executable, Oodle DLL, registration state or personal settings.
