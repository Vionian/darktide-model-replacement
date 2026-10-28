"""Adjacent-joint sleeve field measured from the actual source arm chain.

Unlike the rejected all-segment inverse-distance field, an elbow/wrist sleeve
cannot receive a distant shoulder transform. No guessed offsets or face edits.
"""
from pathlib import Path
import bpy,numpy as np,json,sys,shutil,hashlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm

def run(tag):
 legacy={'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
         'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend','si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
 source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
 base='si'if tag.startswith('si_')else json.loads((source.parent/'conversion.json').read_text())['base']
 meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
 bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
 p=np.asarray([mesh.matrix_world@v.co for v in mesh.data.vertices]);domain=nearest(p,from_armature(arm))
 slots={i for i,m in enumerate(mesh.data.materials)if m and not m.get('costume_skin')and not m.get('costume_is_hair')and (m.name.startswith('Costume_')or m.name.startswith('InkMist_'))}
 used={vi for f in mesh.data.polygons if f.material_index in slots for vi in f.vertices}
 protected={vi for f in mesh.data.polygons if mesh.data.materials[f.material_index].get('costume_skin')for vi in f.vertices}
 ids=np.array(sorted(vi for vi in used-protected if is_arm(str(domain[vi]))),int)
 backup=HERE/'hand_repair_20261024'/tag/'before_sleeve_chain_rebind.blend';assert not backup.exists(),tag
 shutil.copy2(source,backup);names={g.index:g.name for g in mesh.vertex_groups};rows=[]
 for side in ('L','R'):
  own=ids[[str(domain[i]).endswith('.'+side)for i in ids]]
  labels=[n+'.'+side for n in ('肩','腕','ひじ','手首')]
  joints=np.array([arm.matrix_world@arm.data.bones[n].head_local for n in labels])
  distances=[];projections=[]
  for a,z in zip(joints[:-1],joints[1:]):
   axis=z-a;t=np.clip((p[own]-a)@axis/(axis@axis),0,1);projections.append(t)
   distances.append(np.sum((p[own]-a-t[:,None]*axis)**2,axis=1))
  segment=np.argmin(np.stack(distances,axis=1),axis=1)
  field=np.zeros((len(own),4))
  for j in range(3):
   match=segment==j;t=projections[j][match];field[match,j]=1-t;field[match,j+1]=t
  # Garment beyond the measured wrist belongs to the wrist, never a digit.
  wrist_axis=joints[-1]-joints[-2]
  distal=(p[own]-joints[-1])@wrist_axis>=0
  field[distal]=[0,0,0,1]
  for vi,weights in zip(own,field):
   for g in list(mesh.data.vertices[int(vi)].groups):
    if names[g.group]in arm.data.bones:mesh.vertex_groups[g.group].remove([int(vi)])
   for n,w in zip(labels,weights):
    if w>1e-8:(mesh.vertex_groups.get(n)or mesh.vertex_groups.new(name=n)).add([int(vi)],float(w),'REPLACE')
  rows.append(dict(side=side,vertices=len(own),source_joint_positions=joints.tolist(),bones=labels,maximum_influences=int((field>0).sum(1).max())))
 bpy.ops.wm.save_as_mainfile(filepath=str(source))
 report=dict(profile=tag,method='actual source shoulder/elbow/wrist adjacent-joint projection; no distant joint mixing; distal garment follows wrist',rows=rows,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),topology_uv_normals_textures_and_skin_unchanged=True,gameplay_verified=False)
 (backup.parent/'sleeve_chain_rebind.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('ADJACENT_SLEEVE_REBIND',tag,flush=True)

if __name__=='__main__':
 for tag in sys.argv[sys.argv.index('--')+1:]:run(tag)
