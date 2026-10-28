"""Recover the supplied short-skirt/Lolita draws, then bind to original Si.

The local EFMI files contain geometry and draw palettes, but no skeleton or
animation. Palette identities below are measured against the already inspected
Ink Mist body; skin outside that verified subset uses original Si surface
transfer. The original shaded source blend is read only.
"""
from pathlib import Path
import json,re,sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from inspect_si_costumes import PACKAGES,read_sections
from convert_si_ink_mist import decode_normals
OUT=HERE/'si_costumes'
INK=Path('<SOURCE_ROOT>/si_ink_mist_base_32_4fdc3/Si Ink Mist base 3.2')

def resources(blocks):
    return {n:dict(re.findall(r'^\s*([\w.-]+)\s*=\s*(.+?)\s*$',v,re.M))
            for n,v in blocks.items()if n.startswith('Resource')}

def buffer(folder,res,r):
    return folder/res[r]['filename'].replace(chr(92),'/')

def read_component(folder,res,txt):
    binds=dict(re.findall(r'^\s*(vb[012]|ib)\s*=\s*(\S+)\s*$',txt,re.M))
    raw=np.fromfile(buffer(folder,res,binds['vb0']),'<u4').reshape(-1,4)
    p=raw[:,:3].copy().view('<f4');normal=decode_normals(raw[:,3].copy())
    stride=int(res[binds['vb1']]['stride'])
    uv=np.fromfile(buffer(folder,res,binds['vb1']),'u1').reshape(-1,stride)[:,:8].copy().view('<f4').reshape(-1,2)
    stride=int(res[binds['vb2']]['stride'])
    skin=np.fromfile(buffer(folder,res,binds['vb2']),'<u2').reshape(-1,stride//2)
    fmt=res[binds['ib']]['format']
    indices=np.fromfile(buffer(folder,res,binds['ib']),'<u4' if 'R32' in fmt else '<u2')
    return p,normal,uv,skin,indices,binds

def draw_specs(key,blocks):
    specs=[]
    for name,txt in blocks.items():
        if not name.startswith('CommandList_Draw_')or 'LOD1' in name:continue
        if key=='si_short_skirt':
            token=re.search(r'LOD0\.([a-f0-9]+)_',name).group(1)
            if token=='77ea19b6':continue  # Original matching head ornaments.
            component={'59bf046a':5,'6dc25c11':3,'c345bccf':12,'a6b80ffb':13,'b4ea2057':14}[token]
            # Only draw ranges explicitly present in LOD0, never lower LOD copies.
            for match in re.finditer(r'drawindexedinstanced\s*=\s*(\d+),INSTANCE_COUNT,(\d+),0,FIRST_INSTANCE',txt):
                count,start=map(int,match.groups())
                tex=('ps-t14.Body','ps-t15.Body',None)if component==5 else (
                    ('D','N','L')if component in (3,12) else (None,None,None))
                specs.append(dict(section=name,component=component,count=count,start=start,textures=tex))
        else:
            component=int(name.rsplit('Component',1)[1])
            if component not in (3,5):continue
            # Face, hair, ornaments and ink FX are retained from the original.
            # Their native CMB maps are available; no external RabbitFx shader.
            match=re.search(r'drawindexed\s*=\s*(\d+),\s*(\d+),\s*0',txt)
            if not match:continue
            count,start=map(int,match.groups())
            stem='6dc25c11-88650-0' if component==3 else '59bf046a-27468-0'
            tex=(stem+'-DiffuseMap',stem+'-NormalMap',stem+'-LightMap' if component==3 else None)
            specs.append(dict(section=name,component=component,count=count,start=start,textures=tex))
    return specs

def prepare(key):
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    from PIL import Image
    folder=Path('<SOURCE_ROOT>')/PACKAGES[key][0]
    blocks=read_sections(folder/PACKAGES[key][1]);res=resources(blocks)
    dest=OUT/key;dest.mkdir(parents=True,exist_ok=True);(dest/'textures').mkdir(exist_ok=True)
    ref=np.load(HERE/'si_ink_mist/source_reference.npz')
    names=ref['group_names'];positions=ref['positions'].copy();weights=ref['weights'].copy()
    bones=json.loads((HERE/'si_ink_mist/source_armature.json').read_text(encoding='utf8'))['bones']
    valid={b['name']for b in bones}
    weights[:,[n not in valid for n in names]]=0
    weights/=np.maximum(weights.sum(1,keepdims=True),1e-12)
    specs=draw_specs(key,blocks)
    components={s['section']:read_component(folder,res,blocks[s['section']])for s in specs}
    body=next(s for s in specs if s['component']==5)
    raw,_,_,skin,ib,_=components[body['section']]
    used=np.unique(ib[body['start']:body['start']+body['count']])
    # Establish the new package's hand palette by spatial weighted agreement,
    # not by reusing Ink Mist's numeric palette IDs.
    ink_p=np.fromfile(INK/'Buffer/Component5_VB0.buf','<f4').reshape(-1,4)[:,:3]
    ink_s=np.fromfile(INK/'Buffer/Component5_VB2.buf','<u2').reshape(-1,8)
    ink_tree=cKDTree(ink_p)
    inspected=json.loads((HERE/'si_ink_mist/conversion.json').read_text(encoding='utf8'))
    known={int(r['raw_palette']):r['source_bone']for r in inspected['hand_palette_correspondence']}
    known_values=list(dict.fromkeys(known.values()))
    fields=np.column_stack([np.where(np.isin(ink_s[:,4:],[p for p,v in known.items()if v==name]),
                                    ink_s[:,:4]/65535,0).sum(1)for name in known_values])
    distance,nearest=ink_tree.query(raw)
    measured={};evidence=[]
    candidates=[]
    for pal in np.unique(skin[used,4:]):
        mass=np.where(skin[:,4:]==pal,skin[:,:4]/65535,0).sum(1)
        region=(mass>.001)&(np.abs(raw[:,0])>.34)&(raw[:,2]>.75)&(raw[:,2]<1.12)&(distance<.012)
        if mass[region].sum()<.1:continue
        votes=mass[region]@fields[nearest[region]]
        best=np.argsort(votes)[-3:][::-1]
        candidates.append(dict(palette=int(pal),mass=float(mass[region].sum()),
                               votes=[(known_values[i],float(votes[i]/mass[region].sum()))for i in best]))
        if votes.max()/mass[region].sum()<.50:continue
        name=known_values[int(votes.argmax())]
        measured[int(pal)]=name
        evidence.append(dict(palette=int(pal),source_bone=name,agreement=float(votes.max()/mass[region].sum()),
                             median_surface_distance=float(np.median(distance[region]))))
    (dest/'palette_candidates.json').write_text(json.dumps(candidates,ensure_ascii=True,indent=2),encoding='utf8')
    for side in ('.L','.R'):
        actual={n for n in measured.values()if n.endswith(side)}
        required={n for n in known.values()if n.endswith(side)}
        assert required<=actual, ('Unverified costume finger palette',key,sorted(required-actual))
    hand_groups=np.array([bool(re.search(r'手首|指',n))for n in names])
    arm_groups=np.array([bool(re.search(r'腕|ひじ|肘|手首|指',n))and not any(t in n for t in ('dummy','shadow','sleeve'))for n in names])
    poses={}
    for side,angle in (('.L',13.5),('.R',-13.5)):
        raw_ids=[p for p,n in measured.items()if n.endswith(side)]
        mass=np.where(np.isin(skin[:,4:],raw_ids),skin[:,:4]/65535,0).sum(1)
        target=np.unique(raw[np.intersect1d(used,np.flatnonzero(mass>.8))],axis=0)
        selected=np.flatnonzero(weights[:,hand_groups & np.array([n.endswith(side)for n in names])].sum(1)>.8)
        old=np.unique(positions[selected],axis=0)
        linear=.85*Rotation.from_euler('y',angle,degrees=True).as_matrix()
        translation=target.mean(0)-linear@old.mean(0);tree=cKDTree(target)
        for _ in range(40):
            dist,idx=tree.query(old@linear.T+translation);keep=dist<=np.quantile(dist,.9)
            a,z=old[keep],target[idx[keep]];ac=a-a.mean(0);zc=z-z.mean(0)
            u,_,vt=np.linalg.svd(ac.T@zc);rotation=vt.T@u.T
            if np.linalg.det(rotation)<0:vt[-1]*=-1;rotation=vt.T@u.T
            scale=np.clip(np.sum((ac@rotation.T)*zc)/np.sum(ac*ac),.65,1.2)
            linear=scale*rotation;translation=z.mean(0)-linear@a.mean(0)
        transform=np.eye(4);transform[:3,:3]=linear;transform[:3,3]=translation;poses[side]=transform.tolist()
        factor=weights[:,arm_groups & np.array([n.endswith(side)for n in names])].sum(1)
        positions=positions*(1-factor[:,None])+(positions@linear.T+translation)*factor[:,None]
    hair=np.array([bool(re.search(r'hair|ear_|髪|发',n,re.I))for n in names])
    dynamic=np.array([bool(re.search(r'hair|ear_|bow|tail|sleeve|cloth|tassel|裙|ribbon|cloud|bracelet|錘|dummy|shadow',n,re.I))for n in names])
    skin_ids=ref['skin_vertices'];body_weights=weights[skin_ids].copy();body_weights[:,dynamic]=0
    empty=body_weights.sum(1)<1e-8;body_weights[empty,list(names).index('上半身2')]=1
    body_weights/=body_weights.sum(1,keepdims=True)
    trees=(cKDTree(positions),cKDTree(positions[skin_ids]))
    def sample(p,skin_only=False):
        dist,idx=trees[int(skin_only)].query(p,k=4)
        k=1/np.maximum(dist,1e-7)**2;k/=k.sum(1,keepdims=True)
        field=body_weights if skin_only else weights
        # Chunk to avoid a vertices x four x 830-group allocation.
        result=np.empty((len(p),len(names)),np.float32)
        for start in range(0,len(p),1024):
            result[start:start+1024]=np.einsum('nk,nkg->ng',k[start:start+1024],field[idx[start:start+1024]])
        return result,dist[:,0]
    arrays={'group_names':names};rows=[]
    for spec in specs:
        p,n,uv,s,ib,binds=components[spec['section']]
        faces=ib[spec['start']:spec['start']+spec['count']].reshape(-1,3)
        selected,inverse=np.unique(faces,return_inverse=True);faces=inverse.reshape(-1,3)
        p=p[selected].copy();n=n[selected].copy();uv=uv[selected].copy();uv[:,1]=1-uv[:,1]
        dot=(np.cross(p[faces[:,1]]-p[faces[:,0]],p[faces[:,2]]-p[faces[:,0]])*n[faces].mean(1)).sum(1)
        if np.median(dot)<0:faces=faces[:,[0,2,1]]
        c=spec['component'];w,dist=sample(p,c==5)
        contaminated=int(np.count_nonzero(w[:,hair].sum(1)>1e-5))
        w[:,hair]=0
        if c==5:
            for vi,source_vi in enumerate(selected):
                merged={}
                for pal,val in zip(s[source_vi,4:],s[source_vi,:4]/65535):
                    name=measured.get(int(pal))
                    if name:merged[list(names).index(name)]=merged.get(list(names).index(name),0)+val
                if merged:
                    w[vi]*=max(0,1-sum(merged.values()))
                    for gi,val in merged.items():w[vi,gi]+=val
        elif c in (13,14):
            # These exact source FX use separate draw palettes. Use original
            # tail donors for the small tail-fur strip, chest for the ink strip.
            if c==13:w[:]=0;w[:,list(names).index('上半身2')]=1
        else:
            # Fitted torso is not a hair or freely hanging cloth surface.
            core=(abs(p[:,0])<.15)&(p[:,2]>1.05)&(p[:,2]<1.37)
            w[core]=0;w[core,list(names).index('上半身2')]=1
            incidental=(abs(p[:,0])<.25)&(p[:,2]<1.35)
            w[np.ix_(incidental,hand_groups)]=0
        empty=w.sum(1)<1e-8;w[empty,list(names).index('上半身2')]=1
        ids=np.argpartition(w,-4,axis=1)[:,-4:];vals=np.take_along_axis(w,ids,axis=1)
        vals/=np.maximum(vals.sum(1,keepdims=True),1e-12)
        texture_paths=[]
        for stem in spec['textures']:
            if stem is None:texture_paths.append(None);continue
            source=folder/'Textures'/(stem+'.dds');assert source.is_file(),source
            path=dest/'textures'/(stem+'_D.png')
            if not path.exists():Image.open(source).convert('RGBA').save(path)
            texture_paths.append(str(path))
        cutout=None
        if texture_paths[0] and c in (3,12):
            from si_ink_mist_cutouts import trim
            alpha=np.asarray(Image.open(texture_paths[0]).convert('RGBA'))[:,:,3]/255.
            if alpha.min()<.5:
                p,n,uv,faces,ids,vals,cutout=trim(p,n,uv,faces,ids,vals,alpha,.35,max_depth=1)
        if c==13:
            from si_ink_mist_ink_wings import strokes
            p,n,ink_shape=strokes(p,uv,faces)
        name=f'Costume_{key}_{len(rows):02}_Opaque'
        row=dict(spec,name=name,vertices=len(p),triangles=len(faces),texture_paths=texture_paths,
                 geometric_cutout=cutout,removed_hair_vertices=contaminated,
                 source_transfer_distance_quantiles=np.quantile(dist,[.5,.9,.99,1]).tolist(),
                 skin=c==5,two_sided=c!=5)
        i=len(rows);rows.append(row)
        for field,value in dict(positions=p,normals=n,uv=uv,faces=faces,indices=ids,weights=vals).items():
            arrays[f'{i}_{field}']=value
    np.savez_compressed(dest/'restored_meshes.npz',**arrays)
    hair_texture=None
    if key=='si_lolita':
        hair_texture=dest/'textures'/'si_lolita_hair_reference_D.png'
        Image.open(folder/'Textures/ff3790c7-59757-0-DiffuseMap.dds').convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(hair_texture)
    report=dict(key=key,source=str(folder),source_ini=PACKAGES[key][1],
                hair_diffuse=str(hair_texture)if hair_texture else None,
                outfit_author='Not identified in supplied local package; preserve source INI',
                original_model_author='茶叶味香皂',source_arm_pose_maps=poses,
                hand_palette_correspondence=evidence,draws=rows,
                source_animation_available=False,
                limitations=['No EFMI skeleton supplied; non-hand skin is measured original Si nearest-surface transfer.',
                             'Native opaque PBR and geometric lace cutouts approximate the source RabbitFx shader.'])
    (dest/'conversion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('SI_COSTUME_RECOVERED',key,sum(r['triangles']for r in rows),'triangles',len(rows),'draws',flush=True)

def create_blend(key):
    import bpy,bmesh
    from mathutils import Matrix
    from mathutils.kdtree import KDTree
    folder=Path('<SOURCE_ROOT>')/PACKAGES[key][0];dest=OUT/key
    report=json.loads((dest/'conversion.json').read_text(encoding='utf8'))
    data=np.load(dest/'restored_meshes.npz')
    bpy.ops.wm.open_mainfile(filepath='<SOURCE_ROOT>/Rossia/祀.blend')
    for im in bpy.data.images:
        if im.filepath:im.filepath=bpy.path.abspath(im.filepath)
    for mat in bpy.data.materials:
        if not mat.node_tree:continue
        for node in mat.node_tree.nodes:
            if node.type!='TEX_IMAGE' or not node.image or node.image.size[0]:continue
            stem=node.image.name.rsplit('.',1)[0]
            replacement=next((im for im in bpy.data.images if im.name.rsplit('.',1)[0]==stem and im.size[0]and im.packed_file),None)
            if replacement:node.image=replacement
    def visible(c):
        c.exclude=False;c.hide_viewport=False;c.collection.hide_viewport=False
        for child in c.children:visible(child)
    visible(bpy.context.view_layer.layer_collection)
    original=bpy.data.objects['祀_mesh'];arm=bpy.data.objects['祀_arm']
    original.hide_viewport=False;original.hide_set(False);original.shape_key_clear()
    # C0 is the exact original horns/ornaments; retain their original material.
    blocks=read_sections(folder/PACKAGES[key][1]);res=resources(blocks)
    section=next(v for n,v in blocks.items()if n=='CommandList_Draw_Component0'or n=='CommandList_Draw_LOD0.77ea19b6_15198_0')
    known=read_component(folder,res,section)[0]
    tree=KDTree(len(known))
    for i,p in enumerate(known):tree.insert(p,i)
    tree.balance()
    head=np.array([tree.find(original.matrix_world@v.co)[2]<3e-6 for v in original.data.vertices])
    keep={p.index for p in original.data.polygons if p.material_index in (0,1,2,3,4,5,6,12)or head[list(p.vertices)].all()}
    bm=bmesh.new();bm.from_mesh(original.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in keep],context='FACES')
    bm.to_mesh(original.data);bm.free();original.data.update()
    for obj in bpy.context.scene.objects:obj.hide_render=True
    original.hide_render=False
    for side,values in report['source_arm_pose_maps'].items():
        bpy.context.view_layer.objects.active=arm;arm.hide_set(False);arm.hide_viewport=False
        bpy.ops.object.mode_set(mode='EDIT')
        root=arm.data.edit_bones['腕'+side]
        for bone in [root,*root.children_recursive]:bone.transform(Matrix(values),scale=True,roll=True)
        bpy.ops.object.mode_set(mode='OBJECT')
    parts=[]
    for i,row in enumerate(report['draws']):
        me=bpy.data.meshes.new(row['name']);me.from_pydata(data[f'{i}_positions'],[],data[f'{i}_faces']);me.update()
        obj=bpy.data.objects.new(row['name'],me);bpy.context.collection.objects.link(obj)
        layer=me.uv_layers.new(name='UVMap')
        layer.data.foreach_set('uv',data[f'{i}_uv'][np.array([l.vertex_index for l in me.loops])].ravel())
        for p in me.polygons:p.use_smooth=True
        me.normals_split_custom_set_from_vertices(data[f'{i}_normals'])
        mat=bpy.data.materials.new(row['name']);mat.use_nodes=True
        mat['costume_profile']=key;mat['costume_skin']=row['skin'];mat['costume_two_sided']=row['two_sided']
        for field,value in zip(('diffuse','normal','packed'),row['texture_paths']):mat['costume_'+field]=value or ''
        # Some source .blend files carry an empty node tree (e.g. when their
        # preview materials were generated by an importer). Do not assume the
        # default Principled node exists: create a complete PBR surface graph.
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        bs=next((node for node in nodes if node.type=='BSDF_PRINCIPLED'),None)
        if bs is None:bs=nodes.new('ShaderNodeBsdfPrincipled')
        output=next((node for node in nodes if node.type=='OUTPUT_MATERIAL'),None)
        if output is None:output=nodes.new('ShaderNodeOutputMaterial')
        if not any(link.from_node==bs and link.to_node==output and link.to_socket.name=='Surface' for link in links):
            links.new(bs.outputs['BSDF'],output.inputs['Surface'])
        bs.inputs['Roughness'].default_value=.72
        if 'Metallic' in bs.inputs:bs.inputs['Metallic'].default_value=0.0
        if row['texture_paths'][0]:
            node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.name='mmd_base_tex'
            node.image=bpy.data.images.load(row['texture_paths'][0],check_existing=True)
            node.image.alpha_mode='CHANNEL_PACKED';mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
        else:
            # Separate water/fur effects have no local textures in the package.
            # Explicit opaque approximation, not a guessed material binding.
            bs.inputs['Base Color'].default_value=(.015,.025,.02,1)
            mat.diffuse_color=(.015,.025,.02,1)
        me.materials.append(mat)
        for name in data['group_names']:obj.vertex_groups.new(name=str(name))
        for vi,(ii,ww)in enumerate(zip(data[f'{i}_indices'],data[f'{i}_weights'])):
            for gi,w in zip(ii,ww):
                if w>1e-5:obj.vertex_groups[int(gi)].add([vi],float(w),'REPLACE')
        modifier=obj.modifiers.new('Original Si source skeleton','ARMATURE');modifier.object=arm;parts.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts+[original]:obj.select_set(True)
    bpy.context.view_layer.objects.active=original;bpy.ops.object.join()
    # Collapse identical draw materials, retaining every triangle.
    canonical={};remap={}
    for i,mat in enumerate(original.data.materials):
        if 'costume_profile'not in mat:continue
        signature=tuple(mat[k]for k in ('costume_diffuse','costume_normal','costume_packed','costume_skin','costume_two_sided'))
        remap[i]=canonical.setdefault(signature,i)
    for p in original.data.polygons:p.material_index=remap.get(p.material_index,p.material_index)
    for obj in list(bpy.data.objects):
        if obj!=original and obj.type=='MESH' and not obj.name.startswith('祀_mesh__'):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest/(key+'.blend')))
    print('SI_COSTUME_SOURCE_BLEND',key,len(original.data.vertices),len(original.data.polygons))

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else sys.argv[1:]
    key=args[0];assert key in PACKAGES
    create_blend(key)if '--blend'in args else prepare(key)
