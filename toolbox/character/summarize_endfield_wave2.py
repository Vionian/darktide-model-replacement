"""Delivery sheets and evidence; synthetic motion is labeled explicitly."""
import pathlib,json,hashlib
from PIL import Image,ImageOps,ImageDraw,ImageFont,ImageChops
from endfield_wave2 import PROFILES
HERE=pathlib.Path(__file__).parent;OUT=HERE/'endfield_batch'
REFERENCES=dict(zip(PROFILES,('09146be9-3fdf-4d81-98c4-61e61b3cf158',
    '790f91c9-379e-4e47-a480-0a8751724bf8','1eb534f0-a7bd-45b4-8b35-4c5a6aee7907',
    '5f2036d0-e94f-48c6-925f-55823d6dc071','7affb7c8-c508-4aee-8abe-06dc90e68d54',
    '7c0e0698-4385-475e-8d12-a682cf8633c1','ebe0fdb3-de22-4191-ae2c-3ecec1b3a283',
    'd9773aca-8256-4793-8f01-39a5d8b224bc')))
FONT=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',21)
SMALL=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',16)
def subject(path):
    im=Image.open(path).convert('RGB')
    bg=Image.new('RGB',im.size,im.getpixel((0,0)))
    mask=ImageChops.difference(im,bg).convert('L').point(lambda x:255 if x>12 else 0)
    bbox=mask.getbbox();return im.crop(bbox)if bbox else im
def place(canvas,im,box):
    x,y,w,h=box;im=ImageOps.contain(im,(w,h));canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2))
def image(key,folder,contains):return next(p for p in (OUT/key/folder).glob('*.png')if contains in p.name)
body=Image.new('RGB',(1440,1350),'#20262e');bd=ImageDraw.Draw(body)
face=Image.new('RGB',(1600,1100),'#20262e');fd=ImageDraw.Draw(face)
hands=Image.new('RGB',(1600,1100),'#20262e');hd=ImageDraw.Draw(hands)
report={}
for index,(key,p)in enumerate(PROFILES.items()):
    x=index%4;y=index//4
    bd.text((x*360+15,y*650+20),p['name'],font=FONT,fill='white')
    place(body,subject(image(key,'final_body','front_preview')),(x*360+10,y*650+60,340,570))
    fd.text((x*400+12,y*525+12),p['name']+' · 原游戏 / 导出预览',font=SMALL,fill='white')
    ref=Image.open(pathlib.Path(r'<SOURCE_ROOT>\终末地')/(REFERENCES[key]+'.png')).convert('RGB')
    w,h=ref.size;ref=ref.crop((int(w*.22),0,int(w*.80),int(h*.36)))
    place(face,ref,(x*400+5,y*525+45,190,455))
    place(face,subject(image(key,'final_face','front_preview')),(x*400+205,y*525+45,190,455))
    hd.text((x*400+12,y*525+12),p['name']+' · 合成法杖动作 左 / 右',font=SMALL,fill='white')
    for j,side in enumerate(('left','right')):
        place(hands,subject(image(key,'final_hands',side+'_front_preview')),(x*400+j*200+4,y*525+45,192,455))
    folder=OUT/key
    assets=json.loads((folder/'asset_audit.json').read_text(encoding='utf-8'))
    mmr=json.loads((folder/'mmr_hand_authoring.json').read_text(encoding='utf-8'))
    assert mmr['MMR_mappings']==32 and len(mmr['source_MMR_motion_probes'])==7,(key,'MMR probes incomplete')
    runtime=json.loads((folder/'contact_runtime_audit.json').read_text(encoding='utf-8'))
    colors=json.loads((folder/'source_color_calibration.json').read_text(encoding='utf-8'))
    shading=json.loads((OUT/'wave2_shading_parameters.json').read_text(encoding='utf-8'))
    expected=next(r['parameters']['_BaseColor']for r in shading[key]if r['material']=='面')
    assert max(abs(a-z)for a,z in zip(colors['面']['source_linear_base_color'],expected))<1e-6
    for asset in (key,key+'_arms'):
        root=folder/'Custom'/asset
        manifest=json.loads((root/'build.json').read_text(encoding='utf-8'))
        for a in manifest['artifacts']:assert(root/a['path']).stat().st_size==a['size']
    report[key]={'name':p['name'],'provider':p['provider'],'asset_audit':assets,
        'MMR_original_joints':32,'source_MMR_synthetic_motion_cases':7,
        'max_MMR_rest_matrix_error':mmr['max_MMR_matrix_error'],
        'max_MMR_motion_matrix_error':max(r['matrix_error']for r in mmr['source_MMR_motion_probes']),
        'runtime':runtime,'source_colors':colors,'reference_image':REFERENCES[key]+'.png',
        'gameplay_verified':False}
bd.text((20,1310),'编译资源回读预览 · 非游戏截图',font=SMALL,fill='white')
fd.text((20,1060),'不同引擎和灯光的外观对照；不是同场景光照等价证明',font=SMALL,fill='white')
hd.text((20,1060),'实际 MMR 原模关节 + 暗潮原生接点；合成动作不代表全部武器实测',font=SMALL,fill='white')
body.save(OUT/'wave2_body_delivery.png');face.save(OUT/'wave2_face_comparison.png');hands.save(OUT/'wave2_hands_delivery.png')
(OUT/'wave2_delivery_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('WAVE2_DELIVERY_READY',list(report))
