"""Inspect source surface connectivity without changing the source blend."""
import bpy
import collections
import json
import pathlib
import numpy as np

HERE = pathlib.Path(__file__).parent
OUT = HERE / 'perlica_interior_fix_20261022'
OUT.mkdir(exist_ok=True)
inspection = json.loads((HERE / 'endfield_batch/weights.json').read_text(encoding='utf-8'))['佩丽卡']
bpy.ops.wm.open_mainfile(filepath=inspection['source'])
obj = bpy.data.objects[inspection['mesh']]
mesh = obj.data
world = np.asarray(obj.matrix_world)
points = np.array([(*v.co, 1) for v in mesh.vertices]) @ world.T
points = points[:, :3]
mesh.calc_loop_triangles()
report = {'source': inspection['source'], 'materials': []}
for mi, mat in enumerate(mesh.materials):
    tris = np.array([t.vertices[:] for t in mesh.loop_triangles if t.material_index == mi], dtype=int)
    if not len(tris):
        continue
    adjacency = collections.defaultdict(set)
    for tri in tris:
        for a, z in zip(tri, np.roll(tri, -1)):
            adjacency[int(a)].add(int(z)); adjacency[int(z)].add(int(a))
    remaining = set(adjacency)
    components = []
    while remaining:
        stack = [remaining.pop()]; component = set(stack)
        while stack:
            for v in adjacency[stack.pop()]:
                if v in remaining:
                    remaining.remove(v); stack.append(v); component.add(v)
        ids = np.array(sorted(component))
        if len(ids) < 10:
            continue
        selected = tris[np.isin(tris[:, 0], ids)]
        edges = collections.Counter(tuple(sorted((int(a), int(z)))) for tri in selected
                                    for a, z in zip(tri, np.roll(tri, -1)))
        boundaries = [e for e, n in edges.items() if n == 1]
        p = points[ids]
        components.append({'vertices': len(ids), 'triangles': len(selected),
                           'min': p.min(0).tolist(), 'max': p.max(0).tolist(),
                           'boundary_edges': len(boundaries)})
    row = {'index': mi, 'name': mat.name, 'triangles': len(tris),
           'two_sided': bool(getattr(getattr(mat, 'mmd_material', None), 'is_double_sided', False)),
           'components': sorted(components, key=lambda c: c['triangles'], reverse=True),
           'z_triangle_histogram': np.histogram(points[tris].mean(1)[:, 2], np.arange(0, 1.81, .1))[0].tolist()}
    if mi in (9, 10):
        _, unique = np.unique(np.round(points, 6), axis=0, return_inverse=True)
        welded = unique[tris]
        edges = collections.Counter(tuple(sorted((int(a),int(z)))) for tri in welded
                                    for a,z in zip(tri,np.roll(tri,-1)))
        boundary = [edge for edge,n in edges.items() if n == 1]
        boundary_graph = collections.defaultdict(set)
        for a,z in boundary:
            boundary_graph[a].add(z); boundary_graph[z].add(a)
        original = {int(w):i for i,w in enumerate(unique)}
        todo = set(boundary_graph); loops = []
        while todo:
            stack=[todo.pop()]; group=set(stack)
            while stack:
                for v in boundary_graph[stack.pop()]:
                    if v in todo:
                        todo.remove(v);stack.append(v);group.add(v)
            ids=[original[i] for i in group]; pp=points[ids]
            loops.append({'count':len(ids),'closed':all(len(boundary_graph[v])==2 for v in group),
                          'min':pp.min(0).tolist(),'max':pp.max(0).tolist(),'source_vertex_ids':ids})
        row['welded_boundaries'] = sorted(loops,key=lambda v:v['max'][2],reverse=True)
    report['materials'].append(row)
(OUT / 'source_topology.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('SOURCE_TOPOLOGY', json.dumps([{k:r[k] for k in ('index','name','welded_boundaries')}
                                   for r in report['materials'] if 'welded_boundaries' in r], ensure_ascii=False))
