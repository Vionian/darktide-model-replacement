"""Unlit UV diagnostic of restored source draws, before any Darktide rig fit."""
import bpy,pathlib,sys
from mathutils import Vector
HERE=pathlib.Path(__file__).parent;OUT=HERE/'si_ink_mist'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'si_ink_mist.blend'))
obj=bpy.data.objects['祀_mesh']
for ob in bpy.context.scene.objects:ob.hide_render=ob!=obj
for mat in obj.data.materials:
    nt=mat.node_tree
    node=nt.nodes.get('mmd_base_tex')
    if not node or not node.image:continue
    im=node.image;nt.nodes.clear()
    tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
    emit=nt.nodes.new('ShaderNodeEmission');nt.links.new(tex.outputs['Color'],emit.inputs['Color'])
    output=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(emit.outputs[0],output.inputs['Surface'])
    if mat.get('ink_mist_alpha'):
        clip=nt.nodes.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.15
        nt.links.new(tex.outputs['Alpha'],clip.inputs[0])
        transparent=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(clip.outputs[0],mix.inputs[0]);nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(emit.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],output.inputs[0])
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=800;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.film_transparent=False;scene.world.color=(.03,.03,.03)
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
camdata=bpy.data.cameras.new('UV diagnostic');cam=bpy.data.objects.new('UV diagnostic',camdata);scene.collection.objects.link(cam)
cam.location=(0,-3,.95);cam.rotation_euler=(Vector((0,0,.9))-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=2.0;scene.camera=cam
scene.render.filepath=str(OUT/'source_uv_diagnostic.png');bpy.ops.render.render(write_still=True)
