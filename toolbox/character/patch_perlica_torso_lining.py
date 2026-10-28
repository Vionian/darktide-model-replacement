"""Install the source-specific interior without rebuilding a rig or texture."""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import shutil
import struct
import sys

import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
from native_garment_sides import from_parsed, triangle_keys, append_reverse
from perlica_torso_lining import make_lining, boundary_loop

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=pathlib.Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
source_folder = b.ROOT/'Custom/perlica'
meta = json.loads((source_folder/'compile_manifest.json').read_text(encoding='utf-8'))
assert not meta.get('interior_lining_revision'), 'Already patched; use the recorded backup as input'
manifest = json.loads((source_folder/'build.json').read_text(encoding='utf-8'))
file = source_folder/'perlica.unit'
original = b.unit_dt.UnitResourceDT(b.Cursor(str(file)))
info = b.read_unit_offsets(file)
resources = {b.hash64(a['resource']['name']): a['resource']['name'] for a in manifest['artifacts']
             if a['resource']['type']=='material' and a['role']=='primary'}
slots = {s.ID:r.ID for s,r in original.materials}
geometries = [from_parsed(b, g, int(re.search(r'_material_(\d+)$', resources[slots[g.materials[0].ID]]).group(1)))
              for g in original.mesh_geometries]

apply(b, 'perlica'); b.BINDING_MODE = 'proportion-fk'
b.OUTPUT = out/'source_inspection'; b.OUTPUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh = bpy.data.objects[b.MESH_OBJECT_NAME]; arm = bpy.data.objects[b.ARMATURE_OBJECT_NAME]
b.prepare_source(mesh, arm)
template = b.load_target_unit()
names = b.named_node_map(template, b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
palette = {n:p for p,n in enumerate(template.skins[0].node_indices)}
rig = b.dynamic_rig_mapping(mesh, arm, template, names)
from roshia_proportion_rig import adapt
rig = adapt(b, template, names, rig, False)
mapping = b.source_bone_targets(arm, names, rig['source_to_target'])
mapping.update(rig['source_to_target'])
transforms = b.target_bind_transforms(arm, names, template)
transforms.update(rig['bind_transforms']); transforms.update(rig['geometry_bind_transforms'])
targets = {palette[names[n]]: n for n in transforms}
joints, weights, _, positions, _ = b.vertex_influences(mesh, mapping, palette, names, targets, transforms,
                                                    source_bind_transforms=rig['hand_rig']['source_transforms'])
assert template.skins[0].node_indices == original.skins[0].node_indices
lower, source_points = boundary_loop(mesh, 10, (.98, 1.04))
upper, _ = boundary_loop(mesh, 9, (1.23, 1.34))
native_p = positions.copy(); native_j = joints.copy(); native_w = weights.copy()
seam_error = []
for material, ids in ((10, lower), (9, upper)):
    gs = [g for g in geometries if g['material_index'] == material]
    p = np.concatenate([b.geometry_positions(g) for g in gs]).astype(np.float32)
    j = np.concatenate([np.frombuffer(g['streams'][5][0], np.uint8).reshape(-1,4) for g in gs])
    w = np.concatenate([np.frombuffer(g['streams'][4][0], '<f2').reshape(-1,4) for g in gs]).astype(np.float32)
    tree = KDTree(len(p))
    for i, v in enumerate(p): tree.insert(v, i)
    tree.balance()
    for source_id in ids:
        _, index, distance = tree.find(positions[source_id])
        assert distance < .0011, (material, int(source_id), distance)
        seam_error.append(distance)
        native_p[source_id] = p[index]; native_j[source_id] = j[index]; native_w[source_id] = w[index]
lining = make_lining(mesh, native_p, native_j, native_w)
group = dict(triangles=np.arange(len(lining['faces'])), vertices=lining['faces'],
             uv=lining['uv'][lining['faces']], normals=lining['normals'],
             retargeted_positions=lining['positions'], joint_indices=lining['joints'],
             joint_weights=lining['weights'], material_name='丝袜')
lining_geo = b.make_geometry(group, np.arange(len(lining['faces'])), 10, 0)

def spatial_key(tri):
    a,c,d = (np.r_[row,1].astype('<f2').tobytes() for row in tri)
    return min(a+c+d, c+d+a, d+a+c)

# Select only source hip panels, rather than making all legs/hands two-sided.
mesh.data.calc_loop_triangles()
hip_keys = {spatial_key(positions[list(t.vertices)]) for t in mesh.data.loop_triangles
            if t.material_index == 10 and source_points[list(t.vertices),2].min() >= .84}
changed = set(); hip_added = 0
for i, g in enumerate(geometries):
    if g['material_index'] != 10: continue
    direct, reverse = triangle_keys(g); known = set(direct)
    p = b.geometry_positions(g).reshape(-1,3,3)
    selected = np.array([t for t, tri in enumerate(p)
                         if spatial_key(tri) in hip_keys and reverse[t] not in known], dtype=int)
    if len(selected):
        geometries[i] = append_reverse(b, g, selected)
        changed.add(i); hip_added += len(selected)
assert hip_added > 0, 'Source/native hip correspondence did not match'
host = next(i for i,g in enumerate(geometries) if g['material_index'] == 10
            and g['vertices']+lining_geo['vertices'] <= 65535)
g = geometries[host]
assert [s[1] for s in g['streams']] == [s[1] for s in lining_geo['streams']]
g['streams'] = [(a[0]+z[0], a[1]) for a,z in zip(g['streams'],lining_geo['streams'])]
g['vertices'] += lining_geo['vertices']; g['indices'] = g['vertices']
g['triangle_count'] = g['vertices']//3
g['index_data'] = np.arange(g['vertices'], dtype='<u2').tobytes()
p = b.geometry_positions(g).astype(np.float32)
g['bounds'] = np.r_[p.min(0),p.max(0)].astype(np.float32)
changed.add(host)
c = b.Cursor(str(file)); c.seek(info['geometry_start']); blobs = []
for i,g in enumerate(geometries):
    start = c.tell(); b.mesh_geometry.MeshGeometryDT(c); end = c.tell()
    blobs.append(b.serialize_geometry(g) if i in changed else info['raw'][start:end])
output = bytearray(info['raw'][:info['geometry_start']]+b''.join(blobs)+info['raw'][info['geometry_end']:])
struct.pack_into('<I', output, 29, len(output)-b.unit_dt.HEADER_SIZE)
destination = out/'Custom/perlica'
shutil.copytree(source_folder,destination,dirs_exist_ok=True)
target = destination/'perlica.unit'; target.write_bytes(output)
readback = b.read_unit_offsets(target)
assert readback['raw'][readback['geometry_end']:] == info['raw'][info['geometry_end']:]
reread = b.unit_dt.UnitResourceDT(b.Cursor(str(target)))
for a,z in zip(original.mesh_geometries,reread.mesh_geometries):
    for s,t in zip(a.streams,z.streams): assert t.vertex_data.startswith(s.vertex_data)
for g in geometries:
    p = b.geometry_positions(g); assert np.isfinite(p).all()
    w = np.frombuffer(g['streams'][4][0],'<f2').reshape(-1,4).astype(np.float32)
    j = np.frombuffer(g['streams'][5][0],np.uint8).reshape(-1,4)
    assert np.isfinite(w).all() and np.max(abs(w.sum(1)-1)) < .001
    assert j.max() < len(original.skins[0].node_indices)
# The outward lining, considered independently, is a closed manifold.
front = lining['faces'][:lining['outward_triangles']]
edges = collections.Counter(tuple(sorted((int(a),int(z)))) for tri in front
                            for a,z in zip(tri,np.roll(tri,-1)))
assert all(n==2 for n in edges.values())
for entry in manifest['artifacts']:
    if entry['path'] == 'perlica.unit': entry['size'] = len(output)
    else:
        assert (destination/entry['path']).stat().st_size == entry['size']
        assert (destination/entry['path']).read_bytes() == (source_folder/entry['path']).read_bytes()
(destination/'build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
meta['geometry'].update(triangles=sum(g['triangle_count'] for g in geometries),
                        vertices=sum(g['vertices'] for g in geometries))
meta['interior_lining_revision'] = 1
meta['notes'].append('Perlica-specific closed garment lining bridges the authored tights waist and under-chest boundaries; hip reverse surfaces restored. Original exterior streams, skeleton, materials and first-person assets preserved.')
(destination/'compile_manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report = dict(source=str(b.SOURCE_BLEND), original_unit_sha256=hashlib.sha256(info['raw']).hexdigest(),
              candidate_unit_sha256=hashlib.sha256(output).hexdigest(),
              source_rim_vertices=[len(lower),len(upper)], source_to_serialized_seam_max=float(max(seam_error)),
              lining_triangles=lining_geo['triangle_count'], hip_reverse_triangles=hip_added,
              total_triangles=meta['geometry']['triangles'], closed_lining=True,
              original_front_streams_identical=True, serialized_suffix_identical=True,
              material_texture_artifacts_identical=True, gameplay_verified=False,
              changed_geometry_indices=sorted(changed))
(out/'interior_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('PERLICA_INTERIOR_CANDIDATE',json.dumps(report),flush=True)
