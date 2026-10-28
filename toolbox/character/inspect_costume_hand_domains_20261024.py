"""Measure recovered costume digit weights against its own source hand."""
import json,re,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
HERE=Path(__file__).resolve().parent;OUT=HERE/'skins_20261023'
for tag in sys.argv[1:]:
    folder=OUT/tag;meta=json.loads((folder/'conversion.json').read_text(encoding='utf8'))
    source=np.load(OUT/'references'/meta['base']/'source.npz');names=source['group_names']
    original=json.loads((OUT/'references'/meta['base']/'source.json').read_text(encoding='utf8'))
    parents={b['name']:b['parent']for b in original['bones']}
    def below(name,root):
        cur=str(name);seen=set()
        while cur and cur not in seen:
            if cur==root:return True
            seen.add(cur);cur=parents.get(cur)
        return False
    p0=source['positions'];w0=np.zeros((len(p0),len(names)))
    for k in range(4):np.add.at(w0,(np.arange(len(p0)),source['indices'][:,k]),source['weights'][:,k])
    hand=np.array([bool(re.fullmatch(r'(手首|親指[０１２３]|人指[１２３]|中指[１２３]|薬指[１２３]|小指[１２３])\.[LR]',str(n)))for n in names])
    arm=np.array([bool(re.search(r'腕|ひじ|肘|手首|指',str(n)))and not any(t in n for t in ('dummy','shadow','sleeve'))for n in names])
    posed=p0.copy()
    for side,m in meta['source_arm_pose_maps'].items():
        factor=w0[:,np.array([below(n,'腕'+side)for n in names])].sum(1)
        m=np.array(m);posed=posed*(1-factor[:,None])+(p0@m[:3,:3].T+m[:3,3])*factor[:,None]
    skin=source['skin_vertices'];handids=skin[w0[skin][:,hand].sum(1)>.5]
    tree=cKDTree(posed[handids]);data=np.load(folder/'restored_meshes.npz');rows=[]
    for i,draw in enumerate(meta['draws']):
        p=data[f'{i}_positions'];ii=data[f'{i}_indices'];ww=data[f'{i}_weights']
        mass=np.where(hand[ii],ww,0).sum(1);sel=np.flatnonzero(mass>.5)
        if not len(sel):continue
        distance,nearest=tree.query(p[sel]);far=sel[distance>.012]
        rows.append(dict(draw=i,section=draw['section'],start=draw['start'],hand_majority_vertices=len(sel),
            source_skin_hand_distance_mm=(1000*np.quantile(distance,[0,.5,.9,.99,1])).round(6).tolist(),
            farther_than_12mm=len(far),far_vertex_examples=[dict(vertex=int(j),position=p[j].tolist(),weights=[(str(names[k]),float(v))for k,v in zip(ii[j],ww[j])if v>1e-5])for j in far[:4]]))
    report=dict(profile=tag,source_hand_vertices=len(handids),rows=rows)
    dest=HERE/'hand_repair_20261024'/tag;dest.mkdir(parents=True,exist_ok=True)
    (dest/'source_hand_domain_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))
