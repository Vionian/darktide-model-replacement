"""Read the supplied EFFRES2 fields without executing the source mod."""
import struct,json
from pathlib import Path
import numpy as np
from PIL import Image
from probe_skins import fields
from efmi_draws import sections
from skins_sources import source,OUT

def mesh(path):
    fs=fields(path);v=fs['m_VertexData'];count,nchannels=struct.unpack_from('<2I',v)
    channels=[tuple(v[8+i*4:12+i*4])for i in range(nchannels)]
    size=struct.unpack_from('<I',v,8+nchannels*4)[0];data=v[12+nchannels*4:12+nchannels*4+size]
    formats={0:('<f4',1),1:('<f2',1),2:('u1',255),3:('i1',127),4:('<u2',65535),5:('<i2',32767),6:('u1',1),7:('i1',1),8:('<u2',1),9:('<i2',1),10:('<u4',1),11:('<i4',1)}
    strides={}
    for stream,offset,fmt,dim in channels:
        if dim&15:strides[stream]=max(strides.get(stream,0),offset+np.dtype(formats[fmt][0]).itemsize*(dim&15))
    starts={};start=0
    for stream,stride in sorted(strides.items()):starts[stream]=start;start=(start+count*stride+15)//16*16
    def get(i):
        stream,offset,fmt,dim=channels[i];dim&=15;dtype,scale=formats[fmt]
        a=np.ndarray((count,dim),dtype=dtype,buffer=data,offset=starts[stream]+offset,strides=(strides[stream],np.dtype(dtype).itemsize)).copy()
        return a if scale==1 else a.astype(np.float32)/scale
    p=get(0);n=get(1)
    if n.shape[1]==1:
        from skins_geometry import decode_normals
        n=decode_normals(n.view('<u4').ravel())
    uv=get(4)[:,:2];uv[:,1]=1-uv[:,1]
    w=get(12);j=get(13).astype(np.uint16);w/=np.maximum(w.sum(1,keepdims=True),1e-12)
    raw=fs['m_IndexBuffer'];sz=struct.unpack_from('<I',raw)[0]
    ib=np.frombuffer(raw[4:4+sz],'<u4'if struct.unpack_from('<I',fs['m_IndexFormat'])[0] else '<u2').astype(np.int64).reshape(-1,3)
    dot=np.sum(np.cross(p[ib[:,1]]-p[ib[:,0]],p[ib[:,2]]-p[ib[:,0]])*n[ib].mean(1),axis=1)
    if np.median(dot)<0:ib=ib[:,[0,2,1]]
    b=fs['@bones'];nb=struct.unpack_from('<I',b)[0];o=4;names=[]
    for i in range(nb):
        sz=struct.unpack_from('<H',b,o)[0];o+=2;names.append(b[o:o+sz].decode());o+=sz
    poses=np.frombuffer(fs['m_BindPose'],dtype='<f4',offset=4).reshape(-1,4,4)
    return dict(positions=p,normals=n,uv=uv,faces=ib,raw_weights=w,raw_indices=j,bone_paths=names,bindposes=poses)

def read():
    spec=source('si_ink_wash');dest=OUT/'si_ink_wash';dest.mkdir(exist_ok=True);(dest/'textures').mkdir(exist_ok=True)
    raw=sections(spec['ini']);blocks={n:dict(l.split('=',1)for l in lines if '='in l)for n,lines in raw.items()}
    textures={}
    for name,row in blocks.items():
        if not name.startswith('Texture'):continue
        p=spec['folder']/row['path'];fs=fields(p);version,width,height,fmt,mips=struct.unpack_from('<5I',fs['@texture']);assert version==1 and fmt==4
        target=dest/'textures'/(p.stem+'.png')
        if not target.exists():Image.frombytes('RGBA',(width,height),fs['pixels'][:width*height*4]).save(target)
        textures[name]=str(target)
    draws=[]
    for name,row in blocks.items():
        if not name.startswith('Part')or row.get('visible')!='true':continue
        path=spec['folder']/blocks[row['mesh']]['path'];d=mesh(path)
        material=blocks[row['material']]
        d['textures']={k[8:]:textures[v]for k,v in material.items()if k.startswith('texture.')}
        d.update(source=dict(section=name,start=0,count=len(d['faces'])*3),source_palette=str(path),source_files=[str(path)])
        draws.append(d)
    return None,draws,[]

if __name__=='__main__':
    _,draws,_=read()
    for d in draws:print(d['source']['section'],len(d['positions']),len(d['faces']),d['positions'].min(0),d['positions'].max(0),d['textures'],flush=True)
