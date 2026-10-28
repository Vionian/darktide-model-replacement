"""Retract inspected detached FP cuffs to their measured source wrist plane.

The original complete sleeve stays unchanged in third person. No source or
exported triangles are deleted, no hand vertices are moved, and the positive
axial scale is derived from the actual elbow, wrist and sleeve endpoint.
"""
import json
from pathlib import Path
import numpy as np

def apply(b,mesh,groups,targets,bind,arm_only):
    if not arm_only:return
    arm=b.bpy.data.objects[b.ARMATURE_OBJECT_NAME]
    source=np.asarray([b.source_coordinate3()@(mesh.matrix_world@v.co)for v in mesh.data.vertices],float)
    from costume_anatomical_domains import nearest,from_armature,is_arm
    raw_source=np.asarray([mesh.matrix_world@v.co for v in mesh.data.vertices],float)
    arm_region=np.array([is_arm(str(n))for n in nearest(raw_source,from_armature(arm))])
    rows=[]
    for mi,mat in enumerate(mesh.data.materials):
        if not mat or not mat.get('costume_arm_garment'):continue
        group=groups[mi]
        own=np.array(sorted({v for f in mesh.data.polygons if f.material_index==mi for v in f.vertices}),int)
        for side,suffix in (('left','.L'),('right','.R')):
            elbow=np.asarray(b.source_coordinate3()@(arm.matrix_world@arm.data.bones['ひじ'+suffix].head_local),float)
            wrist=np.asarray(b.source_coordinate3()@(arm.matrix_world@arm.data.bones['手首'+suffix].head_local),float)
            # source_coordinate3 flips X/Y. Derive the side from the actual
            # converted landmark, rather than assuming Blender's X sign.
            ids=own[(source[own,0]*wrist[0]>0)&arm_region[own]]
            if not len(ids):continue
            axis=wrist-elbow;length=float(np.linalg.norm(axis));axis=axis/length
            axial=(source[ids]-elbow)@axis;end=float(axial.max())
            if end<=length:
                rows.append(dict(material=mat.name,side=side,vertices=len(ids),
                    source_elbow_to_wrist_mm=length*1000,source_elbow_to_cuff_tip_mm=end*1000,
                    measured_axial_scale=1.,status='source cuff already ends before wrist',
                    triangles_removed=0,hand_vertices_modified=0))
                continue
            scale=length/end
            assert 0<scale<=1
            compression=np.eye(3)+(scale-1)*np.outer(axis,axis)
            ji=group['joint_indices'][ids];ww=group['joint_weights'][ids]
            linear=np.zeros((len(ids),3,3))
            for slot in range(4):
                for palette in np.unique(ji[:,slot]):
                    match=ji[:,slot]==palette
                    if palette not in targets:continue
                    linear[match]+=ww[match,slot,None,None]*np.asarray(bind[targets[int(palette)]])[:3,:3]
            assert np.all(np.linalg.det(linear)>1e-8),('Singular sleeve bind',mat.name,side)
            delta=(scale-1)*axial[:,None]*axis
            group['retargeted_positions'][ids]+=np.einsum('nij,nj->ni',linear,delta)
            jacobian=linear@compression@np.linalg.inv(linear)
            normals=np.linalg.inv(jacobian).transpose(0,2,1)
            by_vertex={int(v):normals[k]for k,v in enumerate(ids)}
            selected=group['triangles'];tri=group['vertices'][selected]
            for ti,corners in zip(selected,tri):
                for ci,vi in enumerate(corners):
                    if int(vi)in by_vertex:group['normals'][ti,ci]=by_vertex[int(vi)]@group['normals'][ti,ci]
            rows.append(dict(material=mat.name,side=side,source_elbow_to_wrist_mm=length*1000,
                source_elbow_to_cuff_tip_mm=end*1000,measured_axial_scale=scale,
                vertices=len(ids),status='retracted to measured wrist plane',
                triangles_removed=0,hand_vertices_modified=0))
    if rows and getattr(b,'HAND_AUTHORING_OUTPUT',None):
        (Path(b.HAND_AUTHORING_OUTPUT)/'first_person_cuff_fit.json').write_text(json.dumps(dict(
            profile=b.COSTUME_PROFILE,method='complete authored sleeve axially retracts from measured elbow to measured wrist plane',
            rows=rows,gameplay_verified=False),indent=2),encoding='utf8')
