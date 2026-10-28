"""Measure serialized hand surfaces and bind contracts, not just builder intent."""
import sys,pathlib,json
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from roshia_native_hand_surface import reference_zones,frame
out=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve()
f=out/'Custom/roshia_arms'
u=b.unit_dt.UnitResourceDT(b.Cursor(str(f/'roshia_arms.unit')))
names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(f/'roshia_arms_bones.bones'))))
z=reference_zones(b,'roshia_arms',f);ref=reference_zones(b)
old=reference_zones(b,'roshia_arms',out.parent/'iter_20261018_grip_contract_candidate/Custom/roshia_arms')
r={}
for n,points in z.items():
    if n not in ref or n.endswith('hand'):continue
    side='left' if n.startswith('j_left') else 'right';prefix=f'j_{side}hand'
    def point(key):return np.array(u.scene_graph.nodes[names[key]].world_transform.translation)
    normal=np.cross(point(prefix+'middle1')-point(prefix),point(prefix+'pinky1')-point(prefix+'index1'))
    k=int(n[-1]);following=n[:-1]+str(k+1) if k<3 else n[:-1]+str(k-1)
    axis=point(following)-point(n) if k<3 else point(n)-point(following)
    basis=frame(axis,normal);a=(points-point(n))@basis;c=(ref[n]-point(n))@basis
    qa=np.quantile(a,[.05,.95],axis=0);qc=np.quantile(c,[.05,.95],axis=0)
    assert np.isfinite(qa).all()
    qb=np.quantile((old[n]-point(n))@basis,[.05,.95],axis=0) if n in old else None
    r[n]={'previous_cross_section_error_mm':None if qb is None else ((qb-qc)[:,1:]*1000).tolist(),'samples':len(points),'reference_samples':len(c),'cross_section_envelope_error_mm':((qa-qc)[:,1:]*1000).tolist(),'tip_extent_error_mm':float((qa[1,0]-qc[1,0])*1000)}
(out/'serialized_hand_surface_audit.json').write_text(json.dumps(r,indent=2))
print('SURFACE_ZONES',len(r),'max_cross_section_error_mm',max(np.max(np.abs(v['cross_section_envelope_error_mm'])) for v in r.values()))
