"""Model-specific FK: native animation axes, Roshia joint distances.

3P preserves source torso proportions. Eligible Endfield profiles use measured
source arm lengths with native rotations; wide-sleeved exceptions retain contacts. Selected
source-digit profiles retain their own distal phalange lengths in native axes.
1P engine-links the complete native hand rig and fits the authored surface.
Native rest articulation is baked with source weights. The runtime separately
compensates wielded 3P equipment for the resulting palm displacement.
"""
import copy
import json
import numpy as np
from mathutils import Matrix, Vector


def adapt(builder, unit, names, original, first_person=False):
    rig = copy.deepcopy(original)
    source = {i: r['world'].copy() for i, r in rig['node_transforms'].items()}
    parents = {i: r['parent_index'] for i, r in rig['node_transforms'].items()}
    by_index = {i: n for n, i in names.items()}
    native = {i: n.world_transform.copy() for i, n in enumerate(unit.scene_graph.nodes)}
    desired, order, visiting = {}, [], set()
    root_map = Matrix(builder.target_bind_transforms(
        builder.bpy.data.objects[builder.ARMATURE_OBJECT_NAME], names, unit)['j_hips'].tolist())
    source_digits = not first_person and getattr(builder, 'SOURCE_BODY_FINGER_LENGTHS', False)
    def distal_finger(name):
        return name.startswith(('j_lefthand', 'j_righthand')) and name[-1:] in ('2', '3')

    def solve(i):
        if i in desired: return desired[i]
        if i in visiting: raise ValueError('Proportion rig parent cycle')
        if i not in source: return native[i]
        visiting.add(i)
        p = parents[i]
        pw = solve(p)
        name = by_index[i]
        if name.startswith('j_'):
            w = native[i].copy()
            finger = 'hand' in name and not name.endswith('hand') and 'inhand' not in name
            native_arm = name.startswith(('j_left','j_right')) and any(
                token in name for token in ('shoulder','arm','hand'))
            if source_digits and distal_finger(name):
                # Keep native palm/contact roots and rest bend directions,
                # but never stretch the source phalanges to adult-rig lengths.
                source_length = (source[i].translation - source[p].translation).length
                native_axis = native[i].translation - native[p].translation
                w.translation = pw.translation + native_axis.normalized() * source_length
            elif first_person or native_arm:
                pass  # Native arm/wrist positions preserve weapon contacts.
            elif name == 'j_hips':
                w.translation = source[i].translation
            else:
                sp = source.get(p, native[p])
                offset = sp.to_3x3().transposed() @ (source[i].translation - sp.translation)
                w.translation = pw.translation + pw.to_3x3() @ offset
        else:
            sp = source.get(p, native[p])
            w = pw @ sp.inverted() @ source[i]
        desired[i] = w
        visiting.remove(i)
        order.append(i)
        return w

    for i in source: solve(i)
    thumb_adaptation = []
    surface_maps = {}
    surface_report = []
    coherent_hands = first_person or getattr(builder, 'COHERENT_BODY_HANDS', False)
    if coherent_hands:
        # The engine contact skeleton is shared by all working human models.
        # Fit the authored surface offline; never chase unreachable contacts.
        for i in order:
            if first_person and by_index[i].startswith('j_'):
                desired[i] = native[i].copy()
        from roshia_native_hand_surface import fit_maps
        builder.HAND_SURFACE_TARGETS = desired if source_digits else native
        builder.HAND_SURFACE_SOURCE_DIGITS = source_digits
        surface_maps, surface_report = getattr(builder, 'hand_surface_fitter', fit_maps)(
            builder, original, source, native, names, root_map)
        thumb_adaptation = [{'side': side, 'method': ('source-length-native-rest-articulation'
                             if source_digits else 'native-contact-source-surface')}
                            for side in ('left', 'right')]
        print('ROSHIA_HAND_SURFACE ' + json.dumps(surface_report))
    if not first_person:
        arm = builder.bpy.data.objects[builder.ARMATURE_OBJECT_NAME]
        mesh = builder.bpy.data.objects[builder.MESH_OBJECT_NAME]
        mapping = builder.source_bone_targets(arm, names, rig['source_to_target'])
        group_names = {g.index: g.name for g in mesh.vertex_groups}
        floor = None
        for v in mesh.data.vertices:
            influence = {}
            for a in v.groups:
                n = mapping.get(group_names.get(a.group))
                if n in ('j_leftfoot', 'j_rightfoot'):
                    influence[n] = influence.get(n, 0) + a.weight
            if not influence or max(influence.values()) < .9: continue
            i = names[max(influence, key=influence.get)]
            point = desired[i] @ source[i].inverted() @ root_map @ (builder.source_coordinate3() @ (mesh.matrix_world @ v.co))
            floor = point.z if floor is None else min(floor, point.z)
        if floor is not None:
            source_floor = min((root_map @ (builder.source_coordinate3() @ (mesh.matrix_world @ v.co))).z for v in mesh.data.vertices)
            for i,w in desired.items():
                name=by_index[i]
                if not (name.startswith(('j_left','j_right')) and any(t in name for t in ('shoulder','arm','hand'))):
                    w.translation.z += source_floor - floor

    shoulder_supports=[]
    support_maps={}
    if not first_person:
        from roshia_shoulder_fit import add_supports
        shoulder_supports,support_maps=add_supports(builder,rig,source,desired,parents,names,root_map)
    maps = {by_index[i]: np.asarray(desired[i] @ source[i].inverted() @ root_map, dtype=np.float32) for i in source}
    maps.update(support_maps)
    maps.update(surface_maps)
    if getattr(builder,'COSTUME_NATIVE_SEGMENT_FIT',False):
        from costume_native_arm_fit import apply as fit_native_segments
        fit_native_segments(builder,source,desired,names,root_map,maps,first_person,parents,rig.get('runtime_bones',()))
    records = builder.scene_graph_transform_records(unit, desired, parents)
    rig['node_transforms'] = records
    rig['hand_node_transforms'] = {i: records[i] for i in rig['hand_node_transforms']}
    rig['geometry_bind_transforms'] = maps
    rig['bind_transforms'] = {n: maps[n] for n in rig['bind_transforms']}
    rig['hand_rig']['source_transforms'] = {}
    from roshia_hand_fit import hand_warps
    if not coherent_hands:
        rig['hand_rig']['source_transforms']['__hand_warps']=hand_warps(builder,original,desired,names,root_map)
    # 1P uses the source's actual skin weights for the rest-pose articulation,
    # not a global RBF interpolation that can shear finger pads and webbing.
    if coherent_hands:
        rig['hand_rig']['source_transforms']['__finger_width_scale'] = 1.0
        if first_person and getattr(builder,'COSTUME_WRIST_CONTINUITY',False):
            from costume_wrist_continuity import describe
            rig['hand_rig']['source_transforms']['__wrist_continuity']=describe(source,native,names,root_map,surface_maps)
        if source_digits:
            # Native reference weight fields must be sampled in their original
            # coordinate system, not at our shorter destination finger points.
            rig['hand_rig']['source_transforms']['__source_digit_targets'] = {
                by_index[i]: desired[i].translation[:] for i in desired
                if by_index[i].startswith(('j_lefthand', 'j_righthand'))}
    rig['hand_rig']['node_transforms'] = rig['hand_node_transforms']
    rig['binding_mode'] = 'proportion-fk'
    runtime = []
    for i in order:
        name = by_index[i]
        if not name.startswith('j_'): continue
        p = parents[i]
        pw = desired.get(p, native[p])
        local = pw.inverted() @ desired[i]
        q = local.to_quaternion()
        pq = native[p].to_quaternion()
        native_local = native[p].inverted() @ native[i]
        nq = native_local.to_quaternion()
        pre = (pw.to_3x3().transposed() @ native[p].to_3x3()).to_quaternion()
        post = (native[i].to_3x3().transposed() @ desired[i].to_3x3()).to_quaternion()
        finger = 'hand' in name and not name.endswith('hand') and 'inhand' not in name
        # Rest-aware local rotation transfer; native animation supplies the
        # motion, authored source pivots supply the hand's proportions.
        native_arm = name.startswith(('j_left','j_right')) and any(
            token in name for token in ('shoulder','arm','hand'))
        limit = 180
        gain = 1.0
        source_hand_fk = False
        native_position_driver = bool(first_person or native_arm) and not (source_digits and distal_finger(name))
        runtime.append({'name': name, 'parent': by_index.get(p), 'parent_index': p,
                        'offset': list(local.translation), 'rest_rotation': [q.x, q.y, q.z, q.w],
                        'native_rest_rotation': [nq.x, nq.y, nq.z, nq.w],
                        'rotation_pre': [pre.x, pre.y, pre.z, pre.w],
                        'rotation_post': [post.x, post.y, post.z, post.w],
                        'parent_position': list(native[p].translation),
                        'parent_rotation': [pq.x, pq.y, pq.z, pq.w],
                        'native_position': list(native[i].translation),
                        'position_offset': list(desired[i].translation - native[i].translation),
                        'native_position_driver': native_position_driver,
                        'finger': finger, 'source_hand_fk': source_hand_fk,
                        'angle_limit': limit, 'curl_gain': gain})
    chains = []
    grip_chains = []
    if first_person:
        rig.pop('node_renames', None)
        for d in runtime:
            d['target_name'] = d['name']
            d['engine_linked'] = True
    rig['hand_surface_report'] = surface_report
    rig['runtime_fk'] = {'schema': 5, 'first_person': first_person,
                         'native_hand_contract': first_person,
                         'source_digit_lengths': source_digits,
                         'engine_linked': first_person, 'bones': runtime,
                         'grip_chains': grip_chains,
                         'arm_chains':chains,'shoulder_supports':shoulder_supports,
                         'thumb_adaptation':thumb_adaptation, 'surface_fit':surface_report}
    from endfield_arm_policy import apply_builder_source
    apply_builder_source(builder, rig['runtime_fk'], root_map)
    return rig


def write_config(path, body, arms):
    data = {'schema': 1, 'body': body['runtime_fk'], 'arms': arms['runtime_fk']}
    path.with_suffix('.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    def lua(v):
        if isinstance(v, dict):
            return '{' + ', '.join(k + ' = ' + lua(x) for k, x in v.items() if x is not None) + '}'
        if isinstance(v, list): return '{' + ', '.join(lua(x) for x in v) + '}'
        if isinstance(v, bool): return 'true' if v else 'false'
        return json.dumps(v, ensure_ascii=True)
    path.write_text('-- Generated native axes and Roshia joint distances.\nreturn ' + lua(data) + '\n', encoding='ascii')
