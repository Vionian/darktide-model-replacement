"""Compact source shoulders with unchanged native elbow/wrist/finger drivers.

Two spare sleeve nodes deform the upper-arm mesh. They have no core children:
axial scale therefore cannot propagate into native forearms or weapon contacts.
"""
import numpy as np
from mathutils import Matrix, Vector


def add_supports(builder, rig, source, desired, parents, names, root_map):
    spine=names['j_spine2']
    torso_map=desired[spine] @ source[spine].inverted()
    definitions=[]
    remaps={}
    maps={}
    for side,node_name in [('left','qianxia_sleeve_126'),('right','qianxia_sleeve_127')]:
        index=names[node_name]
        if index in source or any(r['node']==node_name for r in rig['runtime_bones']):
            raise ValueError(f'Shoulder support slot already occupied: {node_name}')
        arm,shoulder,elbow=[names[f'j_{side}{part}']for part in ('arm','shoulder','forearm')]
        origin=torso_map @ source[arm].translation
        clavicle=torso_map @ source[shoulder].translation
        target=desired[elbow].translation
        axis=(target-origin).normalized()
        native_axis=(desired[elbow].translation-desired[arm].translation).normalized()
        rotation=native_axis.rotation_difference(axis).to_matrix() @ desired[arm].to_3x3()
        world=rotation.to_4x4();world.translation=origin
        length=(target-origin).length
        source_length=(source[elbow].translation-source[arm].translation).length
        stretch=Matrix.Diagonal(Vector((length/source_length,1,1,1)))
        maps[node_name]=np.asarray(world @ stretch @ source[arm].inverted() @ root_map,dtype=np.float32)
        desired[index]=world
        parents[index]=spine
        remaps[f'j_{side}arm']=node_name
        # Source clavicle vertices follow the compact torso, without adopting
        # the much wider template clavicle. Sleeves follow their arm support.
        for name,target_name in list(rig['source_to_target'].items()):
            if target_name==f'j_{side}arm':rig['source_to_target'][name]=node_name
            elif target_name==f'j_{side}shoulder':rig['source_to_target'][name]='j_spine2'
        definitions.append({
            'name':node_name,'parent':'j_spine2','driver_arm':f'j_{side}arm',
            'driver_shoulder':f'j_{side}shoulder','driver_elbow':f'j_{side}forearm',
            'clavicle_offset':list(desired[spine].inverted() @ clavicle),
            'arm_offset':list(desired[shoulder].to_3x3().transposed() @ (origin-clavicle)),
            'rest_length':length,'axis_sign':1 if side=='left' else -1,
            'rest_origin':list(origin),'native_origin':list(desired[arm].translation),
        })
    width=(Vector(definitions[0]['rest_origin'])-Vector(definitions[1]['rest_origin'])).length
    native_width=(Vector(definitions[0]['native_origin'])-Vector(definitions[1]['native_origin'])).length
    print('COMPACT_SHOULDERS',{'source_root_width':width,'native_root_width':native_width})
    return definitions,maps
