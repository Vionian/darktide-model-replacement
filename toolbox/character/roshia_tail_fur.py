"""Keep authored fur cards/UVs, bake their mask and smooth the tail chain."""
import json
import numpy as np
import bpy,bmesh

def prepare(b,mesh,arm):
    if mesh.get('roshia_authored_fur'):return
    from si_ink_mist_cutouts import trim
    bones=sorted((x for x in arm.data.bones if x.name.startswith('tail_base_')),key=lambda x:len(x.parent_recursive))
    if len(bones)<4:raise ValueError('Missing authored fur chain')
    names={g.index:g.name for g in mesh.vertex_groups}
    tail_ids={i for i,n in names.items()if n.startswith('tail_base_')}
    mass=np.array([sum(g.weight for g in v.groups if g.group in tail_ids)for v in mesh.data.vertices])
    mesh.data.calc_loop_triangles();uvlayer=mesh.data.uv_layers.active
    pending=[];remove=set();reports=[]
    head=np.asarray([(mesh.matrix_world.inverted()@arm.matrix_world@x.head_local)[:]for x in bones])
    axis=head[1:]-head[:-1];length=(axis*axis).sum(1)
    for mi,mat in enumerate(list(mesh.data.materials)):
        if mat.name!='发Alpha' and not mat.get('costume_is_hair'):continue
        tris=[t for t in mesh.data.loop_triangles if t.material_index==mi and mass[list(t.vertices)].max()>=.20]
        if not tris:continue
        ids=np.array([v for t in tris for v in t.vertices]);p=np.array([mesh.data.vertices[int(i)].co[:]for i in ids])
        n=np.array([mesh.data.corner_normals[l].vector[:]for t in tris for l in t.loops])
        uv=np.array([uvlayer.data[l].uv[:]for t in tris for l in t.loops]);faces=np.arange(len(p)).reshape(-1,3)
        wi=np.zeros((len(p),4),int);ww=np.zeros((len(p),4),np.float32)
        projection=np.clip(np.einsum('nkj,kj->nk',p[:,None]-head[None,:-1],axis)/np.maximum(length,1e-12),0,1)
        nearest=np.argmin(np.linalg.norm(p[:,None]-head[None,:-1]-projection[:,:,None]*axis,axis=2),axis=1)
        for vi,(old_i,seg)in enumerate(zip(ids,nearest)):
            old={g.group:g.weight for g in mesh.data.vertices[int(old_i)].groups if g.group not in tail_ids}
            t=float(projection[vi,seg]);tm=mass[old_i]
            old[mesh.vertex_groups[bones[seg].name].index]=tm*(1-t)
            old[mesh.vertex_groups[bones[seg+1].name].index]=tm*t
            pairs=sorted(old.items(),key=lambda x:-x[1])[:4];total=sum(w for _,w in pairs)
            for slot,(gi,w)in enumerate(pairs):wi[vi,slot]=gi;ww[vi,slot]=w/total
        image=b.image_pixels_for(mat);cut=None
        if image[0]>1 and image[2][:,:,3].min()<.5 and not mat.get('costume_profile'):
            p,n,uv,faces,wi,ww,cut=trim(p,n,uv,faces,wi,ww,image[2][::-1,:,3],.40,max_depth=1)
        new=mat.copy();new.name='RoshiaTailFur_'+str(mi)
        for key in list(new.keys()):
            if key.startswith('costume_'):del new[key]
        mesh.data.materials.append(new);slot=len(mesh.data.materials)-1
        pending.append((p,n,uv,faces,wi,ww,slot));remove.update(t.polygon_index for t in tris)
        reports.append(dict(source_material=mat.name,triangles=len(faces),cutout=cut))
    if not pending:raise ValueError('No authored tail surface')
    old=np.empty(len(mesh.data.loops)*3,np.float32);mesh.data.corner_normals.foreach_get('vector',old)
    attr=mesh.data.attributes.new('__fur_keep_normals','FLOAT_VECTOR','CORNER');attr.data.foreach_set('vector',old)
    bm=bmesh.new();bm.from_mesh(mesh.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index in remove],context='FACES')
    deform=bm.verts.layers.deform.verify();uvl=bm.loops.layers.uv.verify();norm=bm.loops.layers.float_vector['__fur_keep_normals']
    for p,n,uv,faces,wi,ww,slot in pending:
        verts=[]
        for pos,indices,weights in zip(p,wi,ww):
            v=bm.verts.new(pos);verts.append(v)
            for gi,w in zip(indices,weights):
                if w>1e-8:v[deform][int(gi)]=float(w)
        for tri in faces:
            f=bm.faces.new([verts[int(i)]for i in tri]);f.material_index=slot;f.smooth=True
            for loop,i in zip(f.loops,tri):loop[uvl].uv=uv[i];loop[norm]=n[i]
    bm.to_mesh(mesh.data);bm.free();mesh.data.update()
    normals=np.empty(len(mesh.data.loops)*3,np.float32);mesh.data.attributes['__fur_keep_normals'].data.foreach_get('vector',normals)
    mesh.data.normals_split_custom_set(normals.reshape(-1,3));mesh.data.attributes.remove(mesh.data.attributes['__fur_keep_normals'])
    mesh['roshia_authored_fur']=True
    original_alpha=b.material_is_alpha
    b.material_is_alpha=lambda i,name:False if name.startswith('RoshiaTailFur_')else original_alpha(i,name)
    original_collect=b.collect_triangles
    def collect(*args,**kwargs):
        groups=original_collect(*args,**kwargs)
        for g in groups:
            if g['material_name'].startswith('RoshiaTailFur_'):g['double_sided_garment']=True
        return groups
    b.collect_triangles=collect
    print('ROSHIA_AUTHORED_FUR',json.dumps(reports))
