from pathlib import Path
import sys, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, '<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE=ROOT/'暗潮武器mod/ExcaliburAlterForceSword/Custom/alter_sword'
u=b.unit_dt.UnitResourceDT(b.Cursor(str(b.TEMPLATE/'alter_sword.unit')))
out={'meshes':[], 'nodes':[]}
for i,g in enumerate(u.mesh_geometries):
    ch=next(c for c in g.channels if c.component.name=='POSITION')
    v=g.streams[ch.stream].get_positions(ch)
    np.save(ROOT/f'build/reference_positions_{i}.npy', v)
    out['meshes'].append({'index':i,'vertices':len(v),'bounds':[v.min(axis=0).tolist(),v.max(axis=0).tolist()]})
for i,n in enumerate(u.scene_graph.nodes):
    out['nodes'].append({'index':i,'name':str(n.name),'parent':n.parent_index,'world':[list(row) for row in n.world_transform]})
(ROOT/'build/reference_frame.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
