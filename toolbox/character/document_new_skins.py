"""Source notices and native-preview index for this installed costume set."""
from pathlib import Path
import json,shutil,math
from PIL import Image,ImageDraw,ImageFont
from skins_sources import OUT,SOURCES,source
from adapt_skins import VARIANTS,profile
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/new_skins_20261023'
FONT=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',22)

def main():
    DOC.mkdir(parents=True,exist_ok=True);rows=[]
    for key,(title,base,_)in SOURCES.items():
        spec=source(key);notices=[]
        for p in spec['folder'].rglob('*'):
            if not p.is_file()or p.suffix.lower()not in ('.md','.txt'):continue
            if not any(t in p.stem.lower()for t in ('readme','license','credit','author','说明','声明','版权')):continue
            dest=DOC/'source_notices'/key/p.relative_to(spec['folder'])
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);notices.append(dest.relative_to(DOC).as_posix())
        rows.append(dict(key=key,title=title.split('-')[0],character=title.split('-')[1],base=base,
            variants=VARIANTS[key],source_folder=str(spec['folder']),source_ini=str(spec['ini']),
            original_model_author='茶叶味香皂',outfit_credit='See supplied source notices and INI; no inferred authorship',notices=notices))
    (DOC/'sources.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    text='# 新服装（2026-10-23）\n\n在“模型专属设置”中选择角色，再选择“服装”。\n'
    text+='小恶魔·管理员有四种配色；洛丽塔·洛茜为一个服装项，不再显示重复的服装 1/2/3/4。通过“服装配色／款式”选择；其他服装各一个。原版与既有服装保留。\n\n'
    text+='已移除通用摆动调节和快捷键控件；服装使用各自默认物理。隐藏原身体自动开启。\n\n'
    for r in rows:text+='- '+r['character']+'：'+r['title']+'（'+str(r['variants'])+' 个组合）\n'
    text+='\n原始角色模型：茶叶味香皂。服装来自用户提供的 Skins 包，原声明保留在 source_notices；未标注的服装作者不擅自署名。仅作分享，不改变原作者权利。\n\n'
    text+='原生材质使用已验证的暗潮资源格式；PBR、透明镂空及减少后的动态骨是适配近似，并非完整移植终末地着色器和物理。\n'
    text+='原模型手部经 MMR 离线校准，运行时沿用各角色原生手腕/武器链。离线姿态检查不代表所有武器的游戏实测。\n'
    (DOC/'使用与来源.md').write_text(text,encoding='utf8')

def montage(tags,name,kind='body',view='front'):
    cw,ch=(400,500)if kind=='body'else(400,300)
    width=4*cw;height=math.ceil(len(tags)/4)*ch
    out=Image.new('RGB',(width,height),(34,38,44));d=ImageDraw.Draw(out)
    for i,tag in enumerate(tags):
        meta=json.loads((OUT/tag/'conversion.json').read_text(encoding='utf8'));key=meta['key']
        suffix='first_person_closeup_right_front'if kind=='hands'else view
        sub='preview_hands'if kind=='hands'else 'preview_body'
        image=Image.open(OUT/tag/sub/('roshia_preunit_matrix_hand_rigid_'+suffix+'_preview.png')).convert('RGB')
        if kind=='hands':image=image.crop((0,400,image.width,min(1020,image.height)))
        image.thumbnail((cw-8,ch-42),Image.Resampling.LANCZOS)
        x=(i%4)*cw;y=(i//4)*ch
        out.paste(image,(x+(cw-image.width)//2,y+38+(ch-40-image.height)//2))
        label=SOURCES[key][0]+(' · '+str(meta['variant'])if VARIANTS[key]>1 else '')
        d.text((x+8,y+6),label,font=FONT,fill=(235,238,240))
    path=OUT/name;out.save(path,quality=93);print('NATIVE_PREVIEW_INDEX',path)

if __name__=='__main__':
    main()
    if '--montage'in __import__('sys').argv:
        montage(list(SOURCES),'new_outfits_front.jpg')
        montage(list(SOURCES),'new_outfits_back.jpg',view='back')
        montage(list(SOURCES),'new_outfits_hands.jpg',kind='hands')
        variants=[profile('roshia_lolita',1)]+[profile('endministrator_devil',v)for v in range(1,5)]
        montage(variants,'outfit_variations.jpg')
