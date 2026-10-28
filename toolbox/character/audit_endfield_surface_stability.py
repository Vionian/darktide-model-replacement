"""Serialized bind checks and same-rig, rotation-invariant surface diagnostics.

Triangle area/edge ratios detect collapse/stretch, unlike a rest-normal dot
product, which also changes sign under a valid rigid rotation. Synthetic poses
must be generated from the unit's own fixture and configuration.
"""
import argparse
import gc
import hashlib
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_roshia_native as b

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', type=pathlib.Path, required=True)
parser.add_argument('--candidate', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])


def load(folder, key):
    return b.unit_dt.UnitResourceDT(b.Cursor(str(folder / (key + '.unit'))))


def geometry(geo):
    channel = next(c for c in geo.channels if c.component.name == 'POSITION')
    p = geo.streams[channel.stream].get_positions(channel).astype(np.float64)
    joints = np.frombuffer(geo.streams[5].vertex_data, np.uint8).reshape(-1, 4)
    w = np.frombuffer(geo.streams[4].vertex_data, '<f2').reshape(-1, 4).astype(float)
    assert np.isfinite(p).all() and np.isfinite(w).all() and (w >= 0).all()
    assert abs(w.sum(1) - 1).max(initial=0) < .002
    w /= w.sum(1, keepdims=True)
    return p, joints, w


def rest_check(folder, key, mapping=None):
    unit = load(folder, key)
    nodes = unit.scene_graph.nodes
    worlds = {}
    visiting = set()

    def world(i):
        if i not in worlds:
            assert i not in visiting, (key, 'parent cycle', i)
            visiting.add(i)
            n = nodes[i]
            local = np.array(n.local_transform, dtype=float)
            worlds[i] = world(n.parent_index) @ local if n.parent_type == b.ParentType.INTERNAL else local
            visiting.remove(i)
        return worlds[i]

    maximum = 0.
    count = 0
    for skin in unit.skins:
        # These character resources currently use one shared skin palette.
        assert len(unit.skins) == 1, (key, 'multi-skin resource needs per-mesh lookup')
        weighted = set()
        for geo in unit.mesh_geometries:
            p, joints, w = geometry(geo)
            assert int(joints.max()) < len(skin.node_indices), key
            weighted.update(int(j) for j in joints[w > 0])
        for slot in weighted:
            i = skin.node_indices[slot]
            inv = np.array(skin.inv_bind_matrices[slot], dtype=float)
            maximum = max(maximum, float(abs(world(i) @ inv - np.eye(4)).max()))
        count += len(weighted)
    assert maximum < 2e-4, (key, maximum)
    names = b.named_node_map(unit, b.BonesResourceDT(b.Cursor(str(folder / (key + '_bones.bones')))))
    configs = mapping.get('runtime_bones', []) if mapping else []
    seen = set()
    for row in configs:
        name, parent = row['node'], row['parent']
        assert name in names and parent in names, (key, name, parent)
        assert name not in seen, (key, 'duplicate dynamic node', name)
        seen.add(name)
        assert nodes[names[name]].parent_index == names[parent], (key, 'parent mismatch', name)
        if parent.startswith('qianxia_'):
            assert parent in seen, (key, 'dynamic config is not parent-first', name, parent)
    return {'max_bind_identity_error': maximum, 'weighted_palette': count,
            'geometries': len(unit.mesh_geometries),
            'triangles': sum(g.index_stream.index_count // 3 for g in unit.mesh_geometries),
            'dynamic_nodes_checked': len(configs)}


def motion_check(root):
    unit = load(root / 'Custom/perlica', 'perlica')
    fixture = json.loads((root / 'runtime_fixture.json').read_text(encoding='utf-8'))
    assert np.allclose(np.array(fixture['perlica']['world']).reshape(-1, 4, 4).transpose(0, 2, 1),
                       np.array([np.array(n.world_transform) for n in unit.scene_graph.nodes]), atol=1e-7)
    skin = unit.skins[0]
    inv = np.array([np.array(m) for m in skin.inv_bind_matrices])
    geos = [geometry(g) for g in unit.mesh_geometries]
    rows = {}
    for path in sorted(root.glob('body_run_frame_*_pose.json')):
        pose = json.loads(path.read_text(encoding='utf-8'))
        worlds = np.array(pose['worlds'])
        palette = worlds[skin.node_indices] @ inv
        stats = []
        for index, (p, joints, weights) in enumerate(geos):
            transforms = (palette[joints] * weights[:, :, None, None]).sum(1)
            q = np.einsum('nij,nj->ni', transforms[:, :3, :3], p) + transforms[:, :3, 3]
            assert np.isfinite(q).all()
            # The serializer splits triangles; index topology is validated by
            # the existing compiled-preview byte comparison.
            t, u = p.reshape(-1, 3, 3), q.reshape(-1, 3, 3)
            a = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
            c = np.linalg.norm(np.cross(u[:, 1] - u[:, 0], u[:, 2] - u[:, 0]), axis=1)
            valid = a > 1e-9
            ratio = c[valid] / a[valid]
            edges = []
            for i, j in ((0, 1), (1, 2), (2, 0)):
                before = np.linalg.norm(t[:, j] - t[:, i], axis=1)
                after = np.linalg.norm(u[:, j] - u[:, i], axis=1)
                edges.extend((after[before > 1e-5] / before[before > 1e-5]).tolist())
            stats.append({'geometry': index, 'triangles': len(t),
                          'area_below_20_percent': int((ratio < .2).sum()),
                          'area_above_3x': int((ratio > 3).sum()),
                          'edge_above_3x': int((np.array(edges) > 3).sum()),
                          'edge_ratio_p99': float(np.quantile(edges, .99)),
                          'max_edge_ratio': float(max(edges))})
        rows[str(pose['frame'])] = {'geometries': stats,
                                   'collapsed_triangles': sum(s['area_below_20_percent'] for s in stats),
                                   'stretched_triangles': sum(s['area_above_3x'] for s in stats)}
    assert len(rows) == 5
    return rows


report = {'scope': 'Offline serialized bindings and synthetic gait; no gameplay validation',
          'motion': {'baseline': motion_check(args.baseline), 'candidate': motion_check(args.candidate)},
          'assets': {}, 'source_surface_reports': {}}
for folder in sorted((b.ROOT / 'Custom').iterdir()):
    key = folder.name
    if not folder.is_dir() or not (folder / (key + '.unit')).exists():
        continue
    mapping_path = b.ROOT / 'Custom' / (key.removesuffix('_arms') + '_source_mapping.json')
    mapping = json.loads(mapping_path.read_text(encoding='utf-8')) if mapping_path.exists() and not key.endswith('_arms') else None
    report['assets'][key] = rest_check(folder, key, mapping)
    gc.collect()
for path in (b.ROOT / 'tools/model-work/endfield_batch').glob('*/dynamic_surface_audit_after_20261022.json'):
    source = json.loads(path.read_text(encoding='utf-8'))
    report['source_surface_reports'][path.parent.name] = {
        'dynamic_bones': source['dynamic_source_bones'],
        'dynamic_materials': {k: round(v['dynamic_vertex_fraction'], 4)
                              for k, v in source['materials'].items() if v['dynamic_vertex_fraction'] > .01}}
report['candidate_binding'] = rest_check(args.candidate / 'Custom/perlica', 'perlica',
    json.loads((args.candidate / 'Custom/perlica_source_mapping.json').read_text(encoding='utf-8')))
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'assets_checked': len(report['assets']), 'candidate_binding': report['candidate_binding'],
                  'motion': {k: {f: {x: r[x] for x in ('collapsed_triangles', 'stretched_triangles')}
                                for f, r in v.items()} for k, v in report['motion'].items()}}, indent=2))
