"""Source-specific adapters over the verified native-resource serializer.

Original blends are read only. No Roshia tail/silhouette edits run here.
"""
import json, pathlib, sys, re, hashlib
import numpy as np
from mathutils import Matrix, Vector

HERE=pathlib.Path(__file__).parent
PROFILES={
    'lizhiyan': {'name':'李织烟','provider':'LizhiyanReplacement',
        'hair':('hair','plait'), 'cloth':('裙','cape','ribbon','beltA','FLH_')},
    'endministrator_f': {'name':'女管理员','provider':'EndministratorReplacement',
        'hair':('hair_',), 'cloth':('clothes_yifu','clothes_belt','clothes_skirt','スカート','下摆','piaodai','yifu_','shengzi_')},
    'si': {'name':'祀','provider':'SiReplacement',
        'hair':('hair','髪','发','strand'), 'cloth':('裙','skirt','cloth','clothes','ribbon','cape','belt','tail','tassel','bow','earring'),
        'dynamic_sleeves':('sleeved_',)},
    'typhoea': {'name':'提弗洛斯','provider':'TyphoeaReplacement',
        'hair':('hair_',), 'cloth':('裙','cloth_L_coat','cloth_R_coat','cloth_L_rope','cloth_R_rope','tail_')},
}
from endfield_wave2 import PROFILES as WAVE2
from endfield_wave3 import PROFILES as WAVE3
STYLED_PROFILES = set(WAVE2) | set(WAVE3)
PROFILES['si_ink_mist']=dict(PROFILES['si'],
    source=HERE/'si_ink_mist/si_ink_mist.blend',outfit='Ink Mist',outfit_author='AzNxde')
for costume,label in (('si_short_skirt','Short Skirt'),('si_lolita','Lolita')):
    PROFILES[costume]=dict(PROFILES['si'],source=HERE/'si_costumes'/costume/(costume+'.blend'),
                          outfit=label,outfit_author='See preserved local source INI')
_cloth_terms={
    'chenqianyu':('QZ_','clotch_','piaodai','bao_piaodai','tail_'),
    'gilberta':('スカート','clothes_piaodai','tail_','pd_','Bone_Chain'),
    'liino':('skirt','clothes','tail_','belt_','bowknot','knot_','earring','tie_'),
    'mifu':('cape','short_skirt','clothA','pieceA','tail_','ribbbn','wheat','decorate'),
    'perlica':('外套','内裙','clothes_ribbon','qunbai','clothes_spring'),
    'tangtang':('QB_','HB_','clothes_base','tail_','strap_','pd_','ornament_'),
    'yvonne':('clotch','tail_','piaodai'),
    'zhuangfangyi':('clothes','tail_','pz_','ornament_','fj_'),
}
# Perlica's dense connected coat/inner-skirt grids use torso/limb binds.
# Retain independent pendulum controls for the ribbons and spring dangles.
# This is a source-specific stability adaptation, not imported MMD physics.
_dynamic_cloth_terms={
    'perlica': ('clothes_ribbon', 'qunbai', 'clothes_spring'),
}
PROFILES.update({k:dict(p,hair=('hair',),cloth=_cloth_terms[k])for k,p in WAVE2.items()})
PROFILES.update(WAVE3)
for _key, _terms in _dynamic_cloth_terms.items():
    PROFILES[_key]['dynamic_cloth'] = _terms

def apply(b,key):
    p=PROFILES[key]
    b.COSTUME_FP_CLEARANCE=False
    b.COSTUME_HAND_SMOOTHING=False
    b.MODEL_PROFILE=key
    if key in ('si_short_skirt','si_lolita'):
        b.COSTUME_PROFILE=key
        b.COSTUME_NATIVE_SEGMENT_FIT=True
        b.COSTUME_WRIST_CONTINUITY=False
    if key=='si_ink_mist':
        b.COSTUME_PROFILE=key
        b.COSTUME_NATIVE_SEGMENT_FIT=True
    b.POSITION_FLOAT32=key in ('si_ink_mist','si_short_skirt','si_lolita')
    # Bare costume hands need the same source/MMR fit in body and arms assets.
    # The old body-only RBF extrapolation had no fingertip surface constraint.
    b.COHERENT_BODY_HANDS=key in WAVE3 or key in ('si','si_ink_mist','si_short_skirt','si_lolita')
    b.SOURCE_BODY_FINGER_LENGTHS=key in WAVE3 or key in ('si','si_ink_mist','si_short_skirt','si_lolita')
    b.FACE_NORMAL_BLEND=.35 if key in STYLED_PROFILES else .75
    b.CMB_ALBEDO_MATERIALS=set(p.get('albedo_materials',()))
    # Very short independent calibration bones lose roll precision when
    # Blender reconstructs edit-bone matrices far from the origin. Their
    # display length affects neither source joints nor exported native binds.
    b.MMR_DRIVER_DISPLAY_LENGTH=.15 if key in WAVE3 else .015
    b.SOURCE_EXTRA_SURFACE_MATERIALS=set(p.get('albedo_materials',()))
    if key in WAVE3:b.SOURCE_EXTRA_SURFACE_MATERIALS.add('裙内')
    from endfield_mmr_hands import fit_maps
    b.hand_surface_fitter=fit_maps
    # Keep each costume's own hand/finger weight fields.  Transferring a
    # different character's digit field was the source of the bent fingers,
    # missing nails and disappearing wrists reported in first person.
    b.postprocess_skin_influences=None
    from endfield_surface_materials import surface_maps
    b.material_surface_maps=lambda mesh,index:surface_maps(b,mesh,index)
    b.SOURCE_BLEND=pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(p['name']+'.blend')
    if p.get('source'):b.SOURCE_BLEND=pathlib.Path(p['source'])
    b.MESH_OBJECT_NAME=p['name']+'_mesh';b.ARMATURE_OBJECT_NAME=p['name']+'_arm'
    b.RESOURCE_ROOT='content/mods/'+key
    inspection=json.loads((HERE/'endfield_batch/weights.json').read_text(encoding='utf-8'))[p['name']]
    b.MESH_OBJECT_NAME=inspection.get('mesh',b.MESH_OBJECT_NAME)
    b.ARMATURE_OBJECT_NAME=inspection.get('armature',b.ARMATURE_OBJECT_NAME)
    b.SCALE=inspection['scale']
    b.ARM_MATERIALS=set();b.EYE_MATERIALS=set()
    b.ALPHA_MATERIAL_NAMES=('Alpha',)
    # These source slots are physical horns/tail or garment surfaces, despite
    # MMD slot names containing Alpha. Never send them to alpha-card shaders.
    opaque={'lizhiyan':{12,13,14,15},'typhoea':{13,14},'endministrator_f':{15},
            'liino':{17},'perlica':{13},'tangtang':{14,15},'yvonne':{13}}.get(key,set())
    opaque=set(opaque)|set(p.get('opaque_materials',()))
    old_alpha=b.material_is_alpha
    b.material_is_alpha=lambda index,name:False if index in opaque else (
        True if key in ('gilberta','mifu') and name in ('尾','尾巴') else old_alpha(index,name))
    b.SKIP_MATERIAL_NAMES=('目影','发影','面具影','表情','emo1','emo3','照れ')
    b.FIRST_PERSON_EXCLUDED_MATERIAL_NAMES=('面','目','口','发','髪','睫','眉','二重','表情','face','eye','mouth','hair')
    original_targets=b.source_bone_targets
    def source_targets(arm,names=None,dynamic_targets=None):
        result=original_targets(arm,names,dynamic_targets)
        # Prefer an explicitly selected dynamic ancestor over generic name
        # heuristics; cuff/bracelet descendants instead retain their limb.
        for bone in arm.data.bones:
            if dynamic_targets and bone.name in dynamic_targets:
                result[bone.name]=dynamic_targets[bone.name]
                continue
            cur=bone.parent
            while cur:
                if dynamic_targets and cur.name in dynamic_targets:
                    result[bone.name]=dynamic_targets[cur.name];break
                cur=cur.parent
        return result
    b.source_bone_targets=source_targets
    def prepare(mesh,arm):
        # MMR saves a review copy in another folder. Resolve source-relative
        # image paths before that changes Blender's current file context.
        for image in b.bpy.data.images:
            if image.filepath:image.filepath=b.bpy.path.abspath(image.filepath)
        def image_identity(name):
            name=re.sub(r'\.\d{3}$','',name)
            return re.sub(r'\.(png|dds|tga|jpg|bmp)$','',name,flags=re.I)
        for material in mesh.data.materials:
            if not material or not material.node_tree:continue
            for node in material.node_tree.nodes:
                if node.type!='TEX_IMAGE' or not node.image or node.image.size[0]:continue
                stem=image_identity(node.image.name)
                exact=[im for im in b.bpy.data.images if im.size[0] and im.packed_file
                       and image_identity(im.name)==stem]
                if len(exact)>1:
                    fingerprints=set()
                    for candidate in exact:
                        pixels=np.empty(len(candidate.pixels),np.float32)
                        candidate.pixels.foreach_get(pixels)
                        fingerprints.add((tuple(candidate.size),hashlib.sha256(pixels.tobytes()).hexdigest()))
                    if len(fingerprints)!=1:
                        raise ValueError('Ambiguous embedded diffuse images: '+repr([im.name for im in exact]))
                if exact:
                    node.image=sorted(exact,key=lambda im:im.name)[0]
                    print('ENDFIELD_RECOVERED_IMAGE',material.name,stem,node.image.name)
        if key=='si_short_skirt':
            from si_costume_detail import remove_covered_arm_skin
            remove_covered_arm_skin(b,mesh,arm)
        if key=='si_lolita':
            # Component1 explicitly binds this white-hair diffuse in the source
            # INI. Retain original hair topology/weights; the source atlas uses
            # D3D V coordinates, so its PNG was flipped for the retained UVs.
            path=HERE/'si_costumes/si_lolita/textures/si_lolita_hair_reference_D.png'
            hair=mesh.data.materials.get('发')
            if not hair or not hair.node_tree.nodes.get('mmd_base_tex'):
                raise ValueError('Original Si hair material missing')
            hair.node_tree.nodes['mmd_base_tex'].image=b.bpy.data.images.load(str(path),check_existing=True)
            from si_costume_detail import fit_geometry_budget
            fit_geometry_budget(b,mesh)
            from si_costume_detail import add_lolita_ink_fx
            add_lolita_ink_fx(b,mesh,arm)
        if key=='chenqianyu' and not b.bpy.data.objects.get(mesh.name+'__Cloth1'):
            # This source blend contains only MMD materials. The separately
            # supplied final CMB preset retains the actual cloth parameters.
            preset=pathlib.Path(r'<SOURCE_ROOT>\终末地角色材质预设包\陈千语\陈千语1.0.1.blend')
            metadata=json.loads(preset.with_suffix('.blend.mapping.json').read_text(encoding='utf-8'))
            requested={'CMB_CARRIER_'+identity.split(':')[0]:int(identity.split(':')[0])
                       for identity,recipe in metadata['recipes'].items() if recipe['slot']==0}
            with b.bpy.data.libraries.load(str(preset),link=False)as (available,loaded):
                loaded.objects=[n for n in requested if n in available.objects]
            if len(loaded.objects)!=11:raise ValueError('Incomplete Chen material preset carriers')
            for obj in loaded.objects:
                if obj is None:continue
                index=requested[obj.name]
                obj.name=mesh.name+'__'+mesh.data.materials[index].name
                obj.hide_render=True
            print('ENDFIELD_CMB_PRESET_LOADED',key,len(loaded.objects))
        b.HAND_AUTHORING_POLICY='native_source_weights_topology_and_corner_normals'
        if getattr(b,'HAND_AUTHORING_OUTPUT',None):
            (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'hand_policy.json').write_text(json.dumps({
                'profile':key,'hand_weights':'source character weights retained',
                'topology_uv_and_corner_normals':'source mesh retained',
                'cross_character_weight_transfer':False,
                'topology_weld_subdivide_smooth':False,
                'wrist_continuity_geometry_compensation':False,
                'first_person_garment_cylinder_clearance':False,
                'MMR':'source character bones calibrated against native contact skeleton; game animation not available offline'
            },ensure_ascii=False,indent=2),encoding='utf8')
        # Full inverted hulls self-shadow under substance_basic, unlike CMB's
        # shader-controlled outline. Keep the experiment opt-in, never ship it.
        if key in STYLED_PROFILES and getattr(b,'INCLUDE_FACE_OUTLINE',False):
            from endfield_face_outline import prepare as face_outline
            face_outline(b,mesh,arm)
        elif key in STYLED_PROFILES and getattr(b,'HAND_AUTHORING_OUTPUT',None):
            (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'face_outline.json').write_text(json.dumps({
                'enabled':False,'reason':'Full CMB inverted hull causes self-shadow artifacts with the native opaque pipeline; diagnostic only.'}),encoding='utf8')
        for mat in mesh.data.materials:
            if not mat or not mat.node_tree:continue
            # CMB shader graphs contain multiple unrelated image nodes. Keep
            # diffuse lookup deterministic without modifying the saved blend.
            n=mat.node_tree.nodes.get('mmd_base_tex')
            if n and n.type=='TEX_IMAGE' and n.image and '_D.' in n.image.name:
                n.image.colorspace_settings.name='sRGB'
        print('ENDFIELD_SOURCE',json.dumps({'profile':key,'scale':b.SCALE,'source_untouched':True}))
    if key in ('si_lolita','si_short_skirt','si_ink_mist'):
        old_costume_prepare=prepare
        def prepare(mesh,arm):
            old_costume_prepare(mesh,arm)
            from costume_original_hand_weights import apply as restore_own_hand_surface
            restore_own_hand_surface(b,mesh,arm,reference='si')
    b.prepare_source=prepare
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'hand_detail.json').write_text(json.dumps({
            'profile':key,'source_file_unchanged':True,
            'localized_to':'disabled; native source hand topology and weights retained',
            'subdivision_enabled':False,'coincident_skin_vertices_welded':0,
            'UV_and_skin_weights':'retained from source blend'},indent=2),encoding='utf8')
    if key=='endministrator_f' or key in STYLED_PROFILES:
        original_collect=b.collect_triangles
        def collect(*args,**kwargs):
            groups=original_collect(*args,**kwargs)
            from endfield_hand_detail import final_normals
            final_normals(args[0],groups,args[5])
            if key in STYLED_PROFILES:
                for group in groups:
                    if group['material_name'] not in ('目白','睫','眉','睫眉','二重'):continue
                    # The authored concave sclera is visible from its reverse
                    # side in MMD. Native substance_basic culls that side.
                    # Export both sides explicitly, with opposite normals and
                    # identical UV/weights; only one side survives culling.
                    selected=group['triangles'];count=len(group['vertices'])
                    for field in ('vertices','uv','normals'):
                        reverse=group[field][selected][:,[0,2,1]].copy()
                        if field=='normals':reverse*=-1
                        group[field]=np.concatenate((group[field],reverse),axis=0)
                    group['triangles']=np.concatenate((selected,np.arange(count,count+len(selected),dtype=np.int64)))
                    print('ENDFIELD_TWO_SIDED_FACE_LAYER',key,group['material_name'],len(selected))
            if key == 'perlica':
                from perlica_torso_lining import apply_to_groups
                groups = apply_to_groups(args[0], groups, args[7] if len(args) > 7 else kwargs['arm_only'])
            return groups
        b.collect_triangles=collect
    original_image=b.image_pixels_for
    color_settings={}
    def image_for(mat):
        if mat and mat.node_tree:
            n=mat.node_tree.nodes.get('mmd_base_tex')
            im=n.image if n and n.type=='TEX_IMAGE' else None
            if not im or ('_D.' not in im.name and '_D_AOff.'not in im.name and '_D_NoA.' not in im.name):
                im=next((n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and '_D.' in n.image.name),None)
            if im:
                w,h=im.size
                if not w or not h:raise ValueError('Missing diffuse texture: '+im.name)
                arr=np.empty(w*h*4,np.float32);im.pixels.foreach_get(arr)
                arr=arr.reshape(h,w,4)
                if key in STYLED_PROFILES:
                    if mat.name not in color_settings:
                        proxy=b.bpy.data.objects.get(b.MESH_OBJECT_NAME+'__'+mat.name)
                        base=[1.,1.,1.,1.]
                        if proxy:
                            from character_material_bridge_user import core
                            for pm in proxy.data.materials:
                                snap=core.read_material_column(pm)
                                if snap:
                                    part,col,width,data=snap
                                    value=core.read_param(data,width,col,part,'_BaseColor')
                                    if value:base=value
                                    break
                        # Source screenshot 09146be9 shows dark charcoal hair,
                        # unlike the grey output of native isotropic PBR. This
                        # explicit art calibration is separate from source data.
                        calibration_file=HERE/'endfield_batch/wave2_color_calibration.json'
                        calibration=(json.loads(calibration_file.read_text(encoding='utf-8')).get(key,{})
                                     if calibration_file.exists()else {})
                        category='face_linear_gain'if mat.name=='面'else 'hair_linear_gain'if mat.name in ('发','尾','尾巴')else None
                        art=tuple(calibration.get(category,(.16,.16,.16)if key=='chenqianyu'and mat.name=='发'else (1.,1.,1.)))
                        art=tuple(calibration.get('feature_linear_gains',{}).get(mat.name,art))
                        color_settings[mat.name]={'source_linear_base_color':base,
                            'art_linear_gain':art,'source':'supplied CMB parameter table',
                            'reference':calibration.get('reference','09146be9-3fdf-4d81-98c4-61e61b3cf158.png')if art!=(1.,1.,1.)else None,
                            'calibration_method':calibration.get('method','initial Chen hair art calibration')if art!=(1.,1.,1.)else None}
                    settings=color_settings[mat.name]
                    from endfield_face_materials import albedo
                    baked=albedo(b,key,mat.name)
                    if baked:
                        w,h,arr,row=baked
                        settings['albedo_source']=row.get('bake_kind','unlit CMB albedo')+'; UV verified'
                        settings['source_style_lighting_baked']=row.get('lighting_baked',False)
                        settings['baked_sha256']=row['sha256']
                        gain=np.asarray(settings['art_linear_gain'])
                    else:
                        gain=np.asarray(settings['source_linear_base_color'][:3])*np.asarray(settings['art_linear_gain'])
                    arr=arr.copy();rgb=arr[:,:,:3]
                    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)*gain
                    arr[:,:,:3]=np.clip(np.where(linear<=.0031308,linear*12.92,1.055*np.maximum(linear,0)**(1/2.4)-.055),0,1)
                    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
                        (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'source_color_calibration.json').write_text(
                            json.dumps(color_settings,ensure_ascii=False,indent=2),encoding='utf-8')
                # Art-direction calibration against supplied Endfield shots:
                # standard PBR lacks the source hair/mask shading response.
                tint=({'发':(.25,.25,.25),'面具':(.075,.08,.105)}.get(mat.name)
                      if key=='endministrator_f' else None)
                if tint:
                    arr=arr.copy();rgb=arr[:,:,:3]
                    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
                    linear*=np.asarray(tint)
                    arr[:,:,:3]=np.where(linear<=.0031308,linear*12.92,1.055*linear**(1/2.4)-.055)
                return w,h,arr,im.colorspace_settings.name=='sRGB'
        return original_image(mat)
    b.image_pixels_for=image_for
    b.dynamic_rig_mapping=lambda mesh,arm,unit,names:dynamic_rig(b,p,mesh,arm,unit,names)
    # Face overlay slot identities differ (split lashes/brows in some sources).
    b.FACE_OVERLAY_DEPTH={m['index']:(.0018 if 'HL' in m['name'] else .0012)
                          for m in inspection['materials'] if (m['name'].startswith('目') and '影'not in m['name']) or m['name'] in ('睫','眉','睫眉','二重')}
    if key in STYLED_PROFILES:b.FACE_OVERLAY_DEPTH={}
    import roshia_native_materials as materials
    materials.ROUGHNESS={m['index']:(.24 if m['name'].startswith('目')and '影'not in m['name'] else .90 if m['name']=='面' else
        .57 if m['name']=='肌' else .68 if m['name']=='发' else .78) for m in inspection['materials']}
    if key in STYLED_PROFILES:
        # Painted eyes already carry authored highlights. Broad physical
        # reflections must not wash out the pupil, iris and dark lash contours.
        for m in inspection['materials']:
            if m['name'] in ('目','目1','目2','目白'):materials.ROUGHNESS[m['index']]=.82
            elif m['name'] in ('睫','眉','睫眉','二重'):materials.ROUGHNESS[m['index']]=.96
            elif key in WAVE3 and m['name']=='Fur':materials.ROUGHNESS[m['index']]=.90
    original_manifests=b.write_manifests
    def manifests(result):
        original_manifests(result)
        for asset in result['assets']:
            f=b.OUTPUT/asset['asset_folder']/'compile_manifest.json'
            d=json.loads(f.read_text(encoding='utf-8'))
            d.update(model=key,source_name=p['name'],asset_scale=b.SCALE,
                     dependencies=['CustomAssets','ModelReplacementRegistry',p['provider']],
                     mesh_adapter='Source-proportion torso FK; source shoulder supports; native engine-linked 1P contact skeleton with source-weight surface fit',
                     texture_adapter='Own sRGB BC/BCA diffuse; authored RG normal -> BC5 and metallic/gloss -> ORM, respecting source switches; neutral face/eye normals; native texture profile footers',
                     materials=['Own diffuse, authored cloth/skin/hair normals and per-material ORM; opaque face/eye overlays',
                                'Physical opaque garment/horns/tail slots classified independently of Alpha names'],
                     hand_validation={'weight_source':'original character mesh',
                         'cross_character_weight_transfer':False,'topology_edits':False,
                         'wrist_compensation':False,'garment_clearance_triangle_filter':False,
                         'MMR_authoring':'source-character rest rig mapped to native contacts; no source game animation available'},
                     notes=['Original blend is read only; source hand topology, UV seams, corner normals and character-authored skin weights are retained.',
                            'Native wrist/finger contacts and node names; no wrist seam displacement or runtime finger offsets.',
                            'MMR calibrates this character’s own authored hand joints to the native contact skeleton; no cross-character weight field is copied.',
                            'Dense authored cloth/hair chains reduced to the finite helper palette; dropped controls inherit selected ancestors.',
                            'Preview and synthetic pose checks do not establish in-game action coverage.'])
            if key in STYLED_PROFILES:
                d['notes']=[
                    'Original source blend is read only; source mesh, UV and individual material identities retained.',
                    'Actual original-source MMR authoring: two wrists and 30 finger joints; seven synthetic action probes, not original-game animations.',
                    'Native engine-linked first-person wrist/finger/inhand contact contract; no runtime finger rotation overrides or weapon offsets.',
                    'Hands use this character own source weights and MMR maps; source topology, UVs and transported corner normals are retained.',
                    'Concave MMD sclera and authored lash/brow surfaces exported on both sides with opposite normals for native backface culling.',
                    'Face retains original geometry normals with a 0.35 broad-normal blend; actual CMB unlit albedo rebaked to source UVs, BaseColor applied once.',
                    'Individual face/iris/lash art calibration is recorded separately from source CMB parameters; opaque PBR eyes retain painted highlights with reduced physical glare.',
                    'CMB full-face outline shell and fixed-light final-color bake experiments are excluded from production.',
                    'Authored normal/metallic-gloss switches respected; no complete Endfield toon-shader or environment-lighting port.',
                    'Preview lighting is offline evidence only; real weapon and game-lighting validation remains required.']
            if key=='si_ink_mist':
                d['texture_adapter']='Verified EFMI D/M/N, BC5 (R*A,G) normal, cloth roughness adaptation; physical garments use substance_basic with source-mask geometric cutouts'
                d['notes']=[
                    'Original Si head, hair topology and horns retained; source Resource373 green hair diffuse replaces original pale atlas; no duplicate long-hair shell.',
                    'Reference bare legs exclude optional stocking draw; continuous outfit bare hands retain the costume source weights and use original-source MMR fitting to native contacts.',
                    'Independent ink-wing Components9/11 restored as double-sided source ribbon geometry on chest; opaque native ink approximation, without the source FX shader.',
                    'Replacement uncovered skin transfers only from original Si skin donors; no hair/ear helper influences on outfit or skin.',
                    'Close-fitting bodice and skin share the chest transform; lower garment and sleeve chains remain dynamic.',
                    'All physical garments use substance_basic, with source-mask boundary geometry at .5 for opaque source passes and .15 for adapted lace; no garment depends on the hair Alpha provider.',
                    'Source garment cull=none is represented by opposite-winding triangles and normals; no template seam normals.',
                    'Native first-person hand contacts and runtime animation remain unchanged; offline probes are not game validation.']
                d['notes'].append('Dense Ink Mist surfaces use FLOAT3 positions to avoid measured HALF4 finger quantization; native wrist/finger matrices, costume source weights and contacts are retained. Offline readback and synthetic probes do not establish native FLOAT3 rendering compatibility.')
            f.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    b.write_manifests=manifests
    if key in ('si_short_skirt','si_lolita'):
        from si_costume_materials import install
        install(b)
    if key=='si_ink_mist':
        from si_ink_mist_materials import surface_maps as ink_maps
        original_surface=b.material_surface_maps
        def ink_surface(mesh,index):
            mat=mesh.data.materials[index]
            if 'ink_mist_diffuse'not in mat:return original_surface(mesh,index)
            return ink_maps(b,mat,index)
        b.material_surface_maps=ink_surface
        original_ink_alpha=b.material_is_alpha
        b.material_is_alpha=lambda index,name:False if name.startswith('InkMist_') else original_ink_alpha(index,name)
        def ink_chunks(counts):
            # Boundary tessellation changes the relative material sizes. Reserve
            # uint16-safe chunks first, then spend remaining template slots.
            import math
            mesh=b.bpy.data.objects[b.MESH_OBJECT_NAME]
            allocation={i:math.ceil(count/(10922 if b.material_is_alpha(i,mesh.data.materials[i].name)else 21845))
                        for i,count in enumerate(counts)if count}
            if sum(allocation.values())>b.GEO_COUNT:
                raise ValueError(f'Garment geometric cutouts exceed native slot budget: {allocation}')
            while sum(allocation.values())<b.GEO_COUNT:
                index=max(allocation,key=lambda i:counts[i]/allocation[i])
                allocation[index]+=1
            return allocation
        b.allocate_chunks=ink_chunks
        original_ink_collect=b.collect_triangles
        def ink_collect(*args,**kwargs):
            groups=original_ink_collect(*args,**kwargs)
            from costume_geometry_audit import record
            record(b,args[0],groups,args[5],args[7])
            from endfield_hand_detail import final_normals
            # The outfit's continuous bare skin has an EFMI material name;
            # recompute fitted hand normals just as for source 肌 surfaces.
            skin_groups=[]
            for index,group in enumerate(groups):
                if args[0].data.materials[index].get('ink_mist_component')==5:
                    alias=dict(group,material_name='肌');skin_groups.append(alias)
            final_normals(args[0],skin_groups,args[5])
            for index,group in enumerate(groups):
                mat=args[0].data.materials[index]
                if 'ink_mist_diffuse'not in mat or mat.get('ink_mist_component')not in (3,9,11) or b.material_is_alpha(index,mat.name):continue
                # Source garment passes explicitly use cull=none. Preserve
                # their reverse side without changing the opaque PBR provider.
                selected=group['triangles'];count=len(group['vertices'])
                for field in ('vertices','uv','normals'):
                    reverse=group[field][selected][:,[0,2,1]].copy()
                    if field=='normals':reverse*=-1
                    group[field]=np.concatenate((group[field],reverse),axis=0)
                group['triangles']=np.concatenate((selected,np.arange(count,count+len(selected),dtype=np.int64)))
            return groups
        b.collect_triangles=ink_collect

    original_garment_collect=b.collect_triangles
    def garment_collect(*args,**kwargs):
        groups=original_garment_collect(*args,**kwargs)
        arm_only=kwargs.get('arm_only',args[7] if len(args)>7 else False)
        if not arm_only:
            from native_garment_sides import authored_two_sided_garment
            for index,group in enumerate(groups):
                mat=args[0].data.materials[index]
                if authored_two_sided_garment(mat) and not b.material_is_alpha(index,mat.name):
                    group['double_sided_garment']=True
        return groups
    b.collect_triangles=garment_collect

def dynamic_rig(b,p,mesh,arm,unit,names):
    mass={bone.name:0. for bone in arm.data.bones};groups={g.index:g.name for g in mesh.vertex_groups}
    for v in mesh.data.vertices:
        for g in v.groups:
            n=groups[g.group]
            if n in mass:mass[n]+=g.weight
    def kind(bone):
        n=bone.name.casefold()
        if any(t in n for t in p.get('dynamic_sleeves',())):return 'cloth'
        if any(t in n for t in ('dummy','shadow','錘','cuff','sleeve','upperarm','bracelet')):return None
        if any(t.casefold() in n for t in p['hair']):return 'hair'
        if any(t.casefold() in n for t in p.get('dynamic_cloth', p['cloth'])):return 'cloth'
        return None
    candidates={bone.name:kind(bone) for bone in arm.data.bones if mass[bone.name]>.01 and kind(bone)}
    depth=lambda bone:len(bone.parent_recursive)
    pools={k:sorted(n for n in names if n.startswith('qianxia_'+k+'_')) for k in ('hair','cloth')}
    selected={};reductions={}
    for k,pool in pools.items():
        todo={n for n,v in candidates.items() if v==k};chosen=set()
        def ancestor(n,selected_set):
            cur=arm.data.bones[n].parent
            while cur:
                if cur.name in selected_set:return cur
                cur=cur.parent
            return None
        # Preserve chain roots first, then distribute spare controls according
        # to both source skin mass and distance to the retained ancestor.
        roots=sorted((n for n in todo if ancestor(n,todo) is None),key=lambda n:(-mass[n],n))
        chosen.update(roots[:len(pool)])
        while len(chosen)<min(len(todo),len(pool)):
            def score(n):
                par=ancestor(n,chosen)
                span=(arm.data.bones[n].head_local-par.head_local).length if par else 0.
                return span*(mass[n]**.25)
            nxt=max(todo-chosen,key=lambda n:(score(n),n));chosen.add(nxt)
        for n,target in zip(sorted(chosen,key=lambda n:(depth(arm.data.bones[n]),n)),pool):selected[n]=target
        reductions[k]={'weighted_source':len(todo),'retained':len(chosen),'available':len(pool)}
    base=b.source_bone_targets(arm,names)
    mapping=b.source_bone_targets(arm,names,selected)
    base_records={};maps=b.target_bind_transforms(arm,names,unit,True,node_records=base_records,mesh=mesh)
    root=Matrix(maps['j_hips'].tolist())
    hand=b.source_hand_bind_transforms(arm,mapping,names,unit,root_map=root)
    worlds={i:r['world'] for i,r in base_records.items()};worlds.update({i:r['world']for i,r in hand['node_transforms'].items()})
    overrides={};runtime=[];bind={}
    for src,target in selected.items():
        bone=arm.data.bones[src];par=bone.parent
        while par and par.name not in selected:par=par.parent
        parent=selected[par.name] if par else base[src]
        if not parent.startswith('j_') and par is None:raise ValueError('Invalid dynamic anchor')
        z=b.source_bone_direction(arm,bone)
        ref=Vector((1,0,0)) if abs(z.x)<.9 else Vector((0,1,0))
        x=(ref-z*ref.dot(z)).normalized();y=z.cross(x).normalized()
        world=Matrix((x,y,z)).transposed().to_4x4()
        world.translation=b.source_head_in_target(arm,bone,root)
        worlds[names[target]]=world;overrides[names[target]]=names[parent]
        bind[target]=np.asarray(root,np.float32)
        # The pendulum endpoint reaches the next retained chain control when
        # intermediate source controls have been removed.
        children=[arm.data.bones[n] for n in selected if n!=src and src in [a.name for a in arm.data.bones[n].parent_recursive]
                  and not any(a.name in selected for a in arm.data.bones[n].parent_recursive[:max(0,len(arm.data.bones[n].parent_recursive)-len(bone.parent_recursive)-1)])]
        length=min(((c.head_local-bone.head_local).length for c in children),default=(bone.tail_local-bone.head_local).length)*b.SCALE
        runtime.append({'source_bone':src,'node':target,'parent':parent,'group':candidates[src],
                        'length':round(max(length,.001),6),'weighted':True,'source_parent':bone.parent.name if bone.parent else None})
        if getattr(b,'CLOTH_COLLIDERS',None) and candidates[src]=='cloth':
            z=float((arm.matrix_world@bone.head_local).z)
            runtime[-1]['collision']=.60<z<1.10
    records=b.scene_graph_transform_records(unit,worlds,overrides)
    hands={i:records[i] for i in hand['node_transforms']}
    hand['node_transforms']=hands
    report={'reductions':reductions,'source_to_target':mapping,'runtime_bones':runtime}
    if getattr(b,'OUTPUT',None):
        b.OUTPUT.mkdir(parents=True,exist_ok=True)
        (b.OUTPUT/(b.MODEL_PROFILE+'_source_mapping.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ENDFIELD_HELPER_REDUCTION',json.dumps(reductions))
    return {'dynamic_names':set(selected),'source_to_target':mapping,'source_by_target':selected,
            'node_transforms':records,'hand_node_transforms':hands,'hand_rig':hand,'bind_transforms':bind,
            'runtime_bones':runtime,'source_target_index':{n:names[t] for n,t in selected.items()}}
