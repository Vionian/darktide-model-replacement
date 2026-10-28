import importlib.util, sys, pathlib, json
import numpy as np
here=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("builder",here/"build_roshia_native.py")
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
report={}
for asset in ('qianxia','daniya_blue','aimisi','roshia'):
 b.TEMPLATE=b.ROOT/'Custom'/asset
 unit=b.unit_dt.UnitResourceDT(b.Cursor(str(b.TEMPLATE/(asset+'.unit'))))
 vals=[]
 for geo in unit.mesh_geometries:
  channels={c.component.name:c for c in geo.channels}
  pc=channels['POSITION'];nc=channels['NORMAL']
  pos=geo.streams[pc.stream].get_positions(pc).astype(np.float32)
  normal=geo.streams[nc.stream].get_normals(nc).astype(np.float32)
  ids=geo.index_stream.get_indices().reshape((-1,3))
  face=np.cross(pos[ids[:,1]]-pos[ids[:,0]],pos[ids[:,2]]-pos[ids[:,0]])
  dot=(face*normal[ids].mean(axis=1)).sum(axis=1)
  valid=np.linalg.norm(face,axis=1)>1e-10
  vals.extend((dot[valid]>0).tolist())
 report[asset]={'positive_face_normal_fraction':float(np.mean(vals)), 'triangles':len(vals)}
print('WINDING_COMPARISON',json.dumps(report))
(here/'roshia/winding_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
