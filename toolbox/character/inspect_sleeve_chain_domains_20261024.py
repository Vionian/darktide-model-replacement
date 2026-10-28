from pathlib import Path
import json,sys,re
import bpy,numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm
legacy={'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
        'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend',
        'si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
rows=[]
for tag in sys.argv[sys.argv.index('--')+1:]:
    source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
    meta=json.loads((HERE/'skins_20261023/references/si/source.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
    points=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices]);domain=nearest(points,from_armature(arm))
    labels={g.index:g.name for g in mesh.vertex_groups};result=[]
    for prefix in ('L_sleeveD_','R_sleeveD_','ribbonF_'):
        groups={i for i,n in labels.items()if n.startswith(prefix)}
        mass=np.array([sum(g.weight for g in v.groups if g.group in groups)for v in mesh.data.vertices])
        ids=np.flatnonzero(mass>.01)
        if not len(ids):continue
        roots=[b for b in arm.data.bones if b.name.startswith(prefix)and (not b.parent or not b.parent.name.startswith(prefix))]
        q=np.quantile(points[ids],[0,.5,1],axis=0)
        shares={str(n):float(mass[ids][domain[ids]==n].sum()/mass[ids].sum())for n in np.unique(domain[ids])}
        result.append(dict(prefix=prefix,weighted_vertices=len(ids),roots=[dict(name=b.name,parent=b.parent.name if b.parent else None)for b in roots],
            position_quantiles=q.tolist(),anatomical_mass_shares=shares))
    rows.append(dict(profile=tag,source=str(source),rows=result))
    print('SLEEVE_CHAIN_DOMAINS',json.dumps(rows[-1],ensure_ascii=False),flush=True)
(HERE/'hand_repair_20261024/sleeve_chain_domains.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
