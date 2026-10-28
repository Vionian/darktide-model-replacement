"""Generate local synthetic build fixtures; no third-party character/weapon art."""
import json
from pathlib import Path
import sys
import bpy

job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
sys.path.insert(0, job['addon_parent'])
bpy.ops.preferences.addon_enable(module='darktide_assets')
preferences = bpy.context.preferences.addons['darktide_assets'].preferences
preferences.game_extract_folder = job['extract']
output = Path(job['output'])
output.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
assert bpy.ops.darktide.new_starter_asset(preset='human', region='body') == {'FINISHED'}
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        for key in list(obj.keys()):
            if key.startswith('darktide_'):
                del obj[key]
    if obj.type == 'MESH':
        for mat in obj.data.materials:
            mat.use_nodes = True
            mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.1, .3, .8, 1)
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'character.blend'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .4))
weapon = bpy.context.object
weapon.name = 'synthetic_blade'
weapon.scale = (.025, .04, 1)
material = bpy.data.materials.new('synthetic_blade_material')
material.use_nodes = True
material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.3, .4, .6, 1)
weapon.data.materials.append(material)
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'weapon.blend'))
print('SYNTHETIC_FIXTURES_WRITTEN')
