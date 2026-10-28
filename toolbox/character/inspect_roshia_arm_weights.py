import pathlib,sys,json
import numpy as np
import bpy
from mathutils import Vector
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
unit=b.load_target_unit();names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME];mesh=bpy.data.objects[b.MESH_OBJECT_NAME]
mapping=b.source_bone_targets(arm,names)
groups={g.index:g.name for g in mesh.vertex_groups}
report={}
for side,suffix in [('left','.L'),('right','.R')]:
    bones=[b.find_source_bone(arm,b.side_bone_candidates(s,suffix)) for s in ('腕','ひじ','手首','中指１')]
    points=[b.source_coordinate3()@(arm.matrix_world@q.head_local) for q in bones]
    stats={}
    for v in mesh.data.vertices:
        pt=b.source_coordinate3()@(mesh.matrix_world@v.co)
        if (pt-points[1]).length>.075:continue
        for a in v.groups:
            if a.weight<1e-5:continue
            n=groups[a.group]
            if n not in arm.data.bones:continue
            d=stats.setdefault(n,{'target':mapping.get(n),'count':0,'weight':0,'parent':arm.data.bones[n].parent.name if arm.data.bones[n].parent else None})
            d['count']+=1;d['weight']+=a.weight
    report[side]={'bones':[{ 'name':q.name,'matrix':[list(r)for r in q.matrix_local],'head':list(p)}for q,p in zip(bones,points)],'elbow_weights':stats}
out=b.ROOT/'tools/model-work/roshia/contact_tail_candidate/source_arm_weights.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v['elbow_weights']for k,v in report.items()},ensure_ascii=False))
