from pathlib import Path
import bpy,numpy as np,json,sys
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
tag=sys.argv[sys.argv.index('--')+1]
src=HERE/'si_costumes'/tag/(tag+'.blend')if tag=='si_lolita'else HERE/'skins_20261023'/tag/(tag+'.blend')
out=HERE/'hand_repair_20261024'/tag
meta=json.loads((HERE/'skins_20261023/references/si/source.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(src));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
import build_roshia_native as b
from endfield_profiles import apply
apply(b,tag);b.HAND_AUTHORING_OUTPUT=out/'nail_inspection';b.HAND_AUTHORING_OUTPUT.mkdir(exist_ok=True)
b.prepare_source(mesh,arm)
mesh.data.calc_loop_triangles()
selected=np.load(out/'preview_rest/actual_source_face_selection.npz')
actual=np.asarray([mesh.matrix_world@v.co for v in mesh.data.vertices])
assert actual.shape==selected['source_positions'].shape,'Prepared source count mismatch'
assert np.max(np.abs(actual-selected['source_positions']))<1e-7,'Prepared source vertex identity mismatch'
faces={tuple(sorted(f))for f in selected['faces']}
names={g.index:g.name for g in mesh.vertex_groups}
weights=[{names[g.group]:g.weight for g in v.groups if g.weight>1e-6}for v in mesh.data.vertices]
rows=[]
for side in ['L','R']:
 ids={i for i,w in enumerate(weights)if sum(v for n,v in w.items()if n.startswith('親指')and n.endswith('.'+side))>.1}
 for mi,mat in enumerate(mesh.data.materials):
  tris=[t for t in mesh.data.loop_triangles if t.material_index==mi and set(t.vertices)&ids]
  if not tris:continue
  missing=[t for t in tris if tuple(sorted(t.vertices))not in faces]
  boundary={}
  for t in tris:
   for i in range(3):
    e=tuple(sorted([t.vertices[i],t.vertices[(i+1)%3]]));boundary[e]=boundary.get(e,0)+1
  rows.append(dict(side=side,material=mat.name,total=len(tris),missing=len(missing),
   source_boundary_edges=sum(n==1 for n in boundary.values()),
   missing_vertices=[dict(vertex=int(i),position=list(mesh.matrix_world@mesh.data.vertices[i].co),weights=weights[i])for i in sorted({i for t in missing for i in t.vertices})][:24]))
(out/'nail_coverage.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('NAIL_COVERAGE',json.dumps(rows,ensure_ascii=False),flush=True)
