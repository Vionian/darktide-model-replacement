"""Two traced residuals, not an analytical sleeve deformation.

Cocoa component 17 is the original collar/torso, not a sleeve. Restore its
original source weights exactly. Si Lolita's previously audited leg-domain
skirt points carry sleeve helper bones; rerun that exact correction after the
component repair restored its pre-experiment input.
"""
from pathlib import Path
import bpy,sys,json,shutil,hashlib,datetime
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from repair_nonarm_garment_bindings_20261024 import run as nonarm
R=HERE/'hand_repair_20261024';tag='roshia_cocoa_puff';out=R/tag
source=HERE/'skins_20261023'/tag/(tag+'.blend')
backup=out/'before_final_collar_source_restore.blend';assert not backup.exists();shutil.copy2(source,backup)
meta=json.loads((HERE/'skins_20261023/references/roshia/source.json').read_text(encoding='utf8'))
original=out/'before_sleeve_segment_rebind.blend'
bpy.ops.wm.open_mainfile(filepath=str(original));mesh=bpy.data.objects[meta['mesh']]
slot=next(i for i,m in enumerate(mesh.data.materials)if m and m.name=='Costume_roshia_cocoa_puff_17')
ids=sorted({i for f in mesh.data.polygons if f.material_index==slot for i in f.vertices});names={g.index:g.name for g in mesh.vertex_groups}
weights={i:[(names[g.group],g.weight)for g in mesh.data.vertices[i].groups]for i in ids}
points={i:tuple(mesh.data.vertices[i].co)for i in ids}
bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
assert all(tuple(mesh.data.vertices[i].co)==points[i]for i in ids),'Source topology mismatch'
for i in ids:
 for g in list(mesh.data.vertices[i].groups):
  if mesh.vertex_groups[g.group].name in arm.data.bones:mesh.vertex_groups[g.group].remove([i])
 for n,w in weights[i]:
  if n in arm.data.bones:(mesh.vertex_groups.get(n)or mesh.vertex_groups.new(name=n)).add([i],w,'REPLACE')
bpy.ops.wm.save_as_mainfile(filepath=str(source))
(out/'final_collar_source_restore.json').write_text(json.dumps(dict(profile=tag,material='Costume_roshia_cocoa_puff_17',
 vertices=len(ids),method='exact original pre-experiment collar weights, same topology and source vertex IDs',
 source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),positions_uv_normals_unchanged=True,gameplay_verified=False),indent=2),encoding='utf8')
print('COLLAR_SOURCE_RESTORED',len(ids),flush=True)
out=R/'si_lolita'
for name in ('before_nonarm_garment_rebind.blend','nonarm_garment_rebind.json'):
 p=out/name
 if p.exists():shutil.move(str(p),str(p.with_name(p.stem+'_previous_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+p.suffix)))
nonarm('si_lolita',apply=True,lower_only=True)
