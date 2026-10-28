from pathlib import Path
import sys,json,numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/blade_edge';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE=Path('<DARKTIDE_GAME>/bundle')
names=['root','grip','hilt','blade','pommel','ap_hilt','ap_blade','ap_pommel','ap_grip','ap_weapon','ap_fx','j_blade','j_hilt']
lookup={f'{b.hash64(n)>>32:08X}':n for n in names}
report={}
for family in ('2h_force_sword','2h_power_sword'):
    parts={}
    for part in ('grip_01','hilt_01','blade_01','blade_02','pommel_01'):
        path=OUT/'native/content/weapons/player/melee'/family/'attachments'/part/(part+'.unit')
        u=b.unit_dt.UnitResourceDT(b.Cursor(str(path)))
        m=u.meshes[0];g=u.mesh_geometries[m.geometry_index-1]
        c=next(c for c in g.channels if c.component.name=='POSITION')
        v=g.streams[c.stream].get_positions(c).astype(float)
        M=np.array(u.scene_graph.nodes[m.node_index].world_transform)
        v=v@M[:3,:3].T+M[:3,3]
        f=g.index_stream.get_indices().reshape(-1,3)
        nodes=[{'index':i,'name':lookup.get(str(n.name).upper(),str(n.name)),
                'parent':n.parent_index,'position':list(n.world_transform.translation)}
               for i,n in enumerate(u.scene_graph.nodes)]
        parts[part]={'bounds':[v.min(0).tolist(),v.max(0).tolist()],'nodes':nodes}
        np.savez(OUT/(family+'_'+part+'.npz'),vertices=v,faces=f)
    report[family]=parts
(OUT/'native_nodes.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NATIVE_NODES',json.dumps(report))
