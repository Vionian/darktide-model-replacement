"""Continuous palm/finger rest fitting to the game's shared human hand rig.

Third-person hands may fit native landmarks. First-person hands use a rigid
source-hand fit and rest-aware local FK; native wrists remain weapon anchors.
"""
import numpy as np


def _palm_frame(wrist, index, middle, pinky):
    wrist = np.asarray(wrist, dtype=float)
    long_axis = np.asarray(middle, dtype=float) - wrist
    long_axis /= np.linalg.norm(long_axis)
    width_axis = np.asarray(pinky, dtype=float) - np.asarray(index, dtype=float)
    width_axis -= long_axis * np.dot(width_axis, long_axis)
    width_axis /= np.linalg.norm(width_axis)
    normal = np.cross(long_axis, width_axis)
    normal /= np.linalg.norm(normal)
    width_axis = np.cross(normal, long_axis)
    width_axis /= np.linalg.norm(width_axis)
    return np.column_stack((long_axis, width_axis, normal)), float(np.linalg.norm(
        np.asarray(pinky, dtype=float) - np.asarray(index, dtype=float)
    ))


def retarget_thumb_to_palm(source_palm, source_thumb, target_palm, target_thumb,
                           strength=0.70):
    """Fit the thumb to the destination palm without stretching it to target joints."""
    source_frame, source_width = _palm_frame(**source_palm)
    target_frame, target_width = _palm_frame(**target_palm)
    if source_width < 1e-8 or target_width < 1e-8:
        raise ValueError("Cannot fit a thumb from a degenerate palm frame")
    scale = target_width / source_width
    rotation = target_frame @ source_frame.T
    source_wrist = np.asarray(source_palm["wrist"], dtype=float)
    target_wrist = np.asarray(target_palm["wrist"], dtype=float)
    source_thumb = np.asarray(source_thumb, dtype=float)
    target_thumb = np.asarray(target_thumb, dtype=float)
    fitted = target_wrist + ((source_thumb - source_wrist) @ rotation.T) * scale
    result = target_thumb + (fitted - target_thumb) * strength
    return result, {
        "palm_scale": float(scale),
        "strength": float(strength),
        "source_thumb_length": float(np.linalg.norm(source_thumb[-1] - source_thumb[0])),
        "native_thumb_length": float(np.linalg.norm(target_thumb[-1] - target_thumb[0])),
        "fitted_thumb_length": float(np.linalg.norm(fitted[-1] - fitted[0])),
        "max_joint_shift": float(np.linalg.norm(result - target_thumb, axis=1).max()),
    }

def fit(source, target):
    source=np.asarray(source,dtype=float);target=np.asarray(target,dtype=float)
    origin=source[0].copy()
    scale=np.max(np.linalg.norm(source-origin,axis=1))
    x=(source-origin)/scale
    radius=np.linalg.norm(x[:,None]-x[None,:],axis=2)
    affine=np.column_stack((np.ones(len(x)),x))
    system=np.block([[radius**3,affine],[affine.T,np.zeros((4,4))]])
    coefficients=np.linalg.solve(system,np.vstack((target,np.zeros((4,3)))))
    result={'origin':origin,'scale':scale,'landmarks':x,'coefficients':coefficients}
    out,_=evaluate(result,source)
    error=np.linalg.norm(out-target,axis=1).max()
    if error>1e-6:raise ValueError(f'Hand rest fit error: {error}')
    result['landmark_error']=float(error)
    return result

def evaluate(warp, points):
    x=(np.asarray(points)-warp['origin'])/warp['scale']
    delta=x[:,None]-warp['landmarks'][None,:]
    radius=np.linalg.norm(delta,axis=2)
    c=warp['coefficients'];n=len(warp['landmarks'])
    value=radius**3@c[:n]+np.column_stack((np.ones(len(x)),x))@c[n:]
    # J[output,input], used for inverse-transpose normals.
    derivative=3*radius[:,:,None]*delta
    jac=(np.einsum('nki,ko->noi',derivative,c[:n])+c[n+1:].T)/warp['scale']
    return value,jac

def hand_warps(builder, original, desired, names, root_map):
    warps={}
    source={i:r['world'] for i,r in original['node_transforms'].items()}
    for side in ('left','right'):
        wrist=names[f'j_{side}hand']
        keys=[f'j_{side}hand']+[f'j_{side}hand{finger}{k}'for finger in ('thumb','index','middle','ring','pinky')for k in (1,2,3)]
        a=[np.array(source[names[k]].translation)for k in keys]
        b=[np.array(desired[names[k]].translation)for k in keys]
        # Endpoints beyond DIP keep the distal segments well constrained.
        finger_axes = {}
        for finger_index, finger in enumerate(('thumb','index','middle','ring','pinky')):
            i,j=[names[f'j_{side}hand{finger}{k}']for k in (2,3)]
            a.append(np.array(source[j].translation+(source[j].translation-source[i].translation)*.7))
            b.append(np.array(desired[j].translation+(desired[j].translation-desired[i].translation)*.7))
            first = 1 + finger_index * 3
            tip = 16 + finger_index
            finger_axes[finger] = (
                np.asarray(b[first], dtype=np.float64),
                np.asarray(b[tip], dtype=np.float64),
            )
        for points in (a,b):
            normal=np.cross(points[7]-points[0],points[13]-points[4]);normal/=np.linalg.norm(normal)
            # Preserve Roshia's hand thickness instead of inflating it to the
            # native gauntlet thickness. The extra landmarks constrain depth.
            for center in (points[0].copy(),(points[4]+points[13])*.5):
                points.extend((center+normal*.012,center-normal*.012))
        warp=fit(a,b)
        warp['finger_axes'] = finger_axes
        # Input vertex positions have not yet received root_map.
        warp['origin']-=np.array(root_map.translation)
        warps[side]=warp
    return warps
