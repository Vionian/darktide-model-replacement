"""Localize visible finger-web distortions using the exact preview vertex maps."""
import sys,json
from pathlib import Path
import bpy,numpy as np
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from skins_sources import OUT
tag=sys.argv[sys.argv.index('--')+1]
meta=json.loads((OUT/tag/'conversion.json').read_text(encoding='utf8'))
ref=json.loads((OUT/'references'/meta['base']/'source.json').read_text(encoding='utf8'))
prepared=list((OUT/tag/'native').glob('*_original_hand_MMR.blend'))
assert len(prepared)==1,('Missing prepared source hand evidence',tag)
bpy.ops.wm.open_mainfile(filepath=str(prepared[0]))
mesh=bpy.data.objects[ref['mesh']];mesh.data.calc_loop_triangles()
source=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])*ref['scale']
export=np.load(OUT/tag/'preview_hands/roshia_builder_retargeted_positions.npy')
assert len(source)==len(export),(len(source),len(export))
names={g.index:g.name for g in mesh.vertex_groups}
mass=np.array([sum(g.weight for g in v.groups if '指'in names[g.group]or '手首'in names[g.group])for v in mesh.data.vertices])
tris=np.array([t.vertices[:]for t in mesh.data.loop_triangles if mass[list(t.vertices)].min()>.7])
edges=np.unique(np.sort(np.concatenate([tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]]),axis=1),axis=0)
before=np.linalg.norm(source[edges[:,0]]-source[edges[:,1]],axis=1)
after=np.linalg.norm(export[edges[:,0]]-export[edges[:,1]],axis=1)
valid=before>.0001;edges=edges[valid];before=before[valid];after=after[valid];ratio=after/before
print('HAND_EDGE_SUMMARY',tag,len(edges),np.quantile(ratio,[.5,.95,.99,1]).tolist(),flush=True)
report=dict(profile=tag,edges=len(edges),ratio_quantiles=np.quantile(ratio,[.5,.95,.99,1]).tolist(),
            maximum_edge_extension_mm=float(np.max(after-before)*1000),
            compared_prepared_source_to_actual_export=True,game_verified=False)
(OUT/tag/'hand_topology_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
for ei in np.argsort(ratio)[-2:][::-1]:
    pair=edges[ei];details=[]
    for vi in pair:
        v=mesh.data.vertices[int(vi)]
        details.append(dict(index=int(vi),source=source[vi].tolist(),export=export[vi].tolist(),
            weights=[(names[g.group],round(g.weight,5))for g in sorted(v.groups,key=lambda x:-x.weight)[:5]]))
    print('HAND_EDGE',round(float(ratio[ei]),3),float(before[ei]),float(after[ei]),details,flush=True)
assert np.quantile(ratio,.99)<4 and np.max(ratio)<12,('Hand source/export discontinuity',tag,report)
