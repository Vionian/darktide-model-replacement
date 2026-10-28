"""Native material settings and optional v61 PBR fill serialization.

Layout follows Darktide-SDK material_v61.cpp and pbr_emissive_profile.cpp.
Retail shader streams are extracted locally by limn; no shader is fabricated.
"""
import pathlib,struct
import numpy as np
SHADERS=pathlib.Path(__file__).parent/'roshia/material_templates'
# The shipped character replacements prove that the face slot is reliable when
# it uses substance_basic with its own BC texture.  The experimental custom PBR
# provider made the game fall back to a white face even though Blender previews
# looked correct, so keep the optional provider disabled for this build.
FACE_FILL={}
FACE_DIFFUSE={}
FACE_LINEAR_TINT={}
ROUGHNESS={0:.82,1:.24,2:.28,3:.44,7:.72,9:.75,10:.72,11:.82,12:.78,13:.75}

def face_texture_pair(index, pixels):
    """Return sRGB diffuse and linear emission; preserve texture line art."""
    rgb=np.clip(pixels[:,:,:3],0,1)
    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    linear=np.clip(linear*np.asarray(FACE_LINEAR_TINT[index]),0,1)
    diffuse=pixels.copy()
    lit=linear*FACE_DIFFUSE[index]
    diffuse[:,:,:3]=np.where(lit<=.0031308,lit*12.92,1.055*lit**(1/2.4)-.055)
    emission=pixels.copy()
    emission[:,:,:3]=linear
    emission[:,:,3]=1
    return diffuse,emission

def read_pbr_fill(folder, basename):
    """Read actual v61 instance values rather than previewing build defaults."""
    header=(folder/(basename+'.material')).read_bytes()
    stream=header[38:68].split(b'\0',1)[0].decode('ascii')
    data=(folder/stream).read_bytes()
    version,offset=struct.unpack_from('<2I',data)
    if version!=61:
        raise ValueError('Expected v61 PBR material instance')
    p=offset+20
    n=struct.unpack_from('<I',data,p)[0];p+=4+4*n
    n=struct.unpack_from('<I',data,p)[0];p+=4
    textures=dict(struct.unpack_from('<IQ',data,p+12*i)for i in range(n));p+=12*n
    n=struct.unpack_from('<I',data,p)[0];p+=4+8*n
    n=struct.unpack_from('<I',data,p)[0];p+=4
    variables=[struct.unpack_from('<5I',data,p+20*i)for i in range(n)];p+=20*n
    size=struct.unpack_from('<I',data,p)[0];p+=4
    if p+size>len(data) or any(v[3]+(12 if v[0]==2 else 4)>size for v in variables):
        raise ValueError('Material variables exceed their serialized buffer')
    values={v[2]:struct.unpack_from('<3f' if v[0]==2 else '<f',data,p+v[3])for v in variables}
    return {'intensity':values[0x32f447e5][0],'multiplier':values[0x519c1733][0],
            'color':values[0xc985395a],'textures':textures}

def stream_material(b,folder,name,payload):
    stream=f'data/am/{b.hash64(name+"_stream"):016x}'
    p=folder/stream;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(payload)
    primary=name.rsplit('/',1)[-1]+'.material'
    header=(b.u64(b.hash64('material'))+b.u64(b.hash64(name))+b.u32(1)+b.u32(0)+b.u32(0)+b'\x01'+b.u32(30)+b.u32(1)+b'\0'+stream.encode().ljust(30,b'\0'))
    (folder/primary).write_bytes(header)
    return {'resource':{'type':'material','name':name},'primary':primary,'stream':stream}

def providers(b,folder,prefix):
    parent=f'{b.RESOURCE_ROOT}/{prefix}_pbr_parent'
    provider=f'{b.RESOURCE_ROOT}/{prefix}_pbr_provider'
    a=(SHADERS/'roshia_pbr_parent.material').read_bytes()
    data=bytearray((SHADERS/'roshia_pbr_provider.material').read_bytes())
    assert struct.unpack_from('<Q',data,40)[0]==0xe04dba68a38d1429
    struct.pack_into('<Q',data,40,b.hash64(parent))
    return provider,parent,[stream_material(b,folder,parent,a),stream_material(b,folder,provider,data)]

def pbr_fill(b,folder,name,provider,parent,channels,intensity):
    tex=[(0x8e604079,channels['bc']),(0x5f9dfbfb,channels['em']),(0xb45e95f3,channels['nm']),(0x8655079c,channels['orm'])]
    payload=b.u32(0)+b.u64(b.hash64(provider))+b.u64(b.hash64(parent))+b.u32(0)+b.u32(4)
    payload+=b''.join(b.u32(k)+b.u64(b.hash64(v))for k,v in tex)
    payload+=b.u32(1)+b.u32(b.hash32('surface_material'))+b.u32(b.hash32('plastic'))
    variables=[(0,0,0x32f447e5,32,0),(2,0,0xc985395a,20,0),(0,0,0x519c1733,16,0)]
    payload+=b.u32(3)+b''.join(struct.pack('<5I',*v)for v in variables)
    payload+=b.u32(36)+struct.pack('<9f',.5,0,0,0,1,1,1,1,intensity)+b.u32(0)+b.u32(0)
    stream=struct.pack('<7I',61,28,len(payload),0xffffffff,0,0xffffffff,0)+payload
    return stream_material(b,folder,name,stream)

def set_cutoff(stream_path,threshold):
    data=bytearray(stream_path.read_bytes());p=struct.unpack_from('<I',data,4)[0]+20
    n=struct.unpack_from('<I',data,p)[0];p+=4+4*n
    n=struct.unpack_from('<I',data,p)[0];p+=4+12*n
    n=struct.unpack_from('<I',data,p)[0];p+=4+8*n
    n=struct.unpack_from('<I',data,p)[0];p+=4
    records=[struct.unpack_from('<5I',data,p+20*i)for i in range(n)];p+=20*n+4
    off=next(r[3]for r in records if r[2]==0x53c84707)
    struct.pack_into('<f',data,p+off,threshold);stream_path.write_bytes(data)
