from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).parent/'roshia/contact_tail_candidate'
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',26)
small=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',19)
def board(name,items,columns,tile):
    rows=(len(items)+columns-1)//columns
    out=Image.new('RGB',(columns*tile[0],rows*tile[1]+80),(27,32,40))
    d=ImageDraw.Draw(out)
    d.text((18,12),'洛茜 · 握持链路与材质修订',font=font,fill='white')
    d.text((18,48),'编译资源 + 实际 Lua 解算的离线预览；合成姿态，白杆是握点示意，非实机武器',font=small,fill=(195,202,214))
    for k,(path,label,crop)in enumerate(items):
        im=Image.open(P/path).convert('RGB')
        if crop:im=im.crop(crop)
        im.thumbnail((tile[0]-16,tile[1]-48))
        x=k%columns*tile[0];y=k//columns*tile[1]+80
        out.paste(im,(x+(tile[0]-im.width)//2,y+42+(tile[1]-48-im.height)//2))
        d.text((x+14,y+8),label,font=small,fill='white')
    out.save(P/name)
base='roshia_preunit_matrix_hand_rigid'
board('body_contact_overview.png',[
 (f'body_final_preview/{base}_front_preview.png','抬臂：肘腕链与握点示意',(275,210,915,1195)),
 (f'oraxia_pose_preview/{base}_front_preview.png','Oraxia 步枪方向参考 → 洛茜适配',(255,205,925,1195)),
 (f'body_final_preview/{base}_back_preview.png','背面：尾巴与斗篷',(270,200,920,1195)),
],3,(510,800))
board('arm_hand_details.png',[
 (f'arm_final_preview/{base}_right-arm_front_preview.png','抬起的右臂：修订后肘部与手腕',(140,200,765,1100)),
 (f'arm_final_preview/{base}_right-arm_back_preview.png','同一右臂：反面检查',None),
 (f'hands_final_preview/{base}_first_person_closeup_left_back_preview.png','第一人称左手：合成屈指',(140,470,1170,940)),
 (f'hands_final_preview/{base}_first_person_closeup_right_front_preview.png','第一人称右手：合成屈指',(30,470,1060,940))
],2,(620,660))
board('face_tail_details.png',[
 (f'face_final_preview/{base}_upper-body_front_preview.png','面部与眼睛：原生补光材质',None),
 (f'body_final_preview/{base}_back_preview.png','尾巴：透明材质依赖与动态链',(400,620,800,1110))
],2,(620,730))
print('CONTACT_PREVIEWS_READY')
