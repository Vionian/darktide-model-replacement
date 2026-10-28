import importlib.util, sys, pathlib, json
import bpy
import numpy as np
here=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("builder",here/"build_roshia_native.py")
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
unit=b.load_target_unit();lookup=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
rig=b.dynamic_rig_mapping(mesh,arm,unit,lookup)
mapping=b.source_bone_targets(arm,lookup,rig['source_to_target']);mapping.update(rig['source_to_target'])
groups={v.index:v.name for v in mesh.vertex_groups}
stats={}
for v in mesh.data.vertices:
 p=b.source_coordinate3() @ (mesh.matrix_world @ v.co)
 for a in v.groups:
  if a.weight<1e-5:continue
  n=groups[a.group];d=stats.setdefault(n,{'target':mapping.get(n),'weight':0.,'vertices':0,'minimum':list(p),'maximum':list(p)})
  d['weight']+=a.weight;d['vertices']+=1
  d['minimum']=np.minimum(d['minimum'],p).tolist();d['maximum']=np.maximum(d['maximum'],p).tolist()
for n,d in stats.items():
 bone=arm.data.bones.get(n)
 d['parent']=bone.parent.name if bone and bone.parent else None
 d['head']=list(b.source_coordinate3()@(arm.matrix_world@bone.head_local)) if bone else None
(here/'roshia/source_weight_audit.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
print('SOURCE_WEIGHT_AUDIT',len(stats))
