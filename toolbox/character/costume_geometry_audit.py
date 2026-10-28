"""Source-to-export hand completeness and rigid accessory readback evidence."""
import json
from pathlib import Path
import numpy as np

def rigid_accessories(b,mesh,groups,bind):
    source=None;rows=[]
    for mi,mat in enumerate(mesh.data.materials):
        side=mat.get('costume_rigid_wrist') if mat else None
        if not side:continue
        ids=np.array(sorted({v for p in mesh.data.polygons if p.material_index==mi for v in p.vertices}))
        if not len(ids):continue
        if source is None:
            source=np.array([b.source_coordinate3()@(mesh.matrix_world@v.co) for v in mesh.data.vertices])
        g=groups[mi];points=g['retargeted_positions']
        linear=np.asarray(bind['j_'+side+'forearm'])[:3,:3]
        arm=b.bpy.data.objects[b.ARMATURE_OBJECT_NAME]
        suffix='.L' if side=='left' else '.R'
        a=b.source_coordinate3()@(arm.matrix_world@arm.data.bones['ひじ'+suffix].head_local)
        z=b.source_coordinate3()@(arm.matrix_world@arm.data.bones['手首'+suffix].head_local)
        axis=np.array(z-a,dtype=float,copy=True);axis/=np.linalg.norm(axis)
        axial_scale=float(np.linalg.norm(linear@axis))
        # The original band clearance follows the same measured wrist plane.
        # Remove only segment-length stretching along the band axis; a rigid
        # unscaled watch would no longer fit the expanded native-contact wrist.
        fitted=linear@(np.eye(3)+(1/axial_scale-1)*np.outer(axis,axis))
        assert np.linalg.det(fitted)>0,'Reflected watch fit'
        before=points[ids].copy();center=before.mean(0);original=source[ids]-source[ids].mean(0)
        points[ids]=original@fitted.T+center
        selected=g['triangles']
        correction=np.linalg.inv(fitted).T@linear.T
        g['normals'][selected]=g['normals'][selected]@correction.T
        error=float(np.max(np.abs((points[ids]-center)@np.linalg.inv(fitted).T-original)))
        assert error<1e-6,('Watch dimensions changed',error)
        rows.append(dict(material=mat.name,vertices=len(ids),
            previous_singular_scales=np.linalg.svd(linear)[1].tolist(),
            fitted_singular_scales=np.linalg.svd(fitted)[1].tolist(),axial_scale=1.,
            shape_error_mm=error*1000,method='original watch clearance follows measured MMR wrist plane; source band axial width retained'))
    return rows

def record(b,mesh,groups,targets,arm_only,accessories=()):
    if not getattr(b,'HAND_AUTHORING_OUTPUT',None):return
    rows=[]
    for i,g in enumerate(groups):
        material=mesh.data.materials[i]
        all_tri=g['vertices']
        # This runs before reverse-face expansion, so one row is one authored
        # source triangle with its existing source/UV/weight identity.
        n=len(mesh.data.loop_triangles);tri=all_tri[:n]
        own=np.array([t.material_index==i for t in mesh.data.loop_triangles])
        handpal=[p for p,name in targets.items() if name.startswith(('j_lefthand','j_righthand','j_leftinhand','j_rightinhand'))]
        handmass=np.where(np.isin(g['joint_indices'],handpal),g['joint_weights'],0).sum(1)
        expected=np.flatnonzero(own&(handmass[tri].min(1)>.8))
        selected=g['triangles'];present=np.intersect1d(expected,selected)
        actual=g['retargeted_positions'][all_tri[selected]]
        assert np.isfinite(actual).all(),('Nonfinite geometry',material.name)
        twice_area=np.linalg.norm(np.cross(actual[:,1]-actual[:,0],actual[:,2]-actual[:,0]),axis=1) if len(actual) else np.empty(0)
        if len(expected):assert len(expected)==len(present),('Hand triangles omitted',material.name,len(expected),len(present))
        if len(expected) or len(selected):
            rows.append(dict(material=material.name,source_triangles=int(own.sum()),
                exported_front_triangles=len(selected),source_high_hand_weight_triangles=len(expected),
                exported_high_hand_weight_triangles=len(present),
                zero_area_front_triangles=int((twice_area<1e-12).sum()),
                skin=bool(material.get('costume_skin'))))
    report=dict(profile=getattr(b,'COSTUME_PROFILE',b.MODEL_PROFILE),first_person=arm_only,
        source_hand_topology_retained=True,no_cross_character_digit_weight_override=True,
        materials=rows,rigid_accessories=list(accessories),gameplay_verified=False)
    (Path(b.HAND_AUTHORING_OUTPUT)/('export_geometry_'+('arms' if arm_only else 'body')+'.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
    print('COSTUME_HAND_GEOMETRY_AUDIT',report['profile'],'arms' if arm_only else 'body',len(rows))
