"""Diagnostic original CMB face; independent from native export shader."""
import bpy,pathlib,sys,json,numpy as np
from mathutils import Vector
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
key=sys.argv[sys.argv.index('--')+1]if '--'in sys.argv else 'zhuangfangyi'
apply(b,key);bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh=bpy.data.objects[b.MESH_OBJECT_NAME]
out=pathlib.Path(__file__).parent/'endfield_batch/face_refinement'
face=bpy.data.objects.get(mesh.name+'__面')
objects=[o for o in bpy.data.objects if o.name.startswith(mesh.name+'__')and o.type=='MESH']
for o in bpy.context.scene.objects:o.hide_render=o not in objects
points=[mesh.matrix_world@v.co for p in mesh.data.polygons if p.material_index==0 for v in [mesh.data.vertices[i]for i in p.vertices]]
lo=Vector(tuple(min(p[i]for p in points)for i in range(3)));hi=Vector(tuple(max(p[i]for p in points)for i in range(3)))
center=(lo+hi)*.5;size=max(hi-lo)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=900;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
scene.render.use_compositing=False;scene.world=bpy.data.worlds.new('SourceDiagnosticWorld');scene.world.use_nodes=True
bg=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.15,.15,.15,1);bg.inputs[1].default_value=.3
camera_data=bpy.data.cameras.new('SourceDiagnosticCamera');camera=bpy.data.objects.new('SourceDiagnosticCamera',camera_data);scene.collection.objects.link(camera)
camera.location=center+Vector((0,-size*4,size*.1));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type='ORTHO';camera_data.ortho_scale=size*1.75;scene.camera=camera
scene.view_settings.view_transform='AgX';scene.view_settings.look='None';scene.view_settings.exposure=0
scene.render.filepath=str(out/(key+'_cmb_source.png'));bpy.ops.render.render(write_still=True)
info={}
for obj in objects:
    if not any(n in obj.name for n in ('__面','__目','__睫')):continue
    for mat in obj.data.materials:
        if not mat.node_tree:continue
        info[obj.name]=[{'name':n.name,'type':n.type,'tree':n.node_tree.name if n.type=='GROUP'else None,
                        'inputs':{s.name:str(s.default_value)for s in n.inputs if hasattr(s,'default_value')and not s.is_linked},
                        'links':[(l.from_node.name,l.from_socket.name,l.to_socket.name)for s in n.inputs for l in s.links]}
                       for n in mat.node_tree.nodes]
(out/(key+'_cmb_nodes.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
