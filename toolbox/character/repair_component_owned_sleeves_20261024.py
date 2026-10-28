"""Restore authoring inputs, then transfer only source-owned sleeve islands.

Pointwise nearest anatomy alone assigned the hanging skirt/cape near a resting
hand to the wrist. A sleeve must instead agree in original bone ancestry and
complete source-space connected-surface ownership. No source geometry is cut.
"""
from pathlib import Path
import bpy,numpy as np,json,sys,shutil,hashlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import is_arm
from repair_sleeve_skin_transfer_20261024 import run as transfer

def classify(mesh,arm,p,domain,include_shoulder=False):
 result=np.array(domain,dtype=object);names={g.index:g.name for g in mesh.vertex_groups}
 def owner(n):
  bone=arm.data.bones.get(n)
  while bone:
   if bone.name.startswith('肩.')and not include_shoulder:return 'nonarm'
   if is_arm(bone.name):return bone.name.rsplit('.',1)[-1]
   bone=bone.parent
  return 'nonarm'
 owners={i:owner(n)for i,n in names.items()};report=[]
 skin={vi for f in mesh.data.polygons if mesh.data.materials[f.material_index].get('costume_skin')for vi in f.vertices}
 for mi,mat in enumerate(mesh.data.materials):
  if not mat or mat.get('costume_skin')or mat.get('costume_is_hair')or not mat.name.startswith(('Costume_','InkMist_')):continue
  faces=[list(f.vertices)for f in mesh.data.polygons if f.material_index==mi]
  if not faces:continue
  ids=np.unique(np.concatenate(faces));_,inverse=np.unique(np.round(p[ids],6),axis=0,return_inverse=True)
  parent=np.arange(inverse.max()+1);lookup={int(i):int(j)for i,j in zip(ids,inverse)}
  def root(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  for f in faces:
   a=root(lookup[f[0]])
   for vi in f[1:]:parent[root(lookup[vi])]=a
  comps={}
  for vi in ids:comps.setdefault(root(lookup[int(vi)]),[]).append(int(vi))
  accepted=0;untouched=0;rows=[]
  for comp in comps.values():
   mass={s:0. for s in ('L','R','nonarm')}
   for vi in comp:
    for g in mesh.data.vertices[vi].groups:
     if names[g.group]in arm.data.bones:mass[owners[g.group]]+=g.weight
   total=sum(mass.values());mass={s:w/max(total,1e-12)for s,w in mass.items()}
   side=max(('L','R'),key=lambda s:mass[s])
   anatomical=sum(is_arm(str(domain[i]))and str(domain[i]).endswith('.'+side)for i in comp)/len(comp)
   sleeve=mass[side]>.5 and anatomical>.5
   own=[vi for vi in comp if vi not in skin]
   result[own]='ひじ.'+side if sleeve else 'nonarm-component'
   if sleeve:accepted+=len(own)
   else:untouched+=len(own)
   rows.append(dict(vertices=len(comp),source_ancestor_mass=mass,same_side_anatomical_fraction=anatomical,
    sleeve=sleeve,center_m=p[comp].mean(0).tolist()))
  report.append(dict(material=mat.name,sleeve_vertices=accepted,nonarm_vertices_kept_original=untouched,components=rows))
 classify.report=report
 return result

def run(tag,restore_previous=True):
 out=HERE/'hand_repair_20261024'/tag
 legacy={'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend','si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend','si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
 src=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
 original=out/'before_sleeve_segment_rebind.blend' if restore_previous else src
 assert original.is_file(),tag
 original_sha=hashlib.sha256(original.read_bytes()).hexdigest()
 rejected=out/'rejected_pointwise_sleeve_source.blend';assert not rejected.exists(),tag
 shutil.copy2(src,rejected)
 if restore_previous:shutil.copy2(original,src)
 transfer(tag,output_key='component_owned_sleeve_transfer',classify_domain=classify)
 (out/'component_owned_sleeve_domains.json').write_text(json.dumps(dict(profile=tag,
  restored_input=str(original),restored_sha256=original_sha,restored_previous_input=restore_previous,
  source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),materials=classify.report,
  source_geometry_uv_normals_unchanged=True,gameplay_verified=False),ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:]
 for tag in args:
  if not tag.startswith('--'):run(tag,restore_previous='--fresh'not in args)
