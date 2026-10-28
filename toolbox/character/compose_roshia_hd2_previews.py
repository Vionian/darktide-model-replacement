from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
P=Path(__file__).parent/'roshia/hd2_adapt_candidate'
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',27)
small=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',19)
def board(name,items,columns,tile=(560,760)):
    rows=(len(items)+columns-1)//columns
    out=Image.new('RGB',(columns*tile[0],rows*tile[1]+72),(27,32,40))
    draw=ImageDraw.Draw(out)
    draw.text((18,13),'洛茜适配修订 · 最终资源离线预览',font=font,fill='white')
    draw.text((18,47),'非实机截图；站姿与屈指为合成检查姿态，光照不等同于游戏大厅',font=small,fill=(186,196,210))
    for k,(path,label,crop) in enumerate(items):
        im=Image.open(path).convert('RGB')
        if crop:im=im.crop(crop)
        im.thumbnail((tile[0]-12,tile[1]-48))
        x=k%columns*tile[0];y=72+k//columns*tile[1]
        out.paste(im,(x+(tile[0]-im.width)//2,y+40+(tile[1]-48-im.height)//2))
        draw.text((x+14,y+9),label,font=small,fill='white')
    out.save(P/name)
board('body_overview.png',[(P/'preview'/f'roshia_preunit_matrix_hand_rigid_idle_{v}_preview.png',t,(240,185,960,1220)) for v,t in [('front','正面：缩短胸颈、收拢肩部'),('side','侧面：靴底与体型'),('back','背面：尾巴与斗篷')]],3)
board('face_tail_details.png',[(P/'details/roshia_preunit_matrix_hand_rigid_idle_upper-body_front_preview.png','面部、眼睛与肩颈',(170,215,1060,1300)),(P/'preview/roshia_preunit_matrix_hand_rigid_idle_back_preview.png','尾巴毛片与背部挂件',(255,300,950,1200))],2)
items=[]
for side,label in [('left','左手'),('right','右手')]:
    view='front' if side=='left' else 'back'
    items.append((P/'hands_rest'/f'roshia_preunit_matrix_hand_rigid_first_person_closeup_{side}_{view}_preview.png',label+'：保留原模掌指比例',(70,340,1140,1040)))
    view='back' if side=='left' else 'front'
    items.append((P/'hands'/f'roshia_preunit_matrix_hand_rigid_first_person_grip_closeup_{side}_{view}_preview.png',label+'：合成屈指检查',(70,340,1140,1040)))
board('hands_comparison.png',items,2,(640,480))
print('PREVIEW_BOARDS_READY')
