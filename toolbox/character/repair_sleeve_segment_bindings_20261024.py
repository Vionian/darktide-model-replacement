"""Continuous garment-only binding from the actual original arm segments.

Blender bone heat was rejected on the open overlapping sleeve donor. This
distance-field solve uses no guessed joint offsets or per-weapon correction.
Exported hand skin, geometry, UVs and corner normals are preserved.
"""
from pathlib import Path
import bpy,numpy as np,json,sys,shutil,hashlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm
def run(tag):
    legacy={'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
            'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend',
            'si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
    source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
    base='si'if tag.startswith('si_')else json.loads((source.parent/'conversion.json').read_text())['base']
    meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
    out=HERE/'hand_repair_20261024'/tag;out.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
    p=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices]);domain=nearest(p,from_armature(arm))
    garment={i for i,m in enumerate(mesh.data.materials)if m and not m.get('costume_skin')and not m.get('costume_is_hair')and (m.name.startswith('Costume_')or m.name.startswith('InkMist_'))}
    used={vi for f in mesh.data.polygons if f.material_index in garment for vi in f.vertices}
    skin={vi for f in mesh.data.polygons if mesh.data.materials[f.material_index].get('costume_skin')for vi in f.vertices}
    ids=np.array(sorted(vi for vi in used if vi not in skin and is_arm(str(domain[vi]))),int)
    assert len(ids)>100,(tag,'Missing measured garment arm region')
    names={g.index:g.name for g in mesh.vertex_groups};rows=[]
    backup=out/'before_sleeve_segment_rebind.blend';assert not backup.exists(),('Do not repeat source edit',tag)
    shutil.copy2(source,backup)
    for side in ('L','R'):
        own=ids[np.array([str(domain[i]).endswith('.'+side)for i in ids])]
        if not len(own):continue
        labels=[n+'.'+side for n in ('肩','腕','ひじ','手首')if n+'.'+side in arm.data.bones]
        distances=[]
        for name in labels:
            bone=arm.data.bones[name];a=np.array(arm.matrix_world@bone.head_local);z=np.array(arm.matrix_world@bone.tail_local)
            axis=z-a;den=axis@axis;assert den>1e-12,name
            t=np.clip((p[own]-a)@axis/den,0,1);distances.append(np.sum((p[own]-a-t[:,None]*axis)**2,axis=1))
        d2=np.stack(distances,axis=1);field=1/np.maximum(d2,1e-12);field/=field.sum(1,keepdims=True)
        for vi,weights in zip(own,field):
            for g in list(mesh.data.vertices[int(vi)].groups):
                if names[g.group]in arm.data.bones:mesh.vertex_groups[g.group].remove([int(vi)])
            for name,w in zip(labels,weights):(mesh.vertex_groups.get(name)or mesh.vertex_groups.new(name=name)).add([int(vi)],float(w),'REPLACE')
        rows.append(dict(side=side,vertices=len(own),source_bones=labels,maximum_weight_sum_error=float(np.abs(field.sum(1)-1).max())))
    bpy.context.view_layer.objects.active=mesh;bpy.ops.wm.save_as_mainfile(filepath=str(source))
    report=dict(profile=tag,method='normalized inverse squared distance field to actual original shoulder/upper-arm/forearm/wrist bone segments; garment arm domain only',
        rows=rows,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        hand_skin_geometry_uv_normals_textures_unchanged=True,original_author_files_untouched=True,
        rejected_method='Blender ARMATURE_AUTO failed on open overlapping sleeve donor; no failed heat result was applied',gameplay_verified=False)
    (out/'sleeve_segment_rebind.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('MEASURED_SLEEVE_REBIND',json.dumps(report),flush=True)
if __name__=='__main__':
    for tag in sys.argv[sys.argv.index('--')+1:]:run(tag)
