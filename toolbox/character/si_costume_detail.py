"""Build-only simplification of the over-dense Lolita garment, never source files."""
import json
from pathlib import Path
import bmesh
import numpy as np


def add_lolita_ink_fx(b,mesh,arm):
    """Preserve supplied C9/C11 geometry; original RabbitFx shader is absent."""
    if mesh.get('si_lolita_ink_fx'):return
    import re
    from convert_si_costumes import read_component,resources
    from inspect_si_costumes import read_sections
    from si_ink_mist_ink_wings import strokes
    folder=Path('<SOURCE_ROOT>/洛丽塔-祀')
    sections=read_sections(folder/'si.ini');res=resources(sections)
    mat=b.bpy.data.materials.new('Costume_si_lolita_ink_fx_Opaque')
    mat.diffuse_color=(.015,.025,.02,1)
    mat['costume_profile']='si_lolita';mat['costume_skin']=False;mat['costume_two_sided']=True
    for key in ('diffuse','normal','packed'):mat['costume_'+key]=''
    objects=[];reports=[]
    normals=np.empty(len(mesh.data.loops)*3,np.float32)
    mesh.data.corner_normals.foreach_get('vector',normals)
    attribute=mesh.data.attributes.new('__si_fx_keep_normal','FLOAT_VECTOR','CORNER')
    attribute.data.foreach_set('vector',normals)
    for component in (9,11):
        section=sections['CommandList_Draw_Component'+str(component)]
        p,n,uv,_,indices,_=read_component(folder,res,section)
        match=re.search(r'drawindexed\s*=\s*(\d+),\s*(\d+),\s*0',section)
        count,start=map(int,match.groups());faces=indices[start:start+count].reshape(-1,3)
        used,inverse=np.unique(faces,return_inverse=True);faces=inverse.reshape(-1,3)
        p,n,uv=p[used],n[used],uv[used]
        p,n,report=strokes(p,uv,faces);uv[:,1]=1-uv[:,1]
        me=b.bpy.data.meshes.new('SI_LOLITA_FX_'+str(component));me.from_pydata(p,[],faces);me.update()
        obj=b.bpy.data.objects.new(me.name,me);b.bpy.context.collection.objects.link(obj)
        layer=me.uv_layers.new(name='UVMap')
        loop_ids=np.array([loop.vertex_index for loop in me.loops])
        layer.data.foreach_set('uv',uv[loop_ids].ravel())
        me.normals_split_custom_set_from_vertices(n)
        attr=me.attributes.new('__si_fx_keep_normal','FLOAT_VECTOR','CORNER')
        attr.data.foreach_set('vector',n[loop_ids].ravel())
        me.materials.append(mat)
        obj.vertex_groups.new(name='上半身2').add(list(range(len(p))),1.,'REPLACE')
        objects.append(obj);reports.append(dict(component=component,source_triangles=len(faces),approximation=report))
    b.bpy.ops.object.select_all(action='DESELECT')
    for obj in [mesh,*objects]:obj.hide_viewport=False;obj.hide_set(False);obj.select_set(True)
    b.bpy.context.view_layer.objects.active=mesh;b.bpy.ops.object.join()
    normals=np.empty(len(mesh.data.loops)*3,np.float32)
    mesh.data.attributes['__si_fx_keep_normal'].data.foreach_get('vector',normals)
    mesh.data.normals_split_custom_set(normals.reshape(-1,3))
    mesh.data.attributes.remove(mesh.data.attributes['__si_fx_keep_normal'])
    mesh['si_lolita_ink_fx']=True
    out=getattr(b,'HAND_AUTHORING_OUTPUT',None)
    if out:(Path(out)/'ink_fx_recovery.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
    print('SI_LOLITA_INK_FX',sum(r['source_triangles']for r in reports))


def remove_covered_arm_skin(b,mesh,arm):
    """The short-skirt reference has closed long sleeves, exposed hands only."""
    if mesh.get('si_short_sleeves_hidden_skin'):return
    skin_slots={i for i,m in enumerate(mesh.data.materials) if m.get('costume_skin')}
    points=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])
    covered=np.zeros(len(points),bool)
    for side in ('.L','.R'):
        wrist=np.array(arm.matrix_world@arm.data.bones['手首'+side].head_local)
        elbow=np.array(arm.matrix_world@arm.data.bones['ひじ'+side].head_local)
        shoulder=np.array(arm.matrix_world@arm.data.bones['腕'+side].head_local)
        for a,z,start in ((wrist,elbow,.018/b.SCALE),(elbow,shoulder,0.)):
            axis=z-a;length=np.linalg.norm(axis);axis/=length
            t=(points-a)@axis
            distance=np.linalg.norm(points-a-t[:,None]*axis,axis=1)
            covered|=(t>start)&(t<length+.006/b.SCALE)&(distance<.065/b.SCALE)
    remove={p.index for p in mesh.data.polygons if p.material_index in skin_slots and covered[list(p.vertices)].all()}
    if not remove:raise ValueError('Covered short-skirt arm skin not found')
    normals=np.empty(len(mesh.data.loops)*3,np.float32)
    mesh.data.corner_normals.foreach_get('vector',normals)
    attribute=mesh.data.attributes.new('__si_keep_normal','FLOAT_VECTOR','CORNER')
    attribute.data.foreach_set('vector',normals)
    bm=bmesh.new();bm.from_mesh(mesh.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index in remove],context='FACES')
    bm.to_mesh(mesh.data);bm.free();mesh.data.update()
    values=np.empty(len(mesh.data.loops)*3,np.float32)
    mesh.data.attributes['__si_keep_normal'].data.foreach_get('vector',values)
    mesh.data.normals_split_custom_set(values.reshape(-1,3))
    mesh.data.attributes.remove(mesh.data.attributes['__si_keep_normal'])
    mesh['si_short_sleeves_hidden_skin']=True
    report=dict(profile='si_short_skirt',removed_hidden_skin_polygons=len(remove),
                scope='Skin inside closed sleeves only; hands and 18mm cuff margin retained',
                source_file_unchanged=True)
    out=getattr(b,'HAND_AUTHORING_OUTPUT',None)
    if out:(Path(out)/'covered_arm_skin.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('SI_SHORT_COVERED_ARM_SKIN',json.dumps(report))

def fit_geometry_budget(b,mesh):
    if mesh.get('si_lolita_budget_fit'):return
    slots={i for i,m in enumerate(mesh.data.materials) if m.get('costume_profile')=='si_lolita'
           and not m.get('costume_skin')}
    if not slots:raise ValueError('Lolita clothing materials missing')
    # Keep original head, horns, skin and every separate garment component.
    # Work on a detached cloth copy so decimation cannot reach other surfaces.
    original_count=len(mesh.data.polygons)
    before=sum(len(p.vertices)-2 for p in mesh.data.polygons if p.material_index in slots)
    saved=np.empty(len(mesh.data.loops)*3,np.float32)
    mesh.data.corner_normals.foreach_get('vector',saved)
    attribute=mesh.data.attributes.new('__si_cloth_keep_normal','FLOAT_VECTOR','CORNER')
    attribute.data.foreach_set('vector',saved)
    cloth=mesh.copy();cloth.data=mesh.data.copy();b.bpy.context.collection.objects.link(cloth)
    cloth.name='SI_LOLITA_BUILD_CLOTH'
    cloth.modifiers.clear()
    bm=bmesh.new();bm.from_mesh(cloth.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index not in slots],context='FACES')
    bm.to_mesh(cloth.data);bm.free()
    b.bpy.ops.object.select_all(action='DESELECT')
    cloth.hide_viewport=False;cloth.hide_set(False);cloth.select_set(True)
    b.bpy.context.view_layer.objects.active=cloth
    mod=cloth.modifiers.new('Native slot capacity cloth-only','DECIMATE')
    mod.decimate_type='COLLAPSE';mod.ratio=.88;mod.use_collapse_triangulate=True
    b.bpy.ops.object.modifier_apply(modifier=mod.name)
    after=sum(len(p.vertices)-2 for p in cloth.data.polygons)
    if not (0<after<before):raise ValueError(('Cloth simplification did not reduce geometry',before,after))
    if not cloth.data.uv_layers:raise ValueError('Cloth UV lost during simplification')
    if len(cloth.vertex_groups)!=len(mesh.vertex_groups):raise ValueError('Cloth weights lost')
    bm=bmesh.new();bm.from_mesh(mesh.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index in slots],context='FACES')
    bm.to_mesh(mesh.data);bm.free()
    mesh.hide_viewport=False;mesh.hide_set(False);mesh.select_set(True)
    b.bpy.context.view_layer.objects.active=mesh;b.bpy.ops.object.join()
    mesh.data.update();mesh['si_lolita_budget_fit']=True
    restored=np.empty(len(mesh.data.loops)*3,np.float32)
    mesh.data.attributes['__si_cloth_keep_normal'].data.foreach_get('vector',restored)
    restored=restored.reshape(-1,3)
    restored/=np.maximum(np.linalg.norm(restored,axis=1,keepdims=True),1e-12)
    mesh.data.normals_split_custom_set(restored)
    mesh.data.attributes.remove(mesh.data.attributes['__si_cloth_keep_normal'])
    report={'scope':'Lolita garment only; head/horns/skin excluded',
            'before_cloth_triangles':before,'after_cloth_triangles':after,
            'ratio':after/before,'two_sided_export_retained':True,
            'UV_and_weights':'Blender collapse interpolation; original source file unchanged',
            'original_polygons':original_count,'final_polygons':len(mesh.data.polygons)}
    out=getattr(b,'HAND_AUTHORING_OUTPUT',None)
    if out:(Path(out)/'cloth_budget_fit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('SI_LOLITA_CLOTH_BUDGET',json.dumps(report))
