"""Fit actual source arm segments to native endpoints, retaining native binds.

The former rigid maps aligned only each segment's head. Different source/native
lengths left the forearm's wrist endpoint separated from the fitted palm.
This is a bind-map correction derived from those exact joint pairs, not an
additive seam displacement or a guessed wrist offset.
"""
import json
from pathlib import Path
import numpy as np
from mathutils import Matrix,Vector

def apply(b, source, desired, names, root_map, maps, first_person, parents=None, helpers=()):
    rows=[]
    root=np.asarray(root_map,dtype=float)
    root_inverse=np.linalg.inv(root)
    for side in ('left','right'):
        for start,end in (('forearm','hand'),('arm','forearm')):
            name='j_'+side+start
            i,j=names[name],names['j_'+side+end]
            a,z=np.asarray(source[i].translation),np.asarray(source[j].translation)
            ta,tz=np.asarray(desired[i].translation),np.asarray(desired[j].translation)
            axis=z-a; length=np.linalg.norm(axis); target=tz-ta
            target_length=np.linalg.norm(target)
            if min(length,target_length)<1e-7:raise ValueError(('Zero arm segment',name))
            axis=axis/length
            old=np.asarray(maps[name],dtype=float)
            q=root_inverse@np.r_[z,1.]
            before=old@q
            # Match the entire shared joint plane, not merely its centre.
            # A unit-width forearm next to a 1.36x MMR palm left a narrow wrist
            # and an incorrectly fitting watch despite zero endpoint error.
            following=np.asarray(maps['j_'+side+end],dtype=float)@root_inverse
            plane=np.eye(3)-np.outer(axis,axis)
            if start=='forearm':
                linear=np.outer(target/length,axis)+following[:3,:3]@plane
            else:
                rotation=np.asarray(desired[i].to_quaternion().to_matrix() @ source[i].to_quaternion().to_matrix().transposed())
                correction=np.asarray(Vector(rotation@axis).rotation_difference(Vector(target/target_length)).to_matrix())
                linear=correction@rotation@(np.eye(3)+(target_length/length-1)*np.outer(axis,axis))
            affine=np.eye(4);affine[:3,:3]=linear;affine[:3,3]=ta-linear@a
            fitted=affine@root
            residual=float(np.linalg.norm((fitted@q)[:3]-tz))
            assert residual<2e-6,(name,residual)
            assert np.linalg.det(linear)>0,(name,'reflection')
            maps[name]=fitted.astype(np.float32)
            shared=(following@np.r_[z,1.])[:3]
            plane_error=float(np.max(np.abs((linear-following[:3,:3])@plane)))
            assert np.linalg.norm(shared-tz)<2e-6,(name,'Following pivot mismatch')
            if start=='forearm':assert plane_error<1e-6,(name,'Discontinuous wrist cross-section')
            rows.append(dict(joint=name,source_length_m=float(length),native_length_m=float(target_length),
                measured_axial_scale=float(target_length/length),
                previous_endpoint_error_mm=float(np.linalg.norm(before[:3]-tz)*1000),
                fitted_endpoint_error_mm=residual*1000,
                transverse_method='exact following MMR palm joint plane' if start=='forearm' else 'source upper-arm cross-section with measured axial length',
                shared_plane_jacobian_error=plane_error,
                fitted_singular_scales=np.linalg.svd(linear)[1].tolist(),
                source_axis=axis.tolist(),native_runtime_nodes_unchanged=True))
    support_rows=[]
    if not first_person:
        # Body upper-arm weights are remapped to compact shoulder supports,
        # not j_leftarm/j_rightarm. Validate and fit the path actually exported.
        for side,support in (('left','qianxia_sleeve_126'),('right','qianxia_sleeve_127')):
            if support not in maps:continue
            i,j=names['j_'+side+'arm'],names['j_'+side+'forearm']
            a,z=np.array(source[i].translation),np.array(source[j].translation)
            ta,tz=np.array(desired[names[support]].translation),np.array(desired[j].translation)
            axis=z-a;length=np.linalg.norm(axis);axis/=length
            target=tz-ta;target_length=np.linalg.norm(target)
            old=np.array(maps[support],float);q=root_inverse@np.r_[z,1.]
            before=float(np.linalg.norm((old@q)[:3]-tz))
            rotation=np.array(desired[names[support]].to_quaternion().to_matrix()@source[i].to_quaternion().to_matrix().transposed())
            correction=np.array(Vector(rotation@axis).rotation_difference(Vector(target/target_length)).to_matrix())
            linear=correction@rotation@(np.eye(3)+(target_length/length-1)*np.outer(axis,axis))
            affine=np.eye(4);affine[:3,:3]=linear;affine[:3,3]=ta-linear@a
            maps[support]=(affine@root).astype(np.float32)
            residual=float(np.linalg.norm((maps[support]@q)[:3]-tz))
            assert residual<2e-6,(support,'Actual upper-arm binding misses elbow',residual)
            support_rows.append(dict(node=support,previous_endpoint_error_mm=before*1000,
                fitted_endpoint_error_mm=residual*1000,measured_axial_scale=float(target_length/length)))
    helper_rows=[]
    if parents:
        inverse={i:n for n,i in names.items()}
        anchors={'j_'+s+p for s in ('left','right')for p in ('arm','forearm','hand')}
        for helper in helpers:
            name=helper['node'];i=names[name];j=parents.get(i)
            seen=set()
            while j in parents and inverse.get(j)not in anchors and j not in seen:
                seen.add(j);j=parents.get(j)
            anchor=inverse.get(j)
            if anchor not in anchors:continue
            if not first_person and anchor.endswith('arm') and not anchor.endswith('forearm'):
                support='qianxia_sleeve_'+('126'if 'left'in anchor else '127')
                if support in maps:
                    anchor=support;parents[i]=names[support];helper['parent']=support
            affine=np.asarray(maps[anchor],float)@root_inverse
            src=np.asarray(source[i],float);position=(affine@src)[:3,3]
            u,scales,vt=np.linalg.svd(affine[:3,:3]@src[:3,:3]);rotation=u@vt
            assert np.linalg.det(rotation)>0,(name,'Reflected garment helper')
            w=Matrix(rotation.tolist()).to_4x4();w.translation=position
            desired[i]=w;maps[name]=np.asarray(affine@root,dtype=np.float32)
            factor=float(np.linalg.norm(affine[:3,:3]@src[:3,2]))
            helper['length']*=factor
            helper_rows.append(dict(node=name,source_bone=helper['source_bone'],anchor=anchor,
                length_scale=factor,rest_position=position.tolist()))
    report=dict(profile=getattr(b,'COSTUME_PROFILE',b.MODEL_PROFILE),
        method='exact source/native endpoints and continuous MMR joint-plane bind maps; no additive wrist compensation',
        first_person=first_person,rows=rows,shoulder_supports=support_rows,garment_helpers=helper_rows,gameplay_verified=False)
    folder=getattr(b,'HAND_AUTHORING_OUTPUT',None)
    if folder:
        (Path(folder)/('native_arm_segment_'+('arms' if first_person else 'body')+'.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
    print('COSTUME_NATIVE_ARM_SEGMENTS',json.dumps(report))
    return maps
