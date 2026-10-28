from pathlib import Path
import bpy,sys,json,numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm

for tag in sys.argv[sys.argv.index('--')+1:]:
 out=HERE/'hand_repair_20261024'/tag
 src=out/'before_sleeve_segment_rebind.blend'
 base='si'if tag.startswith('si_')else'roshia'
 meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
 bpy.ops.wm.open_mainfile(filepath=str(src));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
 p=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices]);domains=nearest(p,from_armature(arm))
 names={g.index:g.name for g in mesh.vertex_groups};rows=[]
 def owner(n):
  b=arm.data.bones.get(n)
  while b:
   if is_arm(b.name):return b.name.rsplit('.',1)[-1]
   b=b.parent
  return 'nonarm'
 for mi,mat in enumerate(mesh.data.materials):
  if not mat or mat.get('costume_skin')or not mat.name.startswith('Costume_'):continue
  faces=[list(f.vertices)for f in mesh.data.polygons if f.material_index==mi]
  if not faces:continue
  ids=np.unique(np.concatenate(faces));_,inv=np.unique(np.round(p[ids],6),axis=0,return_inverse=True)
  parent=np.arange(inv.max()+1);lookup={int(i):int(j)for i,j in zip(ids,inv)}
  def root(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  for f in faces:
   a=root(lookup[f[0]])
   for vi in f[1:]:parent[root(lookup[vi])]=a
  comps={}
  for vi in ids:comps.setdefault(root(lookup[int(vi)]),[]).append(int(vi))
  result=[]
  for comp in comps.values():
   v=p[comp];w={}
   for vi in comp:
    for g in mesh.data.vertices[vi].groups:
     if names[g.group]in arm.data.bones:w[names[g.group]]=w.get(names[g.group],0)+g.weight
   mass={s:sum(x for n,x in w.items()if owner(n)==s)/max(sum(w.values()),1e-12)for s in ('L','R','nonarm')}
   result.append(dict(vertices=len(comp),bounds_m=[v.min(0).tolist(),v.max(0).tolist()],center_m=v.mean(0).tolist(),authored_ancestor_mass=mass,
    nearest_anatomy={str(n):int(np.sum(domains[comp]==n))for n in np.unique(domains[comp])},
    original_top_groups=sorted(w.items(),key=lambda x:-x[1])[:8]))
  rows.append(dict(index=mi,material=mat.name,arm_garment=bool(mat.get('costume_arm_garment')),components=sorted(result,key=lambda x:-x['vertices'])))
 (out/'source_garment_components.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
 print('SOURCE_COMPONENTS',tag,[(r['material'],[(c['vertices'],c['center_m'])for c in r['components'][:5]])for r in rows],flush=True)
