from pathlib import Path
import sys, json
import bpy, numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/force_sword_pose'
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE=Path('<DARKTIDE_GAME>/bundle')
BASE=ROOT/'.tmp/force_sword_reference/ordinary_extract/content/weapons/player/melee/force_sword/attachments'
def part(name):
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(BASE/name/(name+'.unit'))))
    mesh=unit.meshes[0]
    geo=unit.mesh_geometries[mesh.geometry_index-1]
    channel=next(c for c in geo.channels if c.component.name=='POSITION')
    v=geo.streams[channel.stream].get_positions(channel).astype(float)
    matrix=np.array(unit.scene_graph.nodes[mesh.node_index].world_transform)
    v=v@matrix[:3,:3].T+matrix[:3,3]
    f=geo.index_stream.get_indices().reshape(-1,3)
    return unit,v,f
grip,g,gf=part('grip_01')
hilt,h,hf=part('hilt_01')
blade,v,vf=part('blade_01')
pommel,p,pf=part('pommel_01')
hilt_anchor=np.array(grip.scene_graph.nodes[-1].world_transform.translation)
blade_anchor=np.array(hilt.scene_graph.nodes[-1].world_transform.translation)
pommel_anchor=np.array(grip.scene_graph.nodes[-2].world_transform.translation)
h+=hilt_anchor;v+=hilt_anchor+blade_anchor;p+=pommel_anchor
native=np.concatenate([g,h,v,p])
np.savez(OUT/'native_assembled.npz',grip=g,grip_faces=gf,hilt=h,hilt_faces=hf,blade=v,blade_faces=vf,pommel=p,pommel_faces=pf)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'build/langzhifei/source.blend'))
obj=bpy.data.objects['S_wpn_sword_0022_01_lod0']
s=np.array([obj.matrix_world@point.co for point in obj.data.vertices])
obj.data.calc_loop_triangles();sf=np.array([t.vertices[:] for t in obj.data.loop_triangles])
np.savez(OUT/'source_mesh.npz',vertices=s,faces=sf)
report={'native_parts':{name:{'min':a.min(0).tolist(),'max':a.max(0).tolist()} for name,a in [('grip',g),('hilt',h),('blade',v),('pommel',p)]},'native_tip':float(native[:,2].max()),'hilt_anchor':hilt_anchor.tolist(),'blade_anchor':blade_anchor.tolist(),'source_sections':[]}
for z in np.arange(-.22,.201,.01):
    section=s[abs(s[:,2]-z)<.005]
    if len(section):report['source_sections'].append({'z':round(float(z),3),'count':len(section),'min':section.min(0).tolist(),'max':section.max(0).tolist()})
(OUT/'measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('MEASUREMENTS',json.dumps(report))
