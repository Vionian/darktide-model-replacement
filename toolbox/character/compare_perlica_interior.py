"""Same serialized pose, cameras and lights for the waist-lining comparison."""
import json
import pathlib
import bpy
from mathutils import Vector

HERE = pathlib.Path(__file__).parent / 'perlica_interior_fix_20261022'
OUT = HERE / 'comparison'
OUT.mkdir(exist_ok=True)
views = None
report = {}
for stage, scene_path in (('before', 'before/low_run.blend'), ('after', 'after/run.blend')):
    bpy.ops.wm.open_mainfile(filepath=str(HERE / scene_path))
    scene = bpy.context.scene
    obj = bpy.data.objects['RoshiaPreUnitPreview']
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (lo + hi) * .5
    if views is None:
        views = {
            'inside_waist': (Vector((center.x, center.y-.04, lo.z+.90)),
                             Vector((center.x, center.y, lo.z+1.55)), 'PERSP', 25),
            'under_rear': (Vector((center.x, center.y-.48, lo.z+.48)),
                           Vector((center.x, center.y, lo.z+1.24)), 'PERSP', 25),
            'exterior_front': (Vector((center.x, center.y+2.8, lo.z+1.06)),
                               Vector((center.x, center.y, lo.z+1.06)), 'ORTHO', 2.70),
        }
        light_specs = [((center.x-.6, center.y+1.2, lo.z+2.3), 80, 2.0),
                       ((center.x+.9, center.y-.7, lo.z+1.5), 35, 1.8)]
        lighting_target = Vector((center.x, center.y, lo.z+1.1))
    for lamp in list(bpy.data.objects):
        if lamp.type == 'LIGHT':
            bpy.data.objects.remove(lamp, do_unlink=True)
    for index, (location, power, size) in enumerate(light_specs):
        data = bpy.data.lights.new('MatchedLight'+str(index), 'AREA')
        data.energy = power
        data.size = size
        lamp = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(lamp)
        lamp.location = location
        lamp.rotation_euler = (lighting_target-lamp.location).to_track_quat('-Z','Y').to_euler()
    world = bpy.data.worlds.new('MatchedWorld')
    world.use_nodes = True
    world.node_tree.nodes.clear()
    background = world.node_tree.nodes.new('ShaderNodeBackground')
    output = world.node_tree.nodes.new('ShaderNodeOutputWorld')
    world.node_tree.links.new(background.outputs['Background'], output.inputs['Surface'])
    background.inputs['Color'].default_value = (.16,.18,.20,1)
    background.inputs['Strength'].default_value = .30
    scene.world = world
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = .2
    scene.view_settings.gamma = 1
    scene.render.resolution_x = 760
    scene.render.resolution_y = 920
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = 48
    scene.camera.data.clip_start = .01
    for material in obj.data.materials:
        material.use_backface_culling = True
    for name, (location, target, kind, value) in views.items():
        scene.camera.data.type = kind
        if kind == 'PERSP': scene.camera.data.lens = value
        else: scene.camera.data.ortho_scale = value
        scene.camera.location = location
        scene.camera.rotation_euler = (target-location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = str(OUT / (stage+'_'+name+'.png'))
        bpy.ops.render.render(write_still=True)
    report[stage] = dict(bounds=[list(lo),list(hi)], source_scene=scene_path)
report.update(views={k:[list(a),list(b),c,d] for k,(a,b,c,d) in views.items()},
              lights=light_specs, gameplay_verified=False)
(OUT/'settings.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')
print('MATCHED_PERLICA_COMPARISON', str(OUT))
