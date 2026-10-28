from pathlib import Path
import bpy,json,numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/langzhifei';OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(ROOT/'武器模型/狼之绯/wpn_sword_0022_refined.fbx'))
report=[]
for obj in bpy.context.scene.objects:
    item={'name':obj.name,'type':obj.type,'matrix':list(map(list,obj.matrix_world))}
    if obj.type=='MESH':
        v=np.array([obj.matrix_world@p.co for p in obj.data.vertices])
        item.update(vertices=len(v),polygons=len(obj.data.polygons),bounds=[v.min(0).tolist(),v.max(0).tolist()],materials=[m.name for m in obj.data.materials],uv_layers=[u.name for u in obj.data.uv_layers])
    if obj.type=='ARMATURE': item['bones']=[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local)} for b in obj.data.bones]
    report.append(item)
(OUT/'source_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'source.blend'))
print('SOURCE_INSPECTED',json.dumps(report,ensure_ascii=False))
