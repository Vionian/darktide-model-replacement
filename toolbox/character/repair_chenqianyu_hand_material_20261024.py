"""Mark the actual sports-outfit hand faces in its generated authoring blend.

The shared atlas is clothing plus skin. Material-wide nearest-cloth voting is
not sufficient. Preserve every position, face, UV and source texture.
"""
from pathlib import Path
import sys,json,hashlib,re
import bpy,numpy as np
HERE=Path(__file__).resolve().parent;folder=HERE/'skins_20261023/chenqianyu_sport'
source=folder/'chenqianyu_sport.blend'
ref=json.loads((HERE/'skins_20261023/references/chenqianyu/source.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[ref['mesh']];arm=bpy.data.objects[ref['armature']]
names={g.index:g.name for g in mesh.vertex_groups}
positions=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices]);rows=[]
for side in ('L','R'):
    side_groups={i for i,n in names.items()if n.endswith('.'+side)and re.match(r'^(手首|親指|人指|中指|薬指|小指)',n)}
    mass=np.array([sum(g.weight for g in v.groups if g.group in side_groups)for v in mesh.data.vertices])
    wrist=np.array(arm.matrix_world@arm.data.bones['手首.'+side].head_local)
    knuckle=np.array(arm.matrix_world@arm.data.bones['中指１.'+side].head_local)
    axis=knuckle-wrist;axis/=np.linalg.norm(axis)
    forward=(positions-wrist)@axis
    faces=[p for p in mesh.data.polygons if mass[list(p.vertices)].min()>.5 and forward[list(p.vertices)].mean()>=0]
    assert len(faces)>100,('Missing original-position costume hand faces',side,len(faces))
    originals=sorted({p.material_index for p in faces});counts=[]
    for index in originals:
        material=mesh.data.materials[index]
        if material.get('costume_skin'):continue
        fixed=material.copy();fixed.name=material.name+'_anatomical_hand_'+side
        fixed['costume_skin']=True;fixed['costume_two_sided']=False
        mesh.data.materials.append(fixed);slot=len(mesh.data.materials)-1
        own=[p for p in faces if p.material_index==index]
        for p in own:p.material_index=slot
        counts.append(dict(original_material=material.name,new_material=fixed.name,faces=len(own)))
    rows.append(dict(side=side,hand_faces=len(faces),material_splits=counts))
assert any(r['material_splits']for r in rows),'Already corrected; do not repeat a completed source edit'
bpy.ops.wm.save_as_mainfile(filepath=str(source))
report=dict(profile='chenqianyu_sport',method='actual source wrist-to-middle-knuckle plane and same-side source hand-majority face weights',
    faces_and_vertex_positions_uvs_normals_unchanged=True,original_source_files_untouched=True,
    rows=rows,source_blend_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
(folder/'hand_material_classification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('CHENQIANU_HAND_MATERIAL_CLASSIFIED',json.dumps(report,ensure_ascii=False),flush=True)
