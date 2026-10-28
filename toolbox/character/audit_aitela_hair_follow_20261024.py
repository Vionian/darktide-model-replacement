from pathlib import Path
import sys,json,re,hashlib
import bpy,numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import build_roshia_native as b
folder=HERE/'skins_20261023/aitela_hiro';tag='aitela_hiro'
meta=json.loads((HERE/'skins_20261023/references/aitela/source.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(folder/(tag+'.blend')))
mesh=bpy.data.objects[meta['mesh']]
hair={i:m.name for i,m in enumerate(mesh.data.materials)if m and (m.get('costume_is_hair')or re.search(r'发|髪|hair',m.name,re.I))}
assert hair,'No actual hair materials'
base=folder/'Custom'/tag;asset=base/(tag+'.unit')
unit=b.unit_dt.UnitResourceDT(b.Cursor(str(asset)))
names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(base/(tag+'_bones.bones')))))
head=names['j_head'];head_nodes=set()
for i in range(len(unit.scene_graph.nodes)):
    p=i;seen=set()
    while p not in seen and 0<=p<len(unit.scene_graph.nodes):
        if p==head:head_nodes.add(i);break
        seen.add(p);node=unit.scene_graph.nodes[p]
        if node.parent_type!=b.ParentType.INTERNAL:break
        p=node.parent_index
palette=[i for i,n in enumerate(unit.skins[0].node_indices)if n in head_nodes]
manifest=json.loads((base/'build.json').read_text())
resources={b.hash64(a['resource']['name']):a['resource']['name']for a in manifest['artifacts']if a['resource']['type']=='material'and a['role']=='primary'}
slots={s.ID:r.ID for s,r in unit.materials};rows=[]
for geo in unit.mesh_geometries:
    material=int(re.search(r'_material_(\d+)$',resources[slots[geo.materials[0].ID]]).group(1))
    if material not in hair:continue
    indices=np.frombuffer(geo.streams[5].vertex_data,np.uint8).reshape(-1,4)
    weights=np.frombuffer(geo.streams[4].vertex_data,'<f2').reshape(-1,4).astype(float)
    mass=np.where(np.isin(indices,palette),weights,0).sum(1)/weights.sum(1)
    rows.append(dict(material=hair[material],vertices=len(mass),min_head_hierarchy_mass=float(mass.min()),not_head_attached_vertices=int((mass<.999).sum())))
assert rows,'No compiled hair geometry'
report=dict(profile=tag,scope='actual serialized hair skin influences and bone parents, plus separate synthetic head-turn driver audit; not captured game animation',
    unit_sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),rows=rows,
    not_head_attached_vertices=sum(r['not_head_attached_vertices']for r in rows),gameplay_verified=False)
(HERE/'hand_repair_20261024/aitela_hiro/serialized_hair_follow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('AITELA_SERIALIZED_HAIR_FOLLOW',json.dumps(report,ensure_ascii=False))
assert report['not_head_attached_vertices']==0,report
