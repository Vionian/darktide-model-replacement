"""Clip actual blade surfaces to narrow cutting-edge bands, never whole faces."""
from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/blade_edge'
KHR_SCALE=.88
def bounds(v):return [v.min(0).tolist(),v.max(0).tolist()]
def native_reference():
    d=json.loads((OUT/'native_nodes.json').read_text());report={}
    for family,parts in d.items():
        def anchor(part,token):
            # Confirmed ap_hilt_01/ap_blade_01/ap_pommel_01 node hashes.
            return np.array(next(n['position'] for n in parts[part]['nodes'] if n['name']==token))
        h=anchor('grip_01','4000D158');p=anchor('grip_01','67E762A6')
        a=h+anchor('hilt_01','894173EC')
        variants=[]
        for blade in ('blade_01','blade_02'):
            arrays={};faces={}
            for part,offset in [('grip_01',np.zeros(3)),('hilt_01',h),(blade,a),('pommel_01',p)]:
                n=np.load(OUT/(family+'_'+part+'.npz'));arrays[part]=n['vertices']+offset;faces[part+'_faces']=n['faces']
            v=np.concatenate(list(arrays.values()))
            np.savez(OUT/(family+'_'+blade+'_assembled.npz'),**arrays,**faces)
            variants.append({'blade':blade,'bounds':bounds(v),'length_m':float(np.ptp(v[:,2])),
                             'tip_z':float(v[:,2].max()),'guard_width_m':float(np.ptp(arrays['hilt_01'][:,1]))})
        report[family]={'attachment_nodes':{'hilt':'ap_hilt_01','blade':'ap_blade_01','pommel':'ap_pommel_01'},'variants':variants}
    return report
def khravengger_mesh():
    n=np.load(ROOT/'build/target_mesh.npz');v=n['vertices'].copy()
    # Preserve the center of the existing straight hand grip, not the tip.
    # The shaft has long triangles and no vertices inside this interval.
    # Intersect its actual surface at the existing hand-grip midpoint.
    tri=v[n['faces']];points=[];z=-.07
    for i,j in ((0,1),(1,2),(2,0)):
        a=tri[:,i];b=tri[:,j];dz=b[:,2]-a[:,2]
        good=(abs(dz)>1e-10)&((a[:,2]-z)*(b[:,2]-z)<=0)
        a=a[good];b=b[good];t=(z-a[:,2])/(b[:,2]-a[:,2]);points.extend(a+(b-a)*t[:,None])
    grip=np.asarray(points)
    pivot=(grip.min(0)+grip.max(0))*.5
    scaled=(v-pivot)*KHR_SCALE+pivot
    report={'uniform_scale':KHR_SCALE,'reduction_percent':12,'pivot':pivot.tolist(),
            'pivot_definition':'actual triangle-plane cross-section center at current hand grip Z=-0.07m',
            'old_bounds':bounds(v),'new_bounds':bounds(scaled),
            'old_length_m':float(np.ptp(v[:,2])),'new_length_m':float(np.ptp(scaled[:,2])),
            'native':native_reference(),'native_hand_animation_unchanged':True,
            'in_game_visual_verified':False}
    (OUT/'size_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    np.savez(OUT/'khravengger_mesh.npz',vertices=scaled,faces=n['faces'],normals=n['normals'],uvs=n['uvs'])
    return scaled,n['faces'],n['normals'],n['uvs']
def clip(poly,fn):
    if not len(poly):return poly
    result=[];a=poly[-1];da=fn(a)
    for p in poly:
        dp=fn(p)
        if (da>=0)!=(dp>=0):result.append(a+(p-a)*(da/(da-dp)))
        if dp>=0:result.append(p)
        a,da=p,dp
    return np.asarray(result)
def edge_ribbon(v,f,n,start,width,sides,name):
    tri=v[f];lo=tri[:,:,2].min(1);hi=tri[:,:,2].max(1)
    zs=np.linspace(start,float(v[:,2].max()),max(3,int((v[:,2].max()-start)/.008)+1))
    envelope=[]
    for z in zs:
        active=tri[(lo<=z+1e-8)&(hi>=z-1e-8)];points=[]
        for i,j in ((0,1),(1,2),(2,0)):
            a=active[:,i];b=active[:,j];dz=b[:,2]-a[:,2]
            good=(abs(dz)>1e-10)&((a[:,2]-z)*(b[:,2]-z)<=1e-12)
            a=a[good];b=b[good];t=(z-a[:,2])/(b[:,2]-a[:,2]);points.extend(a+(b-a)*t[:,None])
        points=np.array(points)
        if not len(points):points=v[np.argsort(abs(v[:,2]-z))[:3]]
        envelope.append([float(z),float(points[:,1].min()),float(points[:,1].max())])
    envelope=np.array(envelope);verts=[];normals=[];faces=[]
    for k,(z0,z1) in enumerate(zip(zs[:-1],zs[1:])):
        indices=np.flatnonzero((lo<=z1)&(hi>=z0))
        for side in sides:
            j=2 if side==1 else 1
            slope=(envelope[k+1,j]-envelope[k,j])/(z1-z0)
            y0=envelope[k,j]
            for face in f[indices]:
                poly=np.column_stack([v[face],n[face]])
                poly=clip(poly,lambda p:p[2]-z0);poly=clip(poly,lambda p:z1-p[2])
                poly=clip(poly,lambda p:side*(p[1]-y0-slope*(p[2]-z0))+width)
                if len(poly)<3:continue
                for i in range(1,len(poly)-1):
                    t=poly[[0,i,i+1]]
                    if np.linalg.norm(np.cross(t[1,:3]-t[0,:3],t[2,:3]-t[0,:3]))<1e-11:continue
                    at=len(verts);verts.extend(t[:,:3]);normals.extend(t[:,3:]);faces.append([at,at+1,at+2])
    verts=np.array(verts);normals=np.array(normals);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    faces=np.array(faces,dtype=int)
    original_area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1).sum()*.5
    q=verts[faces];area=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1).sum()*.5
    report={'band_width_m':width,'sides':list(sides),'start_z':float(start),'bounds':bounds(verts),
            'vertices':len(verts),'triangles':len(faces),'surface_area_m2':float(area),
            'surface_area_fraction_of_weapon':float(area/original_area),'envelope':envelope.tolist(),
            'normal_offset_m':[.0005,.00065,.0008],'whole_weapon_coating':False}
    assert len(faces)>10 and area/original_area<.3,(name,report)
    (OUT/(name+'_edge.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    np.savez(OUT/(name+'_edge.npz'),vertices=verts,normals=normals,faces=faces)
    print('BLADE_EDGE',name,len(faces),'area_fraction',round(area/original_area,4))
    return verts,faces,normals
