"""Run inside Blender; source files are opened read-only and never saved in place."""
import json
import math
from pathlib import Path
import subprocess
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from darktide import murmur64, save_json


def inspect_source():
    objects = []
    for obj in bpy.data.objects:
        row = {"name": obj.name, "type": obj.type, "parent": obj.parent.name if obj.parent else None,
               "hidden": obj.hide_get(), "matrix_world": [list(r) for r in obj.matrix_world]}
        if obj.type == 'MESH':
            row.update(vertices=len(obj.data.vertices), faces=len(obj.data.polygons),
                       armature=obj.find_armature().name if obj.find_armature() else None,
                       materials=[mat.name if mat else None for mat in obj.data.materials],
                       vertex_groups=[group.name for group in obj.vertex_groups])
        elif obj.type == 'ARMATURE':
            row['bones'] = [{'name': bone.name, 'parent': bone.parent.name if bone.parent else None,
                             'head': list(bone.head_local), 'tail': list(bone.tail_local)} for bone in obj.data.bones]
        objects.append(row)
    images = [{'name': im.name, 'path': bpy.path.abspath(im.filepath), 'packed': bool(im.packed_file),
               'size': list(im.size), 'color_space': im.colorspace_settings.name,
               'missing': not im.packed_file and im.source == 'FILE' and not Path(bpy.path.abspath(im.filepath)).is_file()}
              for im in bpy.data.images]
    return {'blender': bpy.app.version_string, 'objects': objects, 'images': images,
            'materials': [{'name': mat.name, 'uses_nodes': mat.use_nodes,
                'node_types': [node.bl_idname for node in mat.node_tree.nodes] if mat.node_tree else []}
                for mat in bpy.data.materials]}


def enable_sdk(job):
    sys.path.insert(0, job['addon_parent'])
    bpy.ops.preferences.addon_enable(module='darktide_assets')
    import darktide_assets as sdk
    preferences = bpy.context.preferences.addons['darktide_assets'].preferences
    preferences.compiler = job['compiler']
    preferences.game_folder = job['game']
    preferences.game_extract_folder = job['extract']
    return sdk


def select_objects(objects, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_select = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active or objects[0]


def choose_source(profile):
    if profile.get('meshes'):
        meshes = [bpy.data.objects[name] for name in profile['meshes']]
    else:
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and len(obj.data.polygons)
                  and len(obj.data.materials) and not obj.hide_get()]
    if not meshes:
        raise ValueError('No visible mesh with materials found; provide profile.meshes explicitly')
    if profile['kind'] == 'weapon':
        return meshes, None
    armatures = {obj.find_armature() for obj in meshes if obj.find_armature()}
    arm = bpy.data.objects[profile['armature']] if profile.get('armature') else next(iter(armatures)) if len(armatures) == 1 else None
    if arm is None:
        raise ValueError('Character needs one unambiguous armature; set profile.armature and profile.meshes')
    unrelated = [obj.name for obj in meshes if obj.find_armature() != arm and obj.parent != arm]
    if unrelated:
        raise ValueError('Review unbound/helper meshes before building: ' + ', '.join(unrelated))
    return meshes, arm


def create_asset(sdk, job, objects, name, resource, arm=None):
    select_objects(objects, arm or objects[0])
    if bpy.ops.darktide.create_asset_collection() != {'FINISHED'}:
        raise ValueError('SDK failed to create an asset collection')
    scene = bpy.context.scene.dt_asset
    scene.output_path = str(Path(job['output']) / 'compiled')
    identity = scene.asset_collection.dt_asset_identity
    identity.asset_filename = name
    identity.asset_path = resource
    identity.output_kind = 'model'
    identity.only_weighted_bones = bool(arm)
    for obj in objects:
        if obj.type == 'MESH':
            obj.dt_collider.unit_actor = 'none'
    return scene.asset_collection


def check_images(meshes):
    missing = []
    for obj in meshes:
        for mat in obj.data.materials:
            if not mat or not mat.node_tree:
                continue
            for node in mat.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or not node.outputs['Color'].is_linked:
                    continue
                image = node.image
                if image is None or (image.source == 'FILE' and not image.packed_file and not Path(bpy.path.abspath(image.filepath)).is_file()):
                    missing.append((mat.name, node.name))
    if missing:
        raise ValueError('Connected textures are missing; resolve or bake the source graph first: ' + str(missing))


def apply_material_overrides(meshes, profile):
    settings = profile.get('materials', {})
    for obj in meshes:
        for material in obj.data.materials:
            if material is None:
                raise ValueError(f'Empty material slot on {obj.name}')
            override = settings.get(material.name, {})
            if 'double_sided' in override:
                material.dt_material.double_sided = bool(override['double_sided'])
            if profile['kind'] == 'weapon':
                material['darktide_material'] = {'version': 1, 'mode': 'generated', 'weapon': True}
            if 'intent' in override:
                material['darktide_material'] = override['intent']


def fit_character(sdk, collection, arm, profile, job):
    identity = collection.dt_asset_identity
    identity.skeleton_preset = 'human'
    sdk.apply_skeleton_preset(identity, job['extract'], 'human')
    if bpy.ops.darktide.auto_map_bones() != {'FINISHED'}:
        raise ValueError('SDK could not map the source skeleton')
    overrides = profile.get('bone_map', {})
    known = {row.source_bone for row in identity.bone_map}
    if set(overrides) - known:
        raise ValueError('Bone-map overrides refer to missing source bones: ' + str(set(overrides) - known))
    for row in identity.bone_map:
        if row.source_bone in overrides:
            row.target_bone = overrides[row.source_bone]
    mapping = {row.source_bone: row.target_bone for row in identity.bone_map if row.target_bone}
    missing = sdk.fit_skeleton.missing_required(mapping.values())
    if missing:
        raise ValueError('Review source bone mapping before fitting: ' + ', '.join(missing))
    identity.fit_keep_torso = bool(profile.get('keep_torso_shape', False))
    identity.fit_keep_proportions = bool(profile.get('keep_proportions', False))
    fitted, lines = sdk.fit_skeleton.fit_to_skeleton(bpy.context, collection, arm, mapping)
    save_json(Path(job['output']) / 'bone-map.json', {'mapping': mapping, 'fit_report': lines,
        'method': 'SDK native-rest skeleton fit', 'source_hand_mmr_executed': False,
        'note': 'Source-hand MMR authoring is a separate optional expert route; do not claim it ran here.'})
    return fitted


def first_person_meshes(meshes, arm, profile):
    wanted = set(profile.get('first_person_meshes', []))
    allowed = {bone.name for bone in arm.data.bones if bone.name.startswith(('j_leftarm', 'j_rightarm',
        'j_leftforearm', 'j_rightforearm', 'j_lefthand', 'j_righthand', 'j_leftshoulder', 'j_rightshoulder'))}
    if not allowed:
        raise ValueError('Fitted rig has no recognized native arm bones')
    result = []
    for obj in meshes:
        if wanted and obj.name not in wanted:
            continue
        indices = {group.index for group in obj.vertex_groups if group.name in allowed}
        keep = {v.index for v in obj.data.vertices if sum(group.weight for group in v.groups if group.group in indices) >= 0.5}
        if not keep:
            continue
        copy = obj.copy()
        copy.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(copy)
        copy.name = obj.name + '_first_person'
        bm = bmesh.new()
        bm.from_mesh(copy.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context='VERTS')
        bm.to_mesh(copy.data)
        bm.free()
        if copy.data.polygons:
            result.append(copy)
    if not result:
        raise ValueError('First-person arm extraction is empty; inspect skin weights or profile.first_person_meshes')
    return result


def align_weapon(meshes, profile):
    alignment = profile.get('alignment')
    if not alignment or not profile.get('coordinate_frame_reviewed'):
        raise ValueError('Weapon alignment must be measured against its native attachment family; see docs/weapons.md')
    scale = float(alignment.get('uniform_scale', 1))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Weapon uniform_scale must be finite and positive')
    rotate = Euler(tuple(math.radians(float(x)) for x in alignment.get('rotation_degrees', [0, 0, 0])), 'XYZ').to_matrix().to_4x4()
    transform = Matrix.Translation(Vector(alignment.get('target_grip', [0, 0, 0]))) @ rotate @ Matrix.Scale(scale, 4) @ Matrix.Translation(-Vector(alignment.get('source_grip', [0, 0, 0])))
    for obj in meshes:
        original = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.data = obj.data.copy()
        obj.data.transform(transform @ original)
        obj.data.update()


def compile_collection(job):
    if bpy.ops.darktide.build_asset() != {'FINISHED'}:
        raise ValueError('Native compilation failed; inspect compiled/<asset>/build.log')
    collection = bpy.context.scene.dt_asset.asset_collection
    path = Path(job['output']) / 'compiled' / collection.dt_asset_identity.asset_filename
    units = list(path.glob('*.unit'))
    if not units:
        raise ValueError('Compiler produced no native UNIT')
    for unit in units:
        subprocess.run([job['compiler'], '--validate', str(unit)], check=True)
    return path


def build(job, sdk):
    profile = job['profile']
    slug = profile['id']
    meshes, arm = choose_source(profile)
    check_images(meshes)
    apply_material_overrides(meshes, profile)
    resource = 'content/mods/' + slug
    compiled = []
    if profile['kind'] == 'character':
        collection = create_asset(sdk, job, meshes + [arm], slug + '_body', resource + '/body', arm)
        arm = fit_character(sdk, collection, arm, profile, job)
        meshes = [obj for obj in collection.all_objects if obj.type == 'MESH']
        compiled.append(compile_collection(job))
        arms = first_person_meshes(meshes, arm, profile)
        collection = create_asset(sdk, job, arms + [arm], slug + '_arms', resource + '/arms', arm)
        sdk.apply_skeleton_preset(collection.dt_asset_identity, job['extract'], 'human')
        compiled.append(compile_collection(job))
    else:
        align_weapon(meshes, profile)
        create_asset(sdk, job, meshes, slug, resource + '/weapon')
        compiled.append(compile_collection(job))
    from native_audit import audit_asset
    audits = [audit_asset(folder, sdk) for folder in compiled]
    save_json(Path(job['output']) / 'native-audit.json', audits)
    save_json(Path(job['output']) / 'build-report.json', {
        'profile': profile, 'source_sha256': job['source_sha256'],
        'blender': bpy.app.version_string, 'assets': [p.name for p in compiled],
        'native_audits_passed': True, 'in_game_visual_verified': False,
        'source_hand_mmr_executed': False,
        'first_person_reference': 'human third-person native bind, linked to native first-person node names; verify representative weapon contacts in game',
    })
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(job['output']) / (slug + '_candidate.blend')))


def main():
    job_path = Path(sys.argv[sys.argv.index('--') + 1])
    job = json.loads(job_path.read_text(encoding='utf-8'))
    save_json(Path(job['output']) / 'source-inspection.json', inspect_source())
    if job['mode'] == 'build':
        build(job, enable_sdk(job))
    print('DARKTIDE_TOOLKIT_DONE', job['mode'])


if __name__ == '__main__':
    main()
