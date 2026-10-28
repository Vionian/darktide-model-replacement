"""Render extracted HD2 geometry/UV atlas as a read-only visual reference."""
import pathlib, sys, json
import bpy, numpy as np
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[2]
setup=(ROOT/'tools/model-work/read_hd2_reference_meshes.py').read_text(encoding='utf-8').split('report=[]')[0]
exec(compile(setup,'hd2_reader_setup','exec'))
path=source/'15b1f3836eb316a7.unit'
obj=hd.LoadStingrayMesh(int(path.stem,16),path.read_bytes(),pathlib.Path(str(path)+'.gpu').read_bytes(),b'',False,False)
m=obj.RawMeshes[2]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
mesh=bpy.data.meshes.new('HD2ExtractedReference')
mesh.from_pydata(m.VertexPositions,[],m.Indices);mesh.update()
model=bpy.data.objects.new('HD2ExtractedReference',mesh);bpy.context.collection.objects.link(model)
uv=mesh.uv_layers.new(name='HD2 UV0')
for loop in mesh.loops:
    u,v=m.VertexUVs[0][loop.vertex_index];uv.data[loop.index].uv=(u,1-v)
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
mat_map={e['id']:e for e in manifest['entries'] if e['type']=='material'}
sections=[]
for section in m.Materials:
    entry=mat_map.get(int(section.MatID))
    atlas='575916970fe824b9' if entry is None else entry['textures'][1]
    mat=bpy.data.materials.new(str(section.MatID));mat.use_nodes=True
    mat.use_backface_culling=True
    nodes=mat.node_tree.nodes;nodes.clear();bs=nodes.new('ShaderNodeBsdfPrincipled');bs.inputs['Roughness'].default_value=.75
    output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(bs.outputs['BSDF'],output.inputs['Surface'])
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(source/(atlas+'.texture.png')))
    mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    mesh.materials.append(mat)
    for p in mesh.polygons[section.StartIndex//3:(section.StartIndex+section.NumIndices)//3]:p.material_index=len(mesh.materials)-1;p.use_smooth=True
    sections.append({'material':str(section.MatID),'first_face':section.StartIndex//3,'faces':section.NumIndices//3,'atlas':atlas,'fallback_atlas':entry is None})
OUT=source.parent
(OUT/'reference_mesh_sections.json').write_text(json.dumps(sections,indent=2))
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1000;scene.render.resolution_y=1300;scene.render.resolution_percentage=100
scene.world.color=(.06,.06,.06);scene.view_settings.view_transform='AgX'
p=np.array(m.VertexPositions);center=Vector((p.min(0)+p.max(0))/2);size=max(p.max(0)-p.min(0))
for sign,name in ((1,'front'),(-1,'back')):
    cd=bpy.data.cameras.new(name);cam=bpy.data.objects.new(name,cd);bpy.context.collection.objects.link(cam)
    cam.location=center+Vector((0,sign*size*2,0));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cd.type='ORTHO';cd.ortho_scale=size*1.2;scene.camera=cam
    ld=bpy.data.lights.new('key','AREA');light=bpy.data.objects.new('key',ld);bpy.context.collection.objects.link(light)
    light.location=center+Vector((size*.4,sign*size,size));light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler();ld.energy=180;ld.size=size
    scene.render.filepath=str(OUT/('extracted_mesh_'+name+'.png'));bpy.ops.render.render(write_still=True);light.hide_render=True
print('HD2_REFERENCE_RENDERED',sections)
