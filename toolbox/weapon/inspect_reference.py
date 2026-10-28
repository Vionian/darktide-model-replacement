from pathlib import Path
import sys, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, '<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE=ROOT/'暗潮武器mod/ExcaliburAlterForceSword/Custom/alter_sword'
u=b.unit_dt.UnitResourceDT(b.Cursor(str(b.TEMPLATE/'alter_sword.unit')))
print('UNIT_FIELDS', list(vars(u)))
for i,g in enumerate(u.mesh_geometries):
    print('GEO',i,vars(g))
    for stream in g.streams:
        print('STREAM', {k:(len(v) if isinstance(v,bytes) else v) for k,v in vars(stream).items()})
        if stream.stride >= 12 and stream.vertex_data:
            data=np.ndarray((stream.size,3),dtype='<f4',buffer=stream.vertex_data,strides=(stream.stride,4)) if hasattr(stream,'size') else None
for i,m in enumerate(u.meshes): print('MESH',i,vars(m))
print('GRAPH', vars(u.scene_graph))
