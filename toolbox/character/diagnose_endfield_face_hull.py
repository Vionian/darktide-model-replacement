"""Inspect evaluated CMB shell orientation without exporting it."""
import bpy,pathlib,sys,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
key=sys.argv[sys.argv.index('--')+1]
apply(b,key);b.INCLUDE_FACE_OUTLINE=False
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh=bpy.data.objects[b.MESH_OBJECT_NAME];b.prepare_source(mesh,bpy.data.objects[b.ARMATURE_OBJECT_NAME])
rows=[]
for name in ('面','目白','口内'):
 obj=bpy.data.objects.get(mesh.name+'__'+name)
 if not obj:continue
 if not obj.users_collection:bpy.context.scene.collection.objects.link(obj)
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ev.to_mesh()
 n=len(obj.data.vertices);p=len(obj.data.polygons)
 flag=data.attributes.get('ruri_outline')
 original=np.array([v.co[:]for v in obj.data.vertices]);points=np.array([v.co[:]for v in data.vertices])
 normals=np.array([v.normal[:]for v in obj.data.vertices]);delta=points[:n]-original
 rows.append({'name':name,'scale':list(obj.scale),'world':np.asarray(obj.matrix_world).tolist(),
  'n':n,'p':p,'flags_first':np.unique([a.value for a in flag.data[:p]]).tolist(),
  'flags_last':np.unique([a.value for a in flag.data[p:]]).tolist(),
  'first_normal_dot_original':float(np.mean([a.normal.dot(c.normal)for a,c in zip(data.polygons,obj.data.polygons)])),
  'second_normal_dot_original':float(np.mean([a.normal.dot(c.normal)for a,c in zip(list(data.polygons)[p:],obj.data.polygons)])),
  'displacement_normal_dot':np.quantile((delta*normals).sum(1),[0,.1,.5,.9,1]).tolist(),
  'extent':np.ptp(original,axis=0).tolist()})
 ev.to_mesh_clear()
print('HULL_DIAG',json.dumps(rows,ensure_ascii=False),flush=True)
