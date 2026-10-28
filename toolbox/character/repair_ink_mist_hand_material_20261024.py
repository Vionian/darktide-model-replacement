from pathlib import Path
import bpy,json,hashlib,shutil
HERE=Path(__file__).resolve().parent
source=HERE/'si_ink_mist/si_ink_mist.blend'
report_dir=HERE/'hand_repair_20261024/si_ink_mist'
inspection=json.loads((report_dir/'hand_material_inspection.json').read_text(encoding='utf8'))
assert all(len(r['materials'])==1 and r['materials'][0]['props']['ink_mist_component']==5 for r in inspection['rows'])
backup=report_dir/'before_skin_material_classification.blend'
assert not backup.exists(),'Classification already attempted; inspect rather than repeat'
shutil.copy2(source,backup)
meta=json.loads((HERE/'skins_20261023/references/si/source.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']]
indices={r['materials'][0]['slot']for r in inspection['rows']}
for i in indices:
    material=mesh.data.materials[i]
    assert material.get('ink_mist_component')==5 and material.get('ink_mist_diffuse')==16
    assert not material.get('costume_skin'), 'Already classified'
    material['costume_skin']=True
bpy.ops.wm.save_as_mainfile(filepath=str(source))
report=dict(profile='si_ink_mist',method='Component5 bare-body diffuse16/normal17 confirmed in source INI and anatomical hand inspection',
    classified_slots=sorted(indices),mesh_uv_weights_textures_unchanged=True,backup=str(backup),
    generated_blend_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),original_author_buffers_unchanged=True)
(report_dir/'hand_material_classification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('INK_MIST_HAND_MATERIAL_CLASSIFIED',json.dumps(report),flush=True)
