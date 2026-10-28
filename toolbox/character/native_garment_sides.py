"""Preserve authored two-sided opaque cloth without changing front geometry."""
import hashlib
import numpy as np


def authored_two_sided_garment(material):
    # Alpha cards already get reverse faces. Closed skin/face meshes are not
    # garment surfaces; do not duplicate them based on the MMD default alone.
    return bool(material and material.name.casefold().startswith('cloth') and
                getattr(getattr(material, 'mmd_material', None), 'is_double_sided', False))


def from_parsed(b, geo, material_index):
    streams=[(s.vertex_data,s.vertex_stream.stride) for s in geo.streams]
    assert [s[1] for s in streams] in ([8,8,4,4,8,4],[8,12,4,4,8,4])
    n=geo.streams[1].vertex_stream.vertices
    indices=np.array(geo.index_stream.get_indices())
    assert np.array_equal(indices,np.arange(n)), 'Requires the native builder split-triangle layout'
    channels=[(4,17,0,0),(0,2 if streams[1][1]==12 else 17,0,1),
              (1,15,0,2),(5,15,0,3),(8,17,0,4),(7,19,0,5)]
    p=geo.streams[1].get_positions(next(c for c in geo.channels if c.component.name=='POSITION'))
    return dict(streams=streams,index_data=geo.index_stream.data,vertices=n,indices=n,
                triangle_count=n//3,bounds=np.r_[p.min(0),p.max(0)].astype('<f4'),
                slot_id=geo.materials[0].ID,material_index=material_index,channels=channels,is_alpha=False)


def triangle_keys(geometry):
    # Include UVs and skin influences so unrelated coincident faces cannot
    # satisfy the reverse-side check.
    streams=[np.frombuffer(geometry['streams'][i][0],np.uint8).reshape(geometry['vertices'],-1)
             for i in (1,3,4,5)]
    rows=np.concatenate(streams,axis=1).reshape(-1,3,sum(s.shape[1] for s in streams))
    def digest(a,b,c):
        return hashlib.blake2b(min(a+b+c,b+c+a,c+a+b),digest_size=16).digest()
    direct=[];reverse=[]
    for tri in rows:
        a,c,d=(r.tobytes() for r in tri)
        direct.append(digest(a,c,d));reverse.append(digest(a,d,c))
    return direct,reverse


def append_reverse(b,geometry,selected):
    if not len(selected):return geometry
    n=geometry['vertices']
    reverse=(selected[:,None]*3+np.array([0,2,1])).reshape(-1)
    assert n+len(reverse)<=65535, 'Split this garment into more uint16-safe chunks before adding reverse sides'
    payloads=[]
    for payload,stride in geometry['streams']:
        rows=np.frombuffer(payload,np.uint8).reshape(n,stride)
        payloads.append(payload+rows[reverse].copy().tobytes())
    normals=b.mesh_geometry.math_utils.octahedral_decode(geometry['streams'][2][0]).astype(np.float32)
    reverse_normals=-normals[reverse]
    payloads[2]=geometry['streams'][2][0]+b.encode_octahedral(reverse_normals).tobytes()
    p=b.geometry_positions(geometry)[reverse].astype(np.float32)
    uv=np.frombuffer(geometry['streams'][3][0],'<f2').reshape(-1,2)[reverse].astype(np.float32)
    payloads[0]=geometry['streams'][0][0]+b.packed_tangent_frame(p,reverse_normals,uv).tobytes()
    result=dict(geometry)
    result['streams']=[(p,s[1]) for p,s in zip(payloads,geometry['streams'])]
    result['vertices']=result['indices']=n+len(reverse)
    result['index_data']=np.arange(result['vertices'],dtype='<u2').tobytes()
    result['triangle_count']=result['vertices']//3
    return result
