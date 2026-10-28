import bpy,pathlib,sys,json
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
from endfield_wave2 import PROFILES
from character_material_bridge_user import core
out=pathlib.Path(__file__).parent/'endfield_batch';report={}
for key,p in PROFILES.items():
    apply(b,key);bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
    mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME];b.prepare_source(mesh,arm)
    rows=[]
    for m in mesh.data.materials:
        if m.name not in ('面','目','目1','目2','发','肌'):continue
        proxy=bpy.data.objects.get(mesh.name+'__'+m.name)
        if not proxy:continue
        for pm in proxy.data.materials:
            snapshot=core.read_material_column(pm)
            if not snapshot:continue
            part,col,width,pixels=snapshot
            vals={n:core.read_param(pixels,width,col,part,n)for n in core.param_names(part)
                  if any(s in n.lower()for s in ('color','bright','satur','expos','diffuse','shadow','rough','smooth','specul','metal'))}
            rows.append({'material':m.name,'part':str(part),'parameters':vals})
    report[key]=rows
    (out/'wave2_shading_parameters.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('WAVE2_SHADING_INSPECTION_DONE')
