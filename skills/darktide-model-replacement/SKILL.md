---
name: darktide-model-replacement
description: Build, adapt, diagnose, preview, or maintain Darktide character and weapon model replacement assets, effects, UI and runtime Lua integration.
---

# Darktide Model Replacement

## Portable repository workflow

This skill ships with the public `Vionian/darktide-model-replacement` toolkit. Locate its checkout using `repository-location.txt` beside this file (written by `install-skill`), the user's current repository, or `DARKTIDE_MODEL_TOOLKIT`. Confirm that `tools/darktide.py` and `dependencies.lock.json` exist before running commands. If only the skill was downloaded, obtain/locate the repository before building; do not assume historical project folders exist.

For a new source blend, read [references/toolkit-workflow.md](references/toolkit-workflow.md) first. Run doctor/setup as needed, inspect the actual model, then write a source-specific profile and adapt missing materials/rigging before building. Use new candidate directories, audit native resources, generate/review runtime and package. Execute the work when the user asks for a replacement; do not stop at a tutorial. The user normally supplies the blend and target weapon/family, while the assistant handles profiles and adaptation scripts.

The public baseline uses native human skeleton fitting and weighted arm extraction. It does not execute source-hand MMR authoring, support Ogryn, implement menu/HUD/costume integration, or cover every weapon attachment family. Do not claim these features from a baseline build. Only extend the relevant route when the task needs it.

Historical scripts in `toolbox` are model-specific reference implementations. Inspect their inputs and imports; regenerate reports and supply authorized templates rather than assuming old named models or third-party addons are present. `materialize-toolbox` changes paths only. No art or game assets are distributed with this skill.

## Authoring invariants and specialist references

Use this skill for character or weapon model swaps that combine Custom Assets units, skeleton retargeting, material conversion, first-person arms or weapon branches, effects, UI selectors, and runtime Lua. For weapon-specific work, read [references/weapon-model-replacement.md](references/weapon-model-replacement.md).

Start by identifying the active source model, generated candidate, deployed package, and game build/log used for the reported result. Treat preview and in-game behavior as separate evidence: a Blender render cannot confirm native animation, material-channel support, culling, streaming, or weapon contact.

Inspect a working replacement that shares the relevant path, then identify which assumptions actually match the source model. Preserve native animation and equipment attachment where possible. Avoid hard-coded per-weapon corrections unless the engine exposes a reliable weapon/action identifier and representative tests cover the affected weapon families.

For finger and gesture work in the documented source-first workflow, start from the original game's source hand geometry, weights and skeleton; verify rest axes and motion transfer with MikuMikuRig (MMR) before adapting to Darktide. Then compare the relevant working implementations in Daniya, Qianxia and Aemeath rather than relying on one template. Record missing source animations explicitly. MMR is an offline authoring/validation tool, not a Darktide runtime dependency. Do not substitute guessed per-joint curl multipliers or template finger proportions for this source-first workflow.

For each reported defect, trace the complete path from source mesh/material/bone through the generated unit and runtime driver. Change one cause at a time, build into an isolated candidate, validate serialized resources and pose previews, then compare screenshots. Deploy only when requested; keep a recoverable copy of the currently deployed resources before replacing them.

Read [references/darktide-model-replacement-knowledge.md](references/darktide-model-replacement-knowledge.md) for verified Darktide-specific resource and retargeting lessons. Add new findings there only when supported by generated-resource inspection, runtime logs, or reproducible previews.

For weapon replacements, follow the complete procedure in [references/weapon-model-replacement.md](references/weapon-model-replacement.md): inspect the native attachment family and source LOD, align and compile an isolated GLB, read back UNIT/material/texture resources, register a per-template profile, bind effects to both equipment roots, apply first-person root offsets after native placement, expose independent class/weapon/skin settings, then run Lua, resource, compiler and Custom Assets fixture checks before a backed-up deployment. Keep particle substitution, serialized blade-cover visibility, and in-game visual confirmation as separate evidence.

For opaque garments disappearing from low camera angles, source double-sided material flags, or motion checks across reduced helper rigs, read [references/garment-culling-and-matched-motion.md](references/garment-culling-and-matched-motion.md). Keep matched-rig evidence and deployment state in a durable task-status file; do not infer culling from static bounds or rest-normal signs alone.

For Endfield material conversion, opaque horns/tails hidden by Alpha slot classification, or local hand rounding, read [references/endfield-material-and-hand-detail.md](references/endfield-material-and-hand-detail.md). It distinguishes inspected source parameters and serialized checks from pending game validation.

For additional Endfield characters, concave eye whites disappearing under culling, separate CMB carrier presets, or source-screenshot color calibration, read [references/endfield-eight-character-adaptation.md](references/endfield-eight-character-adaptation.md).

For Aitela/Laiwanting/Saixi source variants, MMR edit-bone calibration precision, source-length distal fingers, zero corner normals, or new-provider route checks, read [references/endfield-three-character-adaptation.md](references/endfield-three-character-adaptation.md).

For source-game screenshot avatars, transparent head cutouts and native HUD portrait-frame integration, read [references/screenshot-hud-portraits.md](references/screenshot-hud-portraits.md). Keep offline lifecycle/resource evidence distinct from in-game appearance.

For extra models in mission preparation or other preview scenes, read [references/preview-lifecycle-and-deployment.md](references/preview-lifecycle-and-deployment.md). Reproduce against the installed mod, since a tested workspace fix may not have been deployed.

For EFMI/3Dmigoto outfit buffers, missing head accessories, source finger proportions, costume slot limits, or a costume switch inside an existing character provider, read [references/efmi-outfit-adaptation.md](references/efmi-outfit-adaptation.md). Draw palettes are not MMD bone indices; retain the source author's notices and check costume resource closure separately from character counts.

For additional Endfield outfit batches, EFF side-name mismatches, auxiliary donor-weight groups, late-loaded CMB face textures, or nested outfit/combination selectors, read [references/endfield-outfit-batch.md](references/endfield-outfit-batch.md).
