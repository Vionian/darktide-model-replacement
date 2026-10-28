from pathlib import Path
import sys,json,math
import bpy,numpy as np
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE=ROOT/'WeaponModelReplacement/Custom/khravengger'
unit=b.unit_dt.UnitResourceDT(b.Cursor(str(b.TEMPLATE/'khravengger.unit')))
assert len(unit.mesh_geometries)==1 and not unit.skins and not unit.actors
g=unit.mesh_geometries[0]
def attr(name,method):
    c=next(c for c in g.channels if c.component.name==name)
    return getattr(g.streams[c.stream],method)(c)
v=attr('POSITION','get_positions').astype(float)
n=attr('NORMAL','get_normals').astype(float)
uv=attr('TEXCOORD','get_texcoords').astype(float)
faces=g.index_stream.get_indices().reshape(-1,3)
target=np.load(ROOT/'build/target_mesh.npz')
assert len(v)==len(target['vertices'])==11300 and len(faces)==9922
# Export/compile can reorder vertices. Compare quantized triangle corners, including UVs.
def sorted_corners(p,f,t):
    c=np.c_[p[f].reshape(-1,3),t[f].reshape(-1,2)]
    c=np.rint(c/0.002).astype(np.int64)
    return c[np.lexsort(c.T[::-1])]
position_error=float(np.max(np.abs(v-target['vertices']))) if np.array_equal(faces,target['faces']) else None
# KD nearest in position/UV space also permits benign index reordering.
source=np.c_[target['vertices'],target['uvs']]
native=np.c_[v,np.c_[uv[:,0],1-uv[:,1]]]
source_q=np.rint(source/0.002).astype(np.int64)
native_q=np.rint(native/0.002).astype(np.int64)
# Compiler stores UV origin for DDS; verify both conventions explicitly.
uv_direct=float(np.max(np.abs(uv-target['uvs'])))
uv_flipped=float(np.max(np.abs(native[:,3:]-target['uvs'])))
assert position_error is not None and position_error<0.001
assert min(uv_direct,uv_flipped)<0.001
assert np.array_equal(faces,target['faces'])
assert np.isfinite(v).all() and np.isfinite(n).all()
report={'vertices':len(v),'triangles':len(faces),'native_unit_version':115,'index_buffer_matches':True,
        'max_position_error_m':position_error,'max_uv_direct_error':uv_direct,'max_uv_flipped_error':uv_flipped,
        'bounds_m':[v.min(axis=0).tolist(),v.max(axis=0).tolist()],
        'preview_geometry':'read from final compiled khravengger.unit',
        'preview_textures':'largest mip decoded from final native textures and streams',
        'in_game_validation':False}
(ROOT/'build/geometry_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('COMPILED_GEOMETRY_OK',json.dumps(report),flush=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
mesh=bpy.data.meshes.new('compiled_khravengger');mesh.from_pydata(v.tolist(),[],faces.tolist());mesh.update()
blender_uv=uv.copy()
if uv_flipped<uv_direct:blender_uv[:,1]=1-blender_uv[:,1]
layer=mesh.uv_layers.new(name='UVMap')
for loop in mesh.loops:layer.data[loop.index].uv=blender_uv[loop.vertex_index]
for p in mesh.polygons:p.use_smooth=True
mesh.normals_split_custom_set_from_vertices(n.tolist())
obj=bpy.data.objects.new('compiled_khravengger',mesh);bpy.context.collection.objects.link(obj)
mat=bpy.data.materials.new('native_texture_readback');mat.use_nodes=True;mat.use_backface_culling=True
nodes=mat.node_tree.nodes;links=mat.node_tree.links;bsdf=nodes.get('Principled BSDF')
def image(name,space):
    t=nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(ROOT/'build/native_readback'/name));t.image.colorspace_settings.name=space;return t
bc=image('bc.png','sRGB');links.new(bc.outputs['Color'],bsdf.inputs['Base Color'])
nm=image('normal_preview.png','Non-Color');normal=nodes.new('ShaderNodeNormalMap');links.new(nm.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
orm=image('orm.png','Non-Color');split=nodes.new('ShaderNodeSeparateColor');links.new(orm.outputs['Color'],split.inputs[0]);links.new(split.outputs['Green'],bsdf.inputs['Roughness']);links.new(split.outputs['Blue'],bsdf.inputs['Metallic'])
em=image('em.png','Non-Color');links.new(em.outputs['Color'],bsdf.inputs['Emission Color']);bsdf.inputs['Emission Strength'].default_value=.25
obj.data.materials.append(mat)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=48
scene.render.resolution_x=1800;scene.render.resolution_y=600;scene.render.resolution_percentage=100
scene.world.color=(.18,.18,.18)
scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=-1
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
camera_data=bpy.data.cameras.new('Preview');camera=bpy.data.objects.new('Preview',camera_data);bpy.context.collection.objects.link(camera);scene.camera=camera
camera_data.type='ORTHO';camera_data.ortho_scale=1.58
center=Vector((0,0,.4296875))
def light(name,loc,power,size):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
light('Key',(-2,-1,2),450,3);light('Fill',(-1,2,.7),250,2);light('Back',(2,0,1),400,2)
dest=ROOT/'WeaponModelReplacement/预览';dest.mkdir(exist_ok=True)
for side in ('front','back'):
    camera.location=Vector((-3 if side=='front' else 3,0,.4296875))
    q=(center-camera.location).to_track_quat('-Z','Y')@Quaternion((0,0,1),math.pi/2)
    camera.rotation_euler=q.to_euler()
    scene.render.filepath=str(dest/f'khravengger_{side}.png')
    bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'build/compiled_preview.blend'))
print('COMPILED_PREVIEW_OK',flush=True)
