import bpy,json,pathlib
out=pathlib.Path(r'<CHARACTER_WORKSPACE>\tools\model-work\endfield_batch');out.mkdir(exist_ok=True)
result={}
for name in ('李织烟','女管理员','祀','提弗洛斯'):
    path=pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(name+'.blend')
    bpy.ops.wm.open_mainfile(filepath=str(path))
    info={'source':str(path),'objects':[],'materials':[],'images':[]}
    for obj in bpy.data.objects:
        r={'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,'location':list(obj.location),'scale':list(obj.scale)}
        if obj.type=='MESH':r.update(vertices=len(obj.data.vertices),polygons=len(obj.data.polygons),groups=[g.name for g in obj.vertex_groups],materials=[m.name if m else None for m in obj.data.materials],modifiers=[(m.name,m.type)for m in obj.modifiers])
        if obj.type=='ARMATURE':r.update(bones=[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(obj.matrix_world@b.head_local),'tail':list(obj.matrix_world@b.tail_local),'deform':b.use_deform} for b in obj.data.bones])
        info['objects'].append(r)
    for mat in bpy.data.materials:
        r={'name':mat.name,'nodes':[]}
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                r['nodes'].append({'name':n.name,'type':n.bl_idname,'image':n.image.name if n.bl_idname=='ShaderNodeTexImage' and n.image else None})
        info['materials'].append(r)
    for im in bpy.data.images:
        info['images'].append({'name':im.name,'path':bpy.path.abspath(im.filepath),'size':list(im.size),'packed':bool(im.packed_file),'colorspace':im.colorspace_settings.name})
    result[name]=info
(out/'source_inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('INSPECTION_DONE')
