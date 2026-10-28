"""Inspect the supplied EFMI buffers against the existing Si authoring source."""
import bpy
import json
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tools/model-work/si_ink_mist'
OUT.mkdir(exist_ok=True)
source = Path('<SOURCE_ROOT>/Rossia/祀.blend')
bpy.ops.wm.open_mainfile(filepath=str(source))
arm = bpy.data.objects['祀_arm']
mesh = bpy.data.objects['祀_mesh']
report = {'source': str(source), 'mesh_matrix': [list(r) for r in mesh.matrix_world],
          'bounds': [[min((mesh.matrix_world @ v.co)[i] for v in mesh.data.vertices),
                      max((mesh.matrix_world @ v.co)[i] for v in mesh.data.vertices)] for i in range(3)],
          'vertices': len(mesh.data.vertices), 'materials': [m.name for m in mesh.data.materials],
          'bones': []}
for i, bone in enumerate(arm.data.bones):
    mmd = getattr(bone, 'mmd_bone', None)
    pose = arm.pose.bones[bone.name]
    mmd = getattr(pose, 'mmd_bone', mmd)
    report['bones'].append(dict(index=i, name=bone.name, head=list(arm.matrix_world @ bone.head_local),
                               props={k: str(bone[k]) for k in bone.keys()},
                               mmd={k: getattr(mmd, k, None) for k in ('name_j', 'name_e', 'bone_id', 'transform_order')} if mmd else {}))
(OUT / 'source_armature.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('SI_SOURCE', report['vertices'], report['bounds'], report['materials'])
print('SI_BONE_SAMPLE', report['bones'][65:75])
positions = np.asarray([mesh.matrix_world @ v.co for v in mesh.data.vertices], dtype=np.float32)
weights = np.zeros((len(positions), len(mesh.vertex_groups)), np.float32)
for v in mesh.data.vertices:
    for g in v.groups:
        weights[v.index, g.group] = g.weight
np.savez_compressed(OUT / 'source_reference.npz', positions=positions, weights=weights,
                    group_names=np.asarray([g.name for g in mesh.vertex_groups]),
                    skin_vertices=np.unique([v for p in mesh.data.polygons
                        if mesh.data.materials[p.material_index].name == '肌' for v in p.vertices]))
