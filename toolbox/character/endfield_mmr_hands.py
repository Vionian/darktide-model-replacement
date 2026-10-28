"""Original-source hand articulation through real MMR BoneAnimCopy constraints.

MMR supplies evaluated joint placement and rest-axis rotation. Anatomy fitting
supplies segment lengths and one shared cross-section scale per digit. Only the
offline surface is fitted to the selected rig: wrist/palm contacts remain native,
while source-digit 3P profiles retain their own distal segment lengths.
"""
import json
import pathlib
import numpy as np
from mathutils import Matrix
from roshia_native_hand_surface import frame, reference_zones

REFERENCES = ('daniya_blue_arms', 'qianxia_arms', 'aimisi_arms')


def fit_maps(b, original, source, native, names, root_map):
    bpy = b.bpy
    assert hasattr(bpy.types.Scene, 'mmr_kumopult_bac_owner'), 'MMR is required for source-hand authoring'
    arm = bpy.data.objects[b.ARMATURE_OBJECT_NAME]
    mesh = bpy.data.objects[b.MESH_OBJECT_NAME]
    mapping = b.source_bone_targets(arm, names, original['source_to_target'])
    group_names = {g.index:g.name for g in mesh.vertex_groups}
    roots = root_map @ b.source_coordinate3().to_4x4()
    target_rig = getattr(b, 'HAND_SURFACE_TARGETS', native)
    source_digits = getattr(b, 'HAND_SURFACE_SOURCE_DIGITS', False)
    zones = {}
    for v in mesh.data.vertices:
        merged = {}
        for g in v.groups:
            n = mapping.get(group_names[g.group], '')
            if n.startswith(('j_lefthand', 'j_righthand')):
                merged[n] = merged.get(n, 0.) + g.weight
        for n, weight in merged.items():
            if weight > .5:
                zones.setdefault(n, []).append(list(roots @ (mesh.matrix_world @ v.co)))
    zones = {n:np.asarray(v) for n,v in zones.items()}
    # Costume sleeves/decorations must not redefine a digit's calibration
    # envelope. Optional points are from the unchanged authored source hand,
    # moved through the same source shoulder rest rotation as the costume.
    if getattr(b,'HAND_CALIBRATION_POINTS',None):
        from mathutils import Vector
        zones={n:np.asarray([roots@Vector(p)for p in points])
               for n,points in b.HAND_CALIBRATION_POINTS.items()}
    refs = {r:reference_zones(b, r) for r in REFERENCES}
    # Canonical source joints only; wrist helpers are not substitutes for the
    # authored Japanese MMD wrist/finger bones.
    canonical = {}
    for bone in arm.data.bones:
        n = mapping.get(bone.name, '')
        base=bone.name.rsplit('.',1)[0]
        allowed={'手首','親指０','親指１','親指２'} | {
            d+k for d in ('人指','中指','薬指','小指') for k in ('１','２','３')}
        if n.startswith(('j_lefthand', 'j_righthand')) and base in allowed:
            if n in canonical:
                raise ValueError(('Ambiguous authored hand joint', n, bone.name))
            canonical[n] = bone.name
    assert len(canonical) == 32, ('Missing original hand joints', canonical)

    specs = {}
    report = []
    def specify(n, origin, target, fs, ft, scales, detail):
        specs[n] = (origin, target, fs, ft, np.asarray(scales))
        report.append(dict(name=n, method='source-MMR-coherent-digit-fit',
                           transverse_center_offset_mm=[0., 0.], **detail))

    for side in ('left', 'right'):
        prefix = f'j_{side}hand'
        def pos(collection, key):
            return np.asarray(collection[names[prefix+key]].translation, dtype=float)
        sw, tw = pos(source, ''), pos(target_rig, '')
        sf = frame(pos(source, 'middle1')-sw,
                   np.cross(pos(source, 'middle1')-sw, pos(source, 'pinky1')-pos(source, 'index1')))
        tf = frame(pos(native, 'middle1')-tw,
                   np.cross(pos(native, 'middle1')-tw, pos(native, 'pinky1')-pos(native, 'index1')))
        width = np.linalg.norm(pos(native, 'pinky1')-pos(native, 'index1')) / np.linalg.norm(pos(source, 'pinky1')-pos(source, 'index1'))
        length = np.linalg.norm(pos(native, 'middle1')-tw) / np.linalg.norm(pos(source, 'middle1')-sw)
        specify(prefix, sw, tw, sf, tf, [length,width,width], {'kind':'palm'})
        for digit in ('thumb', 'index', 'middle', 'ring', 'pinky'):
            chain = [digit+str(k) for k in (1,2,3)]
            sections, rows = [], []
            for k,key in enumerate(chain):
                a,c = (k,k+1) if k < 2 else (k-1,k)
                sv = pos(source,chain[c])-pos(source,chain[a])
                tv = pos(target_rig,chain[c])-pos(target_rig,chain[a])
                fs, ft = frame(sv,sf[:,2]), frame(tv,tf[:,2])
                origin, target = pos(source,key), pos(target_rig,key)
                n = prefix+key
                sp = zones.get(n, np.empty((0,3)))
                sl = (sp-origin)@fs
                ratios, tips = [], []
                for ref in REFERENCES:
                    tp = refs[ref].get(n, np.empty((0,3)))
                    if len(sp) < 8 or len(tp) < 8: continue
                    tl = (tp-target)@ft
                    slo,shi = np.quantile(sl,[.05,.95],axis=0)
                    tlo,thi = np.quantile(tl,[.05,.95],axis=0)
                    if np.all(shi[1:]-slo[1:] > .001) and np.all(thi[1:]-tlo[1:] > .001):
                        ratios.append((thi[1:]-tlo[1:])/(shi[1:]-slo[1:]))
                    if k==2 and shi[0]>.003 and thi[0]>.003:
                        tips.append(float(thi[0]/shi[0]))
                if ratios: sections.append(np.median(ratios,axis=0))
                axial = np.linalg.norm(tv)/np.linalg.norm(sv)
                if k==2 and tips and not source_digits: axial=float(np.median(tips))
                if source_digits: axial=1.0
                rows.append((n,origin,target,fs,ft,axial,len(sp)))
            # Independent centers/scales at each joint create radial steps and
            # webbing dents. Use a robust digit-wide envelope, anchored at the
            # exact original/native pivots with no lateral translations.
            radial = np.median(sections,axis=0) if sections else np.array([width,width])
            for n,origin,target,fs,ft,axial,samples in rows:
                specify(n,origin,target,fs,ft,[axial,*radial],
                        {'kind':digit,'source_samples':samples,
                         'longitudinal_scale':float(axial),
                         'shared_digit_transverse_scales':radial.tolist(),
                         'reference_models':list(REFERENCES)})

    # Create a driver in the original armature's coordinates. Its rest axes
    # encode the actual source-to-native palm/phalange rotation, not a copy of
    # the native skeleton used as both owner and driver.
    source_to_dt = roots @ arm.matrix_world
    dt_to_source = source_to_dt.inverted()
    wanted = {}
    for n, (origin,target,fs,ft,scales) in specs.items():
        bone = arm.data.bones[canonical[n]]
        dt_rest = source_to_dt.to_quaternion().to_matrix() @ bone.matrix_local.to_quaternion().to_matrix()
        w = Matrix((ft@fs.T@np.asarray(dt_rest)).tolist()).to_4x4()
        w.translation = target
        local = dt_to_source @ w
        normalized = local.to_quaternion().to_matrix().to_4x4()
        normalized.translation = local.translation
        wanted[n] = normalized
    active = bpy.context.view_layer.objects.active
    selected = list(bpy.context.selected_objects)
    for obj in selected: obj.select_set(False)
    data = bpy.data.armatures.new(b.MODEL_PROFILE+'_MMR_native_contact_targets')
    driver = bpy.data.objects.new(data.name, data)
    bpy.context.collection.objects.link(driver)
    driver.matrix_world = arm.matrix_world
    bpy.context.view_layer.objects.active = driver
    driver.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for n,w in wanted.items():
        eb = data.edit_bones.new(n)
        display_length=getattr(b,'MMR_DRIVER_DISPLAY_LENGTH',.015)
        eb.head=(0,0,0); eb.tail=(0,display_length,0)
        eb.matrix=w; eb.length=display_length
    bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    previous_owner = scene.mmr_kumopult_bac_owner
    scene.mmr_kumopult_bac_owner = arm
    state = arm.data.mmr_kumopult_bac
    assert not len(state.mappings), 'Use a clean source armature for MMR calibration'
    state.selected_target = driver
    state.ortho_offset=False; state.calc_offset=False
    state.preview=True
    for n in specs:
        m=state.mappings.add()
        m.selected_owner=canonical[n]; m.target=n
        m.has_rotoffs=False
        m.has_loccopy=True; m.loc_axis=(True,True,True)
    bpy.context.view_layer.update()
    evaluated = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    maps = {}
    max_error = 0.
    worst_joint = None
    for n,(origin,target,fs,ft,scales) in specs.items():
        actual = evaluated.pose.bones[canonical[n]].matrix.copy()
        error=float(np.max(abs(np.asarray(actual)-np.asarray(wanted[n]))))
        if error>max_error:
            max_error=error
            worst_joint={'joint':n,'source':canonical[n],
                'requested_vs_driver_rest':float(np.max(abs(np.asarray(driver.data.bones[n].matrix_local)-np.asarray(wanted[n])))),
                'owner_vs_driver_rest':float(np.max(abs(np.asarray(actual)-np.asarray(driver.data.bones[n].matrix_local)))),
                'position_error':float((actual.translation-wanted[n].translation).length)}
        source_rot = source_to_dt.to_quaternion().to_matrix() @ arm.data.bones[canonical[n]].matrix_local.to_quaternion().to_matrix()
        actual_rot = source_to_dt.to_quaternion().to_matrix() @ actual.to_quaternion().to_matrix()
        delta = np.asarray(actual_rot @ source_rot.transposed())
        linear = delta @ fs @ np.diag(scales) @ fs.T
        anchor = np.asarray(source_to_dt @ actual.translation)
        w=np.eye(4); w[:3,:3]=linear; w[:3,3]=anchor-linear@origin
        assert np.linalg.det(linear)>0, ('Reflected hand map',n)
        assert np.linalg.norm(w[:3,:3]@origin+w[:3,3]-target)<2e-6, ('Pivot mismatch',n)
        maps[n]=np.asarray(Matrix(w.tolist())@root_map,dtype=np.float32)
    assert max_error<1e-4, ('MMR original-source articulation failed',max_error,worst_joint)
    for side in ('left','right'):
        for n in names:
            if n.startswith(f'j_{side}inhand'):maps[n]=maps[f'j_{side}hand'].copy()
    summary={'profile':b.MODEL_PROFILE,'source':str(b.SOURCE_BLEND),
             'original_source_owner':arm.name,'MMR_mappings':len(specs),
             'max_MMR_matrix_error':max_error,'source_animation_available':False,
             'purpose':'MMR evaluated source joint rotations/positions are baked into exported surface maps',
             'native_runtime_skeleton_unchanged':not source_digits,
             'source_digit_lengths':source_digits,'native_wrist_and_palm_unchanged':True,'joints':report,
             'geometry_maps':{n:w.tolist() for n,w in maps.items()}}
    out=pathlib.Path(getattr(b,'HAND_AUTHORING_OUTPUT',pathlib.Path(b.OUTPUT).parent))
    # Save the actual source owner + live MMR constraints as reviewable authoring
    # evidence. Original .blend is never overwritten. Preview callers set OUTPUT
    # to their own paths; only the build directory receives authoring artifacts.
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        out.mkdir(parents=True,exist_ok=True)
        motion=[]
        for f,case in enumerate(('rest','grip','staff','shield','dual_blades','psyker_charge','reload'),1):
            pose_path=out/('arms_'+case+'_pose.json')
            if not pose_path.exists():continue
            pose=json.loads(pose_path.read_text(encoding='utf-8'))
            scene.frame_set(f)
            expected={}
            for n in specs:
                i=names[n]
                animated=Matrix(pose['driver_worlds'][i])
                delta=animated.to_quaternion().to_matrix() @ native[i].to_quaternion().to_matrix().transposed()
                rest_dt=source_to_dt.to_quaternion().to_matrix() @ wanted[n].to_quaternion().to_matrix()
                w=(delta @ rest_dt).to_4x4()
                w.translation=animated.translation
                local=dt_to_source @ w
                w=local.to_quaternion().to_matrix().to_4x4();w.translation=local.translation
                pb=driver.pose.bones[n]
                pb.rotation_mode='QUATERNION'
                pb.matrix=w
                pb.keyframe_insert(data_path='location',frame=f)
                pb.keyframe_insert(data_path='rotation_quaternion',frame=f)
                expected[n]=w
            bpy.context.view_layer.update()
            evaluated=arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
            error=max(float(np.max(abs(np.asarray(evaluated.pose.bones[canonical[n]].matrix)-np.asarray(w))))
                      for n,w in expected.items())
            assert error<1e-4, ('MMR source motion probe failed',case,error)
            motion.append({'case':case,'frame':f,'matrix_error':error,'synthetic':True})
            scene.timeline_markers.new('Synthetic hand probe: '+case,frame=f)
        summary['source_MMR_motion_probes']=motion
        scene.frame_start=1;scene.frame_end=max(1,len(motion));scene.frame_set(1)
        bpy.context.view_layer.update()
        (out/'mmr_hand_authoring.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        tag='body' if source_digits else 'arms'
        (out/('mmr_hand_authoring_'+tag+'.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
        txt=bpy.data.texts.get('MMR_HAND_AUTHORING_README') or bpy.data.texts.new('MMR_HAND_AUTHORING_README')
        txt.clear();txt.write(json.dumps({k:v for k,v in summary.items() if k!='geometry_maps'},indent=2))
        bpy.ops.wm.save_as_mainfile(filepath=str(out/(b.MODEL_PROFILE+'_original_hand_MMR.blend')),copy=True)
    for m in state.mappings: m.clear()
    state.mappings.clear(); state.selected_target=None
    scene.mmr_kumopult_bac_owner=previous_owner
    bpy.data.objects.remove(driver,do_unlink=True)
    bpy.data.armatures.remove(data)
    for obj in bpy.context.selected_objects: obj.select_set(False)
    for obj in selected: obj.select_set(True)
    bpy.context.view_layer.objects.active=active
    bpy.context.view_layer.update()
    print('ENDFIELD_SOURCE_MMR_HANDS',json.dumps({k:v for k,v in summary.items() if k not in ('geometry_maps','joints')}))
    return maps,report
