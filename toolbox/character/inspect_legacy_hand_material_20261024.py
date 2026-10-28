from pathlib import Path
import bpy,json,numpy as np,re
HERE=Path(__file__).resolve().parent
meta=json.loads((HERE/'skins_20261023/references/si/source.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(HERE/'si_ink_mist/si_ink_mist.blend'))
mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
pos=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])
names={g.index:g.name for g in mesh.vertex_groups}
rows=[]
for side in ('L','R'):
    groups={i for i,n in names.items()if n.endswith('.'+side)and re.match(r'^(手首|親指|人指|中指|薬指|小指)',n)}
    mass=np.array([sum(g.weight for g in v.groups if g.group in groups)for v in mesh.data.vertices])
    wrist=np.array(arm.matrix_world@arm.data.bones['手首.'+side].head_local)
    axis=np.array(arm.matrix_world@arm.data.bones['中指１.'+side].head_local)-wrist;axis/=np.linalg.norm(axis)
    fwd=(pos-wrist)@axis
    faces=[p for p in mesh.data.polygons if mass[list(p.vertices)].min()>.5 and fwd[list(p.vertices)].mean()>=0]
    material=[]
    for i in sorted({p.material_index for p in faces}):
        m=mesh.data.materials[i]
        material.append(dict(slot=i,name=m.name,faces=sum(p.material_index==i for p in faces),props=dict(m.items())))
    rows.append(dict(side=side,faces=len(faces),materials=material))
report=dict(profile='si_ink_mist',source=str(HERE/'si_ink_mist/si_ink_mist.blend'),rows=rows)
(HERE/'hand_repair_20261024/si_ink_mist/hand_material_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print('HAND_MATERIAL_INSPECTION',json.dumps(report,ensure_ascii=False,default=str))
