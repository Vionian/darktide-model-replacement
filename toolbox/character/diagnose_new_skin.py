from pathlib import Path
import sys,json,numpy as np
sys.path.insert(0,str(Path(__file__).parent))
import build_roshia_native as b
from skins_sources import OUT
tag=sys.argv[sys.argv.index('--')+1]
rows={}
for asset in (tag,tag+'_arms'):
    folder=OUT/tag/'Custom'/asset
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
    report=[]
    for i,g in enumerate(u.mesh_geometries):
        c={c.component.name:c for c in g.channels}
        p=g.streams[c['POSITION'].stream].get_positions(c['POSITION']).astype(float)
        n=g.streams[c['NORMAL'].stream].get_normals(c['NORMAL']).astype(float)
        f=g.index_stream.get_indices().reshape(-1,3)
        v=p[f];cross=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0])
        length=np.linalg.norm(cross,axis=1);dot=(cross*n[f].mean(1)).sum(1)
        valid=length>1e-10;bad=valid&(dot<=0)
        report.append(dict(chunk=i,triangles=len(f),invalid=int((~valid).sum()),bad=int(bad.sum()),
            bad_center=v[bad].mean((0,1)).tolist()if bad.any()else None))
    rows[asset]=report
(OUT/tag/'winding_diagnostic.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print(json.dumps(rows,indent=2))
