"""Blender native-unit readback, including grip fit and cutting-surface bounds."""
from pathlib import Path
import sys,json,numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/blade_edge'
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
MOD=Path(args[0]) if args else ROOT/'WeaponModelReplacement'
ASSET=MOD/'Custom/khravengger'
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
def mesh_data(path,name):
    b.TEMPLATE=path.parent;unit=b.unit_dt.UnitResourceDT(b.Cursor(str(path)));groups={}
    assert not unit.skins and not unit.actors
    for group,labels in [('base',[name+'_p0',name+'_p0_back'])]+[(c,['cover_'+c+'_mesh_p0','cover_'+c+'_mesh_p0_back']) for c in 'rgb']:
        ids={f'{b.hash64(n)>>32:08X}' for n in labels};vs=[];fs=[];at=0
        for mesh in unit.meshes:
            if str(mesh.name) not in ids:continue
            g=unit.mesh_geometries[mesh.geometry_index-1];ch=next(c for c in g.channels if c.component.name=='POSITION')
            v=g.streams[ch.stream].get_positions(ch).astype(float);M=np.array(unit.scene_graph.nodes[mesh.node_index].world_transform)
            v=v@M[:3,:3].T+M[:3,3];f=g.index_stream.get_indices().reshape(-1,3)
            assert np.isfinite(v).all();vs.append(v);fs.append(f+at);at+=len(v)
        assert vs,(path,group)
        groups[group]=(np.concatenate(vs),np.concatenate(fs))
    nodes={str(n.name) for n in unit.scene_graph.nodes}
    assert all(f'{b.hash64("cover_"+c+"_mesh")>>32:08X}' in nodes for c in 'rgb')
    return groups
def error(a,target):
    tree=KDTree(len(target))
    for i,p in enumerate(target):tree.insert(p,i)
    tree.balance();return max(tree.find(p)[2] for p in a)
backup=Path((ROOT/'build/current_blade_edge_backup.txt').read_text(encoding='utf-8-sig').strip())
report={}
for name,target in [('khravengger',OUT/'khravengger_mesh.npz'),('langzhifei',ROOT/'build/force_sword_pose/aligned_mesh.npz')]:
    groups=mesh_data(ASSET/(name+'.unit'),name);v,f=groups['base'];expected=np.load(target)
    base_error=error(v,expected['vertices']);assert base_error<.0005,base_error
    assert len(f)==2*len(expected['faces'])
    np.savez(OUT/(name+'_compiled.npz'),vertices=v,faces=f)
    edge=json.loads((OUT/(name+'_edge.json')).read_text());authored=np.load(OUT/(name+'_edge.npz'));channels={}
    for i,c in enumerate('rgb'):
        cv,cf=groups[c];offset=edge['normal_offset_m'][i]
        wanted=authored['vertices']+authored['normals']*offset
        e=error(cv,wanted);assert e<.0005,(name,c,e)
        assert len(cf)==2*len(authored['faces']),(name,c,len(cf))
        assert cv[:,2].min()>edge['start_z']-.002
        envelope=np.array(edge['envelope']);left=np.interp(cv[:,2],envelope[:,0],envelope[:,1]);right=np.interp(cv[:,2],envelope[:,0],envelope[:,2])
        d=abs(cv[:,1]-right)
        if len(edge['sides'])==2:d=np.minimum(d,abs(cv[:,1]-left))
        assert d.max()<edge['band_width_m']+.002,(name,c,d.max())
        channels[c]={'max_position_error_m':e,'max_distance_from_edge_m':float(d.max()),'triangles':len(cf)}
        np.savez(OUT/(name+'_compiled_'+c+'.npz'),vertices=cv,faces=cf)
    old=mesh_data(backup/'WeaponModelReplacement/Custom/khravengger'/(name+'.unit'),name)['base'][0]
    if name=='langzhifei':
        assert error(old,v)<.0001 and error(v,old)<.0001
    else:
        size=json.loads((OUT/'size_comparison.json').read_text());pivot=np.array(size['pivot'])
        scaled_old_error=error((old-pivot)*.88+pivot,v)
        # Both old and new UNIT positions are independently half-quantized.
        old_error=error(old,np.load(ROOT/'build/target_mesh.npz')['vertices'])
        assert scaled_old_error<=.88*old_error+base_error+1e-6
        size['compiled_scaled_previous_error_m']=scaled_old_error
        size['old_quantization_error_m']=old_error
        report['native_size_comparison']=size
    report[name]={'base_position_error_m':base_error,'base_triangles':len(f),'channels':channels,
                  'base_bounds':[v.min(0).tolist(),v.max(0).tolist()],
                  'edge_surface_fraction':edge['surface_area_fraction_of_weapon']}
    # Native anchors are translations in both inspected two-handed families.
for path in (OUT/'native').rglob('grip_01.unit'):
    b.TEMPLATE=Path('<DARKTIDE_GAME>/bundle')
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(path)))
    for n in u.scene_graph.nodes:
        if str(n.name) in ('4000D158','67E762A6'):assert np.max(abs(np.array(n.world_transform)[:3,:3]-np.eye(3)))<1e-5
for path in (OUT/'native').rglob('hilt_01.unit'):
    b.TEMPLATE=Path('<DARKTIDE_GAME>/bundle')
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(path)))
    for n in u.scene_graph.nodes:
        if str(n.name)=='894173EC':assert np.max(abs(np.array(n.world_transform)[:3,:3]-np.eye(3)))<1e-5
report.update({'wolf_base_pose_geometry_preserved':True,'khravengger_grip_pivot_preserved':True,
               'three_rgb_edge_channels_per_weapon':True,'guard_grip_and_wolf_spine_uncovered':True,'in_game_visual_verified':False})
(OUT/'geometry_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('BLADE_EDGE_NATIVE_OK',json.dumps({n:report[n] for n in ('khravengger','langzhifei')}))
