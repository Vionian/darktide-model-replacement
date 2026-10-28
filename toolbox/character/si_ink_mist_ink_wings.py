"""Adapt source FX carrier ribbons into thin native ink strokes.

The source FX shader fades most of each wide carrier. Opaque export of that
carrier produces black spear-shaped panels. Preserve each authored strip's
centerline, while narrowing its cross-section for the opaque native fallback.
This is an explicit silhouette approximation, not a port of the FX shader.
"""
import numpy as np


def strokes(positions, uv, faces):
    pos=positions.copy()
    parent=np.arange(len(pos))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for a,b,c in faces:
        ra=root(a)
        for j in (b,c):parent[root(j)]=ra
    labels=np.array([root(i) for i in range(len(pos))])
    widths=[]
    for label in np.unique(labels):
        selected=np.flatnonzero(labels==label)
        rows=np.round(uv[selected,1]*1e6).astype(int)
        for row in np.unique(rows):
            ids=selected[rows==row]
            if len(ids)<2:continue
            u=uv[ids,0];a,b=ids[u.argmin()],ids[u.argmax()]
            if u.max()-u.min()<1e-6:continue
            center=(pos[a]+pos[b])*.5
            phase=float(uv[ids[0],1])
            factor=.12+.10*np.sin(np.pi*phase)**2
            widths.append(float(np.linalg.norm(pos[b]-pos[a])))
            pos[ids]=center+(pos[ids]-center)*factor
    normals=np.zeros_like(pos)
    area=np.cross(pos[faces[:,1]]-pos[faces[:,0]],pos[faces[:,2]]-pos[faces[:,0]])
    for j in range(3):np.add.at(normals,faces[:,j],area)
    normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
    return pos,normals,dict(method='source-connected-strip-centerlines, narrowed opaque ink cross-sections',
        strips=int(len(np.unique(labels))),width_factor_range=[.12,.22],
        source_max_width_m=max(widths,default=0),source_fx_shader_available=False)
