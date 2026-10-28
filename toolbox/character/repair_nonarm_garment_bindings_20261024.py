"""Remove verified arm ownership from non-arm garment anatomical regions.

No face/vertex/UV edits. Actual source skeleton segments determine ownership;
remaining non-arm authored weights are preserved and normalized.
"""
from pathlib import Path
import bpy,numpy as np,json,sys,hashlib,shutil,datetime
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm

def run(tag,apply=False,lower_only=False):
 legacy={'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
         'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend','si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
 source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
 base='si'if tag.startswith('si_')else json.loads((source.parent/'conversion.json').read_text())['base']
 meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
 bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
 p=np.asarray([mesh.matrix_world@v.co for v in mesh.data.vertices]);domain=nearest(p,from_armature(arm))
 def arm_owned(name):
  bone=arm.data.bones.get(name)
  while bone:
   if is_arm(bone.name):return True
   bone=bone.parent
  return False
 names={g.index:g.name for g in mesh.vertex_groups}
 arm_groups={i for i,n in names.items()if arm_owned(n)}
 slots={i for i,m in enumerate(mesh.data.materials)if m and not m.get('costume_skin')and not m.get('costume_is_hair')and (m.name.startswith('Costume_')or m.name.startswith('InkMist_'))}
 used={v for f in mesh.data.polygons if f.material_index in slots for v in f.vertices}
 protected={v for f in mesh.data.polygons if mesh.data.materials[f.material_index].get('costume_skin')for v in f.vertices}
 ids=[i for i in sorted(used-protected)if not is_arm(str(domain[i]))]
 if lower_only:ids=[i for i in ids if str(domain[i]).startswith(('足.','ひざ.','足首.','つま先.'))]
 changes=[];by_group={}
 for vi in ids:
  v=mesh.data.vertices[vi];bad=[g for g in v.groups if g.group in arm_groups and g.weight>1e-8]
  if not bad:continue
  for g in bad:by_group[names[g.group]]=by_group.get(names[g.group],0)+1
  keep=[(g.group,g.weight)for g in v.groups if g.group not in arm_groups and names[g.group]in arm.data.bones and g.weight>1e-8]
  changes.append((vi,keep,sum(g.weight for g in bad)))
 out=HERE/'hand_repair_20261024'/tag;out.mkdir(exist_ok=True)
 report=dict(profile=tag,apply=apply,lower_body_only=lower_only,affected_vertices=len(changes),anatomical_domains={str(n):sum(str(domain[i])==str(n)for i,_,_ in changes)for n in set(domain[i]for i,_,_ in changes)},
  removed_arm_groups=by_group,source=str(source),positions_topology_uv_normals_unchanged=True,gameplay_verified=False)
 if apply:
  backup=out/'before_nonarm_garment_rebind.blend';assert not backup.exists(),('Do not repeat source edit',tag)
  shutil.copy2(source,backup)
  for vi,keep,_ in changes:
   for g in list(mesh.data.vertices[vi].groups):
    if names[g.group]in arm.data.bones:mesh.vertex_groups[g.group].remove([vi])
   if keep:
    mass=sum(w for _,w in keep)
    for gi,w in keep:mesh.vertex_groups[gi].add([vi],float(w/mass),'REPLACE')
   else:
    n=str(domain[vi]);(mesh.vertex_groups.get(n)or mesh.vertex_groups.new(name=n)).add([vi],1.,'REPLACE')
  bpy.ops.wm.save_as_mainfile(filepath=str(source));report['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
  (out/'nonarm_garment_rebind.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print('NONARM_GARMENT_BINDINGS',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:]
 for tag in args:
  if not tag.startswith('--'):run(tag,'--apply'in args,'--lower-body-only'in args)
