from pathlib import Path
import sys, json
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, '<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE = Path('<DARKTIDE_GAME>/bundle')
OUT = ROOT/'build/force_sword_pose'
OUT.mkdir(exist_ok=True)
reports = []
for path in sorted((ROOT/'.tmp/force_sword_reference/ordinary_extract').rglob('*.unit')):
    unit = b.unit_dt.UnitResourceDT(b.Cursor(str(path)))
    report = {'part':path.stem, 'nodes':[], 'meshes':[], 'geometry':[]}
    for i, node in enumerate(unit.scene_graph.nodes):
        report['nodes'].append({'index':i, 'name':str(node.name), 'parent':node.parent_index,
            'world':[list(row) for row in node.world_transform]})
    for i, mesh in enumerate(unit.meshes):
        report['meshes'].append({'index':i, 'fields':{key:str(value) for key,value in vars(mesh).items()}})
    for i, geometry in enumerate(unit.mesh_geometries):
        channel = next((c for c in geometry.channels if c.component.name=='POSITION'),None)
        if channel is None: continue
        vertices = geometry.streams[channel.stream].get_positions(channel)
        faces = geometry.index_stream.get_indices().reshape(-1,3)
        np.savez(OUT/(path.stem+'_'+str(i)+'.npz'), vertices=vertices, faces=faces)
        report['geometry'].append({'index':i, 'vertices':len(vertices), 'triangles':len(faces),
            'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
    reports.append(report)
    print(json.dumps(report))
(OUT/'native_attachments.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
