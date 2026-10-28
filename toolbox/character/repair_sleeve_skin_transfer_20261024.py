"""Derive sleeve weights from the actual same-character source arm surface.

No invented joint offsets, no analytical all-bone field, no face deletion.
The underlying costume arm skin is restored from original rest matrices first.
Garment arm vertices then receive barycentric skin-triangle weights; digits
are collapsed to the wrist for cloth, retaining the original skin unchanged.
"""
from pathlib import Path
import bpy,numpy as np,json,sys,shutil,hashlib,types
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm
from costume_original_hand_weights import apply as restore_hand

def run(tag,output_key='actual_skin_sleeve_transfer',classify_domain=None):
 legacy={'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
         'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend','si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
 source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
 base='si'if tag.startswith('si_')else json.loads((source.parent/'conversion.json').read_text())['base']
 meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
 out=HERE/'hand_repair_20261024'/tag;out.mkdir(exist_ok=True)
 backup=out/('before_'+output_key+'.blend');assert not backup.exists(),tag;shutil.copy2(source,backup)
 bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
 restore_hand(types.SimpleNamespace(bpy=bpy,COSTUME_PROFILE=tag,HAND_AUTHORING_OUTPUT=out),mesh,arm,reference=base)
 p=np.asarray([mesh.matrix_world@v.co for v in mesh.data.vertices]);domain=nearest(p,from_armature(arm))
 if classify_domain is not None:domain=classify_domain(mesh,arm,p,domain)
 skin_slots={i for i,m in enumerate(mesh.data.materials)if m and m.get('costume_skin')}
 garment_slots={i for i,m in enumerate(mesh.data.materials)if m and not m.get('costume_skin')and not m.get('costume_is_hair')and (m.name.startswith('Costume_')or m.name.startswith('InkMist_'))}
 used={vi for f in mesh.data.polygons if f.material_index in garment_slots for vi in f.vertices}
 skin={vi for f in mesh.data.polygons if f.material_index in skin_slots for vi in f.vertices}
 mesh.data.calc_loop_triangles();names={g.index:g.name for g in mesh.vertex_groups}
 original={v.index:{names[g.group]:g.weight for g in v.groups if names[g.group]in arm.data.bones}for v in mesh.data.vertices}
 rows=[]
 for side in ('L','R'):
  own=np.array(sorted(i for i in used-skin if is_arm(str(domain[i]))and str(domain[i]).endswith('.'+side)),int)
  wrist=np.array(arm.matrix_world@arm.data.bones['手首.'+side].head_local);middle=np.array(arm.matrix_world@arm.data.bones['中指１.'+side].head_local);axis=middle-wrist;axis/=np.linalg.norm(axis)
  forward=(p-wrist)@axis
  donor=[list(f.vertices)for f in mesh.data.loop_triangles if f.material_index in skin_slots and
         all(is_arm(str(domain[i]))and str(domain[i]).endswith('.'+side)for i in f.vertices)and
         forward[list(f.vertices)].max()<=0]
  assert len(donor)>100,('No actual underlying skin arm surface',tag,side,len(donor))
  triangles=np.array(donor,int);tree=BVHTree.FromPolygons(p.tolist(),donor,all_triangles=True)
  distances=[];collapsed=set()
  for vi in own:
   point,normal,face,dist=tree.find_nearest(Vector(p[vi]));assert face is not None
   ids=triangles[face];a,z,c=p[ids];e=z-a;o=c-a;v=np.array(point)-a;gram=np.array([[e@e,e@o],[e@o,o@o]])
   if abs(np.linalg.det(gram))<1e-20:continue
   s,t=np.linalg.solve(gram,[v@e,v@o]);bary=np.maximum([1-s-t,s,t],0);bary/=bary.sum();weights={}
   for i,bw in zip(ids,bary):
    for n,w in original[int(i)].items():
     bone=arm.data.bones[n];label=n
     if n!='手首.'+side and any(parent.name=='手首.'+side for parent in bone.parent_recursive):label='手首.'+side;collapsed.add(n)
     weights[label]=weights.get(label,0)+float(bw*w)
   total=sum(weights.values());assert total>1e-8
   for g in list(mesh.data.vertices[int(vi)].groups):
    if names[g.group]in arm.data.bones:mesh.vertex_groups[g.group].remove([int(vi)])
   for n,w in weights.items():
    if w/total>1e-8:mesh.vertex_groups.get(n).add([int(vi)],w/total,'REPLACE')
   distances.append(float(dist))
  rows.append(dict(side=side,garment_vertices=len(own),actual_skin_donor_triangles=len(donor),surface_distance_mm=(1000*np.quantile(distances,[0,.5,.9,1])).tolist(),cloth_digit_groups_collapsed_to_wrist=sorted(collapsed)))
 bpy.ops.wm.save_as_mainfile(filepath=str(source))
 report=dict(profile=tag,method='same-character actual arm-skin triangle barycentric weights after original-rest hand restoration; cloth digits collapsed to wrist',rows=rows,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),original_author_files_untouched=True,positions_topology_uv_normals_textures_unchanged=True,gameplay_verified=False)
 (out/(output_key+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('ACTUAL_SKIN_SLEEVE_TRANSFER',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
 for tag in sys.argv[sys.argv.index('--')+1:]:run(tag)
