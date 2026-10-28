"""Restore exact source weights for shoulder-only panels misclassified as sleeves."""
from pathlib import Path
import bpy,sys,json,numpy as np,shutil,hashlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from repair_component_owned_sleeves_20261024 import classify
from costume_anatomical_domains import nearest,from_armature,is_arm

args=sys.argv[sys.argv.index('--')+1:]
for tag in args:
 if tag.startswith('--'):continue
 out=HERE/'hand_repair_20261024'/tag;base='si'if tag.startswith('si_')else'roshia'
 meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
 legacy={'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend','si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend','si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
 source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'));original=out/'before_sleeve_segment_rebind.blend'
 bpy.ops.wm.open_mainfile(filepath=str(original));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
 p=np.asarray([mesh.matrix_world@v.co for v in mesh.data.vertices]);anatomy=nearest(p,from_armature(arm))
 old=classify(mesh,arm,p,anatomy,include_shoulder=True);new=classify(mesh,arm,p,anatomy,include_shoulder=False)
 ids=[i for i in range(len(p))if is_arm(str(old[i]))and not is_arm(str(new[i]))]
 names={g.index:g.name for g in mesh.vertex_groups};weights={i:[(names[g.group],g.weight)for g in mesh.data.vertices[i].groups]for i in ids}
 points={i:tuple(mesh.data.vertices[i].co)for i in ids}
 report=dict(profile=tag,shoulder_only_vertices=len(ids),apply='--apply'in args,source_geometry_unchanged=True,gameplay_verified=False)
 if '--apply'in args and ids:
  backup=out/'before_shoulder_only_source_restore.blend';assert not backup.exists(),tag;shutil.copy2(source,backup)
  bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
  assert all(tuple(mesh.data.vertices[i].co)==points[i]for i in ids),tag
  for i in ids:
   for g in list(mesh.data.vertices[i].groups):
    if mesh.vertex_groups[g.group].name in arm.data.bones:mesh.vertex_groups[g.group].remove([i])
   for n,w in weights[i]:
    if n in arm.data.bones:(mesh.vertex_groups.get(n)or mesh.vertex_groups.new(name=n)).add([i],w,'REPLACE')
  bpy.ops.wm.save_as_mainfile(filepath=str(source));report['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
 (out/('shoulder_ownership_restoration.json'if '--apply'in args else'shoulder_ownership_probe.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
 print('SHOULDER_SOURCE_PROBE',json.dumps(report),flush=True)
