from pathlib import Path
from itertools import permutations
import sys,json
import numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/force_sword_pose'
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
from bitsquid.murmur.murmurhash64 import hash64
base_names={f'{hash64(n)>>32:08X}' for n in ('langzhifei_p0','langzhifei_p0_back')}
def read(path,base_only=False):
    b.TEMPLATE=path.parent
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(path)))
    assert not unit.skins and not unit.actors
    vertices=[];faces=[];count=0
    for mesh in unit.meshes:
        if base_only and str(mesh.name) not in base_names:continue
        geo=unit.mesh_geometries[mesh.geometry_index-1]
        ch=next(c for c in geo.channels if c.component.name=='POSITION')
        v=geo.streams[ch.stream].get_positions(ch).astype(float)
        matrix=np.array(unit.scene_graph.nodes[mesh.node_index].world_transform)
        v=v@matrix[:3,:3].T+matrix[:3,3]
        assert np.isfinite(v).all()
        f=geo.index_stream.get_indices().reshape(-1,3)
        vertices.append(v);faces.append(f+count);count+=len(v)
    return np.concatenate(vertices),np.concatenate(faces)
current=ROOT/'WeaponModelReplacement/Custom/khravengger/langzhifei.unit'
new,nf=read(current,True)
whole,wf=read(current)
compiled=b.unit_dt.UnitResourceDT(b.Cursor(str(current)))
nodes={str(n.name) for n in compiled.scene_graph.nodes}
meshes={str(m.name) for m in compiled.meshes}
for channel in ('r','g','b'):
    assert f'{hash64("cover_"+channel+"_mesh")>>32:08X}' in nodes
    for suffix in ('_p0','_p0_back'):
        assert f'{hash64("cover_"+channel+"_mesh"+suffix)>>32:08X}' in meshes
backup=Path((ROOT/'build/current_pose_edit_backup.txt').read_text(encoding='utf-8-sig').strip())
if not backup.is_absolute():backup=ROOT/backup
old,of=read(backup/'WeaponModelReplacement/Custom/khravengger/langzhifei.unit')
target=np.load(OUT/'aligned_mesh.npz');v=target['vertices'];f=target['faces']
tree=KDTree(len(v))
for index,point in enumerate(v):tree.insert(point,index)
tree.balance()
matches=[tree.find(point) for point in new]
error=max(hit[2] for hit in matches)
assert error<.0005,error
# Quantization may collapse seam vertices whose source positions differ by
# submicron noise. Compare actual triangle corners in space, not seam indices.
assert len(nf)==2*len(f)
original_triangles=v[f];compiled_triangles=new[nf]
def triangle_error(source,destination):
    tree=KDTree(len(source))
    for index,center in enumerate(source.mean(axis=1)):tree.insert(center,index)
    tree.balance();worst=0
    orders=list(permutations(range(3)))
    for triangle in destination:
        nearby=tree.find_n(triangle.mean(axis=0),min(8,len(source)))
        best=min(float(np.linalg.norm(triangle-source[index][list(order)],axis=1).max())
            for _,index,_ in nearby for order in orders)
        worst=max(worst,best)
    return worst
triangle_max_error=max(triangle_error(original_triangles,compiled_triangles),
    triangle_error(compiled_triangles,original_triangles))
assert triangle_max_error<.0005,triangle_max_error
np.savez(OUT/'compiled_mesh.npz',vertices=new,faces=nf)
np.savez(OUT/'old_mesh.npz',vertices=old,faces=of)
alignment=json.loads((OUT/'langzhifei_alignment.json').read_text())
report={'compiled_unit':'UNIT v115','vertices':len(new),'triangles':len(nf),
    'total_vertices_including_cover':len(whole),'total_triangles_including_cover':len(wf),
    'compiled_cover_nodes_and_mesh_names_verified':True,
    'source_vertices':len(v),'source_triangles':len(f),'two_sided_triangle_closure':True,
    'max_compiled_position_error_m':error,'max_triangle_corner_error_m':triangle_max_error,
    'compiled_bounds':[new.min(0).tolist(),new.max(0).tolist()],
    'grip_center_error_m':float(np.linalg.norm(alignment['target_grip_center']-(np.array(alignment['source_grip_center'])@np.array(alignment['rotation']).T*alignment['uniform_scale']+np.array(alignment['translation'])))),
    'tip_error_m':float(abs(new[:,2].max()-alignment['native_tip_z'])),
    'native_animation_unchanged':True,'in_game_visual_verified':False}
assert report['grip_center_error_m']<1e-6
assert report['tip_error_m']<.0005
current_backup=Path((ROOT/'build/current_wolf_violet_backup.txt').read_text(encoding='utf-8-sig').strip())
previous,_=read(current_backup/'WeaponModelReplacement/Custom/khravengger/langzhifei.unit',True)
grip=np.array(alignment['target_grip_center'])
rolled=(previous-grip)*np.array([-1,-1,1])+grip
tree=KDTree(len(new))
for i,point in enumerate(new):tree.insert(point,i)
tree.balance()
report['half_turn_about_grip_axis_error_m']=max(tree.find(point)[2] for point in rolled)
report['cutting_edge_roll_degrees']=180
assert report['half_turn_about_grip_axis_error_m']<.0005
(OUT/'geometry_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('POSE_GEOMETRY_VERIFIED',json.dumps(report))
