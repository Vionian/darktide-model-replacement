"""EFMI-specific material recovery; distinct from Endfield CMB source graphs.

Si.ini binds D/M/N to t17/t18/t19. p1.hlsl reads 1-t18.A for roughness,
t18.R for metallic and (t19.R*t19.A,t19.G)*2-1 for normal XY (lines 498-528).
The former converter incorrectly treated t18 as normal and t19 as gloss.
Roughness floors/metal caps below are explicit Darktide cloth art adaptation.
"""
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).parent

def surface_maps(b,mat,index):
    from endfield_surface_materials import pixels
    def read(number):
        im=b.bpy.data.images.load(str(HERE/f'si_ink_mist/textures/InkMist_{number}_D.png'),check_existing=True)
        return pixels(im)
    n=int(mat['ink_mist_normal']);p=int(mat['ink_mist_packed'])
    d=int(mat['ink_mist_diffuse']);result={}
    if n>0:
        data=read(n)
        xy=np.stack((data[:,:,0]*data[:,:,3],data[:,:,1]),axis=-1)*2-1
        if d==16:xy*=.25  # Soft skin microdetail, not fabric-strength relief.
        xy[:,:,1]*=-1  # Native UV has reversed V; preview reverses it back.
        xy/=np.maximum(np.linalg.norm(xy,axis=2,keepdims=True),1)
        nm=np.ones_like(data);nm[:,:,:2]=xy*.5+.5
        nm[:,:,2]=np.sqrt(np.maximum(0,1-(xy*xy).sum(2)))
        result['nm']=nm
    if p>0:
        data=read(p);orm=np.ones_like(data)
        # Distinguish brocade, silver satin and actual gold/metal. A global
        # .64/.12 cloth clamp erased the outfit's satin highlights. These are
        # labeled native-PBR art values; the source uses a different shader.
        floor,metal_cap=((.29,.95) if d in (18,28) else
                         (.48,.18) if d in (22,55) else (.36,.42))
        orm[:,:,1]=np.clip(1-data[:,:,3],floor,.94)
        orm[:,:,2]=np.minimum(data[:,:,0],metal_cap)
    else:
        # The bare-body pass supplies only diffuse + normal, no metallic map.
        # Neutral dielectric skin must not inherit a template garment's gloss.
        orm=np.array([[[1.,.96 if d==1009 else .64,0.,1.]]],np.float32)
    result['orm']=orm
    output=getattr(b,'HAND_AUTHORING_OUTPUT',None)
    if output:
        path=Path(output)/'ink_mist_surfaces.json'
        report=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        report[str(index)]={'name':mat.name,'diffuse':d,'normal':n,'metallic_smoothness':p,
            'normal_decode':'(R*A,G)*2-1; native green reversed with UV',
            'roughness_quantiles':np.quantile(orm[:,:,1],[0,.5,1]).tolist(),
            'metallic_quantiles':np.quantile(orm[:,:,2],[0,.5,1]).tolist(),
            'policy':'Source channel recovery plus labeled cloth roughness floor/metallic cap; body dielectric'}
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return result
