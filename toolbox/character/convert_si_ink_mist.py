"""Restore the supplied EFMI base edition, without executing its shader code.

Run with the workspace Python first, then with Blender --python ... -- --blend.
The INI's default draw ranges are explicit and checked against the original INI.
Skin is transferred from the original Si source surface, never from raw palette
numbers (EFMI supplies no skeleton). Original source hands/head are retained.
"""
from pathlib import Path
import json, re, sys
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / 'si_ink_mist'
SOURCE = Path(r'<SOURCE_ROOT>\si_ink_mist_base_32_4fdc3\Si Ink Mist base 3.2')
BLEND = OUT / 'si_ink_mist.blend'

# component, count, first index, diffuse, metallic/gloss, normal, mode, alpha,
# Verified against INI ps-t17/18/19 and p1.hlsl: t18.A is smoothness;
# t19.R*t19.A and t19.G decode normal XY. This is NOT the CMB file order.
# alternate UV buffer. Only the supplied base edition's default enabled draws.
DRAWS = [
 (3,4902,0,18,19,20,None,False,False),
 # v106 is the original Endfield weapon/back attachment, not the outfit.
 # Darktide owns its own equipment; never import this baked weapon geometry.
 (3,5112,227859,28,30,31,2,False,False),
 (3,2196,111105,22,24,25,0,False,False),
 (3,6660,41019,28,30,31,2,False,False),
 (3,5232,47679,22,24,25,0,False,False),
 (3,31416,280608,28,30,31,2,False,False),
 (3,21360,78789,22,24,25,0,False,False),
 (3,8706,57783,55,56,57,None,False,False),
 (3,1656,211803,28,30,31,2,False,False),
 (3,528,213459,28,30,31,2,False,False),
 (3,7320,213987,22,24,25,0,False,False),
 # 20418 @ 185049 is the optional recolored head/long-hair shell. The exact
 # original Si hair is retained below; importing both creates overlapping hair.
 (3,5232,100149,48,26,27,0,True,False),
 (3,6552,221307,46,38,39,1,True,False),
 (3,1272,105381,37,38,39,1,True,False),
 (3,4452,106653,23,26,27,0,True,False),
 (3,4872,52911,37,38,39,1,True,False),
 (3,7500,113301,23,26,27,0,True,False),
 (3,29028,120801,37,38,39,1,True,False),
 (3,6336,205467,37,38,39,1,True,False),
 # Optional white stockings (v119 / CustomShader084), absent in the supplied
 # in-game reference. The underlying C5 legs remain, with their authored skin.
 (3,11379,232971,22,49,25,None,False,True),
 (3,6576,244350,50,49,27,None,True,True),
 (3,18456,250926,51,49,39,None,True,True),
 (3,11226,269382,51,49,39,None,True,True),
 (5,210402,400764,16,None,17,None,False,False),
 (5,93888,212988,16,None,17,None,False,False),
 # Independent ink-effect ribbons, not clothing or the excluded weapon.
 # CommandList016 / 005; source FX shader is not part of the supplied package.
 (9,4680,0,1009,None,None,None,False,False),
 (11,924,0,1009,None,None,None,False,False),
]

def blocks():
    parts=re.split(r'^\[([^\]]+)\]\s*$',(SOURCE/'Si.ini').read_text(),flags=re.M)
    return dict(zip(parts[1::2],parts[2::2]))

def decode_normals(words):
    q=np.column_stack([((words<<s).view(np.int32)>>22) for s in (22,12,2)])/511.
    n=np.column_stack((q[:,:2],1-np.abs(q[:,:2]).sum(1)))
    below=n[:,2]<0
    n[below,:2]=(1-np.abs(n[below,1::-1]))*np.where(n[below,:2]>=0,1,-1)
    return (n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)).astype('f4')

def prepare():
    from PIL import Image
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    OUT.mkdir(exist_ok=True)
    tex=OUT/'textures';tex.mkdir(exist_ok=True)
    ini=blocks();reference=np.load(OUT/'source_reference.npz')
    points=reference['positions'];weights=reference['weights'].copy();names=reference['group_names']
    bone_names={r['name']for r in json.loads((OUT/'source_armature.json').read_text(encoding='utf8'))['bones']}
    valid=np.asarray([n in bone_names for n in names]);weights[:,~valid]=0
    weights/=np.maximum(weights.sum(1,keepdims=True),1e-10)
    arm_groups=np.asarray([bool(re.search(r'腕|ひじ|肘|手首|指',n)) and not any(x in n for x in ('sleeve','dummy','shadow')) for n in names])
    arm=weights[:,arm_groups].sum(1)
    hand_groups=np.asarray([bool(re.search(r'手首|指',n)) for n in names])
    raw=np.fromfile(SOURCE/'Buffer/Component5_VB0.buf','<f4').reshape(-1,4)[:,:3]
    skin=np.fromfile(SOURCE/'Buffer/Component5_VB2.buf','<u2').reshape(-1,8)
    poses={}
    bones=json.loads((OUT/'source_armature.json').read_text(encoding='utf8'))['bones']
    bone_by_name={b['name']:b for b in bones}
    for suffix,hand_ids,angle in (('.L',[333,336,*range(342,356)],13.5),('.R',[307,310,*range(316,330)],-13.5)):
        ids=np.asarray(hand_ids)
        target=np.unique(raw[np.where(np.isin(skin[:,4:],ids),skin[:,:4]/65535.,0).sum(1)>.8],axis=0)
        selected=np.flatnonzero(weights[:,hand_groups & np.asarray([n.endswith(suffix)for n in names])].sum(1)>.8)
        old=np.unique(points[selected],axis=0)
        rot=Rotation.from_euler('y',angle,degrees=True).as_matrix();scale=.85
        linear=scale*rot;trans=target.mean(0)-linear@old.mean(0);tree=cKDTree(target)
        # Original source glove -> supplied arm-rest pose. Positive similarity
        # only; MMR later fits these same authored hands onto native contacts.
        for _ in range(35):
            q=old@linear.T+trans;dist,nearest=tree.query(q)
            keep=dist<=np.quantile(dist,.9);a=old[keep];z=target[nearest[keep]]
            ac=a-a.mean(0);zc=z-z.mean(0)
            u,s,vt=np.linalg.svd(ac.T@zc);r=vt.T@u.T
            if np.linalg.det(r)<0:vt[-1]*=-1;r=vt.T@u.T
            scale=np.sum((ac@r.T)*zc)/np.sum(ac*ac)
            linear=np.clip(scale,.65,1.2)*r;trans=z.mean(0)-linear@a.mean(0)
        pose=np.eye(4);pose[:3,:3]=linear;pose[:3,3]=trans;poses[suffix]=pose.tolist()
        # Pose the source transfer field by each side's actual source arm skin.
        factor=weights[:,arm_groups & np.asarray([n.endswith(suffix)for n in names])].sum(1)
        transformed=points@linear.T+trans
        points=points*(1-factor[:,None])+transformed*factor[:,None]
        print('SOURCE_HAND_POSE_FIT',suffix,'median_m',float(np.median(tree.query(old@linear.T+trans)[0])),'scale',scale)
    # Restrict skin donors to the original body's actual skin surface. Nearby
    # hair, earrings, ribbons and sleeves are not valid donors for bare skin.
    hair_groups=np.asarray([bool(re.search(r'hair|ear_',n,re.I)) for n in names])
    dynamic_groups=np.asarray([bool(re.search(r'hair|ear_|bow|tail|sleeve|cloth|tassel|裙|ribbon|cloud|bracelet|錘|dummy|shadow',n,re.I)) for n in names])
    skin_ids=reference['skin_vertices']
    body_weights=weights[skin_ids].copy();body_weights[:,dynamic_groups]=0
    body_empty=body_weights.sum(1)<1e-8
    body_weights[body_empty,list(names).index('上半身2')]=1
    body_weights/=body_weights.sum(1,keepdims=True)
    body_tree=cKDTree(points[skin_ids])
    def skin_field(pos):
        dist,idx=body_tree.query(pos,k=4)
        blend=1/np.maximum(dist,1e-7)**2;blend/=blend.sum(1,keepdims=True)
        return np.einsum('nk,nkg->ng',blend,body_weights[idx])
    tree=cKDTree(points)
    # No global raw-index-to-MMD assumption. Transfer a known source field.
    # The outfit's bare hands use the posed original Si skin field and skeleton.
    # Palette numbers alone cannot establish finger identities.
    bcache={};rows=[];arrays={};all_textures=set();hand_identity_evidence=[]
    for draw,spec in enumerate(DRAWS):
        c,count,start,d,p,n,mode,alpha,sleeves=spec
        source_blended=alpha
        # x245=100262/100264 uses diffuse alpha-test even on the source's
        # nominally opaque passes (p1.hlsl 189-249). Ignoring it leaves black
        # atlas-background rectangles on the collar, back and sleeve hems.
        # Physical garments must stay on the proven substance_basic path.
        # Their diffuse masks are baked into boundary geometry below; sending
        # every garment to the copied hair Alpha provider hid the whole outfit
        # in the user's October 21 game test, despite correct Blender previews.
        alpha=False
        signature=f'{count}, {start}, 0'
        assert signature in (SOURCE/'Si.ini').read_text() or any(
            re.search(r'\$v954\s*=\s*'+str(count)+r'\b',block) and
            re.search(r'\$v955\s*=\s*'+str(start)+r'\b',block)
            for block in ini.values()), ('Draw not present in supplied base edition',signature)
        if c not in bcache:
            vpath=SOURCE/f'Buffer/Component{c}_VB0.buf'
            raw=np.fromfile(vpath,'<u4').reshape(-1,4)
            v=raw[:,:3].copy().view('<f4')
            normal=decode_normals(raw[:,3].copy())
            ib=np.fromfile(SOURCE/f'Buffer/Component{c}_IB.buf','<u2' if c in (9,11) else '<u4')
            if c in (9,11):
                # FX VB2 is four uint16 palette entries, NOT four normalized
                # weights plus IDs. Keep its geometry on a stable chest root.
                skin=np.zeros((len(v),8),np.uint16);skin[:,0]=65535
            else:skin=np.fromfile(SOURCE/f'Buffer/Component{c}_VB2.buf','<u2').reshape(-1,8)
            bcache[c]=(v,normal,ib,skin)
        v,normal,ib,skin=bcache[c]
        faces=ib[start:start+count].reshape(-1,3).copy()
        assert len(faces)*3==count and faces.max()<len(v)
        selected,inverse=np.unique(faces,return_inverse=True);faces=inverse.reshape(-1,3)
        pos=v[selected].copy();nor=normal[selected].copy()
        uvfile=SOURCE/('Buffer/Sleeves_VB1.buf'if sleeves else f'Buffer/Component{c}_VB1.buf')
        stride=20 if c in (9,11) else 12
        uv=np.fromfile(uvfile,'u1').reshape(-1,stride)[:,:8].copy().view('<f4').reshape(-1,2)[selected].copy()
        if mode in (0,1,2,3):
            resource={0:204,1:207,2:205,3:206}[mode]
            values=np.asarray([float(x)for x in re.search(r'^data\s*=\s*(.+)$',ini[f'Resource{resource}'],re.M).group(1).split()])
            uv=uv*values[:2]+values[2:]
        # EFMI's DDS UVs address top-left; source Blender UVs address bottom-left.
        uv[:,1]=1-uv[:,1]
        # Recover orientation using authored normals, independent of API winding.
        cross=np.cross(pos[faces[:,1]]-pos[faces[:,0]],pos[faces[:,2]]-pos[faces[:,0]])
        dot=(cross*nor[faces].mean(1)).sum(1)
        if np.median(dot)<0:faces=faces[:,[0,2,1]]
        ink_strokes=None
        if c in (9,11):
            from si_ink_mist_ink_wings import strokes
            pos,nor,ink_strokes=strokes(pos,uv,faces)
        dist,idx=tree.query(pos,k=4)
        k=1/np.maximum(dist,1e-7)**2;k/=k.sum(1,keepdims=True)
        w=np.einsum('nk,nkg->ng',k,weights[idx])
        if c in (9,11):
            w[:]=0;w[:,list(names).index('上半身2')]=1
        hair_contaminated=int(np.count_nonzero(w[:,hair_groups].sum(1)>1e-5))
        # The outfit contains no replacement hair. No imported garment/skin
        # vertex may move with a hair/ear helper, including near the neck.
        hair_mass=w[:,hair_groups].sum(1);w[:,hair_groups]=0
        w+=skin_field(pos)*hair_mass[:,None]
        raw_arm=np.where((skin[selected,4:]>=304)&(skin[selected,4:]<=355),skin[selected,:4]/65535.,0).sum(1)
        # Use the continuous authored bare forearm/palm/finger surface. Its
        # hand skin is sampled from the original Si field after arm-rest fit;
        # only the known upper-arm palette is explicitly remapped below.
        if c==5:
            w=skin_field(pos)
            arm_map={304:'ひじ.R',305:'ひじ.R',306:'ひじ.R',311:'腕捩.R',312:'腕.R',313:'腕.R',314:'ひじ.R',315:'ひじ.R',
                     330:'ひじ.L',331:'ひじ.L',332:'ひじ.L',337:'腕捩.L',338:'腕.L',339:'腕.L',340:'ひじ.L',341:'ひじ.L'}
            # These identities were established by bilateral weighted votes
            # against the fitted original source hand field, not raw-index
            # assumptions. Preserve the supplied hand's own smooth weights:
            # nearest-surface samples bleed between adjacent finger webs.
            hand_map={307:'手首',308:'手首',309:'手首',310:'親指０',
                      316:'人指３',317:'人指２',318:'人指１',
                      319:'中指１',320:'中指３',321:'中指２',
                      322:'薬指１',323:'薬指３',324:'薬指２',
                      325:'小指１',326:'小指３',327:'小指２',328:'親指２',329:'親指１'}
            arm_map.update({i:label+'.R' for i,label in hand_map.items()})
            arm_map.update({i+26:label+'.L' for i,label in hand_map.items()})
            for raw_id in (*hand_map.keys(),*(i+26 for i in hand_map)):
                mass=np.where(skin[selected,4:]==raw_id,skin[selected,:4]/65535.,0).sum(1)
                if mass.sum()<1e-5:continue
                votes=(w*mass[:,None]).sum(0);expected=arm_map[raw_id]
                assert names[votes.argmax()]==expected, ('Source hand palette correspondence changed',raw_id,expected)
                hand_identity_evidence.append(dict(raw_palette=raw_id,source_bone=expected,
                    vote_share=float(votes.max()/votes.sum()),
                    method='bilateral weighted correspondence against fitted original Si skin field'))
            for vi in np.flatnonzero(raw_arm>.01):
                merged={}
                for raw_id,weight in zip(skin[selected[vi],4:],skin[selected[vi],:4]/65535.):
                    name=arm_map.get(int(raw_id))
                    if name in names:merged[list(names).index(name)]=merged.get(list(names).index(name),0)+weight
                if merged:
                    w[vi]*=max(0,1-sum(merged.values()))
                    for gi,val in merged.items():w[vi,gi]+=val
        else:
            # Drape triangles must not inherit incidental arm/hand weights
            # simply because their original reference surface is nearby.
            drape=raw_arm<.01
            w[np.ix_(drape,arm_groups)]=0
            empty=w.sum(1)<1e-8
            w[empty,list(names).index('上半身2')]=1
        # The bodice is fitted cloth, not a hanging ribbon. Use the same chest
        # transform for skin and its close-fitting shell, feathering into the
        # waist/neck so physics cannot uncover one cup or tear the back seam.
        radial=np.clip((.18-np.abs(pos[:,0]))/.03,0,1)
        vertical=np.minimum(np.clip((pos[:,2]-1.02)/.06,0,1),np.clip((1.37-pos[:,2])/.05,0,1))
        fitted=radial*vertical
        w*=1-fitted[:,None];w[:,list(names).index('上半身2')]+=fitted
        # Rigid collar follows neck/head skin, never a nearby long-hair chain.
        collar=(np.abs(pos[:,0])<.09)&(pos[:,2]>=1.37)
        if c==3 and np.any(collar):w[collar]=skin_field(pos[collar])
        ids=np.argpartition(w,-4,axis=1)[:,-4:]
        vals=np.take_along_axis(w,ids,axis=1);vals/=np.maximum(vals.sum(1,keepdims=True),1e-12)
        cutout=None
        if c==3:
            from si_ink_mist_cutouts import trim
            mask=np.asarray(Image.open(SOURCE/f'Tex/{d}.dds').convert('RGBA'))[:,:,3]/255.
            # Dense metallic trim already has authored silhouette topology.
            # One boundary split there keeps the complete 31-slot carrier
            # within its uint16 budget; fabric boundaries receive two levels.
            pos,nor,uv,faces,ids,vals,cutout=trim(pos,nor,uv,faces,ids,vals,mask,.15 if source_blended else .5,
                                               max_depth=1 if d==28 else 2)
            # A new boundary point can interpolate across the chest feather.
            # Restore the same fitted core contract at its actual position.
            core=(np.abs(pos[:,0])<=.15)&(pos[:,2]>=1.08)&(pos[:,2]<=1.32)
            ids[core]=list(names).index('上半身2');vals[core]=[1,0,0,0]
            print('GARMENT_GEOMETRIC_CUTOUT',draw,cutout,flush=True)
        name=f'InkMist_{draw:02}_{d}_'+('Alpha'if alpha else 'Opaque')
        row=dict(name=name,component=c,index_count=count,index_start=start,triangles=len(faces),vertices=len(pos),
                 diffuse=d,normal=n,packed=p,alpha=alpha,source_blended=source_blended,
                 mask_threshold=.15 if source_blended else .5,mode=mode,sleeves=sleeves,
                 weight_method='Original Si source surface field, inverse-distance 4-neighbor; no raw skeleton supplied',
                 removed_hair_influence_vertices=hair_contaminated,
                 fitted_bodice_vertices=int(np.count_nonzero(fitted>.999)),
                 geometric_cutout=cutout,
                 ink_strokes=ink_strokes,
                 transfer_distance_quantiles=np.quantile(dist[:,0],[.5,.9,.99,1]).tolist(),
                 uv_quantiles=np.quantile(uv,[0,.5,1],axis=0).tolist())
        rows.append(row)
        for key,val in dict(positions=pos,normals=nor,faces=faces,uv=uv,indices=ids,weights=vals).items():arrays[f'{draw}_{key}']=val
        all_textures.update(x for x in (d,n,p)if x is not None)
    arrays['group_names']=names
    np.savez_compressed(OUT/'restored_meshes.npz',**arrays)
    for i in sorted(all_textures):
        if i==1009:
            Image.new('RGBA',(4,4),(15,19,18,255)).save(tex/f'InkMist_{i}_D.png')
        else:Image.open(SOURCE/f'Tex/{i}.dds').convert('RGBA').save(tex/f'InkMist_{i}_D.png')
    # CommandList034 replaces original hair with Resource373 (59.dds). The
    # retained MMD atlas is vertically reversed from the source EFMI UV space.
    # Transfer the texture, not the overlapping replacement long-hair shell.
    Image.open(SOURCE/'Tex/59.dds').convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(tex/'InkMist_hair_reference_D.png')
    report=dict(author='AzNxde',source=str(SOURCE),edition='base 3.2; reference green hair, bare hands and legs',
                original_source_hand_skeleton_and_skin_field_retained=True,
                bare_hand_geometry='Component5; continuous forearm/hand surface with original Si skin-field transfer',
                hand_palette_correspondence=hand_identity_evidence,
                original_source_face_and_hair_topology_retained=True,
                hair_diffuse='CommandList034 / Resource373 / 59.dds; V reversed for retained source atlas',
                excluded_white_stocking_draw=[20472,312024],
                ink_wings={'components':[9,11],'source_triangles':1868,'anchor':'上半身2',
                    'method':'source ribbon geometry, opaque ink material; no original FX shader/animation supplied'},
                original_game_animation_not_supplied=True,source_arm_pose_maps=poses,draws=rows,
                excluded_duplicate_hair_draw=[20418,185049],
                channel_evidence='Si.ini ps-t18=metallic/smoothness; ps-t19=normal; p1.hlsl lines 498-528',
                fitted_surface_policy='Original head/hair/horns/hands; outfit uncovered skin uses original skin-only donors; no garment/skin hair weights')
    (OUT/'conversion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('RESTORED',sum(r['triangles']for r in rows),'triangles',len(rows),'draws')

def create_blend():
    import bpy
    from mathutils import Matrix
    bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\祀.blend')
    for im in bpy.data.images:
        if im.filepath:im.filepath=bpy.path.abspath(im.filepath)
    # The user moved source folders. The supplied shaded blend still embeds
    # the actual CMB source images; reuse these instead of broken old PNG paths.
    for mat in bpy.data.materials:
        if not mat.node_tree:continue
        for node in mat.node_tree.nodes:
            if node.type!='TEX_IMAGE' or not node.image or node.image.size[0]:continue
            stem=node.image.name.rsplit('.',1)[0]
            replacement=next((im for im in bpy.data.images if im.name.rsplit('.',1)[0]==stem and im.size[0] and im.packed_file),None)
            if replacement:node.image=replacement
    def visible(collection):
        collection.exclude=False;collection.hide_viewport=False
        collection.collection.hide_viewport=False
        for child in collection.children:visible(child)
    visible(bpy.context.view_layer.layer_collection)
    original=bpy.data.objects['祀_mesh'];arm=bpy.data.objects['祀_arm']
    original.hide_viewport=False;original.hide_set(False)
    original.shape_key_clear()
    # Retain authored face/eyes/hair. Bare hands come from the supplied outfit;
    # the original blue glove surface must not overlap them.
    original.data.calc_loop_triangles()
    limb_groups={g.index for g in original.vertex_groups if re.search(r'手首|指',g.name)}
    arm_mass=np.asarray([sum(g.weight for g in v.groups if g.group in limb_groups)for v in original.data.vertices])
    # C0/C6 exactly match original source head ornaments/ears. Preserve their
    # original material/UV corners, rather than guessing EFMI's external maps.
    from mathutils.kdtree import KDTree
    known=np.concatenate([np.fromfile(SOURCE/f'Buffer/Component{c}_VB0.buf','<f4').reshape(-1,4)[:,:3]for c in (0,6)])
    tree=KDTree(len(known))
    for i,p in enumerate(known):tree.insert(p,i)
    tree.balance()
    head_part=np.asarray([tree.find(original.matrix_world@v.co)[2]<2e-6 for v in original.data.vertices])
    keep=[]
    for p in original.data.polygons:
        if p.material_index in (0,1,2,3,4,5,6,12) or head_part[list(p.vertices)].all():keep.append(p.index)
    import bmesh
    keep=set(keep)
    bm=bmesh.new();bm.from_mesh(original.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in keep],context='FACES')
    bm.to_mesh(original.data);bm.free();original.data.update()
    # Hide source shader carriers, auxiliary meshes and source physics visuals.
    for obj in bpy.context.scene.objects:
        obj.hide_render=True
    original.hide_render=False
    data=np.load(OUT/'restored_meshes.npz');report=json.loads((OUT/'conversion.json').read_text(encoding='utf8'))
    hair=original.data.materials.get('发')
    assert hair and hair.node_tree.nodes.get('mmd_base_tex'), 'Original hair material missing'
    hair.node_tree.nodes['mmd_base_tex'].image=bpy.data.images.load(str(OUT/'textures/InkMist_hair_reference_D.png'),check_existing=True)
    hair['ink_mist_reference_hair']=True
    # Move original gloves and the source skeleton together into the new body
    # arm rest pose. This is offline authoring, not a runtime finger correction.
    for suffix,values in report['source_arm_pose_maps'].items():
        transform=Matrix(values)
        groups={g.index for g in original.vertex_groups if g.name.endswith(suffix) and re.search(r'手首|指',g.name)}
        for v in original.data.vertices:
            factor=min(1,sum(g.weight for g in v.groups if g.group in groups))
            if factor:v.co=v.co.lerp(transform@v.co,factor)
        bpy.context.view_layer.objects.active=arm;arm.hide_set(False);arm.hide_viewport=False
        bpy.ops.object.mode_set(mode='EDIT')
        root=arm.data.edit_bones['腕'+suffix]
        for bone in [root,*root.children_recursive]:bone.transform(transform,scale=True,roll=True)
        bpy.ops.object.mode_set(mode='OBJECT')
    names=data['group_names'];parts=[]
    for i,row in enumerate(report['draws']):
        me=bpy.data.meshes.new(row['name']);me.from_pydata(data[f'{i}_positions'],[],data[f'{i}_faces']);me.update()
        obj=bpy.data.objects.new(row['name'],me);bpy.context.collection.objects.link(obj)
        layer=me.uv_layers.new(name='UVMap');uv=data[f'{i}_uv']
        layer.data.foreach_set('uv',uv[np.asarray([l.vertex_index for l in me.loops])].ravel())
        for p in me.polygons:p.use_smooth=True
        me.normals_split_custom_set_from_vertices(data[f'{i}_normals'])
        mat=bpy.data.materials.new(row['name']);mat.use_nodes=True
        mat['ink_mist_diffuse']=row['diffuse'];mat['ink_mist_normal']=row['normal']or -1;mat['ink_mist_packed']=row['packed']or -1
        mat['ink_mist_alpha']=row['alpha']
        mat['ink_mist_component']=row['component']
        mat['ink_mist_mask_threshold']=row['mask_threshold']
        nt=mat.node_tree;nt.nodes.clear()
        bs=nt.nodes.new('ShaderNodeBsdfPrincipled');bs.inputs['Roughness'].default_value=.75
        output=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(bs.outputs['BSDF'],output.inputs['Surface'])
        node=nt.nodes.new('ShaderNodeTexImage');node.name='mmd_base_tex'
        node.image=bpy.data.images.load(str(OUT/f"textures/InkMist_{row['diffuse']}_D.png"),check_existing=True)
        node.image.alpha_mode='CHANNEL_PACKED';nt.links.new(node.outputs['Color'],bs.inputs['Base Color'])
        me.materials.append(mat)
        for name in names:obj.vertex_groups.new(name=str(name))
        ids=data[f'{i}_indices'];weights=data[f'{i}_weights']
        for vi,(ii,ww)in enumerate(zip(ids,weights)):
            for gi,w in zip(ii,ww):
                if w>1e-5:obj.vertex_groups[int(gi)].add([vi],float(w),'REPLACE')
        modifier=obj.modifiers.new('Source Si skeleton','ARMATURE');modifier.object=arm
        parts.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts+[original]:obj.select_set(True)
    bpy.context.view_layer.objects.active=original;bpy.ops.object.join()
    assert len(original.data.vertices)>100000, 'Joining restored meshes failed'
    # The retail unit template has 31 geometry slots. Draws sharing the same
    # native material can share a slot after UV restoration; never drop parts.
    canonical={};remap={}
    for i,mat in enumerate(original.data.materials):
        if 'ink_mist_diffuse'not in mat:continue
        key=tuple(mat[k]for k in ('ink_mist_diffuse','ink_mist_normal','ink_mist_packed','ink_mist_alpha','ink_mist_mask_threshold'))
        remap[i]=canonical.setdefault(key,i)
    for p in original.data.polygons:p.material_index=remap.get(p.material_index,p.material_index)
    # Discard residual MMD physics modifiers; the exporter reads source skin.
    original.hide_render=False
    for obj in list(bpy.data.objects):
        if obj!=original and obj.type=='MESH' and not obj.name.startswith('祀_mesh__'):
            bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print('INK_MIST_SOURCE_BLEND',BLEND,len(original.data.vertices),len(original.data.polygons))

if __name__=='__main__':
    create_blend() if '--blend'in sys.argv else prepare()
