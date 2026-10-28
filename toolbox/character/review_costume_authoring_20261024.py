"""Render prepared source mesh without modifiers or runtime/native retargeting."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent;tag=sys.argv[sys.argv.index('--')+1]
folder=HERE/'skins_20261023'/tag
meta=json.loads((folder/'conversion.json').read_text(encoding='utf8'))
ref=json.loads((HERE/'skins_20261023/references'/meta['base']/'source.json').read_text(encoding='utf8'))
path=list((folder/'native').glob('*_original_hand_MMR.blend'))[0]
bpy.ops.wm.open_mainfile(filepath=str(path));mesh=bpy.data.objects[ref['mesh']]
for ob in bpy.context.scene.objects:ob.hide_render=ob!=mesh
mesh.hide_render=False
for modifier in mesh.modifiers:modifier.show_render=False
for material in mesh.data.materials:
    if not material or not material.use_nodes:continue
    base=material.node_tree.nodes.get('mmd_base_tex')
    if base and base.image:
        nodes=material.node_tree.nodes;bs=nodes.new('ShaderNodeBsdfPrincipled');out=nodes.new('ShaderNodeOutputMaterial')
        material.node_tree.links.new(base.outputs['Color'],bs.inputs['Base Color']);material.node_tree.links.new(bs.outputs[0],out.inputs[0]);out.is_active_output=True
        bs.inputs['Roughness'].default_value=.75
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12
scene.render.resolution_x=720;scene.render.resolution_y=840;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('SourceReview');scene.world.use_nodes=True
world_nodes=scene.world.node_tree.nodes;bg=world_nodes.new('ShaderNodeBackground');bg.inputs[0].default_value=(.18,.18,.18,1)
wo=world_nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs[0],wo.inputs[0])
camera_data=bpy.data.cameras.new('SourceReview');camera=bpy.data.objects.new('SourceReview',camera_data);bpy.context.collection.objects.link(camera)
camera_data.type='ORTHO';camera_data.ortho_scale=1.65;scene.camera=camera
target=Vector((0,0,1.0))
for name,position,energy in [('key',(1,-3,3),400),('fill',(-2,-1,2),200)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='DISK';data.size=3
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);ob.location=position;ob.rotation_euler=(target-ob.location).to_track_quat('-Z','Y').to_euler()
dest=HERE/'hand_repair_20261024'/tag/'authoring_source';dest.mkdir(parents=True,exist_ok=True)
for view,position in [('front',(0,-3,1)),('side',(3,0,1))]:
    camera.location=position;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(dest/(view+'.png'));bpy.ops.render.render(write_still=True)
print('AUTHORING_REVIEW_DONE',dest,flush=True)
