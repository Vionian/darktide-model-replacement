"""Classify actual hand faces on generated outfits without altering geometry."""
from pathlib import Path
import sys,json,hashlib,re,shutil
import bpy,numpy as np
HERE=Path(__file__).resolve().parent
def classify(tag,apply=False):
    folder=HERE/'skins_20261023'/tag;report_dir=HERE/'hand_repair_20261024'/tag
    report_dir.mkdir(parents=True,exist_ok=True)
    source=folder/(tag+'.blend')
    conversion=json.loads((folder/'conversion.json').read_text(encoding='utf8'))
    meta=json.loads((HERE/'skins_20261023/references'/conversion['base']/'source.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
    names={g.index:g.name for g in mesh.vertex_groups}
    positions=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices]);rows=[]
    backup=report_dir/'before_hand_material_classification.blend'
    if apply:
        assert not backup.exists(),('Existing classification backup; inspect before repeating',tag)
        shutil.copy2(source,backup)
    for side in ('L','R'):
        groups={i for i,n in names.items()if n.endswith('.'+side)and re.match(r'^(手首|親指|人指|中指|薬指|小指)',n)}
        mass=np.array([sum(g.weight for g in v.groups if g.group in groups)for v in mesh.data.vertices])
        wrist=np.array(arm.matrix_world@arm.data.bones['手首.'+side].head_local)
        axis=np.array(arm.matrix_world@arm.data.bones['中指１.'+side].head_local)-wrist;axis/=np.linalg.norm(axis)
        forward=(positions-wrist)@axis
        faces=[p for p in mesh.data.polygons if mass[list(p.vertices)].min()>.5 and forward[list(p.vertices)].mean()>=0]
        assert len(faces)>100,(tag,side,'Missing measured anatomical hand')
        counts=[]
        for index in sorted({p.material_index for p in faces}):
            material=mesh.data.materials[index];own=[p for p in faces if p.material_index==index]
            row=dict(original_material=material.name,faces=len(own),already_skin=bool(material.get('costume_skin')))
            if apply and not row['already_skin']:
                fixed=material.copy();fixed.name=material.name+'_anatomical_hand_'+side
                fixed['costume_skin']=True
                mesh.data.materials.append(fixed);slot=len(mesh.data.materials)-1
                for p in own:p.material_index=slot
                row['new_material']=fixed.name
            counts.append(row)
        rows.append(dict(side=side,hand_faces=len(faces),materials=counts))
    if apply:
        assert any('new_material'in m for r in rows for m in r['materials']),('No classification needed',tag)
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
    report=dict(profile=tag,applied=apply,method='actual wrist-to-middle-knuckle plane and same-side authored hand-majority face weights',
        rows=rows,faces_positions_uv_normals_weights_textures_unchanged=True,original_author_files_untouched=True,
        source_blend_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (report_dir/('hand_material_classification.json'if apply else 'hand_material_inspection.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('ANATOMICAL_HAND_CLASSIFICATION',json.dumps(report,ensure_ascii=False),flush=True)
    return report
if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];apply='--apply'in args
    for tag in args:
        if tag!='--apply':classify(tag,apply)
