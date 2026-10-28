from pathlib import Path
import bpy, numpy as np, json
from mathutils import Vector
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blade_edge_geometry import khravengger_mesh,edge_ribbon
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/revision';OUT.mkdir(exist_ok=True)
def external(name,resource):
    m=bpy.data.materials.new(name);m.use_nodes=True
    m['darktide_material']={'version':1,'mode':'external','resource':resource}
    return m
def export(name):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',export_extras=True,export_yup=True,export_normals=True,export_tangents=True,use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'.blend')))
def reset():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
reset()
v,f,normal,uv=khravengger_mesh()
data={'vertices':v,'faces':f,'normals':normal,'uvs':uv}
base,edge_faces,edge_normals=edge_ribbon(v,f,normal,.26,.006,(-1,1),'khravengger')
for i,ch in enumerate(('r','g','b')):
    p=base+edge_normals*(.0005+i*.00015)
    mesh=bpy.data.meshes.new('ice_cover_'+ch);mesh.from_pydata(p.tolist(),[],edge_faces.tolist());mesh.update()
    layer=mesh.uv_layers.new(name='UVMap')
    # Blade shader expects longitudinal UVs, not the model's packed atlas.
    for loop in mesh.loops:
        co=p[loop.vertex_index];layer.data[loop.index].uv=(float((co[1]+.16)/.32),float((co[2]-.16)/.98))
    for poly in mesh.polygons:poly.use_smooth=True
    ob=bpy.data.objects.new('cover_'+ch+'_mesh',mesh);bpy.context.collection.objects.link(ob)
    mat=external('ice_cover_'+ch,'content/mods/weapon_model_replacement/ice_cover_'+ch)
    mat['darktide_double_sided']=True
    ob.data.materials.append(mat)
# Embed the cover in the weapon unit; its lifetime, visibility and FOV then
# follow the replacement without a second unmanaged spawned child.
mesh=bpy.data.meshes.new('khravengger_mesh');mesh.from_pydata(v.tolist(),[],data['faces'].tolist());mesh.update()
layer=mesh.uv_layers.new(name='UVMap')
for loop in mesh.loops:layer.data[loop.index].uv=data['uvs'][loop.vertex_index]
for poly in mesh.polygons:poly.use_smooth=True
mesh.normals_split_custom_set_from_vertices(data['normals'].tolist())
ob=bpy.data.objects.new('khravengger',mesh);bpy.context.collection.objects.link(ob)
ob.data.materials.append(external('khravengger_pbr','content/mods/weapon_model_replacement/khravengger_material_0'))
export('khravengger')
# The wolf sword uses the ordinary one-handed force-sword frame.
# Keep its measured grip calibration in the dedicated, repeatable builder.
import runpy, shutil
runpy.run_path(str(ROOT/'tools/build_langzhifei_pose.py'),run_name='__main__')
for name in ('langzhifei.glb','langzhifei.blend','langzhifei_alignment.json'):
    shutil.copy2(ROOT/'build/force_sword_pose'/name,ROOT/'build/revision'/name)
print('REVISION_SCENES_READY')
