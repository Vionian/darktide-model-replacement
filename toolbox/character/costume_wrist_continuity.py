"""Join authored forearms to MMR palms without moving engine contact nodes."""
import numpy as np
from mathutils import Vector

def describe(source, native, names, root_map, palm_maps):
    rows=[];inverse=np.linalg.inv(np.asarray(root_map))
    for side in ('left','right'):
        e,h=[names['j_'+side+part] for part in ('forearm','hand')]
        a,z=[np.asarray(source[i].translation,dtype=float)for i in (e,h)]
        ta,tz=[np.asarray(native[i].translation,dtype=float)for i in (e,h)]
        axis=z-a;length=np.linalg.norm(axis);axis/=length
        target=tz-ta;target_length=np.linalg.norm(target)
        rot=np.asarray(Vector(axis).rotation_difference(Vector(target/target_length)).to_matrix())
        linear=rot@(np.eye(3)+(target_length/length-1)*np.outer(axis,axis))
        affine=np.eye(4);affine[:3,:3]=linear;affine[:3,3]=ta-linear@a
        old=np.asarray(native[e]@source[e].inverted()@root_map)
        rows.append(dict(side=side,elbow=(inverse@np.r_[a,1])[:3].tolist(),
                         wrist=(inverse@np.r_[z,1])[:3].tolist(),
                         forearm_map=(affine@np.asarray(root_map)).tolist(),
                         old_forearm_map=old.tolist(),
                         palm_map=np.asarray(palm_maps['j_'+side+'hand']).tolist()))
    return rows

def apply(source_positions, result, targets, rows, mesh):
    ji,jw,arm,points,normals=result
    for row in rows:
        side=row['side'];a=np.asarray(row['elbow']);z=np.asarray(row['wrist'])
        axis=z-a;length=np.linalg.norm(axis);axis/=length
        axial=(source_positions-a)@axis
        radial=np.linalg.norm(source_positions-a-axial[:,None]*axis,axis=1)
        ps=[p for p,n in targets.items()if n=='j_'+side+'forearm']
        mass=np.where(np.isin(ji,ps),jw,0).sum(1)
        digits=[p for p,n in targets.items()if n.startswith('j_'+side+'hand')and n!='j_'+side+'hand']
        digit_mass=np.where(np.isin(ji,digits),jw,0).sum(1)
        selected=(mass>1e-5)&(axial>0)&(axial<length*1.3)&(radial<length*.6)
        ids=np.flatnonzero(selected)
        if not len(ids):continue
        t=np.clip((axial[ids]/length-.40)/.60,0,1);t=t*t*(3-2*t)
        f=np.asarray(row['forearm_map']);h=np.asarray(row['palm_map'])
        p=source_positions[ids]
        continuous=(p@f[:3,:3].T+f[:3,3])*(1-t[:,None])+(p@h[:3,:3].T+h[:3,3])*t[:,None]
        old=np.asarray(row['old_forearm_map']);previous=p@old[:3,:3].T+old[:3,3]
        fade=np.clip(axial[ids]/(length*.15),0,1);fade=fade*fade*(3-2*fade)
        influence=mass[ids]*fade
        delta=influence[:,None]*(continuous-previous)
        points[ids]+=delta
        normal_f=np.linalg.inv(f[:3,:3]).T;normal_h=np.linalg.inv(h[:3,:3]).T
        correction=normal_f[None]*(1-t[:,None,None])+normal_h[None]*t[:,None,None]-np.linalg.inv(old[:3,:3]).T[None]
        normals[ids]+=influence[:,None,None]*correction
        print('COSTUME_WRIST_CONTINUITY',side,len(ids),float(np.linalg.norm(delta,axis=1).max()))
        for mi,mat in enumerate(mesh.data.materials):
            if not mat or mat.get('costume_rigid_wrist')!=side:continue
            ids=np.array(sorted({v for face in mesh.data.polygons if face.material_index==mi for v in face.vertices}))
            if not len(ids):continue
            center=source_positions[ids].mean(0)
            t=float(np.clip(((center-a)@axis/length-.4)/.6,0,1));t=t*t*(3-2*t)
            anchor=(f[:3,:3]@center+f[:3,3])*(1-t)+(h[:3,:3]@center+h[:3,3])*t
            u,s,vt=np.linalg.svd(f[:3,:3]);rotation=u@vt
            points[ids]=(source_positions[ids]-center)@rotation.T+anchor
            normals[ids]=rotation
            palette=next(p for p,n in targets.items()if n=='j_'+side+'forearm')
            ji[ids]=0;jw[ids]=0;ji[ids,0]=palette;jw[ids,0]=1;arm[ids]=1
            print('COSTUME_RIGID_WRIST_ACCESSORY',side,len(ids),'unit-source-scale')
    return result
