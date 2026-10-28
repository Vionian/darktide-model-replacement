from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageChops
import json

p = Path(__file__).parent/'perlica_interior_fix_20261022'/'comparison'
font = ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',26)
small = ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',21)
sheet = Image.new('RGB',(1060,1390),(31,34,39))
d = ImageDraw.Draw(sheet)
d.text((28,14),'佩丽卡 · 同姿势 / 同相机 / 同灯光对比',font=font,fill='white')
for row,view in enumerate(('inside_waist','exterior_front')):
    for col,stage in enumerate(('before','after')):
        im = Image.open(p/(stage+'_'+view+'.png')).convert('RGB')
        im.thumbnail((500,605))
        x=20+col*530; y=85+row*650
        label=('修复前' if col==0 else '修复后')+' · '+('裙内向上' if row==0 else '正常正面')
        d.text((x,y-32),label,font=small,fill='white')
        sheet.paste(im,(x,y))
d.text((28,1360),'离线合成跑步姿势；不代表已通过实机测试。',font=small,fill=(202,205,210))
sheet.save(p/'comparison_sheet.jpg',quality=94)
report={}
for view in ('inside_waist','under_rear','exterior_front'):
    a=Image.open(p/('before_'+view+'.png')).convert('RGB')
    b=Image.open(p/('after_'+view+'.png')).convert('RGB')
    report[view]={'difference_bbox':ImageChops.difference(a,b).getbbox()}
(p/'image_difference.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
