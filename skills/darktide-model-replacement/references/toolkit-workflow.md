# Portable toolkit workflow

Use the repository recorded by the installer. All commands below run from its root with Python 3.12+. Windows and Blender 5.2.3 LTS are the verified local baseline. Do not modify the user's original blend or deploy simply because a build passed.

## Environment and inspection

1. `python tools/darktide.py doctor`. If unconfigured, run `setup`, optionally with `--game` and `--blender`. Setup downloads digest-pinned SDK/limn/MMR and extracts native skeleton references locally. It does not install DML/DMF/Custom Assets or deploy a mod.
2. `python tools/darktide.py inspect SOURCE.blend --output work/inspection`. Read source-inspection.json, including actual object/armature names, missing textures, transforms, bone names and node types. Use additional Blender inspection when required; the summary is not a complete shader interpreter.
3. Start from profiles/character.example.json or weapon.example.json and write a profile under work/. Explicitly choose source meshes/armature where ambiguous. Repair/bake unsupported shaders in a separate working blend. Missing art/plugins must be resolved from authorized user inputs.

## Character route

SDK auto-mapping uses local native human references. `bone_map` overrides map source names to native names; review required bones and mapping output. `keep_proportions`/`keep_torso_shape` are fit choices, not universal recommendations. The first-person mesh is selected by native arm-group weights; `first_person_meshes` only filters source objects. Default arms use body bind with 1P node-name linking, so representative native weapon contacts need in-game checks.

Default output records `source_hand_mmr_executed: false`. If source finger lengths/gesture fidelity are part of the request, perform the source-first MMR route and record real results; do not turn a flag on to simulate it. Review referenced source workflows and available original animation evidence.

## Weapon route

Inspect the target native attachment family and source LOD. Measure scale, XYZ rotation and source/target grips before setting `coordinate_frame_reviewed`. Target templates and attachment prefix must be real game identifiers. Baseline runtime uses sword-style grip/hilt/blade/pommel attachment selection; adapt other families explicitly. Particle and blade-cover work is separate.

## Build, audit and package

```powershell
python tools/darktide.py build SOURCE.blend --profile work/profile.json --output work/candidate-001
python tools/scaffold_mod.py work/candidate-001 --mod-id MyReplacement --output work/runtime-001
python tools/darktide.py package work/candidate-001 --runtime work/runtime-001 --output dist/candidate-001
```

Review bone-map, native-audit, resource-audit and build-report. Compiler validation alone is insufficient: UNIT material bindings must be nonzero and reference packaged material resources. Runtime must acquire matching CustomAssets logical IDs and resource paths. Package includes only manifest resources and reviewed runtime; keep source blend, local jobs/logs/configuration and game extracts private.

For advanced work use `python tools/darktide.py materialize-toolbox --output work/expert-adapters`. Read only the relevant scripts, validate dependencies and rebuild model-specific reports. Templates referencing prior models are evidence, not shipped inputs.

## Deployment and evidence

Deploy when requested or already authorized. Close the game and create recoverable backups of affected mod/registration/database/bundle/stream files according to the installed Custom Assets distribution. Inspect its current CLI/help and planned writes; do not guess a patcher command. Require a final no-change registration check, then a new game session.

Report offline, registration and actual game evidence separately. Verify 1P/3P, native equipment contact and actions, settings, death/respawn, level unload and return-to-menu. Preview/HUD paths are separate integrations. Basic actor template assumes initialization in a fresh game session. Missing source animation or in-game observation stays explicit.
