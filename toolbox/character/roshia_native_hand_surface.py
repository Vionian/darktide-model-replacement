"""Fit authored hand surfaces to the common native animation contact rig.

No reference topology, UVs or textures are copied. Reference skin zones supply
cross-section measurements; original Roshia weights blend the affine fits.
"""
import numpy as np
from mathutils import Matrix


def reference_zones(b, asset='daniya_blue_arms', folder=None):
    folder=folder or b.ROOT/'Custom'/asset
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
    names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(next(folder.glob('*.bones'))))))
    inverse={i:('j'+n[1:] if n.startswith(('r_lefthand','r_righthand','r_leftinhand','r_rightinhand')) else n) for n,i in names.items()}
    zones={}
    for obj in unit.meshes:
        geo=unit.mesh_geometries[obj.geometry_index-1]
        channels={c.component.name:c for c in geo.channels}
        def read(key,method):
            c=channels[key];return getattr(geo.streams[c.stream],method)(c)
        points=np.asarray(read('POSITION','get_positions'),float)
        indices=read('BLENDINDICES','get_blendindices')
        weights=read('BLENDWEIGHTS','get_blendweights')
        # Mesh skin_index is not an array index in these DT resources.
        # Reference arm assets each serialize one shared skin palette.
        assert len(unit.skins)==1, "Reference needs explicit skin-palette resolution"
        skin=unit.skins[0]
        for palette in np.unique(indices):
            node=skin.node_indices[int(palette)]
            name=inverse.get(node,'')
            if not name.startswith(('j_lefthand','j_righthand')):continue
            summed=np.sum(np.where(indices==palette,weights,0),axis=1)
            zones.setdefault(name,[]).extend(points[summed>.5].tolist())
    return {n:np.unique(np.asarray(p),axis=0) for n,p in zones.items() if p}


def frame(axis,normal):
    axis=axis/np.linalg.norm(axis)
    normal=normal-axis*np.dot(axis,normal)
    normal/=np.linalg.norm(normal)
    width=np.cross(normal,axis)
    return np.column_stack((axis,width,normal))


def fit_maps(b, original, source, native, names, root_map):
    reference=reference_zones(b)
    mesh=b.bpy.data.objects[b.MESH_OBJECT_NAME]
    arm=b.bpy.data.objects[b.ARMATURE_OBJECT_NAME]
    mapping=b.source_bone_targets(arm,names,original['source_to_target'])
    groups={g.index:g.name for g in mesh.vertex_groups}
    zones={}
    for v in mesh.data.vertices:
        merged={}
        for g in v.groups:
            n=mapping.get(groups[g.group],'')
            if n.startswith(('j_lefthand','j_righthand')):
                merged[n]=merged.get(n,0)+g.weight
        for n,w in merged.items():
            if w>.5:
                p=root_map@(b.source_coordinate3()@(mesh.matrix_world@v.co))
                zones.setdefault(n,[]).append(list(p))
    zones={n:np.asarray(p) for n,p in zones.items()}
    if getattr(b,'HAND_CALIBRATION_POINTS',None):
        from mathutils import Vector
        zones={n:np.asarray([root_map@(b.source_coordinate3()@Vector(p)) for p in points])
               for n,points in b.HAND_CALIBRATION_POINTS.items()}
    maps={};report=[]
    for side in ('left','right'):
        prefix=f'j_{side}hand'
        def pos(collection,key):return np.array(collection[names[prefix+key]].translation)
        sw=pos(source,'');tw=pos(native,'')
        sf=frame(pos(source,'middle1')-sw,
                 np.cross(pos(source,'middle1')-sw,pos(source,'pinky1')-pos(source,'index1')))
        tf=frame(pos(native,'middle1')-tw,
                 np.cross(pos(native,'middle1')-tw,pos(native,'pinky1')-pos(native,'index1')))
        width=np.linalg.norm(pos(native,'pinky1')-pos(native,'index1'))/np.linalg.norm(pos(source,'pinky1')-pos(source,'index1'))
        length=np.linalg.norm(pos(native,'middle1')-tw)/np.linalg.norm(pos(source,'middle1')-sw)
        def affine(name,origin,target,fs,ft,scales,offset):
            linear=ft@np.diag(scales)@fs.T
            matrix=np.eye(4);matrix[:3,:3]=linear
            matrix[:3,3]=target+ft@offset-linear@origin
            if np.linalg.det(linear)<=0:raise ValueError('Hand surface fit reflected')
            maps[name]=np.asarray(Matrix(matrix.tolist())@root_map,dtype=np.float32)
        affine(prefix,sw,tw,sf,tf,[length,width,width],np.zeros(3))
        for digit in ('thumb','index','middle','ring','pinky'):
            keys=[digit+str(k) for k in (1,2,3)]
            for k,key in enumerate(keys):
                a,c=(k,k+1) if k<2 else (k-1,k)
                sv=pos(source,keys[c])-pos(source,keys[a])
                tv=pos(native,keys[c])-pos(native,keys[a])
                fs=frame(sv,sf[:,2]);ft=frame(tv,tf[:,2])
                origin,target=pos(source,key),pos(native,key)
                name=prefix+key
                scales=np.array([np.linalg.norm(tv)/np.linalg.norm(sv),width,width])
                offset=np.zeros(3)
                sp=zones.get(name,np.empty((0,3)));tp=reference.get(name,np.empty((0,3)))
                if len(sp)>=8 and len(tp)>=8:
                    sl=(sp-origin)@fs;tl=(tp-target)@ft
                    slo,shi=np.quantile(sl,[.05,.95],axis=0)
                    tlo,thi=np.quantile(tl,[.05,.95],axis=0)
                    for axis in (1,2):
                        if shi[axis]-slo[axis]>.001 and thi[axis]-tlo[axis]>.001:
                            scales[axis]=(thi[axis]-tlo[axis])/(shi[axis]-slo[axis])
                            offset[axis]=(thi[axis]+tlo[axis]-(shi[axis]+slo[axis])*scales[axis])*.5
                    if k==2 and shi[0]>.003 and thi[0]>.003:
                        scales[0]=thi[0]/shi[0]
                affine(name,origin,target,fs,ft,scales,offset)
                report.append({'name':name,'source_samples':len(sp),'reference_samples':len(tp),
                    'longitudinal_scale':float(scales[0]),'transverse_scales':scales[1:].tolist(),
                    'surface_center_offset_mm':(offset*1000).tolist()})
        for name in names:
            if name.startswith(f'j_{side}inhand'):
                maps[name]=maps[prefix].copy()
    return maps,report
