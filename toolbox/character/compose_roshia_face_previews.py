from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

P=Path(__file__).parent/'roshia/contact_tail_candidate'
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',26)
small=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',20)
base='roshia_preunit_matrix_hand_rigid'

def board(name,items,title,subtitle,tile=(500,510)):
    out=Image.new('RGB',(len(items)*tile[0],tile[1]+100),(27,32,40))
    d=ImageDraw.Draw(out)
    d.text((18,12),title,font=font,fill='white')
    d.text((18,52),subtitle,font=small,fill=(195,202,214))
    for i,(path,label,crop)in enumerate(items):
        im=Image.open(path).convert('RGB').crop(crop)
        scale=min((tile[0]-16)/im.width,(tile[1]-48)/im.height)
        im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
        x=i*tile[0]
        d.text((x+14,103),label,font=small,fill='white')
        out.paste(im,(x+(tile[0]-im.width)//2,145+(tile[1]-48-im.height)//2))
    out.save(P/name)

crop=(270,680,935,1210)
board('face_lighting_comparison.png',[
    (Path('<SCREENSHOT_ROOT>/source.png'),'用户提供的《终末地》参考',(348,267,477,367)),
    (P/f'face_before_preview/{base}_face_front_preview.png','修改前 · 同一灯光',crop),
    (P/f'face_after_preview/{base}_face_front_preview.png','修改后 · 原生面部材质',crop),
], '洛茜 · 面部光照调整','参考图裁切放大；后两图使用相同相机、灯光和曝光，读取最终原生材质，非实机画面')
board('face_lighting_angles.png',[
    (P/f'face_after_preview/{base}_face_front_preview.png','正面 · 标准预览光',crop),
    (P/f'face_after_preview/{base}_face_three-quarter_preview.png','斜侧面 · 检查鼻颊阴影',(320,680,1000,1210)),
    (P/f'face_dim_preview/{base}_face_front_preview.png','正面 · 灯光降至 10%',crop),
], '洛茜 · 角度与弱光检查','局部材质提供基础亮度；Darktide 的曝光与光照仍需实机确认')
print('FACE_PREVIEWS_READY')
