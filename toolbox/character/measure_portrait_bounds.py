"""Measure compiled head silhouettes; run with Blender's bundled mathutils."""
import pathlib, sys, json
import numpy as np
from mathutils import Vector
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from package_share_variants import ENDFIELD, WUWA

OUT=b.ROOT/'tools/model-work/distribution_fix'
result={}
for key in {**ENDFIELD, **WUWA}:
    folder=b.ROOT/'Custom'/key
    b.unit_dt.load_stream_dt=lambda path: b.StreamReader(b.Cursor(str(folder/pathlib.Path(path))))
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(key+'.unit'))))
    bones=b.BonesResourceDT(b.Cursor(str(folder/(key+'_bones.bones'))))
    names=b.named_node_map(unit,bones)
    head=names['j_head']; head_world=unit.scene_graph.nodes[head].world_transform
    head_pos=np.asarray(head_world.translation)
    rotation=np.asarray(head_world.to_quaternion().to_matrix())
    head_nodes={head}
    for _ in unit.scene_graph.nodes:
        before=len(head_nodes)
        for i,node in enumerate(unit.scene_graph.nodes):
            if node.parent_index in head_nodes: head_nodes.add(i)
        if len(head_nodes)==before: break
    palette=np.asarray([int(n in head_nodes) for n in unit.skins[0].node_indices])
    points=[]
    formats=[]
    for g in unit.mesh_geometries:
        streams=g.streams
        xyz=np.frombuffer(streams[1].vertex_data,dtype='<f2').reshape((-1,4))[:,:3].astype(np.float32)
        joints=np.frombuffer(streams[5].vertex_data,dtype='u1').reshape((-1,4))
        weights=np.frombuffer(streams[4].vertex_data,dtype='<f2').reshape((-1,4))
        keep=(palette[joints]*weights).sum(1)>=.5
        # Long hanging hair below the jaw belongs outside a face portrait.
        keep &= xyz[:,2]>=head_pos[2]-.13
        points.append(xyz[keep])
    points=np.concatenate(points)
    local=(points-head_pos)@rotation
    low=local.min(0);high=local.max(0)
    result[key]={'head_node':head,'head_world':np.asarray(head_world).tolist(),
        'min':low.tolist(),'max':high.tolist(),'vertices':len(local),
        'world_min':points.min(0).tolist(),'world_max':points.max(0).tolist(),
        'unit_sha256':__import__('hashlib').sha256((folder/(key+'.unit')).read_bytes()).hexdigest()}
    print(key, head_pos, low,high,flush=True)
(OUT/'portrait_bounds.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
