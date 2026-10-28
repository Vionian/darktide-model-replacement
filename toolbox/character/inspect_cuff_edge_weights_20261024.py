from pathlib import Path
import bpy,json,sys,numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from repair_native_hands_20261024 import REPAIR,LEGACY
import build_roshia_native as b
from build_new_skin import configure
from endfield_profiles import apply
rows=[]
for tag in sys.argv[sys.argv.index('--')+1:]:
    if tag in LEGACY:apply(b,tag)
    else:configure(b,tag)
    folder=REPAIR/tag/'edge_weight_inspection';folder.mkdir(exist_ok=True)
    b.HAND_AUTHORING_OUTPUT=folder
    bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
    mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
    b.prepare_source(mesh,arm)
    names={g.index:g.name for g in mesh.vertex_groups}
    audit=json.loads((REPAIR/tag/'preview_rest/exported_surface_edge_audit.json').read_text())
    result=[]
    for m in audit['materials']:
        if m['stretch_quantiles'][-1]<3:continue
        vertices=[]
        for index in m['worst'][0]['vertices']:
            v=mesh.data.vertices[index]
            vertices.append(dict(index=index,point=list(b.source_coordinate3()@(mesh.matrix_world@v.co)),
                weights=[(names[g.group],g.weight)for g in v.groups if g.weight>1e-5]))
        result.append(dict(material=m['material'],ratio=m['stretch_quantiles'][-1],vertices=vertices))
    row=dict(profile=tag,rows=result);rows.append(row)
    print('CUFF_EDGE_WEIGHTS',json.dumps(row,ensure_ascii=False),flush=True)
(REPAIR/'cuff_edge_weight_inspection.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
