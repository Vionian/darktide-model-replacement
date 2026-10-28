from pathlib import Path
import bpy, numpy as np, json
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
src=np.load(ROOT/'build/source_mesh_0.npz')
v=src['vertices']; faces=src['faces']; normals=src['normals'].astype(float)
ref=json.loads((ROOT/'build/reference_frame.json').read_text())['meshes'][0]['bounds']
scale=(ref[1][2]-ref[0][2])/(v[:,2].max()-v[:,2].min())
offset=ref[0][2]-v[:,2].min()*scale
# Source wide axis X -> native sword wide axis Y. Positive determinant rotation.
rot=np.array([[0,1,0],[-1,0,0],[0,0,1]],dtype=float)
positions=v@rot.T*scale; positions[:,2]+=offset
normals=normals@rot.T; normals/=np.linalg.norm(normals,axis=1,keepdims=True)
mesh=bpy.data.meshes.new('khravengger_mesh')
mesh.from_pydata(positions.tolist(),[],faces.tolist()); mesh.update()
uv=mesh.uv_layers.new(name='UVMap'); uvs=src['uvs'][0]
for loop in mesh.loops: uv.data[loop.index].uv=uvs[loop.vertex_index]
for poly in mesh.polygons: poly.use_smooth=True
mesh.normals_split_custom_set_from_vertices(normals.tolist())
obj=bpy.data.objects.new('khravengger',mesh); bpy.context.collection.objects.link(obj)
mat=bpy.data.materials.new('khravengger_pbr'); mat.use_nodes=True
mat.use_backface_culling=True
mat['darktide_material']={'version':1,'mode':'generated','weapon':True}
nodes=mat.node_tree.nodes; links=mat.node_tree.links; bsdf=nodes.get('Principled BSDF')
def image_node(name,space):
    node=nodes.new('ShaderNodeTexImage'); node.image=bpy.data.images.load(str(ROOT/'build/textures'/name))
    node.image.colorspace_settings.name=space; return node
bc=image_node('khravengger_base.png','sRGB'); links.new(bc.outputs['Color'],bsdf.inputs['Base Color'])
nm=image_node('khravengger_normal.png','Non-Color'); normal=nodes.new('ShaderNodeNormalMap')
links.new(nm.outputs['Color'],normal.inputs['Color']); links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
orm=image_node('khravengger_orm.png','Non-Color'); split=nodes.new('ShaderNodeSeparateColor')
links.new(orm.outputs['Color'],split.inputs[0]); links.new(split.outputs['Green'],bsdf.inputs['Roughness'])
links.new(split.outputs['Blue'],bsdf.inputs['Metallic'])
em=image_node('khravengger_emissive.png','sRGB'); links.new(em.outputs['Color'],bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value=1
obj.data.materials.append(mat)
bpy.context.view_layer.objects.active=obj; obj.select_set(True)
for image in bpy.data.images: image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'build/khravengger.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'build/khravengger.glb'),export_format='GLB',
    use_selection=True,export_extras=True,export_yup=True,export_normals=True,export_tangents=True)
np.savez(ROOT/'build/target_mesh.npz',vertices=positions,faces=faces,normals=normals,uvs=uvs)
report={'uniform_scale':float(scale),'rotation':rot.tolist(),'z_offset_m':float(offset),
        'bounds_m':[positions.min(axis=0).tolist(),positions.max(axis=0).tolist()],
        'source_vertices':len(v),'triangles':len(faces),'reference':'ExcaliburAlterForceSword baked base-unit frame',
        'fit':'uniform scale matching reference pommel and tip; source proportions retained'}
(ROOT/'build/alignment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('WEAPON_EXPORT_OK',json.dumps(report))
