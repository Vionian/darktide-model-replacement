from pathlib import Path
from PIL import Image
import numpy as np, json
ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'build/textures'
Image.open(T/'BML.dds').convert('RGB').save(T/'khravengger_base.png')
Image.open(T/'EMI.dds').convert('RGB').save(T/'khravengger_emissive.png')
nm=np.asarray(Image.open(T/'NM.dds').convert('RGB')).astype(np.float32)/255
xy=nm[:,:,:2]*2-1
length=np.linalg.norm(xy,axis=2,keepdims=True)
xy/=np.maximum(length,1)
z=np.sqrt(np.maximum(0,1-np.sum(xy*xy,axis=2)))
normal=np.dstack((xy*.5+.5,z*.5+.5))
Image.fromarray(np.rint(normal*255).clip(0,255).astype(np.uint8)).save(T/'khravengger_normal.png')
rmt=np.asarray(Image.open(T/'RMT.dds').convert('RGB'))
orm=np.dstack((np.full(rmt.shape[:2],255,dtype=np.uint8),rmt[:,:,0],rmt[:,:,1]))
Image.fromarray(orm).save(T/'khravengger_orm.png')
report={'base_color':'BML RGB, opaque','normal':'NM BC5 R/G tangent X/Y; reconstruct positive Z, preserve source importer Y convention',
        'roughness':'RMT.R','metallic':'RMT.G','occlusion':'1 (source has no separate AO map)',
        'emissive':'EMI RGB; original blue and purple retained','source_dimensions':[2048,2048]}
(ROOT/'build/material_conversion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
