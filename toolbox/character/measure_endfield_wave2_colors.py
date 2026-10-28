"""Explicit screenshot-based art calibration; does not recover a toon shader."""
import pathlib,json,numpy as np
from PIL import Image
from endfield_wave2 import PROFILES,REFERENCE_IMAGES
OUT=pathlib.Path(__file__).parent/'endfield_batch'
def linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def sample(im,box,skin=False):
    w,h=im.size;coords=[int(v*s)for v,s in zip(box,(w,h,w,h))]
    x=np.asarray(im.crop(coords).convert('RGB'),float).reshape(-1,3)/255
    if skin:
        mask=(x[:,0]>x[:,1]*1.02)&(x[:,0]>x[:,2]*1.02)&(x[:,0]>.5)&(x[:,0]<x[:,1]*1.4)&(x[:,0]<x[:,2]*1.5)
        x=x[mask]
    assert len(x)>50,('Unusable color ROI',box,len(x))
    return np.median(linear(x),axis=0),len(x),coords
report={}
for key in PROFILES:
    src=Image.open(pathlib.Path(r'<SOURCE_ROOT>\终末地')/(REFERENCE_IMAGES[key]+'.png'))
    dst=Image.open(next((OUT/key/'final_face').glob('*face_front_preview.png')))
    face_a,na,ra=sample(src,(.46,.19,.54,.285),True)
    face_b,nb,rb=sample(dst,(.46,.62,.54,.78),True)
    hair_a,nha,rha=sample(src,(.46,.09,.54,.16))
    hair_b,nhb,rhb=sample(dst,(.46,.28,.54,.38))
    gain=face_a/face_b;hair_gain=hair_a/hair_b
    if key=='chenqianyu':hair_gain*=.16
    report[key]={'reference':REFERENCE_IMAGES[key]+'.png','face_linear_gain':gain.tolist(),'hair_linear_gain':hair_gain.tolist(),
        'source_face_roi':ra,'preview_face_roi':rb,'source_hair_roi':rha,'preview_hair_roi':rhb,
        'skin_pixels':[na,nb],'source_face_linear':face_a.tolist(),'preview_face_linear':face_b.tolist(),
        'method':'median linear screenshot color from documented ROIs; art direction, not recovered lighting or shader parameters'}
    print(key,'face',np.round(gain,3),'hair',np.round(hair_gain,3))
(OUT/'wave2_color_measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
