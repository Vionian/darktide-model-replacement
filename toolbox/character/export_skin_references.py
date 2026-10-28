"""Read original shaded sources; preserve sparse skin fields and head identities."""
import json,sys
from pathlib import Path
import bpy
import numpy as np
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
from skins_sources import OUT,SOURCES
import build_roshia_native as b
from endfield_profiles import PROFILES
weights=json.loads((HERE/'endfield_batch/weights.json').read_text(encoding='utf-8'))
for key in sorted(set(row[1] for row in SOURCES.values())):
    folder=OUT/'references'/key;folder.mkdir(parents=True,exist_ok=True)
    name='洛茜' if key=='roshia' else PROFILES[key]['name']
    source=Path('<SOURCE_ROOT>/Rossia')/(name+'.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    objects=weights.get(name,{})
    mesh=bpy.data.objects[objects.get('mesh',name+'_mesh')]
    arm=bpy.data.objects[objects.get('armature',name+'_arm')]
    p=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices],np.float32)
    names=np.array([g.name for g in mesh.vertex_groups])
    bone_groups={g.index for g in mesh.vertex_groups if g.name in arm.data.bones}
    auxiliary_groups=[g.name for g in mesh.vertex_groups if g.index not in bone_groups]
    ii=np.zeros((len(p),4),np.uint16);ww=np.zeros((len(p),4),np.float32)
    for v in mesh.data.vertices:
        groups=sorted((g for g in v.groups if g.group in bone_groups),key=lambda g:-g.weight)[:4]
        for i,g in enumerate(groups):ii[v.index,i]=g.group;ww[v.index,i]=g.weight
    ww/=np.maximum(ww.sum(1,keepdims=True),1e-12)
    mesh.data.calc_loop_triangles()
    tris=np.array([t.vertices[:] for t in mesh.data.loop_triangles],np.int32)
    mats=np.array([t.material_index for t in mesh.data.loop_triangles],np.int16)
    material_names=[m.name if m else '' for m in mesh.data.materials]
    skin=[i for i,n in enumerate(material_names) if n in ('肌','身体','Skin','Body') or 'Skin' in n]
    skin_ids=np.unique(tris[np.isin(mats,skin)])
    hand_mass=np.where(np.array(['手首' in n or '指' in n for n in names])[ii],ww,0).sum(1)
    skin_ids=np.unique(np.r_[skin_ids,np.flatnonzero(hand_mass>.01)])
    np.savez_compressed(folder/'source.npz',positions=p,indices=ii,weights=ww,
                        group_names=names,triangles=tris,materials=mats,skin_vertices=skin_ids)
    bones=[dict(name=bone.name,parent=bone.parent.name if bone.parent else None,
                head=list(arm.matrix_world@bone.head_local),tail=list(arm.matrix_world@bone.tail_local))
           for bone in arm.data.bones]
    data=dict(key=key,name=name,source=str(source),mesh=mesh.name,armature=arm.name,
              materials=material_names,bones=bones,source_mesh_matrix=list(map(list,mesh.matrix_world)),
              source_armature_matrix=list(map(list,arm.matrix_world)),
              bounds=[p.min(0).tolist(),p.max(0).tolist()],skin_materials=skin,
              scale=b.SCALE if key=='roshia' else weights[name]['scale'],
              weight_contract='bone-groups-only-top4-normalized-v2',
              excluded_auxiliary_groups=auxiliary_groups)
    (folder/'source.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SKIN_SOURCE_REFERENCE',key,len(p),len(tris),len(skin_ids),flush=True)
