from pathlib import Path
import sys,json,re
import numpy as np
from scipy.spatial import cKDTree
from skins_sources import OUT,SOURCES
from adapt_skins import load
key=sys.argv[1]
meta=json.loads((OUT/key/'conversion.json').read_text(encoding='utf8'))
ref=np.load(OUT/'references'/meta['base']/'source.npz')
names=ref['group_names'];p0=ref['positions'];w=np.zeros((len(p0),len(names)),np.float32)
for k in range(4):np.add.at(w,(np.arange(len(p0)),ref['indices'][:,k]),ref['weights'][:,k])
mask=np.array([bool(re.fullmatch(r'(手首|親指[０１２３]|人指[１２３]|中指[１２３]|薬指[１２３]|小指[１２３])\.[LR]',str(n)))for n in names])
ids=np.flatnonzero(mask);p=p0.copy()
for side,transform in meta['source_arm_pose_maps'].items():
    arm=np.array([bool(re.search(r'腕|ひじ|肘|手首|指',str(n)))and str(n).endswith(side)and not any(t in n for t in ('dummy','shadow','sleeve'))for n in names])
    f=w[:,arm].sum(1);t=np.array(transform);p=p*(1-f[:,None])+(p0@t[:3,:3].T+t[:3,3])*f[:,None]
tree=cKDTree(p);_,draws,_=load(key,1)
centers={i:(w[:,i,None]*p).sum(0)/w[:,i].sum()for i in ids if w[:,i].sum()>.01}
for palette in sorted({d['source_palette']for d in draws}):
    group=[d for d in draws if d['source_palette']==palette]
    positions=np.concatenate([d['positions']for d in group]);ii=np.concatenate([d['raw_indices']for d in group]);ww=np.concatenate([d['raw_weights']for d in group])
    dist,near=tree.query(positions);eligible=(dist<.012)&(w[near][:,mask].sum(1)>.6)
    rows=[]
    for raw in np.unique(ii[eligible]):
        mass=np.where(ii==raw,ww,0).sum(1);m=mass*eligible
        if m.sum()<1:continue
        center=m@positions/m.sum()
        norms=[]
        for i in centers:
            b=w[near,i]*eligible
            cosine=float(m@b/max(np.linalg.norm(m)*np.linalg.norm(b),1e-10))
            norms.append((str(names[i]),round(cosine,3),round(float(np.linalg.norm(center-centers[i])),4)))
        rows.append(dict(raw=int(raw),mass=round(float(m.sum()),1),best=sorted(norms,key=lambda x:-x[1])[:3]))
    if rows:print(palette,json.dumps(rows,ensure_ascii=False))
