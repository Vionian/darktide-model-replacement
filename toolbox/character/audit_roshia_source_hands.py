"""Blender-only source-hand geometry audit and real MMR comparison project.

Reads original authored joint positions and actual compiled unit poses. MMR
is used only in this offline project; no third-party plugin enters the game.
"""
import json
import pathlib
import sys
import numpy as np
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from roshia_proportion_rig import adapt
from roshia_hand_fit import evaluate

OUT = pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
unit = b.load_target_unit()
names = b.named_node_map(unit, b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
mesh = bpy.data.objects[b.MESH_OBJECT_NAME]
armature = bpy.data.objects[b.ARMATURE_OBJECT_NAME]
original = b.dynamic_rig_mapping(mesh, armature, unit, names)
adapted = adapt(b, unit, names, original, True)
root = Matrix(b.target_bind_transforms(armature, names, unit)['j_hips'].tolist())
source = {i:r['world'] for i,r in original['node_transforms'].items()}
desired = {i:r['world'] for i,r in adapted['node_transforms'].items()}
fixture = json.loads((OUT/'runtime_fixture.json').read_text())
compiled = [Matrix(np.array(w).reshape(4,4).T.tolist()) for w in fixture['roshia_arms']['world']]
bone_targets = b.source_bone_targets(armature, names, original['source_to_target'])
group_names = {g.index:g.name for g in mesh.vertex_groups}
report = {'source':str(b.SOURCE_BLEND), 'hands':{}, 'synthetic_only':True,
          'source_armature_action':(armature.animation_data.action.name
             if armature.animation_data and armature.animation_data.action else None)}
for side in ('left','right'):
    wrist = names[f'j_{side}hand']
    rigid = desired[wrist] @ source[wrist].inverted()
    keys = [n for n in names if n.startswith(f'j_{side}hand')]
    joints_error = max((compiled[names[n]].translation-(rigid@source[names[n]]).translation).length
                       for n in keys if names[n] in source)
    points=[]
    for v in mesh.data.vertices:
        total = sum(g.weight for g in v.groups if bone_targets.get(group_names[g.group], '').startswith(f'j_{side}hand'))
        if total>.999:
            points.append(list(b.source_coordinate3() @ (mesh.matrix_world @ v.co)))
    points=np.array(points)
    warps = adapted['hand_rig']['source_transforms'].get('__hand_warps', {})
    if side in warps:
        actual,jac=evaluate(warps[side], points)
    else:
        # Source-weight LBS rest articulation: no RBF/Jacobian fit is used.
        actual=[]
        for v in mesh.data.vertices:
            total=sum(g.weight for g in v.groups if bone_targets.get(group_names[g.group], '').startswith(f'j_{side}hand'))
            if total<=.999:continue
            point=b.source_coordinate3() @ (mesh.matrix_world @ v.co)
            result=Vector((0,0,0));weight=0.
            for g in v.groups:
                target=bone_targets.get(group_names[g.group])
                if target in adapted['geometry_bind_transforms']:
                    result+=g.weight*(Matrix(adapted['geometry_bind_transforms'][target].tolist())@point)
                    weight+=g.weight
            actual.append(list(result/weight))
        actual=np.array(actual);jac=None
    transform=np.array(rigid @ root)
    expected=points@transform[:3,:3].T+transform[:3,3]
    vertex_error=float(np.linalg.norm(actual-expected,axis=1).max())
    jac_error=float(abs(jac-transform[:3,:3]).max()) if jac is not None else None
    # Articulated-rest mode preserves segment lengths rather than a single
    # straight-hand rigid pose. Verify serialized pivots against the adapter.
    articulated = adapted['runtime_fk']['thumb_adaptation'][0]['method'] == 'source-length-native-rest-articulation'
    compiled_error = max((compiled[names[n]].translation-desired[names[n]].translation).length
                         for n in keys if names[n] in desired)
    assert compiled_error<2e-6,(side,compiled_error)
    native_contract = adapted['runtime_fk'].get('native_hand_contract', False)
    if not articulated and not native_contract:
        assert joints_error<2e-6,(side,joints_error)
        assert vertex_error<2e-6,(side,vertex_error)
        assert jac_error<2e-5,(side,jac_error)
    spans={}
    for digit in ('thumb','index','middle','ring','pinky'):
        chain=[names[f'j_{side}hand{digit}{k}'] for k in (1,2,3)]
        spans[digit]={'source_joint_span_mm':sum((source[j].translation-source[i].translation).length for i,j in zip(chain,chain[1:]))*1000,
                      'compiled_joint_span_mm':sum((compiled[j].translation-compiled[i].translation).length for i,j in zip(chain,chain[1:]))*1000}
        for i,j in zip(chain,chain[1:]):
            assert abs((compiled[j].translation-compiled[i].translation).length-
                       ((unit.scene_graph.nodes[j].world_transform.translation-unit.scene_graph.nodes[i].world_transform.translation).length if native_contract else (source[j].translation-source[i].translation).length))<2e-6
    report['hands'][side]={'compiled_joint_error_m':joints_error,'rigid_mesh_error_m':vertex_error,
                           'rigid_jacobian_error':jac_error,'tested_vertices':len(points),
                           'segment_scale':None if native_contract else 1.0,'radial_scale':None if native_contract else 1.0,'joint_spans':spans}
    report['hands'][side]['method'] = adapted['runtime_fk']['thumb_adaptation'][0]['method']
    report['hands'][side]['compiled_joint_error_m'] = compiled_error
    if articulated or native_contract:
        report['hands'][side].pop('rigid_mesh_error_m')
        report['hands'][side].pop('rigid_jacobian_error')
        report['hands'][side]['straight_to_articulated_mesh_change_m'] = vertex_error

# Save an actual MMR/BoneAnimCopy mapping, with auto-offset rounding disabled.
# Rounded 90-degree offsets are inappropriate for a source hand's arbitrary roll.
assert hasattr(bpy.types.Scene,'mmr_kumopult_bac_owner'), 'Install MikuMikuRig before the MMR audit'
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
inverse_names={i:n for n,i in names.items()}
keys=[n for n in names if n.startswith(('j_lefthand','j_righthand','j_leftinhand','j_rightinhand'))]
indices=[names[n] for n in keys]
hand_indices=set(indices)
def rig(name, worlds, parents):
    data=bpy.data.armatures.new(name)
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    created={}
    for i in indices:
        w=worlds[i]
        eb=data.edit_bones.new(inverse_names.get(i,f'node_{i:04d}'))
        # A new edit bone has zero length; initialize its axis before assigning
        # matrix, otherwise Blender cannot retain the requested direction.
        eb.head=(0,0,0)
        eb.tail=(0,.015,0)
        eb.matrix=Matrix(w)
        eb.length=.015
        created[i]=eb
    for i in indices:
        p=parents[i]
        if p in hand_indices:created[i].parent=created[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    obj.show_in_front=True
    return obj

native=np.array(fixture['template_world']).reshape(-1,4,4).transpose(0,2,1)
bind=np.array(fixture['roshia_arms']['world']).reshape(-1,4,4).transpose(0,2,1)
driver=rig('Darktide_native_motion',native.tolist(),fixture['parents'])
owner=rig('Roshia_source_hands_MMR',bind.tolist(),fixture['roshia_arms']['parents'])
for n in keys:
    i=names[n]
    err=float(np.max(abs(np.array(owner.data.bones[n].matrix_local)-bind[i])))
    assert err<2e-4, ('blender_bind',n,err,np.array(owner.data.bones[n].matrix_local).tolist(),bind[i].tolist())
bpy.context.scene.mmr_kumopult_bac_owner=owner
state=owner.data.mmr_kumopult_bac
state.selected_target=driver
state.ortho_offset=False
state.calc_offset=False
for name in keys:
    mapping=state.mappings.add()
    mapping.selected_owner=name
    mapping.target=name
    mapping.offset=(Matrix(native[names[name]]) .inverted() @ Matrix(bind[names[name]])).to_euler()
    mapping.has_rotoffs=True
    mapping.has_loccopy=name in ('j_lefthand','j_righthand')
    # BoneAnimCopy exposes position-axis masks separately; set them explicitly
    # for wrist contacts rather than depending on a saved UI default.
    mapping.loc_axis=(True,True,True)
bpy.context.view_layer.update()
maximum_angle=maximum_position=maximum_rotation_matrix_error=0.
case_frames={}
case_errors={}
for frame,case in enumerate(('rest','grip','staff','shield','dual_blades','reload','extreme'),1):
    pose=json.loads((OUT/f'arms_{case}_pose.json').read_text())
    worlds=pose['driver_worlds']
    # World matrices must be assigned in parent-depth order for Blender too.
    pending=set(indices)
    order=[]
    while pending:
        available=sorted(i for i in pending if fixture['parents'][i] not in pending)
        assert available
        order.extend(available)
        pending.difference_update(available)
    bpy.context.scene.frame_set(frame)
    for i in order:
        pb=driver.pose.bones[inverse_names.get(i,f'node_{i:04d}')]
        pb.rotation_mode='QUATERNION'
        p=fixture['parents'][i]
        kwargs={} if p not in hand_indices else {
            'parent_matrix':Matrix(worlds[p]),
            'parent_matrix_local':pb.parent.bone.matrix_local}
        # Supplying the explicit parent pose avoids Blender's stale parent
        # cache when assigning an entire hierarchy in one Python batch.
        pb.matrix_basis=pb.bone.convert_local_to_pose(
            Matrix(worlds[i]),pb.bone.matrix_local,invert=True,**kwargs)
        pb.keyframe_insert(data_path='location',frame=frame)
        pb.keyframe_insert(data_path='rotation_quaternion',frame=frame)
    bpy.context.view_layer.update()
    evaluated=owner.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_driver=driver.evaluated_get(bpy.context.evaluated_depsgraph_get())
    case_angle=case_position=driver_error=wrist_error=0.
    worst_joint=None
    for n in keys:
        i=names[n]
        actual=evaluated.pose.bones[n].matrix
        # MMR validates the animation/rest-axis stage. Contact IK is a second
        # stage tested independently for target residuals and fixed lengths.
        expected=Matrix(pose.get('mmr_worlds',pose['worlds'])[i])
        maximum_rotation_matrix_error=max(maximum_rotation_matrix_error,
            float(np.max(abs(np.array(actual.to_3x3())-np.array(expected.to_3x3())))))
        angle=actual.to_quaternion().rotation_difference(expected.to_quaternion()).angle
        maximum_angle=max(maximum_angle,min(angle,2*np.pi-angle))
        case_angle=max(case_angle,min(angle,2*np.pi-angle))
        driver_error=max(driver_error,float(np.max(abs(np.array(evaluated_driver.pose.bones[n].matrix)-np.array(worlds[i])))))
        # Only wrists have explicit global position constraints. All finger
        # positions follow source-length FK from those native wrist anchors.
        maximum_position=max(maximum_position,(actual.translation-expected.translation).length)
        distance=(actual.translation-expected.translation).length
        if n in ('j_lefthand','j_righthand'):wrist_error=max(wrist_error,distance)
        if distance>case_position:
            case_position=distance
            worst_joint={'name':n,'actual':list(actual.translation),'expected':list(expected.translation)}
    case_frames[case]=frame
    case_errors[case]={'angle':case_angle,'position':case_position,'driver_error':driver_error,'wrist_error':wrist_error,'worst_joint':worst_joint}
report['mmr']={'installed':True,'mapping_count':len(keys),'round_offsets_to_90_degrees':False,
               'max_rotation_error_radians':maximum_angle,'max_joint_position_error_m':maximum_position,
               'max_rotation_matrix_error':maximum_rotation_matrix_error,
               'case_frames':case_frames,'case_errors':case_errors}
(OUT/'source_hand_audit.json').write_text(json.dumps(report,indent=2))
# Fail before delivery if the actual plugin disagrees with the runtime adapter.
assert maximum_angle<.002, report['mmr']
assert maximum_rotation_matrix_error<1e-4, report['mmr']
assert maximum_position<2e-5, report['mmr']
bpy.context.scene.frame_start=1
bpy.context.scene.frame_end=len(case_frames)
for case,frame in case_frames.items():
    bpy.context.scene.timeline_markers.new('Synthetic: '+case,frame=frame)
instructions=bpy.data.texts.new('READ_ME')
instructions.write('This is an offline MikuMikuRig BoneAnimCopy comparison.\n'
    'Darktide_native_motion is the driver; Roshia_source_hands_MMR is the target.\n'
    'Frames are SYNTHETIC regression poses, NOT captured game animations.\n'
    'Native-contact mode deliberately adapts authored source joint distances offline; all 1P nodes follow native animation.\n'
    'Automatic 90-degree offset rounding is disabled.\n'
    'No MMR plugin, action, or Python is installed in the game.\n')
bpy.context.scene.frame_set(1)
bpy.context.view_layer.objects.active=owner
owner.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'roshia_source_hand_mmr.blend'))
print('SOURCE_HAND_MMR_AUDIT '+json.dumps(report))
