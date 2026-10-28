from pathlib import Path
import bpy,sys,json,numpy as np,bmesh
from mathutils import Vector
HERE=Path(__file__).resolve().parent
tag=sys.argv[sys.argv.index('--')+1]
source=HERE/'si_costumes'/tag/(tag+'.blend')if tag.startswith('si_')else HERE/'skins_20261023'/tag/(tag+'.blend')
base='si'if tag.startswith('si_')else json.loads((source.parent/'conversion.json').read_text())['base']
meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(source))
mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
filtered='--filtered'in sys.argv
fitted='--fitted'in sys.argv
if filtered:
 data=np.load(HERE/'hand_repair_20261024'/tag/'filter_source_diagnostic/actual_source_face_selection.npz')
 geometry=bpy.data.meshes.new('Actual selected source triangles')
 geometry.from_pydata(data['fitted_positions']if fitted else data['source_positions'],[],data['faces']);geometry.update()
 mesh=bpy.data.objects.new('Actual selected source triangles',geometry);bpy.context.collection.objects.link(mesh)
 material=bpy.data.materials.new('Diagnostic gold');material.diffuse_color=(.65,.3,.1,1);geometry.materials.append(material)
for obj in bpy.context.scene.objects:obj.hide_render=obj!=mesh
for modifier in mesh.modifiers:modifier.show_render=False
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16
scene.render.resolution_x=720;scene.render.resolution_y=840;scene.render.resolution_percentage=100
scene.world.color=(.12,.12,.12)
camera=bpy.data.objects.new('SourceInspectionCamera',bpy.data.cameras.new('SourceInspectionCamera'));scene.collection.objects.link(camera);scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=.42
light=bpy.data.objects.new('SourceInspectionLight',bpy.data.lights.new('SourceInspectionLight','AREA'));scene.collection.objects.link(light);light.data.energy=25;light.data.shape='DISK';light.data.size=.7
out=HERE/'hand_repair_20261024'/tag/('fitted_source_sleeve'if fitted else('filtered_source_sleeve'if filtered else'source_sleeve'));out.mkdir(exist_ok=True)
for side in ('L','R'):
 wrist=arm.matrix_world@arm.data.bones['手首.'+side].head_local
 elbow=arm.matrix_world@arm.data.bones['ひじ.'+side].head_local
 center=wrist*.7+elbow*.3
 if fitted:
  index=np.argmin(np.linalg.norm(data['source_positions']-np.array(center),axis=1));center=Vector(data['fitted_positions'][index])
 for view,y in [('front',-1),('back',1)]:
  camera.location=center+(Vector((1 if side=='L'else -1,y*.08,.4)).normalized()*1.5 if fitted else Vector((0,y*.8,.15)));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
  camera.data.clip_start=.001
  light.location=center+Vector((.2,y*.5,.5));light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(out/(side+'_'+view+'.png'));bpy.ops.render.render(write_still=True)
print('SOURCE_SLEEVE_RENDERED',tag)
