import pathlib,sys,json
import bpy,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import PROFILES,apply
out=pathlib.Path(__file__).parent/'endfield_batch'
results={}
for key,profile in PROFILES.items():
    bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(profile['name']+'.blend')))
    m=bpy.data.objects[profile['name']+'_mesh'];a=bpy.data.objects[profile['name']+'_arm']
    r={'shape_keys':[(k.name,k.value)for k in m.data.shape_keys.key_blocks]if m.data.shape_keys else [],'materials':[],'hands':{}}
    for i,mat in enumerate(m.data.materials):
        verts={v for p in m.data.polygons if p.material_index==i for v in p.vertices}
        points=np.asarray([m.data.vertices[v].co for v in verts])
        proxy=bpy.data.objects.get(m.name+'__'+mat.name)
        images=[]
        if proxy:
            for pm in proxy.data.materials:
                ims=sorted({n.image.name for n in pm.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.image.name.startswith('T_actor_')})
                images.append({'material':pm.name,'images':ims})
        r['materials'].append({'index':i,'name':mat.name,'vertices':len(verts),
            'bbox':[points.min(0).tolist(),points.max(0).tolist()]if len(points)else None,'proxy':images})
    for side in ('L','R'):
        for digit in ('薬指','中指','小指'):
            chain=[a.data.bones[digit+k+'.'+side] for k in ('１','２','３')]
            r['hands'][digit+'.'+side]=[{'name':x.name,'head':list(x.head_local),'tail':list(x.tail_local),
                                      'parent':x.parent.name,'matrix':np.asarray(x.matrix_local).tolist()}for x in chain]
    # Geometry connected components in relevant typhoea body-material slots.
    if key=='typhoea':
        parent=list(range(len(m.data.vertices)))
        def find(v):
            while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
            return v
        for e in m.data.edges:parent[find(e.vertices[0])]=find(e.vertices[1])
        comps={}
        for v in m.data.vertices:comps.setdefault(find(v.index),[]).append(v.index)
        r['components']=[]
        gn={g.index:g.name for g in m.vertex_groups}
        for verts in comps.values():
            if len(verts)<25:continue
            pts=np.asarray([m.data.vertices[v].co for v in verts]);mass={}
            for v in verts:
                for g in m.data.vertices[v].groups:mass[gn[g.group]]=mass.get(gn[g.group],0)+g.weight
            r['components'].append({'vertices':len(verts),'bbox':[pts.min(0).tolist(),pts.max(0).tolist()],
                                    'weights':sorted(mass.items(),key=lambda x:-x[1])[:4]})
    results[key]=r
(out/'defects_source_inspection.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('DEFECT_INSPECTION_DONE')
