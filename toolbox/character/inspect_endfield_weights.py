import bpy, json, pathlib, numpy as np, sys
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
out=pathlib.Path(__file__).parent/'endfield_batch'
result={}
u=b.load_target_unit();names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
for name in ('李织烟','女管理员','祀','提弗洛斯'):
    bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(name+'.blend')))
    m=bpy.data.objects[name+'_mesh'];a=bpy.data.objects[name+'_arm']
    mass={g.name:0. for g in m.vertex_groups};gn={g.index:g.name for g in m.vertex_groups}
    for v in m.data.vertices:
        for g in v.groups:mass[gn[g.group]]+=g.weight
    mats=[]
    for i,mat in enumerate(m.data.materials):
        n=mat.node_tree.nodes.get('mmd_base_tex') if mat.node_tree else None
        im=next((x.image for x in mat.node_tree.nodes if x.type=='TEX_IMAGE' and x.image and '_D.' in x.image.name), None) if mat.node_tree else None
        alpha=None
        if im and im.size[0]:
            p=np.empty(im.size[0]*im.size[1]*4,np.float32);im.pixels.foreach_get(p)
            alpha=[float(p[3::4].min()),float((p[3::4]<.5).mean())]
        mats.append({'index':i,'name':mat.name,'image':im.name if im else None,'alpha':alpha,'triangles':sum(len(p.vertices)-2 for p in m.data.polygons if p.material_index==i)})
    points=np.asarray([m.matrix_world@v.co for v in m.data.vertices])
    zmin=float(points[:,2].min());sh=a.matrix_world@a.data.bones['腕.L'].head_local
    target=u.scene_graph.nodes[names['j_leftarm']].world_transform.translation.z
    result[name]={'materials':mats,'weighted_bones':{k:round(v,3) for k,v in mass.items() if v>.01},'source_floor':zmin,'source_shoulder_z':sh.z,'scale':target/(sh.z-zmin),'helpers':{k:sum(n.startswith(k) for n in names) for k in ('qianxia_hair_','qianxia_cloth_')}}
(out/'weights.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('WEIGHTS_DONE')
