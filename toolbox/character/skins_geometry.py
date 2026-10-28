"""Decode inspected native EFMI buffers and retain per-draw provenance."""
from pathlib import Path
import json,hashlib,re
import numpy as np
from scipy.spatial import cKDTree
from efmi_draws import Reader
from skins_sources import source,OUT,SOURCES

def decode_normals(packed):
    # EFMI uses signed 10-bit octahedral components, not oct16.
    from convert_si_ink_mist import decode_normals as verified
    return verified(packed)

def component(r,bindings,cache):
    signature=tuple(bindings.get(k)for k in ('vb0','vb1','vb2','ib'))
    if signature in cache:return cache[signature]
    signature=tuple(s+'_0' if not r.path(s) and r.path(s+'_0') else s for s in signature)
    rows=[r.resources[s.casefold()] for s in signature]
    vp,uvp,sp,ip=[r.path(s) for s in signature]
    stride=int(rows[0].get('stride',16))
    vb=np.fromfile(vp,np.uint8).reshape(-1,stride)
    p=vb[:,:12].copy().view('<f4').reshape(-1,3)
    assert np.isfinite(p).all()and np.max(abs(p))<50,('Source position layout',vp)
    if stride==16:n=decode_normals(vb[:,12:16].copy().view('<u4').ravel())
    elif stride>=24:n=vb[:,12:24].copy().view('<f4').reshape(-1,3)
    else:raise ValueError(('Unsupported source position stride',stride))
    uvb=np.fromfile(uvp,np.uint8).reshape(-1,int(rows[1]['stride']))
    uv=uvb[:,:8].copy().view('<f4').reshape(-1,2)
    ss=int(rows[2]['stride']);sb=np.fromfile(sp,np.uint8).reshape(-1,ss)
    if ss in (12,16):
        w=sb[:,:8].copy().view('<u2').reshape(-1,4).astype(np.float32)/65535
        j=sb[:,8:12].copy().astype(np.uint16) if ss==12 else sb[:,8:16].copy().view('<u2').reshape(-1,4)
        assert np.isfinite(w).all(),('Invalid source blend layout',sp)
        w/=np.maximum(w.sum(1,keepdims=True),1e-12)
    elif ss==32:
        w=sb[:,:16].copy().view('<f4').reshape(-1,4)
        j=sb[:,16:].copy().view('<u4').reshape(-1,4)
    else:w=np.zeros((len(p),4),np.float32);j=np.zeros((len(p),4),np.uint16)
    fmt=rows[3].get('format','R32_UINT')
    ib=np.fromfile(ip,'<u4' if 'R32' in fmt else '<u2')
    assert len(p)==len(uv)==len(w),(vp,len(p),len(uv),len(w))
    result=dict(positions=p,normals=n,uv=uv,raw_weights=w,raw_indices=j,ib=ib,
                files=[str(f)for f in (vp,uvp,sp,ip)],source_palette=signature[2])
    cache[signature]=result
    return result

def read(key,overrides=None):
    spec=source(key);r=Reader(spec['ini'],overrides);raw=r.collect()
    cache={};draws=[];seen=set();duplicates=[]
    for draw in raw:
        if not all(k in draw['bindings']for k in ('vb0','vb1','vb2','ib')):
            # A draw without custom buffers means the INI retains the original
            # game component. Record it, and retain original model geometry.
            r.warnings.append(('Retained original draw',draw['section']))
            continue
        c=component(r,draw['bindings'],cache)
        faces=c['ib'][draw['start']:draw['start']+draw['count']].astype(np.int64)+draw['base_vertex']
        assert len(faces)==draw['count']and len(faces)%3==0
        assert faces.max()<len(c['positions'])
        ids,inverse=np.unique(faces,return_inverse=True);faces=inverse.reshape(-1,3)
        arrays={k:c[k][ids].copy()for k in ('positions','normals','uv','raw_weights','raw_indices')}
        textures={k:str(r.path(v))for k,v in draw['bindings'].items()if r.path(v)and (k.startswith('ps-t')or 'rabbit' in k)}
        h=hashlib.sha256()
        # Ignore winding and split normals when finding the source's duplicate
        # back/depth surfaces. Reverse sides are exported explicitly later.
        keys=np.round(np.c_[arrays['positions'],arrays['uv']],6)
        unique,canonical=np.unique(keys,axis=0,return_inverse=True)
        tri=np.sort(canonical[faces],axis=1)
        tri=tri[np.lexsort(tri.T[::-1])]
        h.update(unique.tobytes());h.update(tri.tobytes())
        h.update(json.dumps(textures,sort_keys=True).encode())
        if h.digest()in seen:duplicates.append(draw['section']);continue
        seen.add(h.digest())
        p,n=arrays['positions'],arrays['normals']
        dot=np.sum(np.cross(p[faces[:,1]]-p[faces[:,0]],p[faces[:,2]]-p[faces[:,0]])*n[faces].mean(1),axis=1)
        if np.median(dot)<0:faces=faces[:,[0,2,1]]
        arrays['uv'][:,1]=1-arrays['uv'][:,1]
        draws.append(dict(arrays,faces=faces,source=draw,textures=textures,source_palette=c['source_palette'],
                          source_files=c['files']))
    return r,draws,duplicates

def diagnose(key):
    r,draws,dups=read(key)
    base=source(key)['base'];ref=np.load(OUT/'references'/base/'source.npz')
    tree=cKDTree(ref['positions']);rows=[];names=ref['group_names']
    for d in draws:
        p=d['positions'];distance,near=tree.query(p)
        mat_per_vertex=np.full(len(ref['positions']),-1,np.int32)
        for tri,mat in zip(ref['triangles'],ref['materials']):mat_per_vertex[tri]=mat
        mat_counts=np.bincount(np.maximum(0,mat_per_vertex[near]))
        rows.append(dict(section=d['source']['section'],count=len(d['faces']),vertices=len(p),
            source_start=d['source']['start'],bounds=[p.min(0).tolist(),p.max(0).tolist()],
            source_distance=np.quantile(distance,[0,.5,.9,.99,1]).tolist(),
            nearest_materials=sorted(enumerate(mat_counts.tolist()),key=lambda x:-x[1])[:4],textures=d['textures'],
            palette=d['source_palette'],skin_sum_range=[float(d['raw_weights'].sum(1).min()),float(d['raw_weights'].sum(1).max())]))
    folder=OUT/key;folder.mkdir(exist_ok=True)
    (folder/'geometry_diagnostic.json').write_text(json.dumps(dict(draws=rows,duplicates=dups),ensure_ascii=False,indent=2),encoding='utf-8')
    print('GEOMETRY',key,len(draws),sum(x['count']for x in rows),'duplicate passes',len(dups),flush=True)

if __name__=='__main__':
    import sys,traceback
    for key in sys.argv[1:] or SOURCES:
        if key=='si_ink_wash':continue
        try:diagnose(key)
        except Exception as e:print('GEOMETRY_FAILED',key,repr(e),flush=True)
