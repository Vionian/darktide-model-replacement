"""Bake EFMI garment masks into geometry; use the proven opaque native shader.

Only boundary triangles are refined. New points barycentrically interpolate the
authored position, normal, UV and skin weights; no rest-pose fitting is changed.
This intentionally approximates lace by small geometric openings, not blending.
"""
import numpy as np


def trim(positions, normals, uv, faces, indices, weights, alpha, cutoff,
         pixel_limit=6., max_depth=2):
    alpha=np.asarray(alpha,dtype=np.float32)
    height,width=alpha.shape
    # Conservative min/max bounds at successive mip levels. A mixed rectangle
    # may contain a uniform triangle, but a uniform rectangle is safe to accept.
    low=[alpha];high=[alpha]
    while min(low[-1].shape)>1:
        h,w=low[-1].shape
        # Source costumes may use cropped, non-power-of-two DDS sheets.
        # Edge padding preserves conservative bounds in the final mip texel.
        pad=((0,h%2),(0,w%2))
        a=np.pad(low[-1],pad,mode='edge');z=np.pad(high[-1],pad,mode='edge')
        hh,ww=a.shape
        low.append(a.reshape(hh//2,2,ww//2,2).min((1,3)))
        high.append(z.reshape(hh//2,2,ww//2,2).max((1,3)))

    def sample(q):
        x=q[...,0]*width-.5;y=(1-q[...,1])*height-.5
        ix=np.floor(x).astype(np.int64);iy=np.floor(y).astype(np.int64)
        fx=x-ix;fy=y-iy
        return ((1-fy)*((1-fx)*alpha[iy%height,ix%width]+fx*alpha[iy%height,(ix+1)%width])+
                fy*((1-fx)*alpha[(iy+1)%height,ix%width]+fx*alpha[(iy+1)%height,(ix+1)%width]))

    def bounds(q):
        pixels=q*np.array([width,-height])+np.array([0,height])
        pmin=pixels.min(1)-1;pmax=pixels.max(1)+1
        level=np.ceil(np.log2(np.maximum((pmax-pmin).max(1),1))).astype(int)
        level=np.minimum(level,len(low)-1)
        lo=np.empty(len(q));hi=np.empty(len(q))
        for k in np.unique(level):
            use=level==k;size=2**k;hh,ww=low[k].shape
            a=np.floor(pmin[use]/size).astype(int);z=np.floor(pmax[use]/size).astype(int)
            corners=[(a[:,0],a[:,1]),(a[:,0],z[:,1]),(z[:,0],a[:,1]),(z[:,0],z[:,1])]
            lo[use]=np.minimum.reduce([low[k][y%hh,x%ww]for x,y in corners])
            hi[use]=np.maximum.reduce([high[k][y%hh,x%ww]for x,y in corners])
            # A rectangle spanning an entire repeat tile needs global bounds.
            wide=((pmax[use]-pmin[use])>=np.array([width,height])).any(1)
            if wide.any():
                ids=np.flatnonzero(use)[wide];lo[ids]=alpha.min();hi[ids]=alpha.max()
        return lo,hi,(pmax-pmin).max(1)

    pending_ids=np.arange(len(faces));pending_bary=np.broadcast_to(np.eye(3),(len(faces),3,3)).copy()
    accepted_ids=[];accepted_bary=[];dropped=0;clipped=0
    for depth in range(max_depth+1):
        if not len(pending_ids):break
        q=np.einsum('nvc,ncd->nvd',pending_bary,uv[faces[pending_ids]])
        lo,hi,span=bounds(q)
        inside=lo>=cutoff;outside=hi<cutoff
        # Texture-rectangle bounds overestimate very narrow triangles. Seven
        # footprint probes avoid refining the entire lace panel just because
        # its UV rectangle also touches a different atlas island. Tiny internal
        # lace holes remain an explicit geometric approximation.
        probes=sample(np.concatenate((q,(q+np.roll(q,-1,axis=1))*.5,q.mean(1)[:,None]),axis=1))
        inside|=probes.min(1)>cutoff+1e-5
        if depth>=2:outside|=probes.max(1)<cutoff-1e-5
        if inside.any():
            accepted_ids.append(pending_ids[inside]);accepted_bary.append(pending_bary[inside])
        dropped+=int(outside.sum())
        mixed=~(inside|outside)
        ids=pending_ids[mixed];bary=pending_bary[mixed];q=q[mixed];span=span[mixed]
        refine=(span>pixel_limit)&(depth<max_depth)
        # Leaf intersections use linear scalar clipping, with real bilinear
        # image samples, rather than keeping a whole triangle by its centroid.
        for fi,bc,tuv in zip(ids[~refine],bary[~refine],q[~refine]):
            values=sample(tuv)-cutoff;poly=[]
            for j in range(3):
                k=(j+1)%3
                if values[j]>=0:poly.append(bc[j])
                if (values[j]>=0)!=(values[k]>=0):
                    t=values[j]/(values[j]-values[k]);poly.append(bc[j]*(1-t)+bc[k]*t)
            if len(poly)>=3:
                out=np.asarray([[poly[0],poly[j],poly[j+1]]for j in range(1,len(poly)-1)])
                accepted_ids.append(np.full(len(out),fi));accepted_bary.append(out);clipped+=1
            else:dropped+=1
        ids=ids[refine];bc=bary[refine]
        mids=(bc+np.roll(bc,-1,axis=1))*.5
        children=np.stack((np.stack((bc[:,0],mids[:,0],mids[:,2]),1),
                           np.stack((mids[:,0],bc[:,1],mids[:,1]),1),
                           np.stack((mids[:,2],mids[:,1],bc[:,2]),1),
                           np.stack((mids[:,0],mids[:,1],mids[:,2]),1)),1)
        pending_ids=np.repeat(ids,4);pending_bary=children.reshape(-1,3,3)

    if not accepted_ids:raise ValueError('Garment mask removed the complete draw')
    face_ids=np.concatenate(accepted_ids);bary=np.concatenate(accepted_bary).reshape(-1,3)
    source=faces[np.repeat(face_ids,3)]
    pos=np.einsum('nc,ncd->nd',bary,positions[source])
    nor=np.einsum('nc,ncd->nd',bary,normals[source]);nor/=np.maximum(np.linalg.norm(nor,axis=1,keepdims=True),1e-12)
    tex=np.einsum('nc,ncd->nd',bary,uv[source])
    # Merge shared corners by source vertex identities and barycentric weight.
    # This keeps original smooth topology and interpolated skin across seams.
    order=np.argsort(source,axis=1);vid=np.take_along_axis(source,order,1)
    coeff=np.take_along_axis(bary,order,1);vid[coeff<1e-9]=-1
    coeff[coeff<1e-9]=0
    order=np.argsort(vid,axis=1);vid=np.take_along_axis(vid,order,1);coeff=np.take_along_axis(coeff,order,1)
    keys=np.column_stack((vid,np.round(coeff*1e8).astype(np.int64)))
    _,first,inverse=np.unique(keys,axis=0,return_index=True,return_inverse=True)
    bary=bary[first];source=source[first]
    count=int(indices.max())+1;dense=np.zeros((len(first),count),np.float32)
    for j in range(3):
        np.add.at(dense,(np.arange(len(first))[:,None],indices[source[:,j]]),weights[source[:,j]]*bary[:,j,None])
    ji=np.argpartition(dense,-4,axis=1)[:,-4:];jw=np.take_along_axis(dense,ji,axis=1)
    jw/=np.maximum(jw.sum(1,keepdims=True),1e-12)
    triangles=inverse.reshape(-1,3)
    # Suppress numerical zero-area slivers at exactly-on-threshold pixels.
    area=np.linalg.norm(np.cross(pos[first][triangles[:,1]]-pos[first][triangles[:,0]],
                                pos[first][triangles[:,2]]-pos[first][triangles[:,0]]),axis=1)
    triangles=triangles[area>1e-12]
    report=dict(input_triangles=len(faces),output_triangles=len(triangles),
                discarded_cells=dropped,clipped_boundary_cells=clipped,
                source_cutoff=float(cutoff),boundary_texel_limit=pixel_limit,max_refinement=max_depth,
                native_provider='substance_basic',method='source-UV-mask-barycentric-geometric-cutout')
    return pos[first].astype('f4'),nor[first].astype('f4'),tex[first].astype('f4'),triangles,ji,jw,report
