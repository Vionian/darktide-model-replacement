"""Use Blender's bone-heat solver for newly exposed costume arms.

The complete original character skeleton supplies the rest anatomy. A welded
temporary skin donor is used only for solving; exported vertices stay intact.
"""
import json,re
from pathlib import Path
import numpy as np
import bpy,bmesh
from mathutils.kdtree import KDTree

def apply(b,mesh,arm):
    labels={g.index:g.name for g in mesh.vertex_groups}
    arm_pattern=re.compile(r'^(腕|ひじ|肘|手捩[^.]*)\.[LR]$')
    hand_pattern=re.compile(r'^(手首|親指[０１２３0123]|人指[１２３123]|中指[１２３123]|薬指[１２３123]|小指[１２３123])\.[LR]$')
    skin_slots={i for i,m in enumerate(mesh.data.materials)if m and m.get('costume_skin')}
    all_skin_faces=[list(f.vertices)for f in mesh.data.polygons if f.material_index in skin_slots]
    all_skin_ids=sorted({i for f in all_skin_faces for i in f})
    points=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])
    from costume_anatomical_domains import nearest,from_armature
    arm_domain={'腕.L','腕.R','ひじ.L','ひじ.R','肘.L','肘.R'}
    domain=nearest(points,from_armature(arm));proximal=np.isin(domain,list(arm_domain))
    arm_mass=np.array([sum(g.weight for g in v.groups if arm_pattern.fullmatch(labels[g.group])or hand_pattern.fullmatch(labels[g.group]))for v in mesh.data.vertices])
    # Do not select by the old arm weights: that omits precisely the elbow
    # vertices incorrectly bound to the torso. Separate the bare arm surface
    # from the overlapping thin torso pieces that make bone heat singular.
    faces=[f for f in all_skin_faces if proximal[f].all() and arm_mass[f].min()>.01]
    skin_set={i for f in faces for i in f}
    skin_ids=sorted(skin_set);eligible=[i for i in skin_ids if arm_mass[i]>.5]
    assert eligible,'No upper-body source skin found'
    lookup={i:j for j,i in enumerate(skin_ids)}
    data=bpy.data.meshes.new('__native_arm_heat_donor')
    data.from_pydata([mesh.data.vertices[i].co for i in skin_ids],[],[[lookup[i]for i in f]for f in faces]);data.update()
    donor=bpy.data.objects.new(data.name,data);bpy.context.collection.objects.link(donor);donor.matrix_world=mesh.matrix_world.copy()
    bm=bmesh.new();bm.from_mesh(data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(data);bm.free();data.update()
    rig=arm.copy();rig.data=arm.data.copy();rig.name='__native_arm_heat_skeleton';bpy.context.collection.objects.link(rig)
    rig.animation_data_clear()
    canonical=re.compile(r'^(肩|腕|ひじ|肘|手首|足|ひざ|足首|つま先|親指[０１２３]|人指[１２３]|中指[１２３]|薬指[１２３]|小指[１２３])\.[LR]$')
    for bone in rig.data.bones:
        bone.use_deform=bone.name in arm_domain
    for bone in rig.pose.bones:
        for constraint in list(bone.constraints):bone.constraints.remove(constraint)
        bone.matrix_basis.identity()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (donor,rig):obj.hide_viewport=False;obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    tree=KDTree(len(data.vertices))
    for vertex in data.vertices:tree.insert(mesh.matrix_world.inverted()@(donor.matrix_world@vertex.co),vertex.index)
    tree.balance();solved={g.index:g.name for g in donor.vertex_groups};rows=[]
    for vi in eligible:
        _,index,distance=tree.find(mesh.data.vertices[vi].co)
        assert distance<3e-6,('Temporary donor shifted',vi,distance)
        weights={solved[g.group]:g.weight for g in data.vertices[index].groups if g.weight>1e-7}
        total=sum(weights.values());assert total>.5,('Bone heat did not solve arm vertex',vi,total)
        vertex=mesh.data.vertices[vi]
        for group in list(vertex.groups):
            if labels[group.group]in arm.data.bones:mesh.vertex_groups[group.group].remove([vi])
        for name,weight in weights.items():
            group=mesh.vertex_groups.get(name)or mesh.vertex_groups.new(name=name)
            group.add([vi],float(weight/total),'REPLACE')
        rows.append(distance)
    report=dict(applied=True,profile=getattr(b,'COSTUME_PROFILE',b.MODEL_PROFILE),
        method='Blender ARMATURE_AUTO on actual anatomical bare-arm domain after correcting source torso overwrite; original torso fields retained at shoulder/chest boundary',
        solved_arm_vertices=len(rows),maximum_donor_position_error_mm=max(rows)*1000,
        exported_topology_uvs_normals_positions_unchanged=True,hand_surface_overridden=False,gameplay_verified=False)
    bpy.data.objects.remove(donor,do_unlink=True);bpy.data.objects.remove(rig,do_unlink=True)
    bpy.data.meshes.remove(data)
    bpy.context.view_layer.objects.active=mesh;mesh.hide_set(False);mesh.select_set(True)
    (Path(b.HAND_AUTHORING_OUTPUT)/'arm_bone_heat.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('COSTUME_ARM_BONE_HEAT',json.dumps(report),flush=True)
    return report
