import bpy
bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\洛茜.blend')
arm=bpy.data.objects.get('洛茜_arm')
print('SOURCE_ACTIONS',len(bpy.data.actions))
print('ARMATURE_ANIMATION_DATA',bool(arm and arm.animation_data), 'ACTIVE',bool(arm and arm.animation_data and arm.animation_data.action))
