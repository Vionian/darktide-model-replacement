"""Carry authored CMB facial inverted hulls into the native opaque pipeline."""
import pathlib,json,numpy as np

def prepare(b,mesh,arm):
    if mesh.get('native_cmb_face_hull'):return
    bpy=b.bpy;verts=[];faces=[];uvs=[];normals=[];report=[]
    inverse=mesh.matrix_world.inverted()
    for name in ('面','目白','口内'):
        proxy=bpy.data.objects.get(mesh.name+'__'+name)
        if proxy is None:continue
        if not proxy.users_collection:bpy.context.scene.collection.objects.link(proxy)
        evaluated=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get())
        data=evaluated.to_mesh();data.calc_loop_triangles()
        flag=data.attributes.get('ruri_outline')
        if not flag or flag.domain!='FACE':
            evaluated.to_mesh_clear();continue
        transform=inverse@proxy.matrix_world;normal_matrix=transform.to_3x3().inverted().transposed()
        start=len(faces)
        for tri in data.loop_triangles:
            if flag.data[tri.polygon_index].value<.5:continue
            loops=list(tri.loops)[::-1]
            offset=len(verts)
            for li in loops:
                vi=data.loops[li].vertex_index
                verts.append(tuple(transform@data.vertices[vi].co))
                uvs.append(tuple(data.uv_layers.active.data[li].uv))
                normals.append(tuple(-(normal_matrix@data.corner_normals[li].vector).normalized()))
            faces.append((offset,offset+1,offset+2))
        report.append({'source_layer':name,'shell_triangles':len(faces)-start})
        evaluated.to_mesh_clear()
    if not faces:raise ValueError('Source CMB facial hulls missing for '+b.MODEL_PROFILE)
    old=mesh.data;n=len(old.vertices);old_loops=len(old.loops)
    source_verts=[v.co[:]for v in old.vertices];source_faces=[tuple(p.vertices)for p in old.polygons]
    source_normals=[tuple(v.vector)for v in old.corner_normals]
    source_uv=[tuple(l.uv)for l in old.uv_layers.active.data]
    source_weights=[[(a.group,a.weight)for a in v.groups]for v in old.vertices]
    source_groups=[g.name for g in mesh.vertex_groups]
    data=bpy.data.meshes.new(old.name+'_NativeFaceHull')
    data.from_pydata(source_verts+verts,[],source_faces+[tuple(i+n for i in f)for f in faces])
    for m in old.materials:data.materials.append(m)
    mat=bpy.data.materials.new('CMBFaceOutline');mat.use_nodes=True
    mat.diffuse_color=(.012,.007,.006,1)
    image=bpy.data.images.new(b.MODEL_PROFILE+'_face_outline_D.png',width=8,height=8,alpha=True)
    image.colorspace_settings.name='sRGB';image.pixels.foreach_set(np.tile([.035,.023,.020,1.],64).astype(np.float32))
    node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.name='mmd_base_tex';node.image=image
    # image_pixels_for uses source RGBA byte samples for sRGB diffuse inputs.
    data.materials.append(mat);material_index=len(data.materials)-1
    for p,oldp in zip(data.polygons,old.polygons):p.material_index=oldp.material_index;p.use_smooth=oldp.use_smooth
    for p in list(data.polygons)[len(old.polygons):]:p.material_index=material_index;p.use_smooth=True
    layer=data.uv_layers.new(name=old.uv_layers.active.name)
    for loop,uv in zip(layer.data,source_uv+uvs):loop.uv=uv
    data.update();data.normals_split_custom_set(source_normals+normals)
    mesh.data=data
    mesh.vertex_groups.clear()
    for name in source_groups:mesh.vertex_groups.new(name=name)
    for vi,assignments in enumerate(source_weights):
        for gi,weight in assignments:mesh.vertex_groups[gi].add([vi],weight,'REPLACE')
    head=next((g for g in mesh.vertex_groups if g.name=='頭'),None)
    if head is None:raise ValueError('Source head group missing for face hull')
    head.add(list(range(n,n+len(verts))),1,'REPLACE')
    mesh['native_cmb_face_hull']=True
    result={'layers':report,'material':material_index,'triangles':len(faces),
            'source_geometry_nodes':True,'winding':'inverted hull; native backface culling',
            'base_vertices_preserved':n,'base_loops_preserved':old_loops,'source_blend_unchanged':True}
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'face_outline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('ENDFIELD_NATIVE_FACE_HULL',json.dumps(result,ensure_ascii=False),flush=True)
