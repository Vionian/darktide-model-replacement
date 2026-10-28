from pathlib import Path
import sys,json,bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
ref=ROOT/'暗潮武器mod/ExcaliburAlterForceSword/Custom/alter_sword'
b.TEMPLATE=ref
u=b.unit_dt.UnitResourceDT(b.Cursor(str(ref/'alter_sword.unit')))
print('REFERENCE_MESHES',[(i,vars(m)) for i,m in enumerate(u.meshes)])
build=json.loads((ref/'build.json').read_text())
print('COVER_RESOURCES',json.dumps([r for r in build['resources'] if 'cover' in r['key']['name']],indent=2))
arms=Path('<CHARACTER_WORKSPACE>/Custom/roshia_arms')
b.TEMPLATE=arms
u=b.unit_dt.UnitResourceDT(b.Cursor(str(arms/'roshia_arms.unit')))
nodes=u.scene_graph.nodes
from bitsquid.murmur.murmurhash64 import hash64
names={f'{hash64(n)>>32:08X}':n for n in ('ap_aim','ap_camera_node','j_camera_attach','root','j_hips','j_spine','j_leftshoulder','j_rightshoulder')}
print('SKELETON',[(i,names.get(str(n.name),str(n.name)),n.parent_index) for i,n in enumerate(nodes)][:35])
print('REF_FIELDS',[(i,list(vars(g))) for i,g in enumerate(u.mesh_geometries)][:1])
for file in (ROOT/'build/native_reference').rglob('*.unit'):
    b.TEMPLATE=Path('<DARKTIDE_GAME>/bundle')
    v=b.unit_dt.UnitResourceDT(b.Cursor(str(file)))
    info={'nodes':[{'index':i+1,'name':names.get(str(n.name),str(n.name)),'parent':n.parent_index+1,'position':list(n.world_transform.translation)} for i,n in enumerate(v.scene_graph.nodes)],'bounds':[]}
    for g in v.mesh_geometries:
        c=next((c for c in g.channels if c.component.name=='POSITION'),None)
        if c:
            p=g.streams[c.stream].get_positions(c);info['bounds'].append([p.min(0).tolist(),p.max(0).tolist()])
    (ROOT/'build/native_reference'/(file.stem+'_inspection.json')).write_text(json.dumps(info,indent=2),encoding='utf-8')
    print('NATIVE',file.name,[(n['index'],n['name'],n['parent']) for n in info['nodes'][:15]],info['bounds'])
