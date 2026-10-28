# Opaque garment backs and matching motion fixtures (2026-10-22)

## Verified resource mismatch

Perlica's authored MMD materials Cloth1, Cloth2 and Cloth2Alpha have
`mmd_material.is_double_sided=true` and Blender backface culling disabled.
The native export forced these physical garments onto opaque substance_basic,
but only duplicated alpha-card and eye-layer triangles. The reverse garment
surface therefore did not exist in the serialized resource. Running and low
camera angles can expose that reverse surface. This is a verified export
mismatch consistent with the reported missing torso/waist panels; an offline
preview does not prove the entirety of the reported game defect is fixed.

`native_garment_sides.py` and `patch_endfield_garment_sides.py` repair missing
reverse faces of source-authored double-sided opaque Cloth materials, excluding
alpha resources already handled by the exporter. They check existing coverage
using cyclic triangle keys containing position, UV, weights and palette IDs.
They append opposite winding/normals and an appropriate tangent frame, with
uint16 limits enforced. Every original front stream remains an identical byte
prefix. The raw unit suffix containing skins, scene graph, attachments and
material maps remains identical. Texture payloads and all first-person units
are preserved. Current exports also carry an explicit double-sided garment flag
and account for its additional vertices in chunk allocation.

The October 22 source/resource pass found this mismatch in 18 Endfield bodies
or outfit assets (15 character profiles plus three Si outfits). The patch keeps
31 geometry/material slots; triangle counts rise where back surfaces are added.
This check does not justify duplicating closed skin/face meshes or globally
disabling renderer culling.

## Perlica's separate dynamic stability adaptation

The candidate reduces Perlica from 131 to 45 pendulum helpers (26 hair and
19 cloth). Connected coat/inner-skirt grid controls use the torso/limb binding;
ribbons, hem dangles and springs remain simulated. Source cloth grids are not
equivalent to a set of independent pendulums. A matching synthetic gait removed
the sampled greater-than-3x area stretches (baseline 2/3 triangles in two
sampled frames, candidate 0). This small count is not evidence that dynamics
alone caused the large game screenshot holes. Do not claim it as the sole cause.

Core named-joint world transforms are unchanged. Rebuilding this candidate
changed a diffuse texture and reordered two equivalent runtime records; neither
is needed for this repair. Restore existing texture artifacts and keep the
production first-person assets. Compare configuration bone records by name as
well as serialized order, so an incidental same-depth order change is not
mistaken for a different hand rig.

## Motion audit limits

- Generate poses with each unit's own serialized fixture, inverse binds and
  matching runtime configs. A 131-helper pose applied to a 45-helper rig, or a
  different character's pose, produces invalid displacement statistics.
- A rest-versus-posed normal dot product below zero is not a flipped triangle
  test: valid rigid rotations exceeding 90 degrees also change its sign.
- A static AABB overrun does not establish renderer culling. Actor/root motion
  and mesh local space must be handled, and actual engine behavior is separate.
- Triangle area and edge ratios are rotation invariant but only diagnostics;
  narrow valid triangles or blended joint folds can also have small area.
- `test_roshia_contacts.py --cases rest motion run` executes the production Lua
  with a synthetic alternating gait and stale target world caches. It is not a
  captured Darktide run. `--serialized-geometry` previews the actual patched
  streams; it does not claim a fresh source-builder byte match.

Record source, candidate, installed hashes and completed/pending stages in a
durable task-status file. After context compaction, continue from its next
unfinished step instead of restarting source and bounds investigations.

## Deployment evidence

The October 22 deployment copied 60 tracked files for the 18 body/outfit assets
and Perlica's matched generated configs, with both workspace/game readback hashes.
All non-unit material/texture artifacts matched the existing installation before
copying. All 23 first-person unit hashes remained unchanged. Custom Assets found
49 ready assets, updated 18 bundles, and its final dry-run reported zero bundle,
stream or database changes pending. Backup and deployment records are under
`tools/model-work/endfield_surface_fix_20261022/`. The game was not launched;
gameplay outcome remains pending user testing.

## Follow-up: open source interiors are a separate defect

The user reported that the deployed garment-back patch still failed, then
clarified the view: only looking upward from inside the skirt shows the gap;
ordinary exterior views stay complete. This evidence does not support hiding
the entire body unit. Inspect actual source boundary loops before repeating
bounds or runtime visibility changes. A reverse face cannot fill missing mesh.

Perlica's source has a 22-vertex tights waist boundary and a separate 38-vertex
under-chest boundary, with no continuous torso surface joining them. The
source-specific `perlica_torso_lining.py` bridges these real loops with a closed
garment lining, interpolates their skin influences, and uses an existing uniform
textile UV area. Local reverse hip panels cover their authored interior. This
is an adaptation for the inspected clothed source; do not cap every boundary
or synthesize body geometry on unrelated characters.

The native surface patch appends 1,680 lining and 486 reverse hip triangles.
All original exterior streams remain byte prefixes and the serialized skeleton/
material suffix stays identical. The source collect hook is separately executed
to preserve future rebuilds and bypasses first-person exports. Five matching
synthetic gait frames retain finite, normalized influences without degenerate
new triangles. These checks are offline evidence, not captured game animation.

Compare the serialized before/after units with identical pose, camera AND lights.
Saved preview scenes may use view-dependent light positions, even when their
cameras are later matched. Here the interior gap is occluded in the comparison
and the ordinary exterior remains visually consistent. Record deployment and
pending user gameplay confirmation separately; do not label the original
garment-back pass a complete fix after contrary user evidence.

This follow-up was deployed at 2026-10-22 23:59 +08:00: only the Perlica body
unit and its two manifests were replaced, with matching workspace/game hashes.
All 23 installed first-person units stayed unchanged. Custom Assets updated one
bundle and its final dry-run reported no pending bundle/stream/database writes.
The recoverable backup and deployment record are under
`tools/model-work/perlica_interior_fix_20261022/`. User gameplay verification
is still pending; do not infer it from successful deployment.
