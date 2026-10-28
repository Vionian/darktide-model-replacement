"""Measure source-to-fitted local edges without editing geometry or weights."""
import json
from pathlib import Path
import numpy as np
def record(b,mesh,fitted,destination,groups=None):
    mesh.data.calc_loop_triangles()
    p=np.asarray([b.source_coordinate3()@(mesh.matrix_world@v.co)for v in mesh.data.vertices],float)
    tris=np.asarray([t.vertices[:]for t in mesh.data.loop_triangles],int)
    mats=np.asarray([t.material_index for t in mesh.data.loop_triangles],int)
    rows=[]
    for mi in (range(len(groups)) if groups is not None else np.unique(mats)):
        own=groups[mi]['vertices'][groups[mi]['triangles']] if groups is not None else tris[mats==mi]
        if not len(own):continue
        edges=np.unique(np.sort(np.concatenate([own[:,[0,1]],own[:,[1,2]],own[:,[2,0]]]),axis=1),axis=0)
        old=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1)
        new=np.linalg.norm(fitted[edges[:,0]]-fitted[edges[:,1]],axis=1)
        ids=np.flatnonzero(old>.0005)
        if not len(ids):continue
        ratio=new[ids]/old[ids];worst=ids[np.argsort(ratio)[-4:][::-1]]
        rows.append(dict(material=mesh.data.materials[int(mi)].name,edges=len(ids),
            stretch_quantiles=np.quantile(ratio,[.5,.95,.99,1]).tolist(),
            worst=[dict(vertices=edges[k].tolist(),source_mm=float(old[k]*1000),fitted_mm=float(new[k]*1000),
                ratio=float(new[k]/old[k]),source_positions=p[edges[k]].tolist(),fitted_positions=fitted[edges[k]].tolist())for k in worst]))
    Path(destination).write_text(json.dumps(dict(profile=getattr(b,'COSTUME_PROFILE',getattr(b,'MODEL_PROFILE','roshia')),
        scope='actual selected export triangles after cuff/watch adjustment, before runtime pose' if groups is not None else 'all authoring source triangles, including first-person-excluded body; not a gameplay pass',
        materials=rows),indent=2),encoding='utf8')
