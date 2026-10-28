"""Validate the source hook and matching serialized motion of the new lining."""
import json
import pathlib
import sys
import bpy
import numpy as np

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import build_roshia_native as b
from endfield_profiles import apply
from native_garment_sides import from_parsed
from perlica_torso_lining import apply_to_groups

OUT = HERE/'perlica_interior_fix_20261022'
apply(b, 'perlica')
b.BINDING_MODE = 'proportion-fk'
b.OUTPUT = OUT/'source_hook_validation'
b.OUTPUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh = bpy.data.objects[b.MESH_OBJECT_NAME]
arm = bpy.data.objects[b.ARMATURE_OBJECT_NAME]
b.prepare_source(mesh, arm)
unit = b.load_target_unit()
names = b.named_node_map(unit, b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
palette = {n:p for p,n in enumerate(unit.skins[0].node_indices)}
rig = b.dynamic_rig_mapping(mesh, arm, unit, names)
from roshia_proportion_rig import adapt
rig = adapt(b, unit, names, rig, False)
mapping = b.source_bone_targets(arm, names, rig['source_to_target'])
mapping.update(rig['source_to_target'])
transforms = b.target_bind_transforms(arm, names, unit)
transforms.update(rig['bind_transforms'])
transforms.update(rig['geometry_bind_transforms'])
targets = {palette[names[n]]:n for n in transforms}
# Avoid decoding/baking unrelated textures; exercise the real geometry wrapper.
b.image_pixels_for = lambda material: None
groups = b.collect_triangles(mesh, arm, mapping, palette, names, targets, transforms, False,
                             source_bind_transforms=rig['hand_rig']['source_transforms'])
g = groups[10]
for field in ('vertices','uv','normals'):
    assert len(g[field]) == len(g['vertices'])
assert g['vertices'].max() < len(g['retargeted_positions'])
assert g['triangles'].max() < len(g['vertices'])
assert np.isfinite(g['retargeted_positions']).all()
assert np.max(abs(g['joint_weights'].sum(1)-1)) < .001
assert len(g['retargeted_positions']) > len(mesh.data.vertices)
assert apply_to_groups(mesh, groups, True) is groups

old = b.unit_dt.UnitResourceDT(b.Cursor(str(b.ROOT/'Custom/perlica/perlica.unit')))
new = b.unit_dt.UnitResourceDT(b.Cursor(str(OUT/'Custom/perlica/perlica.unit')))
added = []
for before, after in zip(old.mesh_geometries, new.mesh_geometries):
    offset = before.streams[1].vertex_stream.vertices
    geo = from_parsed(b, after, 10)
    if geo['vertices'] > offset:
        p = b.geometry_positions(geo)[offset:].astype(np.float64)
        w = np.frombuffer(geo['streams'][4][0],'<f2').reshape(-1,4)[offset:].astype(np.float64)
        j = np.frombuffer(geo['streams'][5][0],np.uint8).reshape(-1,4)[offset:]
        added.append((p,w,j))
binds = np.asarray(new.skins[0].inv_bind_matrices,dtype=np.float64)
motion = {}
for frame in (0,5,10,15,19):
    pose = json.loads((HERE/'endfield_surface_fix_20261022'/f'body_run_frame_{frame:02}_pose.json').read_text())
    assert pose['synthetic']
    worlds = np.asarray(pose['worlds'],dtype=np.float64)
    skin = worlds[new.skins[0].node_indices] @ binds
    ratios = []
    for p,w,j in added:
        ph = np.c_[p,np.ones(len(p))]
        q = (np.einsum('nkij,nj->nki',skin[j],ph)[:,:,:3]*w[:,:,None]).sum(1)
        assert np.isfinite(q).all()
        t = p.reshape(-1,3,3); u = q.reshape(-1,3,3)
        a = np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)
        z = np.linalg.norm(np.cross(u[:,1]-u[:,0],u[:,2]-u[:,0]),axis=1)
        ratios.extend(z[a>1e-10]/a[a>1e-10])
    ratios = np.asarray(ratios)
    assert np.isfinite(ratios).all()
    assert ratios.min() > .01
    motion[str(frame)] = dict(min_area_ratio=float(ratios.min()), max_area_ratio=float(ratios.max()),
                              p99_area_ratio=float(np.quantile(ratios,.99)))
report = dict(source_collect_hook_passed=True, arms_hook_bypassed=True,
              source_group10_triangles=len(g['triangles']),
              source_lining_extra_vertices=len(g['retargeted_positions'])-len(mesh.data.vertices),
              matched_synthetic_frames=motion, gameplay_verified=False)
(OUT/'source_and_motion_validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('PERLICA_SOURCE_MOTION_VALIDATION',json.dumps(report))
