# Extra characters in mission preparation / preview scenes

## Reproduced cause (2026-10-20)

`UIProfileSpawner._despawn_current_character_profile` unequips gear before
clearing `_character_spawn_data`. Unequip can reenter `_update_items_visibility`
while the old parent remains alive. A replacement hook which merely destroys
its custom unit before calling the original allows that callback to respawn a
new replacement. The engine then destroys the parent and clears the profile;
the replacement can remain as an orphan and accumulate across scene changes.

Guard the entire original teardown, including all reentrant callbacks, with a
shared spawner depth counter. Every provider checks that counter before applying
or spawning its replacement. Clear each provider's handles during teardown and
restore the depth in an exception-safe wrapper which preserves all original
return values (including nil gaps). Missing/deleted parents must trigger cleanup
from both visibility and update paths. Do not fix this with a global four-model
cap: ownership belongs to each actual preview slot/parent.

The project implementation is
`scripts/mods/AnimeModelReplacement/preview_lifecycle.lua`, consumed by all 16
replacement providers. A shared counter is intentional: all hooks can wrap the
same teardown and none should spawn while any wrapper is still cleaning up.

## Deployment is a separate gate

The 2026-10-20 user's new screenshot came from an installation still running the
old provider Lua, despite a previously passing workspace regression. A preceding
avatar-only deployment had not copied the lifecycle fix. Checking the workspace
again would have missed this. Run the regression against the actual installed
mod root before and after deployment and hash every changed installed file.

- Installed pre-fix: `test_preview_lifecycle.py --root <game-mod> --expect-old-leak`
  reproduced one teardown orphan for every provider.
- Targeted staging/deployment: `deploy_preview_lifecycle.py` copied only 16
  provider entrypoints and the shared helper, preserving installed model, hand,
  material and screenshot resources. It backed up the original files and wrote
  an exact diff plus candidate/installed test reports.
- Installed post-fix: 16 providers passed four live slots with 20 reassignments,
  missing/deleted parent cleanup, visibility/update reentry, disable/re-enable,
  original return preservation and error guard recovery. LuaJIT parsed all staged
  Lua files. This is offline lifecycle evidence; in-game acceptance is pending.

Evidence is under `tools/model-work/distribution_fix/`:
`live_preview_before_20261020.json`, `preview_lifecycle_deployment_latest.json`
and the corresponding timestamped backup/candidate directory.

## Follow-up: teardown alone did not resolve the screenshot (18:28 session)

The session `e7fa2521-27b1-4568-904a-5d4472b01a84` started after the
18:26 deployment and still showed extra moving models behind the four-person
lineup. The previous single-provider teardown regression was insufficient;
do not attribute this later report to an undeployed fix. Its console log did
not record individual replacement spawn owners, so the exact source of each
extra screenshot model is not proven by that log.

Two additional ownership/visibility gaps were reproduced offline:

- The generic UI hook would replace any matching `UIProfileSpawner` in the
  preparation world, irrespective of whether it belonged to an occupied squad
  slot. The inspected `MissionIntroView` source creates six candidate positions
  and assigns at most four players. Scope replacements to actual occupied
  `view._spawn_slots[*].profile_spawner` identities in that view's world. Sweep
  already-created non-slot replacements when adopting the world, and clean up
  before world destruction. Preserve independent portrait/inventory worlds.
  A companion-only spawner's hidden human container must stay hidden.
- Endfield third-person bodies use manual pose updates and are not linked as
  native actor children. `PlayerVisibilityExtension.hide()` recursively hides
  the native actor and takes/restores visibility snapshots; an independent
  replacement is outside those operations. Mirror the driver's public
  `visible()` state, suppress gameplay replacement meshes while the preparation
  view is active, and restore the saved first/third-person visibility policy
  afterward. Cover native hide/show, player and husk updates, spawned-late
  models, and refresh callbacks. Hide queued-for-deletion meshes immediately.

Keep the scene/subject/actor registry shared across all provider `io_dofile`
executions. The controller must clear ownership on disable/unload because
managed hooks may be inactive when a view exits. The same teardown-depth guard
also prevents gameplay extension destruction from respawning replacements via
equipment visibility callbacks. Do not change native player/weapon poses to
solve a rendering ownership defect.

`test_preview_scene_ownership.py` runs all 16 production provider hook chains
together and executes the inspected game's MissionIntroView slot methods and
PlayerVisibilityExtension hide/show methods with mocked engine calls. The old
installed runtime reproduces six visible models for four occupied slots plus
two auxiliary spawners. The new runtime keeps four, switches every provider,
preserves other-world portraits, hides companion-only containers, follows
native visibility snapshots and restores 1P arms. Both player and husk paths
cover deferred deletion and reentrant destruction. The prior teardown tests
still pass for all providers.

`deploy_preview_scene_ownership.py` stages from installed scripts and applies
only this patch, preserving unrelated workspace differences. Deployment at
18:48 updated 18 Lua files (controller, shared helper, 16 providers), parsed all
145 installed Lua files, reran both suites against the installation, and
recorded before/after hashes and backups in
`tools/model-work/distribution_fix/preview_scene_ownership_latest.json`.
No model resources or share archives were rebuilt.

This is source and offline regression evidence, not an in-game acceptance
result. The source snapshot is public 1.13.2 (`ba6c148`); exact correspondence
to the latest retail patch has not been established. Runtime logs now emit a
`Preview ownership v2` entry on scene adoption and once per rejected non-squad
spawner, without on-screen notifications or per-frame spam, to identify any
remaining path during the user's next test.

## Notification versus exception

The same session's screenshot text `[CurioHunter]: FOUND: Wound curio ...` matched
a normal `CurioHunter` `ECHO` in the console log at 10:04:43 UTC (18:04:43 Hong
Kong). It is that mod's shop notification, not a model replacement Lua failure.
Trace the exact message source before suppressing errors or altering unrelated
mod settings. That session contained no `<<Script Error>>` marker.
