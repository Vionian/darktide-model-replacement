"""Read source blends without saving; record actual objects, parts and bone mass."""
import bpy,json,pathlib,sys,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_wave2 import PROFILES
out=pathlib.Path(__file__).parent/'endfield_batch'
out.mkdir(exist_ok=True)
weights_file=out/'weights.json'
weights=json.loads(weights_file.read_text(encoding='utf-8'))
result={}
u=b.load_target_unit();names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
for key,p in PROFILES.items():
    name=p['name'];path=pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(name+'.blend')
    bpy.ops.wm.open_mainfile(filepath=str(path))
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and len(o.vertex_groups)]
    m=max(meshes,key=lambda o:len(o.data.vertices))
    a=next((mod.object for mod in m.modifiers if mod.type=='ARMATURE' and mod.object),None)
    if a is None:a=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    gn={g.index:g.name for g in m.vertex_groups};mass={}
    for v in m.data.vertices:
        for g in v.groups:mass[gn[g.group]]=mass.get(gn[g.group],0.)+g.weight
    mats=[]
    for i,mat in enumerate(m.data.materials):
        if not mat:continue
        images=[x.image for x in mat.node_tree.nodes if x.type=='TEX_IMAGE' and x.image] if mat.node_tree else []
        im=next((im for im in images if '_D.' in im.name),None)
        alpha=None
        if im and im.size[0]:
            data=np.empty(im.size[0]*im.size[1]*4,np.float32);im.pixels.foreach_get(data)
            alpha=[float(data[3::4].min()),float((data[3::4]<.5).mean())]
        verts={v for poly in m.data.polygons if poly.material_index==i for v in poly.vertices}
        pts=np.asarray([m.matrix_world@m.data.vertices[v].co for v in verts])
        proxy=bpy.data.objects.get(m.name+'__'+mat.name)
        pmass={}
        for vi in verts:
            for g in m.data.vertices[vi].groups:pmass[gn[g.group]]=pmass.get(gn[g.group],0)+g.weight
        mats.append({'index':i,'name':mat.name,'image':im.name if im else None,'alpha':alpha,
            'triangles':sum(len(poly.vertices)-2 for poly in m.data.polygons if poly.material_index==i),
            'bbox':[pts.min(0).tolist(),pts.max(0).tolist()]if len(pts)else None,
            'dominant_bones':sorted(pmass.items(),key=lambda x:-x[1])[:8],
            'proxy':proxy.name if proxy else None})
    points=np.asarray([m.matrix_world@v.co for v in m.data.vertices])
    zmin=float(points[:,2].min())
    shoulder=next((a.data.bones[n]for n in ('腕.L','左腕')if n in a.data.bones),None)
    if shoulder is None:raise ValueError((name,'No authored left upper arm'))
    sh=a.matrix_world@shoulder.head_local
    target=u.scene_graph.nodes[names['j_leftarm']].world_transform.translation.z
    record={'source':str(path),'mesh':m.name,'armature':a.name,'materials':mats,
            'weighted_bones':{k:round(v,3)for k,v in mass.items()if v>.01},
            'source_floor':zmin,'source_shoulder_z':sh.z,'scale':target/(sh.z-zmin),
            'vertices':len(m.data.vertices),'helpers':{k:sum(n.startswith(k)for n in names)for k in ('qianxia_hair_','qianxia_cloth_')},
            'bones':[{'name':x.name,'parent':x.parent.name if x.parent else None,'head':list(x.head_local),'tail':list(x.tail_local)}for x in a.data.bones],
            'images':[{'name':im.name,'size':list(im.size),'path':bpy.path.abspath(im.filepath),'packed':bool(im.packed_file)}for im in bpy.data.images]}
    result[key]=record;weights[name]=record
    print('WAVE2_SOURCE',key,m.name,a.name,len(m.data.vertices),len(a.data.bones),record['scale'],flush=True)
    (out/'wave2_source_inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
weights_file.write_text(json.dumps(weights,ensure_ascii=False,indent=2),encoding='utf-8')
print('WAVE2_INSPECTION_DONE',flush=True)
