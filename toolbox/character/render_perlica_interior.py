"""Repeat an underside-camera comparison from the same serialized pose."""
import bpy
import json
import pathlib
from mathutils import Vector

HERE = pathlib.Path(__file__).parent / 'perlica_interior_fix_20261022'
bpy.ops.wm.open_mainfile(filepath=str(HERE / 'before/low_run.blend'))
scene = bpy.context.scene
obj = bpy.data.objects['RoshiaPreUnitPreview']
p = [obj.matrix_world @ v.co for v in obj.data.vertices]
lo = Vector(tuple(min(v[i] for v in p) for i in range(3)))
hi = Vector(tuple(max(v[i] for v in p) for i in range(3)))
center = (lo + hi) * .5
scene.render.resolution_x = 900
scene.render.resolution_y = 1100
scene.eevee.taa_render_samples = 48
scene.camera.data.type = 'PERSP'
scene.camera.data.lens = 25
scene.camera.data.clip_start = .01
views = {'under_rear': (Vector((center.x, center.y - .48, lo.z + .48)),
                        Vector((center.x, center.y, lo.z + 1.24))),
         'under_close': (Vector((center.x + .14, center.y - .24, lo.z + .72)),
                         Vector((center.x, center.y, lo.z + 1.46))),
         'inside_waist': (Vector((center.x, center.y - .04, lo.z + .90)),
                          Vector((center.x, center.y, lo.z + 1.55)))}
for tag, (location, target) in views.items():
    if tag != 'inside_waist':
        continue
    scene.camera.location = location
    scene.camera.rotation_euler = (target - location).to_track_quat('-Z','Y').to_euler()
    for mode in ('current', 'body_backs', 'all_backs'):
        for mat in obj.data.materials:
            index = int(mat.name.rsplit('_', 1)[1])
            mat.use_backface_culling = not (mode == 'all_backs' or mode == 'body_backs' and index in (0,9,10))
        scene.render.filepath = str(HERE / f'{tag}_{mode}.png')
        bpy.ops.render.render(write_still=True)
print('UNDERSIDE_CAMERAS', json.dumps({k:[list(a),list(b)] for k,(a,b) in views.items()}))
