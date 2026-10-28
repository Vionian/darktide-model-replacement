import pathlib, sys, json
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_roshia_native as b

root = pathlib.Path(__file__).parent / 'endfield_batch'
report = {}
for key in ('saixi',):
    report[key] = {}
    for asset in (key, key + '_arms'):
        folder = root / key / 'Custom' / asset
        unit = b.unit_dt.UnitResourceDT(b.Cursor(str(folder / (asset + '.unit'))))
        report[key][asset] = []
        for gi, geo in enumerate(unit.mesh_geometries):
            packed = np.frombuffer(geo.streams[0].vertex_data, '<f2').reshape(-1, 4)
            bad = np.flatnonzero(~np.isfinite(packed).all(axis=1))
            if not len(bad):
                continue
            pos_channel = next(c for c in geo.channels if c.component.name == 'POSITION')
            positions = geo.streams[pos_channel.stream].get_positions(pos_channel).astype(np.float64)
            normals = b.mesh_geometry.math_utils.octahedral_decode(geo.streams[2].vertex_data).astype(np.float64)
            uv = np.frombuffer(geo.streams[3].vertex_data, '<f2').reshape(-1, 2).astype(np.float64)
            records = []
            for vi in bad[:20]:
                start = int(vi // 3 * 3)
                p = positions[start:start+3]
                n = normals[start:start+3].copy()
                t = uv[start:start+3]
                e1, e2 = p[1]-p[0], p[2]-p[0]
                d1, d2 = t[1]-t[0], t[2]-t[0]
                det = d1[0]*d2[1]-d1[1]*d2[0]
                frame = b.packed_tangent_frame(p, n, t)
                records.append({'vertex': int(vi), 'tri_start': start,
                    'packed_rows': packed[start:start+3].tolist(),
                    'positions': p.tolist(), 'normals': n.tolist(), 'uv': t.tolist(),
                    'uv_det': float(det), 'edge_cross': np.cross(e1,e2).tolist(),
                    'recomputed_frame': frame.tolist(),
                    'finite_source': bool(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(t).all())})
            report[key][asset].append({'geo': gi, 'bad_count': int(len(bad)), 'bad': records})
print('WAVE3_NAN_DIAGNOSTIC', json.dumps(report))
(root / 'wave3_nan_diagnostic.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
