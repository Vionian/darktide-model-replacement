from pathlib import Path
from PIL import Image
import numpy as np,json
ROOT=Path(__file__).resolve().parents[1];src=ROOT/'武器模型/狼之绯';out=ROOT/'build/langzhifei/textures';out.mkdir(exist_ok=True)
Image.open(src/'T_wpn_sword_0022_refined_01_D.png').convert('RGB').save(out/'base.png')
n=np.array(Image.open(src/'T_wpn_sword_0022_01_N.png').convert('RGB')).astype(float)/255;xy=n[:,:,:2]*2-1;xy/=np.maximum(np.linalg.norm(xy,axis=2,keepdims=True),1);z=np.sqrt(np.maximum(0,1-np.sum(xy*xy,axis=2)))
Image.fromarray(np.rint(np.dstack((xy*.5+.5,z*.5+.5))*255).astype(np.uint8)).save(out/'normal.png')
p=np.array(Image.open(src/'T_wpn_sword_0022_01_P.png').convert('RGBA'))
# No source shader accompanies FBX. P.R metalness / P.B gloss are a documented
# provisional interpretation; keep a moderate roughness floor on painted parts.
rough=np.clip(255-p[:,:,2].astype(float),55,230).astype(np.uint8)
Image.fromarray(np.dstack((p[:,:,1],rough,p[:,:,0]))).save(out/'orm.png')
(out/'conversion.json').write_text(json.dumps({'normal':'RG tangent XY, reconstructed positive Z; source B=0 is not normal Z','base':'D RGB opaque','orm':'P.G AO, 1-P.B roughness (floor .216), P.R metalness; provisional without original shader','P.A':'preserved in source, unused until shader semantics confirmed'},indent=2),encoding='utf-8')
print('LANGZHIFEI_TEXTURES_READY')
