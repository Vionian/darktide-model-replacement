import pathlib,sys,json
HERE=pathlib.Path(__file__).parent;sys.path.insert(0,str(HERE))
from skins_sources import OUT
def configure(b,tag):
    meta=json.loads((OUT/tag/'conversion.json').read_text(encoding='utf8'));base=meta['base']
    ref=json.loads((OUT/'references'/base/'source.json').read_text(encoding='utf8'))
    if base!='roshia':
        from endfield_profiles import apply
        apply(b,base)
        if base=='perlica':
            # Original Perlica's material-10 torso insert belongs to her original
            # inner skirt, which this outfit replaces. Never insert it into JK.
            import perlica_torso_lining
            perlica_torso_lining.apply_to_groups=lambda mesh,groups,arm_only:groups
    else:
        b.MODEL_PROFILE='roshia'
        b.prepare_source=lambda mesh,arm:None
        from endfield_mmr_hands import fit_maps
        b.hand_surface_fitter=fit_maps
        # Use the actual MMR-evaluated maps for every costume.  The previous
        # Lolita exception ran MMR then discarded its coherent maps in favor
        # of independent per-joint recentering from a single reference.
        if not hasattr(b,'material_surface_maps'):b.material_surface_maps=lambda mesh,i:{}
    b.SOURCE_BLEND=OUT/tag/(tag+'.blend');b.MESH_OBJECT_NAME=ref['mesh'];b.ARMATURE_OBJECT_NAME=ref['armature'];b.SCALE=ref['scale']
    b.POSITION_FLOAT32=True
    # Keep the engine's native wrist/forearm contact.  The previous costume
    # continuity pass could move the seam by centimetres and made wrists and
    # fingers disappear in first person.
    b.COSTUME_WRIST_CONTINUITY=False
    b.COSTUME_PROFILE=tag
    b.COSTUME_NATIVE_SEGMENT_FIT=True
    if tag.startswith('endministrator_devil'):
        b.CLOTH_COLLIDERS=[['j_'+side+'upleg','j_'+side+'leg',.105*ref['scale']]for side in ('left','right')]
    b.MMR_DRIVER_DISPLAY_LENGTH=.15
    b.RESOURCE_ROOT='content/mods/'+tag
    b.OUTPUT=OUT/tag/'Custom';b.OUTPUT.mkdir(exist_ok=True)
    b.HAND_AUTHORING_OUTPUT=OUT/tag/'native';b.HAND_AUTHORING_OUTPUT.mkdir(exist_ok=True)
    b.COSTUME_FP_CLEARANCE=False
    b.COSTUME_HAND_SMOOTHING=False
    from si_costume_materials import install
    install(b)
    old_prepare=b.prepare_source
    def prepare(mesh,arm):
        import re
        import numpy as np
        # Some characters load their packed CMB carriers in prepare_source.
        # Resolve missing original images after those authoritative donors exist.
        old_prepare(mesh,arm)
        # The source blend already contains the character's authored hand
        # weights, nail UVs and cuff topology.  Do not overwrite them with a
        # nearest-triangle transfer or a topology-changing hand pass.
        b.HAND_AUTHORING_POLICY='native_source_weights_and_topology'
        (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'hand_policy.json').write_text(json.dumps({
            'profile':tag,'weight_source':'same-character original hand triangle interpolation in actual current rest pose; see original_hand_weights.json',
            'cross_character_weight_transfer':False,
            'topology_uv_and_corner_normals':'source mesh retained',
            'same_character_original_hand_surface_reconstruction':True,
            'previous_misaligned_lolita_only_override':False,
            'hand_weld_subdivide_smooth':False,
            'wrist_continuity_geometry_compensation':False,
            'first_person_garment_cylinder_clearance':False,
            'MMR':'source character bones calibrated to native contact skeleton; source game animation unavailable offline'
        },ensure_ascii=False,indent=2),encoding='utf8')
        def identity(name):
            return re.sub(r'\.(png|dds|tga|jpg|bmp)$','',re.sub(r'\.\d{3}$','',name),flags=re.I)
        label='洛茜' if base=='roshia'else __import__('endfield_profiles').PROFILES[base]['name']
        roots=list(pathlib.Path('<SOURCE_ROOT>').glob('【明日方舟：终末地】'+label+'_*'))
        files={p.name.lower():p for root in roots for p in root.rglob('*')if p.is_file()and p.suffix.lower()in ('.png','.dds','.jpg','.tga','.bmp')}
        for im in b.bpy.data.images:
            if im.filepath:im.filepath=b.bpy.path.abspath(im.filepath)
        for material in mesh.data.materials:
            if not material.node_tree:continue
            for node in material.node_tree.nodes:
                if node.type!='TEX_IMAGE' or not node.image or node.image.size[0]:continue
                stem=re.sub(r'\.\d{3}$','',node.image.name)
                candidates=[im for im in b.bpy.data.images if im.packed_file and im.size[0]and identity(im.name)==identity(stem)]
                if not candidates:
                    proxy=b.bpy.data.objects.get(mesh.name+'__'+material.name)
                    proxy_images=[n.image for pm in proxy.data.materials if pm and pm.node_tree for n in pm.node_tree.nodes
                                  if n.type=='TEX_IMAGE'and n.image and n.image.size[0]and '_D.'in n.image.name
                                  and n.image.name.startswith('T_actor_')and 'common'not in n.image.name]if proxy else []
                    distinct={identity(im.name):im for im in proxy_images}
                    if len(distinct)==1:candidates=list(distinct.values())
                if candidates:node.image=sorted(candidates,key=lambda im:im.name)[0]
                elif stem.lower()in files:node.image=b.bpy.data.images.load(str(files[stem.lower()]),check_existing=True)
        ref_data=np.load(OUT/'references'/base/'source.npz')
        source_groups={i:str(n)for i,n in enumerate(ref_data['group_names'])}
        source_points=ref_data['positions'];source_indices=ref_data['indices'];source_weights=ref_data['weights']
        mapping=b.source_bone_targets(arm,None,None)
        zones={}
        for vi,point in enumerate(source_points):
            for gi,weight in zip(source_indices[vi],source_weights[vi]):
                name=source_groups[int(gi)];target=mapping.get(name,'')
                if weight>.5 and target.startswith(('j_lefthand','j_righthand')):
                    side='.L' if target.startswith('j_left')else '.R'
                    transform=np.array(meta['source_arm_pose_maps'][side])
                    zones.setdefault(target,[]).append((transform@np.r_[point,1])[:3])
        b.HAND_CALIBRATION_POINTS=zones
        required=[f'j_{side}hand{digit}{k}'for side in ('left','right')
                  for digit in ('thumb','index','middle','ring','pinky')for k in (1,2,3)]
        assert all(len(zones.get(n,[]))>=8 for n in required),('Incomplete source hand calibration',tag)
        if base=='roshia':
            from roshia_tail_fur import prepare as tail_core
            tail_core(b,mesh,arm)
        if tag.startswith('endministrator_devil'):
            from costume_arm_heat_weights import apply as solve_bare_arm_weights
            solve_bare_arm_weights(b,mesh,arm)
        from costume_original_hand_weights import apply as restore_own_hand_surface
        restore_own_hand_surface(b,mesh,arm,reference=base)
    b.prepare_source=prepare

if __name__=='__main__':
    sys.stdout.reconfigure(line_buffering=True)
    import build_roshia_native as b
    tag=sys.argv[sys.argv.index('--')+1]
    arms_only='--arms-only' in sys.argv
    configure(b,tag)
    # Inspection/preview also calls configure; cleanup belongs to a build only.
    for stale in ('hand_detail.json','original_hand_weights.json','ring_skin_adaptation.json'):
        p=b.HAND_AUTHORING_OUTPUT/stale
        if p.exists():p.unlink()
    sys.argv=[sys.argv[0],'--','--asset-prefix',tag,'--source-blend',str(b.SOURCE_BLEND),
          '--resource-root',b.RESOURCE_ROOT,'--mesh-object',b.MESH_OBJECT_NAME,
          '--armature-object',b.ARMATURE_OBJECT_NAME,'--scale',str(b.SCALE),
          '--output-dir',str(b.OUTPUT),'--runtime-config-output',str(b.OUTPUT/(tag+'_jiggle_bones.lua'))]
    if arms_only:sys.argv.append('--arms-only')
    b.main()
    for suffix in ('proportion_bones.lua','proportion_bones.json','jiggle_bones.json'):
        f=b.OUTPUT/('roshia_'+suffix)
        if f.exists():f.replace(b.OUTPUT/(tag+'_'+suffix))
    print('NEW_SKIN_BUILD_DONE',tag,flush=True)
