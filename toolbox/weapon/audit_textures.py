from pathlib import Path
import sys, io, json, struct
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, '<CHARACTER_WORKSPACE>/tools/model-work')
from native_texture import Oodle
from read_native_texture import read_native_top_mip
codec=Oodle(Path('<DARKTIDE_GAME>/binaries/oo2core_9_win64.dll'))
folder=ROOT/'WeaponModelReplacement/Custom/khravengger'
dest=ROOT/'build/native_readback'; dest.mkdir(exist_ok=True)
report=[]
for suffix,source in [('bc','base'),('em','emissive'),('nm','normal'),('orm','orm')]:
    dds,meta=read_native_top_mip(folder/f'khravengger_material_0_{suffix}.texture',codec)
    (dest/(suffix+'.dds')).write_bytes(dds)
    preview_dds=bytearray(dds)
    if meta['dxgi'] in (72,78): struct.pack_into('<I',preview_dds,128,meta['dxgi']-1)
    image=Image.open(io.BytesIO(preview_dds)).convert('RGB')
    pixels=np.asarray(image).astype(float)
    original=np.asarray(Image.open(ROOT/f'build/textures/khravengger_{source}.png').convert('RGB')).astype(float)
    if suffix=='em':
        s=original/255
        original=np.where(s<=.04045,s/12.92,((s+.055)/1.055)**2.4)*255
    channels=2 if suffix=='nm' else 3
    error=float(np.sqrt(np.mean((pixels[:,:,:channels]-original[:,:,:channels])**2)))
    assert error<12,(suffix,error)
    assert image.size==(2048,2048)
    image.save(dest/(suffix+'.png'))
    if suffix=='nm':
        xy=pixels[:,:,:2]/127.5-1
        xy/=np.maximum(np.linalg.norm(xy,axis=2,keepdims=True),1)
        z=np.sqrt(np.maximum(0,1-np.sum(xy*xy,axis=2)))
        Image.fromarray(np.rint(np.dstack((xy*.5+.5,z*.5+.5))*255).clip(0,255).astype(np.uint8)).save(dest/'normal_preview.png')
    report.append({'channel':suffix,'source':source,'rms_8bit':error,**meta})
(ROOT/'build/texture_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NATIVE_TEXTURE_READBACK_OK',json.dumps(report))
