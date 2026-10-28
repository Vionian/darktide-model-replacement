"""Report source group, material and collision geometry for Roshia."""
import importlib.util,json,pathlib,sys
import bpy
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('roshia_builder',ROOT/'tools/model-work/build_roshia_native.py')
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
group_names={g.index:g.name for g in mesh.vertex_groups}
records=[]
for v in mesh.data.vertices:
    groups={group_names[a.group]:a.weight for a in v.groups}
    p=mesh.matrix_world@v.co
    names=list(groups)
    if any(any(t in n.lower() for t in ('tail_base','cloak','cape','shawl','skirt','dress','arm','hand')) for n in names):
        records.append({'p':list(p),'groups':groups,'material':None})
by_material={}
for poly in mesh.data.polygons:
    mat=mesh.data.materials[poly.material_index]
    entry=by_material.setdefault(poly.material_index,{'name':mat.name,'faces':0,'min':[1e9]*3,'max':[-1e9]*3,'groups':{}})
    entry['faces']+=1
    for vi in poly.vertices:
        p=mesh.matrix_world@mesh.data.vertices[vi].co
        entry['min']=[min(a,float(x))for a,x in zip(entry['min'],p)]
        entry['max']=[max(a,float(x))for a,x in zip(entry['max'],p)]
        for a in mesh.data.vertices[vi].groups:
            name=group_names[a.group]
            if a.weight>.2:entry['groups'][name]=entry['groups'].get(name,0)+1
bone_info={bone.name:{'parent':bone.parent.name if bone.parent else None,
 'head':list(arm.matrix_world@bone.head_local),'tail':list(arm.matrix_world@bone.tail_local)}
 for bone in arm.data.bones if any(t in bone.name.lower() for t in ('tail_base','cloth','skirt','dress','腰','上半身','腕','ひじ','手首'))}
out=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve() if '--' in sys.argv else ROOT/'tools/model-work/roshia'
out.mkdir(parents=True,exist_ok=True)
report={'materials':by_material,'bones':bone_info,'weighted_vertices':records[:15000]}
(out/'collision_diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('COLLISION_DIAGNOSIS',len(records),len(by_material),len(bone_info),out/'collision_diagnosis.json')
for i,m in by_material.items():print('MAT',i,m['name'],m['faces'],m['min'],m['max'],sorted(m['groups'],key=m['groups'].get,reverse=True)[:12])
for name,bone in bone_info.items():
 if 'tail_base' in name:print('TAIL',name,bone)
