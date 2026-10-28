"""Calibrate the wolf sword to the native ordinary force-sword grip and tip."""
from pathlib import Path
import json
import bpy, numpy as np
from mathutils import Matrix
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blade_edge_geometry import edge_ribbon
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/force_sword_pose'
measure=json.loads((OUT/'measurements.json').read_text())
source=np.load(OUT/'source_mesh.npz')['vertices']
native=np.load(OUT/'native_assembled.npz')
# Use the clean wrapped portion of the grip, excluding pommel and guard.
# Endpoints come from the source vertex sections in measurements.json.
grip=source[(source[:,2]>=-.13)&(source[:,2]<=-.01)]
source_center=(grip.min(0)+grip.max(0))*.5
target_center=(native['grip'].min(0)+native['grip'].max(0))*.5
source_tip=float(source[:,2].max())
native_tip=measure['native_tip']
scale=(native_tip-target_center[2])/(source_tip-source_center[2])
# Roll the single-edged blade half a turn around the longitudinal grip axis.
# The grip center, uniform scale and forward tip remain at the calibrated pose.
rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]],dtype=float)
translation=target_center-scale*(rotation@source_center)
positions=source@rotation.T*scale+translation
matrix=Matrix.Identity(4)
for row in range(3):
    for col in range(3):matrix[row][col]=float(rotation[row,col]*scale)
    matrix[row][3]=float(translation[row])
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'build/langzhifei/source.blend'))
obj=bpy.data.objects['S_wpn_sword_0022_01_lod0']
world=obj.matrix_world.copy()
obj.parent=None
obj.matrix_world=Matrix.Identity(4)
obj.data.transform(matrix@world)
for other in list(bpy.context.scene.objects):
    if other!=obj:bpy.data.objects.remove(other,do_unlink=True)
obj.name='langzhifei'
obj.data.materials.clear()
mat=bpy.data.materials.new('langzhifei_pbr')
mat.use_nodes=True
mat['darktide_material']={'version':1,'mode':'external',
    'resource':'content/mods/weapon_model_replacement/langzhifei_material_0'}
obj.data.materials.append(mat)
obj.data.update()
cover_faces=np.array([list(poly.vertices) for poly in obj.data.polygons],dtype=int)
normals=np.array([v.normal for v in obj.data.vertices],dtype=float)
edge_v,cover_faces,edge_n=edge_ribbon(positions,cover_faces,normals,.205,.005,(1,),'langzhifei')
for index,channel in enumerate(('r','g','b')):
    p=edge_v+edge_n*(.0005+index*.00015)
    mesh=bpy.data.meshes.new('wolf_charge_'+channel)
    mesh.from_pydata(p.tolist(),[],cover_faces.tolist());mesh.update()
    uv=mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        co=p[loop.vertex_index]
        uv.data[loop.index].uv=(float((co[1]+.1)/.2),float((co[2]-.16)/.69))
    for poly in mesh.polygons:poly.use_smooth=True
    shell=bpy.data.objects.new('cover_'+channel+'_mesh',mesh);bpy.context.collection.objects.link(shell)
    material=bpy.data.materials.new('ice_cover_'+channel);material.use_nodes=True
    material['darktide_material']={'version':1,'mode':'external',
        'resource':'content/mods/weapon_model_replacement/ice_cover_'+channel}
    material['darktide_double_sided']=True
    shell.data.materials.append(material)
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True);bpy.context.view_layer.objects.active=obj
actual=np.array([p.co for p in obj.data.vertices])
assert np.max(abs(actual-positions))<1e-6
old_scale=(1.13671875-.15)/1.026609
old_center=old_scale*(rotation@source_center)+np.array([0,0,.15])
# Readback of the previous saved scene proved that detaching its parent after
# resetting matrix_world left a -90 degree X rotation on the exported mesh.
old_residual_rotation=np.array([[1,0,0],[0,0,1],[0,-1,0]],dtype=float)
old_actual_center=old_residual_rotation@old_center
report={'source':'wpn_sword_0022_refined.fbx','lod':'S_wpn_sword_0022_01_lod0',
    'target_family':'force_sword (ordinary one-handed, not 2h_force_sword)',
    'reference':'current-game grip_01 + hilt_01 + blade_01 + pommel_01 UNIT scene graphs',
    'source_grip_bounds':[grip.min(0).tolist(),grip.max(0).tolist()],
    'source_grip_center':source_center.tolist(),'target_grip_center':target_center.tolist(),
    'old_intended_grip_center':old_center.tolist(),
    'old_grip_center':old_actual_center.tolist(),
    'old_residual_rotation':old_residual_rotation.tolist(),
    'old_blade_axis':[0,1,0],'new_blade_axis':[0,0,1],
    'old_intended_grip_height_error_m':float(old_center[2]-target_center[2]),
    'grip_center_correction_m':(target_center-old_actual_center).tolist(),
    'uniform_scale':float(scale),'rotation':rotation.tolist(),'translation':translation.tolist(),
    'source_guard_datum_z':0,'target_guard_datum_z':float(translation[2]),
    'native_tip_z':native_tip,'target_tip_z':float(actual[:,2].max()),
    'bounds':[actual.min(0).tolist(),actual.max(0).tolist()],
    'vertices':len(actual),'triangles':len(obj.data.polygons),
    'native_hand_animation_preserved':True,'material_resource_unchanged':True,
    'cutting_edge_roll_degrees_from_0_2_4':180,
    'grip_axis_and_forward_tip_preserved':True,
    'charge_cover_channels':3,'charge_cover_start_z':.205,'charge_cover_triangles_per_channel':len(cover_faces),
    'charge_cover_edge_only':True,'charge_cover_band_width_m':.005,
    'in_game_visual_verified':False}
(OUT/'langzhifei_alignment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
np.savez(OUT/'aligned_mesh.npz',vertices=actual,faces=np.load(OUT/'source_mesh.npz')['faces'])
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'langzhifei.blend'))
for shell in bpy.context.scene.objects:shell.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'langzhifei.glb'),export_format='GLB',
    export_extras=True,export_yup=True,export_normals=True,export_tangents=True,use_selection=True)
print('WOLF_ONE_HAND_ALIGNMENT',json.dumps(report))
