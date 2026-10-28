import bpy,pathlib,sys,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
keys=sys.argv[sys.argv.index('--')+1:]
for key in keys:
 apply(b,key);bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
 mesh=bpy.data.objects[b.MESH_OBJECT_NAME];b.prepare_source(mesh,bpy.data.objects[b.ARMATURE_OBJECT_NAME])
 result={}
 for name in ('面','目白','口内'):
  obj=bpy.data.objects.get(mesh.name+'__'+name)
  if not obj:continue
  if not obj.users_collection:bpy.context.scene.collection.objects.link(obj)
  ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());em=ev.to_mesh();em.calc_loop_triangles()
  row={'original_vertices':len(obj.data.vertices),'vertices':len(em.vertices),'polygons':len(em.polygons),'groups':len(obj.vertex_groups),'attrs':[(a.name,a.domain,a.data_type)for a in em.attributes]}
  a=em.attributes.get('ruri_outline')
  if a:
   vals=np.array([getattr(d,'value',getattr(d,'vector',getattr(d,'color',(0,))))for d in a.data])
   row['flag']={'min':vals.min().item(),'max':vals.max().item(),'unique':np.unique(vals).tolist()[:12]}
  n=len(obj.data.vertices)
  points=np.asarray([v.co[:]for v in em.vertices]);original=np.asarray([v.co[:]for v in obj.data.vertices])
  if len(points)==n*2:
   row['first_delta_max']=float(np.linalg.norm(points[:n]-original,axis=1).max())
   row['second_delta_max']=float(np.linalg.norm(points[n:]-original,axis=1).max())
   row['second_delta_median']=float(np.median(np.linalg.norm(points[n:]-original,axis=1)))
   row['original_group_count']=len(obj.data.vertices[0].groups)
   row['second_group_count']=len(em.vertices[n].groups)
  row['group_name_head']=[g.name for g in obj.vertex_groups][:12]
  result[name]=row
 out=pathlib.Path(__file__).parent/'endfield_batch/face_refinement'/key
 (out/'outline_inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(result,ensure_ascii=False),flush=True)
